"""Small executable suite backend used by the P0/P3 CLI.

The correctness suite is intentionally offline and deterministic.  Live suites
stop with an explicit blocked error until a configured model/data adapter is
provided; no synthetic result is labelled as a real benchmark run.
"""

from __future__ import annotations

import json
import csv
from pathlib import Path
import time
from typing import Any, Mapping

from .config import content_hash, write_json
from .construction import apply_delta, build_fresh, query, validate_snapshot
from .ir import canonical_json, normalize_trajectory, stable_hash
from .runtime import BackendUnavailable
from .telemetry import JsonlLogger, utc_now


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _fixture() -> list[Any]:
    return [
        {
            "trajectory_id": "correctness-web-1",
            "environment_family": "web",
            "environment_instance_id": "browser-a",
            "goal": "update a profile",
            "steps": [
                {"source_sequence": 0, "action": "open profile", "post_state": {"page": "profile"}},
                {"source_sequence": 1, "action": "save name", "outcome": "failed: validation", "post_state": {"page": "profile", "saved": False}},
                {"source_sequence": 2, "action": "fix validation", "post_state": {"page": "profile", "saved": True}},
            ],
        },
        {
            "trajectory_id": "correctness-enterprise-1",
            "environment_family": "enterprise",
            "environment_instance_id": "tenant-b",
            "steps": [
                {"source_sequence": 0, "action": "create ticket", "post_state": {"ticket": "T-1"}},
            ],
        },
    ]


def run_correctness(*, paths: Any, runtime: Mapping[str, Any]) -> dict[str, Any]:
    started = time.perf_counter_ns()
    store_path = paths.root / "correctness.sqlite3"
    config = {"storage_path": str(store_path), "source_context_window_events_default": 2}
    checks: list[dict[str, Any]] = []
    spans: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    dependencies: list[dict[str, Any]] = []
    all_events = []
    for raw in _fixture():
        all_events.extend(normalize_trajectory(raw))
    # Fresh and incremental use the same canonical input semantics.
    prefix = all_events[:2]
    fresh_prefix = build_fresh(prefix, config=config)
    snapshots.append({"mode": "fresh", "snapshot_id": fresh_prefix.snapshot_id, "epoch": fresh_prefix.epoch})
    t0 = time.perf_counter_ns()
    receipt = apply_delta(fresh_prefix, all_events[2:], config=config)
    spans.append({"name": "incremental_delta", "elapsed_ns": time.perf_counter_ns() - t0})
    if not receipt.queryable or receipt.snapshot_id is None:
        checks.append({"name": "delta_queryable", "passed": False, "detail": receipt.to_dict()})
    else:
        snapshots.append({"mode": "incremental", "snapshot_id": receipt.snapshot_id, "epoch": receipt.epoch})
        checks.append({"name": "delta_queryable", "passed": True})
    incremental = None
    if receipt.snapshot_id:
        # The construction registry keeps the immutable object available.
        from .construction import _resolve_snapshot
        incremental = _resolve_snapshot(receipt.snapshot_id, config)
    t1 = time.perf_counter_ns()
    fresh_full = build_fresh(all_events, config=config)
    spans.append({"name": "fresh_full", "elapsed_ns": time.perf_counter_ns() - t1})
    if incremental is not None:
        equivalent = {
            "events": [event.to_dict() for event in incremental.events] == [event.to_dict() for event in fresh_full.events],
            "evidence": [item.to_dict() for item in incremental.evidence] == [item.to_dict() for item in fresh_full.evidence],
            "state": incremental.state_view == fresh_full.state_view,
            "workflow": incremental.workflow_view == fresh_full.workflow_view,
        }
        checks.append({"name": "fresh_incremental_equivalence", "passed": all(equivalent.values()), "details": equivalent})
        dependencies.extend({"node_id": node.node_id, "operator": node.operator, "read_dependencies": list(node.read_dependencies)} for node in incremental.nodes)
    validation = validate_snapshot(fresh_full)
    checks.append({"name": "fresh_validation", "passed": validation.valid, "details": validation.to_dict()})
    if incremental is not None:
        validation_delta = validate_snapshot(incremental)
        checks.append({"name": "incremental_validation", "passed": validation_delta.valid, "details": validation_delta.to_dict()})
    bundle = query(fresh_full, "saved profile validation", 8)
    checks.append({"name": "query_returns_grounded_evidence", "passed": bool(bundle.evidence), "evidence_count": len(bundle.evidence)})
    # Explicitly check that an unconfirmed/failed attempt did not become a
    # success-only state.  Failure evidence remains queryable as history.
    failed = [item for item in fresh_full.evidence if item.event_kind == "failure"]
    checks.append({"name": "failure_not_promoted_to_success", "passed": bool(failed) and all(item.event_kind != "confirmation" for item in failed)})
    duration = time.perf_counter_ns() - started
    metrics = {
        "protocol": "C",
        "backend": "deterministic_local",
        "status": "completed" if all(item["passed"] for item in checks) else "failed",
        "checks": len(checks),
        "passed": sum(1 for item in checks if item["passed"]),
        "duration_ns": duration,
        "events": len(all_events),
        "fresh_evidence": len(fresh_full.evidence),
        "incremental_reused_nodes": len(receipt.reused_node_ids),
        "incremental_invalidated_nodes": len(receipt.invalidated_node_ids),
    }
    write_json(paths.root / "correctness.json", {"status": metrics["status"], "checks": checks, "metrics": metrics})
    write_json(paths.root / "metrics.json", metrics)
    _write_jsonl(paths.root / "spans.jsonl", spans)
    _write_jsonl(paths.root / "dependencies.jsonl", dependencies)
    _write_jsonl(paths.root / "snapshots.jsonl", snapshots)
    _write_jsonl(paths.root / "llm_calls.jsonl", [])
    _write_jsonl(paths.root / "qa_per_question.jsonl", [])
    (paths.root / "stderr.log").write_text("", encoding="utf-8")
    write_json(paths.root / "status.json", {"status": metrics["status"], "updated_at": utc_now(), "backend": "deterministic_local"})
    reports_root = Path(str(runtime.get("paths", {}).get("reports", paths.root.parent.parent / "reports"))).expanduser().resolve()
    reports_root.mkdir(parents=True, exist_ok=True)
    equivalence = next((item for item in checks if item.get("name") == "fresh_incremental_equivalence"), {"name": "fresh_incremental_equivalence", "passed": False})
    write_json(reports_root / "equivalence.json", {"status": "completed", "run_id": paths.root.name, "check": equivalence, "note": "Finite deterministic fixture; not a proof of all natural-language dependency completeness."})
    ledger = reports_root / "experiment_ledger.csv"
    exists = ledger.is_file() and ledger.stat().st_size > 0
    with ledger.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["method", "protocol", "split", "workload", "config_hash", "code_commit", "model_fingerprint", "repeat", "status", "metrics_path", "superseded_by"])
        if not exists:
            writer.writeheader()
        writer.writerow({"method": "deterministic_local", "protocol": "C", "split": "fixture", "workload": "correctness", "config_hash": runtime.get("runtime_sha256"), "code_commit": (runtime.get("discovery", {}).get("git", {}) or {}).get("head"), "model_fingerprint": "deterministic_local", "repeat": 1, "status": metrics["status"], "metrics_path": str(paths.root / "metrics.json"), "superseded_by": ""})
    return {"status": metrics["status"], "metrics": metrics, "correctness": str(paths.root / "correctness.json")}


def run_suite(*, runtime: Mapping[str, Any], suite: str, task_plan: Mapping[str, Any], paths: Any, resume: bool = False) -> dict[str, Any]:
    if suite == "correctness":
        result = run_correctness(paths=paths, runtime=runtime)
        if result.get("status") != "completed":
            raise RuntimeError("correctness checks failed; inspect correctness.json")
        return result
    # A local Transformers path is an explicit live backend.  It is selected
    # only when the embedded plan names both local checkpoints; otherwise the
    # suite remains blocked rather than silently falling back to deterministic
    # heuristics.
    models = runtime.get("plan", {}).get("models", {}) if isinstance(runtime, Mapping) else {}
    construction = models.get("construction", {}) if isinstance(models, Mapping) else {}
    embedding = models.get("embedding", {}) if isinstance(models, Mapping) else {}
    if isinstance(construction, Mapping) and isinstance(embedding, Mapping) and construction.get("local_path") and embedding.get("local_path"):
        from .live_pipeline import LiveRunBlocked, run_live_suite
        try:
            return run_live_suite(runtime=runtime, suite=suite, paths=paths, resume=resume)
        except LiveRunBlocked as exc:
            raise BackendUnavailable(str(exc)) from exc
    # A live model call is never silently replaced by the deterministic
    # backend.  A caller can register a richer backend module later.
    discovery = runtime.get("discovery", {}) if isinstance(runtime, Mapping) else {}
    endpoints = discovery.get("model_endpoints", []) if isinstance(discovery, Mapping) else []
    configured = [row for row in endpoints if isinstance(row, Mapping) and row.get("base_url_configured")]
    raise BackendUnavailable(
        f"suite {suite!r} requires live construction/reader services; configured endpoints={len(configured)}. "
        "Inject a workflow_memory suite backend and model adapters before running live experiments."
    )


__all__ = ["run_suite", "run_correctness"]
