"""Small, auditable real-model execution path for local development runs.

This module intentionally keeps the official LongMemEval evaluator and
external baseline implementations separate.  It runs the internal builder on
the local development export, records real Qwen calls/embeddings, and uses a
content-addressed replay for paired B0/B1/B2/B3/Ours comparisons when a full
set of repeated model calls would be needlessly expensive.  Replay-derived
timings are labelled as such and are never presented as live provider latency.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

from .backends import ModelResponse, OpenAICompatibleBackend, backend_fingerprint
from .construction import apply_delta, build_fresh, query, validate_snapshot
from .ir import SourceEvent, canonical_json, normalize_trajectory, stable_hash
from .local_backends import (
    LocalBackendUnavailable,
    TransformersEmbeddingBackend,
    TransformersQwenBackend,
)
from .replay import DeterministicReplayBackend
from .config import write_json
from .telemetry import utc_now


class LiveRunBlocked(RuntimeError):
    """Raised when a requested real-model suite cannot be completed."""


class _RecordingBackend:
    def __init__(self, backend: Any, replay: DeterministicReplayBackend) -> None:
        self.backend = backend
        self.replay = replay
        self.calls: list[dict[str, Any]] = []

    def fingerprint(self) -> str:
        return backend_fingerprint(self.backend)

    def complete(self, request: Any, role: str = "construction", **kwargs: Any) -> ModelResponse:
        started = time.perf_counter_ns()
        response = self.backend.complete(request, **kwargs)
        response = ModelResponse.from_any(response)
        self.replay.record(request, response)
        self.calls.append(
            {
                "request_fingerprint": getattr(request, "fingerprint", None),
                "role": role,
                "model": response.model or backend_fingerprint(self.backend),
                "usage": dict(response.usage),
                "elapsed_ns": time.perf_counter_ns() - started,
                "cache": "miss_live",
            }
        )
        return response

    def answer(self, question: str, evidence: Any, **kwargs: Any) -> str:
        kwargs["_complete"] = lambda request: self.complete(request, role="reader")
        return self.backend.answer(question, evidence, **kwargs)


def _data_records(runtime: Mapping[str, Any], suite: str) -> list[Mapping[str, Any]]:
    from .adapters.longmemeval_v2 import LongMemEvalV2Adapter

    plan = runtime.get("plan", {}) if isinstance(runtime, Mapping) else {}
    data_spec = plan.get("data", {}) if isinstance(plan, Mapping) else {}
    root = (data_spec.get("smoke_root") if suite == "pilot" else data_spec.get("root")) if isinstance(data_spec, Mapping) else None
    candidates: list[Path] = []
    if root:
        candidate = Path(str(root)).expanduser()
        if candidate.is_file():
            candidates.append(candidate)
        elif candidate.is_dir():
            candidates.extend(sorted(candidate.glob("*.jsonl")))
            candidates.extend(sorted(candidate.glob("*.json")))
    if not candidates:
        data_root = Path(str(runtime["paths"]["data"])).expanduser().resolve()
        candidates.extend(sorted(data_root.glob("*.jsonl")))
        candidates.extend(path for path in sorted(data_root.glob("*.json")) if path.name != "PREPARE_DATA_PENDING.json")
    if not candidates:
        raise LiveRunBlocked("no local JSON/JSONL trajectory export is configured")
    rows: list[Mapping[str, Any]] = []
    for path in candidates:
        rows.extend(LongMemEvalV2Adapter(path).records())
    target = 4 if suite == "pilot" else int(data_spec.get("dev_trajectory_target", len(rows)) or len(rows))
    return rows[: max(1, min(target, len(rows)))]


def _event_text(event: SourceEvent) -> str:
    return canonical_json(
        {
            "goal": event.goal,
            "action": event.action,
            "pre_state": event.pre_state_ref,
            "post_state": event.post_state_ref,
            "outcome": event.observed_outcome,
        }
    )


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _model_config(runtime: Mapping[str, Any], role: str) -> Mapping[str, Any]:
    models = runtime.get("plan", {}).get("models", {})
    value = models.get(role, {}) if isinstance(models, Mapping) else {}
    return value if isinstance(value, Mapping) else {}


def _run_live_suite(*, runtime: Mapping[str, Any], suite: str, paths: Any, resume: bool = False) -> dict[str, Any]:
    """Run a real local-Qwen internal suite and emit the standard run files."""

    if suite not in {"pilot", "dev", "main", "scale", "ablations", "stress"}:
        raise LiveRunBlocked(f"unsupported live suite {suite!r}")
    records = _data_records(runtime, suite)
    construction_cfg = _model_config(runtime, "construction")
    embedding_cfg = _model_config(runtime, "embedding")
    construction_path = construction_cfg.get("local_path")
    embedding_path = embedding_cfg.get("local_path")
    if not construction_path or not Path(str(construction_path)).is_dir():
        raise LiveRunBlocked("local construction model path is not configured")
    if not embedding_path or not Path(str(embedding_path)).is_dir():
        raise LiveRunBlocked("local embedding model path is not configured")

    # The local model occupies GPU 0 and the embedding model GPU 1.  Loading
    # is lazy so a blocked preflight never allocates VRAM.
    construction = TransformersQwenBackend(
        str(construction_path),
        device=construction_cfg.get("device", "cuda:0"),
        max_input_tokens=int(construction_cfg.get("context_limit") or 8192),
    )
    replay = DeterministicReplayBackend(strict=True, model_fingerprint="qwen-replay")
    recording = _RecordingBackend(construction, replay)
    embedding = TransformersEmbeddingBackend(
        str(embedding_path),
        device=embedding_cfg.get("device", "cuda:1"),
        max_length=int(embedding_cfg.get("input_limit") or 8192),
        batch_size=2,
    )
    config = {
        "storage_path": str(paths.root / "live.sqlite3"),
        "source_context_window_events_default": 2,
        "construction_model": construction_cfg.get("id"),
        "extraction_output_tokens": 256,
        "model_input_char_budget": 6000,
        "temperature": 0.0,
        "extract_operator_version": "qwen-local-v1",
    }
    spans: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    dependencies: list[dict[str, Any]] = []
    qa_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    trajectory_metrics: list[dict[str, Any]] = []
    all_evidence_texts: list[str] = []
    live_started = time.perf_counter_ns()

    # B0/Fresh is the only method that populates the replay manifest.  This is
    # a real local-model construction; paired methods below use exactly the
    # same request->response mapping and are explicitly marked replay-derived.
    for record_index, record in enumerate(records):
        events = normalize_trajectory(record)
        if not events:
            continue
        trajectory_started = time.perf_counter_ns()
        fresh = build_fresh(events, model_backend=recording, config=config)
        spans.append({"name": "fresh_local", "trajectory_id": events[0].trajectory_id, "elapsed_ns": time.perf_counter_ns() - trajectory_started, "backend": "transformers_local"})
        snapshots.append({"mode": "fresh", "trajectory_id": events[0].trajectory_id, "snapshot_id": fresh.snapshot_id, "epoch": fresh.epoch, "backend": "transformers_local", "included_event_frontier": dict(fresh.published.included_event_frontier), "object_versions": dict(fresh.published.object_versions), "index_manifest": dict(fresh.published.index_manifest)})
        validation = validate_snapshot(fresh)
        for event in events:
            event_rows.append({"event_id": event.event_id, "trajectory_id": event.trajectory_id, "scheduled_arrival_sequence": event.arrival_sequence, "source_sequence": event.source_sequence, "status": "fresh_queryable" if validation.valid else "fresh_invalid"})
        for evidence in fresh.evidence:
            all_evidence_texts.append(canonical_json({"subject": evidence.subject_ref, "predicate": evidence.predicate, "value": evidence.value, "kind": evidence.event_kind}))
        incremental = None
        if len(events) > 1:
            cut = max(1, len(events) // 2)
            prefix = build_fresh(events[:cut], model_backend=replay, config={**config, "storage_path": str(paths.root / f"prefix_{record_index}.sqlite3")})
            delta_started = time.perf_counter_ns()
            receipt = apply_delta(prefix, events[cut:], model_backend=replay, config={**config, "storage_path": str(paths.root / f"prefix_{record_index}.sqlite3")})
            spans.append({"name": "incremental_replay", "trajectory_id": events[0].trajectory_id, "elapsed_ns": time.perf_counter_ns() - delta_started, "backend": "deterministic_replay"})
            incremental = receipt.snapshot
            if incremental is not None:
                snapshots.append({"mode": "incremental", "trajectory_id": events[0].trajectory_id, "snapshot_id": incremental.snapshot_id, "epoch": incremental.epoch, "backend": "deterministic_replay", "included_event_frontier": dict(incremental.published.included_event_frontier), "object_versions": dict(incremental.published.object_versions), "index_manifest": dict(incremental.published.index_manifest)})
                comparison = {
                    "events": [item.to_dict() for item in incremental.events] == [item.to_dict() for item in fresh.events],
                    "evidence": [item.to_dict() for item in incremental.evidence] == [item.to_dict() for item in fresh.evidence],
                    "state": incremental.state_view == fresh.state_view,
                    "workflow": incremental.workflow_view == fresh.workflow_view,
                }
                trajectory_metrics.append({"trajectory_id": events[0].trajectory_id, "events": len(events), "fresh_valid": validation.valid, "incremental_status": receipt.status, "equivalent": all(comparison.values()), "reused_nodes": len(receipt.reused_node_ids), "invalidated_nodes": len(receipt.invalidated_node_ids), "comparison": comparison})
        else:
            trajectory_metrics.append({"trajectory_id": events[0].trajectory_id, "events": len(events), "fresh_valid": validation.valid, "incremental_status": "not_applicable", "equivalent": None, "reused_nodes": 0, "invalidated_nodes": 0})

        query_spec = record.get("query", {}) if isinstance(record, Mapping) else {}
        if isinstance(query_spec, Mapping) and query_spec.get("question_text"):
            question = str(query_spec["question_text"])
            official_question = True
        elif isinstance(record, Mapping) and record.get("goal"):
            # Raw trajectory exports do not carry the benchmark question.
            # A goal query is useful for a construction smoke, but it is not
            # counted as official QA and has no hidden gold answer.
            question = str(record["goal"])
            official_question = False
        else:
            question = "What was observed in this trajectory?"
            official_question = False
        if question:
            answer_started = time.perf_counter_ns()
            bundle = query(fresh, question, 8, reader_backend=construction)
            qa_rows.append({"trajectory_id": events[0].trajectory_id, "query_id": query_spec.get("query_id") if isinstance(query_spec, Mapping) else None, "question_hash": stable_hash(question), "answer": bundle.reader_answer, "evidence_count": len(bundle.evidence), "reader_backend": "qwen_local", "elapsed_ns": time.perf_counter_ns() - answer_started, "official_question": official_question, "gold_answer_available": bool(query_spec.get("gold_answer")) if isinstance(query_spec, Mapping) else False, "gold_answer_hash": stable_hash(query_spec.get("gold_answer")) if isinstance(query_spec, Mapping) and query_spec.get("gold_answer") else None})

        dependencies.extend({"trajectory_id": events[0].trajectory_id, "node_id": node.node_id, "operator": node.operator, "read_dependencies": list(node.read_dependencies), "backend": "transformers_local"} for node in fresh.nodes)
        write_json(
            paths.root / "progress.json",
            {
                "status": "running",
                "suite": suite,
                "completed_trajectories": record_index + 1,
                "total_trajectories": len(records),
                "completed_events": sum(item["events"] for item in trajectory_metrics),
                "live_model_calls": len(recording.calls),
                "updated_at": utc_now(),
            },
        )

    embedding_started = time.perf_counter_ns()
    embedding_response = embedding.embed(all_evidence_texts) if all_evidence_texts else None
    spans.append({"name": "embedding_local", "elapsed_ns": time.perf_counter_ns() - embedding_started, "backend": "transformers_local", "texts": len(all_evidence_texts), "dimensions": len(embedding_response.vectors[0]) if embedding_response and embedding_response.vectors else 0})

    # A single API preflight is optional.  It is never substituted into local
    # construction and the token is only read from the process environment.
    judge_cfg = _model_config(runtime, "judge")
    judge_probe: dict[str, Any] = {"status": "blocked", "reason": "not_configured"}
    base_url = os.environ.get(str(judge_cfg.get("base_url_env", "JUDGE_BASE_URL")), "")
    api_key = os.environ.get(str(judge_cfg.get("api_key_env", "JUDGE_API_KEY")), "")
    if base_url and api_key:
        try:
            judge = OpenAICompatibleBackend(base_url=base_url, api_key=api_key, model=str(judge_cfg.get("id", "gpt-5.2")))
            response = judge.complete({"messages": ({"role": "user", "content": "Reply with OK only."},), "max_tokens": 8, "temperature": 0})
            judge_probe = {"status": "completed", "model": response.model, "usage": dict(response.usage), "response_hash": stable_hash(response.text)}
        except Exception as exc:
            judge_probe = {"status": "blocked", "error_type": type(exc).__name__, "error": str(exc)[:240]}

    total_ns = time.perf_counter_ns() - live_started
    live_calls = len(recording.calls)
    metrics = {
        "status": "completed",
        "protocol": "B",
        "suite": suite,
        "backend": "transformers_local",
        "replay_for_paired_methods": True,
        "records": len(records),
        "events": sum(item["events"] for item in trajectory_metrics),
        "trajectories": len(trajectory_metrics),
        "live_model_calls": live_calls,
        "live_model_input_tokens": sum(int(item.get("usage", {}).get("prompt_tokens", 0) or 0) for item in recording.calls),
        "live_model_output_tokens": sum(int(item.get("usage", {}).get("completion_tokens", 0) or 0) for item in recording.calls),
        "embedding_texts": len(all_evidence_texts),
        "embedding_dimensions": len(embedding_response.vectors[0]) if embedding_response and embedding_response.vectors else 0,
        "equivalent_trajectories": sum(1 for item in trajectory_metrics if item.get("equivalent") is True),
        "equivalence_checked_trajectories": sum(1 for item in trajectory_metrics if item.get("equivalent") is not None),
        "qa_rows": len(qa_rows),
        "judge_probe": judge_probe,
        "elapsed_ns": total_ns,
    }
    replay_manifest = replay.to_dict()
    write_json(paths.root / "metrics.json", metrics)
    write_json(paths.root / "progress.json", {"status": "completed", "suite": suite, "completed_trajectories": len(trajectory_metrics), "total_trajectories": len(records), "completed_events": metrics["events"], "live_model_calls": live_calls, "updated_at": utc_now()})
    write_json(paths.root / "correctness.json", {"status": "completed", "trajectory_metrics": trajectory_metrics, "judge_probe": judge_probe})
    write_json(paths.root / "replay_manifest.json", replay_manifest)
    _write_jsonl(paths.root / "llm_calls.jsonl", recording.calls)
    _write_jsonl(paths.root / "spans.jsonl", spans)
    _write_jsonl(paths.root / "dependencies.jsonl", dependencies)
    _write_jsonl(paths.root / "snapshots.jsonl", snapshots)
    _write_jsonl(paths.root / "qa_per_question.jsonl", qa_rows)
    _write_jsonl(paths.root / "events.jsonl", event_rows)
    (paths.root / "stderr.log").write_text("", encoding="utf-8")
    write_json(paths.root / "status.json", {"status": "completed", "updated_at": utc_now(), "backend": "transformers_local"})

    reports_root = Path(str(runtime["paths"]["reports"])).expanduser().resolve()
    reports_root.mkdir(parents=True, exist_ok=True)
    ledger = reports_root / "experiment_ledger.csv"
    fields = ["method", "protocol", "split", "workload", "config_hash", "code_commit", "model_fingerprint", "repeat", "status", "metrics_path", "superseded_by"]
    exists = ledger.is_file() and ledger.stat().st_size > 0
    with ledger.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({"method": "Ours", "protocol": "B", "split": "development", "workload": suite, "config_hash": runtime.get("runtime_sha256"), "code_commit": (runtime.get("discovery", {}).get("git", {}) or {}).get("head"), "model_fingerprint": construction.fingerprint(), "repeat": 1, "status": "completed", "metrics_path": str(paths.root / "metrics.json"), "superseded_by": ""})
    return {"status": "completed", "run_id": paths.root.name, "metrics": metrics, "metrics_path": str(paths.root / "metrics.json")}


def run_live_suite(*, runtime: Mapping[str, Any], suite: str, paths: Any, resume: bool = False) -> dict[str, Any]:
    """Run a live suite and persist a terminal failed marker on exceptions."""
    try:
        return _run_live_suite(runtime=runtime, suite=suite, paths=paths, resume=resume)
    except BaseException as exc:
        now = utc_now()
        try:
            write_json(paths.root / "progress.json", {"status": "failed", "suite": suite, "error_type": type(exc).__name__, "error": str(exc), "updated_at": now})
            write_json(paths.root / "status.json", {"status": "failed", "suite": suite, "error_type": type(exc).__name__, "error": str(exc), "updated_at": now, "backend": "transformers_local"})
            (paths.root / "stderr.log").write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        except Exception:
            pass
        raise


__all__ = ["LiveRunBlocked", "run_live_suite"]
