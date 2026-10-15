#!/usr/bin/env python3
"""Real B0/Fresh and Ours-dev comparison on a predeclared prefix workload.

No replay, simulation, official benchmark claim, or silent model substitution.
Each B0 checkpoint has an empty independent store/cache. Ours-dev retains only
its own window state. Checkpoint measurements and model responses are flushed
immediately, including failures. The same resident model is warmed once before
both methods; cold load and warmup are explicitly outside kernel latency.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Mapping, Sequence

CODE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_ROOT / "src"))

from workflow_memory.backends import EmbeddingResponse, ModelRequest, ModelResponse, backend_fingerprint
from workflow_memory.config import load_json, write_json
from workflow_memory.construction import Snapshot, apply_delta, build_fresh, query, validate_snapshot
from workflow_memory.event_store import EventStore
from workflow_memory.ir import canonical_json, normalize_trajectory, stable_hash
from workflow_memory.local_backends import TransformersQwenBackend


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def load_workload(manifest: Mapping[str, Any], *, limit_windows: int | None = None) -> list[tuple[dict[str, Any], list[Any]]]:
    source = Path(str(manifest["source_file"])).resolve()
    actual = file_hash(source)
    if actual != manifest["source_sha256"]:
        raise ValueError(f"source hash mismatch: expected {manifest['source_sha256']}, got {actual}")
    wanted = {window["trajectory_id"] for window in manifest["windows"]}
    records: dict[str, Any] = {}
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            trajectory_id = str(record.get("trajectory_id", record.get("id", "")))
            if trajectory_id in wanted:
                if trajectory_id in records:
                    raise ValueError(f"duplicate trajectory {trajectory_id}")
                records[trajectory_id] = record
    windows = list(manifest["windows"])
    if limit_windows is not None:
        windows = windows[:limit_windows]
    result = []
    for spec in windows:
        if spec["trajectory_id"] not in records:
            raise ValueError(f"missing trajectory {spec['trajectory_id']}")
        events = normalize_trajectory(records[spec["trajectory_id"]])[: int(spec["event_count"])]
        if [event.event_id for event in events] != spec["event_ids"]:
            raise ValueError(f"normalized event IDs disagree with manifest for {spec['window_id']}")
        checkpoints = spec["checkpoint_prefix_lengths"]
        if not checkpoints or checkpoints != sorted(set(checkpoints)) or checkpoints[-1] != len(events):
            raise ValueError(f"invalid checkpoints in {spec['window_id']}")
        result.append((dict(spec), events))
    return result


class RecordingBackend:
    def __init__(self, backend: Any, run_root: Path) -> None:
        self.backend = backend
        self.run_root = run_root
        self.context: dict[str, Any] = {}
        self.calls: list[dict[str, Any]] = []
        self.supports_batch_calls = callable(getattr(backend, "complete_batch", None))
        self.max_batch_size = int(getattr(backend, "max_batch_size", 1))
        self.batch_count = 0

    def fingerprint(self) -> str:
        return backend_fingerprint(self.backend)

    def complete(self, request: ModelRequest, **kwargs: Any) -> ModelResponse:
        call_id = f"call-{len(self.calls):06d}"
        started = time.perf_counter_ns()
        row = {**self.context, "call_id": call_id, "request_hash": request.fingerprint,
               "request": request.to_dict(), "started_at": now(), "backend": "transformers_local", "cache": "miss_live"}
        append_jsonl(self.run_root / "requests.jsonl", row)
        try:
            response = ModelResponse.from_any(self.backend.complete(request, **kwargs))
            usage = dict(response.usage)
            if "prompt_tokens" not in usage or "completion_tokens" not in usage:
                raise ValueError("live backend must return actual token usage")
            row.update(status="completed", elapsed_ns=time.perf_counter_ns() - started,
                       input_tokens=int(usage["prompt_tokens"]), output_tokens=int(usage["completion_tokens"]),
                       usage=usage, model=response.model, response_text=response.text,
                       response_hash=stable_hash(response.text), finish_reason=response.finish_reason)
            row["actual_batch_size"] = int((response.raw or {}).get("batch_size", 1)) if isinstance(response.raw, Mapping) else 1
        except BaseException as exc:
            row.update(status="failed", elapsed_ns=time.perf_counter_ns() - started,
                       input_tokens=None, output_tokens=None, error_type=type(exc).__name__, error=str(exc))
            self.calls.append(row)
            append_jsonl(self.run_root / "llm_calls.jsonl", row)
            raise
        self.calls.append(row)
        append_jsonl(self.run_root / "llm_calls.jsonl", row)
        return response


    def complete_batch(self, requests: Sequence[ModelRequest], **kwargs: Any) -> tuple[ModelResponse, ...]:
        if not self.supports_batch_calls:
            raise RuntimeError("resident backend has no real batch implementation")
        responses_out = []
        # Log each actual <=2 GPU batch separately so later chunk failures
        # cannot erase the preceding successful live requests.
        for offset in range(0, len(requests), self.max_batch_size):
            group = requests[offset:offset + self.max_batch_size]
            batch_id = f"batch-{self.batch_count:06d}"
            self.batch_count += 1
            started = time.perf_counter_ns()
            rows = []
            for index, request in enumerate(group):
                row = {**self.context, "call_id": f"call-{len(self.calls)+index:06d}",
                       "batch_id": batch_id, "request_hash": request.fingerprint,
                       "request": request.to_dict(), "started_at": now(),
                       "backend": "transformers_local", "cache": "miss_live"}
                append_jsonl(self.run_root / "requests.jsonl", row)
                rows.append(row)
            try:
                responses = tuple(ModelResponse.from_any(value) for value in self.backend.complete_batch(group, **kwargs))
                if len(responses) != len(group):
                    raise ValueError("live batch response count mismatch")
                duration = time.perf_counter_ns() - started
                for row, response in zip(rows, responses):
                    usage = dict(response.usage)
                    if "prompt_tokens" not in usage or "completion_tokens" not in usage:
                        raise ValueError("live batch response is missing actual token usage")
                    actual = int((response.raw or {}).get("batch_size", 1)) if isinstance(response.raw, Mapping) else 1
                    row.update(status="completed", elapsed_ns=duration, batch_elapsed_ns=duration,
                               actual_batch_size=actual, input_tokens=int(usage["prompt_tokens"]),
                               output_tokens=int(usage["completion_tokens"]), usage=usage,
                               model=response.model, response_text=response.text,
                               response_hash=stable_hash(response.text), finish_reason=response.finish_reason)
                responses_out.extend(responses)
            except BaseException as exc:
                duration = time.perf_counter_ns() - started
                for row in rows:
                    row.update(status="failed", elapsed_ns=duration, batch_elapsed_ns=duration,
                               actual_batch_size=None, input_tokens=None, output_tokens=None,
                               error_type=type(exc).__name__, error=str(exc))
                for row in rows:
                    self.calls.append(row)
                    append_jsonl(self.run_root / "llm_calls.jsonl", row)
                append_jsonl(self.run_root / "generation_batches.jsonl", {**self.context, "batch_id": batch_id,
                             "status": "failed", "elapsed_ns": duration, "requested_batch_size": len(group)})
                raise
            for row in rows:
                self.calls.append(row)
                append_jsonl(self.run_root / "llm_calls.jsonl", row)
            append_jsonl(self.run_root / "generation_batches.jsonl", {**self.context, "batch_id": batch_id,
                         "status": "completed", "elapsed_ns": duration, "requested_batch_size": len(group),
                         "actual_batch_size": max(row["actual_batch_size"] for row in rows)})
        return tuple(responses_out)


def model_wall_ns(calls: Sequence[Mapping[str, Any]]) -> int:
    batches = {}
    serial = 0
    for call in calls:
        if call.get("batch_id") is not None:
            batches[call["batch_id"]] = call["batch_elapsed_ns"]
        else:
            serial += call["elapsed_ns"]
    return serial + sum(batches.values())


class RecordingEmbedding:
    def __init__(self, backend: Any, run_root: Path):
        self.backend, self.run_root = backend, run_root
        self.context = {}
        self.calls = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.backend, name)

    def fingerprint(self) -> str:
        return backend_fingerprint(self.backend)

    def embed(self, texts: Sequence[str], **kwargs: Any) -> EmbeddingResponse:
        started = time.perf_counter_ns()
        row = {**self.context, "embedding_call_id": f"embed-{len(self.calls):06d}", "started_at": now(),
               "request_hash": stable_hash({"texts": list(texts), "fingerprint": self.fingerprint()}),
               "texts": list(texts), "n_texts": len(texts), "cache": "miss_live"}
        try:
            response = EmbeddingResponse.from_any(self.backend.embed(texts, **kwargs))
            tokens = response.usage.get("input_tokens", response.usage.get("prompt_tokens"))
            if tokens is None:
                raise ValueError("local embedding backend must report actual input tokens")
            row.update(status="completed", elapsed_ns=time.perf_counter_ns()-started,
                       input_tokens=int(tokens), usage=dict(response.usage), model=response.model,
                       vector_hash=stable_hash(response.vectors), dimensions=len(response.vectors[0]) if response.vectors else 0)
        except BaseException as exc:
            row.update(status="failed", elapsed_ns=time.perf_counter_ns()-started,
                       input_tokens=None, error_type=type(exc).__name__, error=str(exc))
            self.calls.append(row)
            append_jsonl(self.run_root / "embedding_calls.jsonl", row)
            raise
        self.calls.append(row)
        append_jsonl(self.run_root / "embedding_calls.jsonl", row)
        return response


def token_sum(calls: Sequence[Mapping[str, Any]], field: str) -> int | None:
    if any(call.get(field) is None for call in calls):
        return None
    return sum(int(call[field]) for call in calls)


def summarize(rows: Sequence[Mapping[str, Any]], *, run_root: Path, config_hash: str, workload_hash: str, scope: str) -> list[dict[str, Any]]:
    summaries = []
    for method in dict.fromkeys(row["method"] for row in rows):
        selected = [row for row in rows if row["method"] == method]
        successful = [row for row in selected if row["status"] == "completed"]
        latencies = [float(row["elapsed_s"]) for row in successful]
        summaries.append({
            "run_id": run_root.name, "method": method, "config_hash": config_hash,
            "workload_hash": workload_hash, "input_modality": "text-only", "scope": scope,
            "n_windows": len({row["window_id"] for row in selected}), "n_checkpoints": len(selected),
            "successful_checkpoints": len(successful), "failed_checkpoints": len(selected) - len(successful),
            "initial_build_s": sum(float(row["elapsed_s"]) for row in selected if row["phase"] == "initial_build"),
            "update_total_s": sum(float(row["elapsed_s"]) for row in selected if row["phase"] == "update"),
            "total_s": sum(float(row["elapsed_s"]) for row in selected),
            "checkpoint_latency_p50_s": percentile(latencies, 0.5), "checkpoint_latency_p95_s": percentile(latencies, 0.95),
            "live_model_calls": sum(row["live_model_calls"] for row in selected),
            "failed_model_calls": sum(row["failed_model_calls"] for row in selected),
            "input_tokens": token_sum(selected, "input_tokens"), "output_tokens": token_sum(selected, "output_tokens"),
            "reused_nodes": sum(row["reused_nodes"] for row in selected), "invalidated_nodes": sum(row["invalidated_nodes"] for row in selected),
            "snapshot_checks_passed": sum(bool(row["snapshot_valid"]) for row in selected),
            "kernel_total_s": sum(float(row.get("kernel_elapsed_ns", row["elapsed_ns"] if "elapsed_ns" in row else row["elapsed_s"]*1e9)) / 1e9 for row in selected),
            "model_total_s": sum(float(row.get("model_elapsed_s", 0)) for row in selected),
            "embedding_total_s": sum(float(row.get("embedding_elapsed_s", 0)) for row in selected),
            "embedding_model_calls": sum(int(row.get("embedding_model_calls", 0)) for row in selected),
            "embedding_input_tokens": sum(int(row.get("embedding_input_tokens", 0)) for row in selected),
            "new_vectors": sum(int(row.get("new_vectors", 0)) for row in selected),
            "reused_vectors": sum(int(row.get("reused_vectors", 0)) for row in selected),
            "dense_checks_passed": sum(bool(row.get("dense_valid", False)) for row in selected),
            "actual_concurrency_max": max(int(row.get("actual_concurrency", 1)) for row in selected),
            "qa_status": "not_evaluated", "raw_metrics_path": str(run_root / "checkpoint_metrics.jsonl"),
        })
    return summaries


def write_table(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("status\nmissing\n", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())


def check_publication(snapshot: Snapshot, events: Sequence[Any], config: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_snapshot(snapshot)
    if not validation.valid:
        raise RuntimeError(f"snapshot validation failed: {validation.errors}")
    expected = [event.event_id for event in events]
    if [event.event_id for event in snapshot.events] != expected:
        raise RuntimeError("snapshot source frontier differs from arrived prefix")
    covered = {source for item in snapshot.evidence for source in item.source_refs}
    missing = sorted(set(expected) - covered)
    if missing:
        raise RuntimeError(f"extraction dropped source events: {missing}")
    if not snapshot.workflow_view:
        raise RuntimeError("required workflow view is empty")
    disk_store = EventStore(str(config["storage_path"]))
    try:
        record = disk_store.get_snapshot(snapshot.snapshot_id)
        if record is None:
            raise RuntimeError("snapshot publication missing from SQLite")
        disk_snapshot = Snapshot.from_dict(record["payload"])
        if canonical_json(disk_snapshot.to_dict()) != canonical_json(snapshot.to_dict()):
            raise RuntimeError("persisted snapshot payload differs from published epoch")
    finally:
        disk_store.close()
    if not validate_snapshot(disk_snapshot).valid:
        raise RuntimeError("persisted snapshot validation failed")
    # A goal search can have no lexical match to valid attempt evidence.
    # Readability is checked by an unfiltered pinned query, separately from
    # the goal's retrieval coverage (which is a later quality diagnostic).
    readable = query(disk_snapshot, "", 8, config=config)
    if not readable.evidence or readable.epoch != snapshot.epoch:
        raise RuntimeError("published snapshot is not readable at its pinned epoch")
    goal_hits = query(disk_snapshot, events[-1].goal or "observed state", 8, config=config)
    return {"validation": validation.to_dict(), "source_events_with_evidence": len(covered),
            "source_coverage_fraction": len(covered) / len(expected),
            "goal_retrieval_hits": len(goal_hits.evidence)}


def run(args: argparse.Namespace) -> int:
    run_root = args.out.resolve()
    if run_root.exists():
        raise ValueError(f"refuse to overwrite existing run directory: {run_root}")
    runtime = load_json(args.config)
    workload = load_json(args.manifest)
    windows = load_workload(workload, limit_windows=args.limit_windows)
    methods = args.methods.split(",")
    if len(set(methods)) != len(methods) or any(method not in {"B0", "Ours-dev", "B3-c1", "B3-c2"} for method in methods):
        raise ValueError("methods must be distinct B0, Ours-dev, B3-c1 and/or B3-c2")
    scope = args.scope
    e2e = scope == "construction_e2e"
    model_cfg = runtime["plan"]["models"]["construction"]
    settings = dict(workload["shared_initial_settings"])
    if args.settings:
        settings.update(load_json(args.settings))
    settings.update(construction_model=model_cfg["id"], strict_model_output=True,
                    extract_operator_version="qwen-fastloop-strict-v2",
                    extraction_prompt=(CODE_ROOT / "prompts/extract_evidence_v2.txt").read_text(encoding="utf-8").strip())
    code_paths = [Path(__file__), CODE_ROOT / "src/workflow_memory/construction.py",
                  CODE_ROOT / "src/workflow_memory/local_backends.py", CODE_ROOT / "prompts/extract_evidence_v2.txt"]
    if any(method.startswith("B3-") for method in methods):
        from workflow_memory.strong_baseline import build_strong_prefix
        code_paths.append(CODE_ROOT / "src/workflow_memory/strong_baseline.py")
    embedding_cfg = None
    if e2e:
        from workflow_memory.dense_publication import publish_dense, read_dense
        from workflow_memory.local_backends import TransformersEmbeddingBackend
        embedding_cfg = {**runtime["plan"]["models"]["embedding"],
                         "max_length": int(settings.get("embedding_max_length", 1024)),
                         "batch_size": int(settings.get("embedding_batch_size", 4))}
        code_paths.append(CODE_ROOT / "src/workflow_memory/dense_publication.py")
    code_hashes = {str(path.relative_to(CODE_ROOT)): file_hash(path) for path in code_paths}
    config_hash = stable_hash({"runtime_file_sha256": file_hash(args.config), "settings": settings,
                               "model_cfg": model_cfg, "embedding_cfg": embedding_cfg,
                               "code_sha256": code_hashes, "scope": scope})
    workload_hash = stable_hash({"manifest": workload, "selected_windows": [spec for spec, _ in windows]})
    run_root.mkdir(parents=True)
    os.environ["WORKFLOW_MEMORY_SNAPSHOT_INDEX"] = str(run_root / "snapshot_locations.json")
    frozen_run_manifest = {"schema_version": "fast-compare/1", "run_id": run_root.name,
                           "started_at": now(), "methods": methods, "config_hash": config_hash,
                           "workload_hash": workload_hash, "workload": workload,
                           "settings": settings, "model_cfg": model_cfg, "embedding_cfg": embedding_cfg,
                           "source_verified": True, "input_modality": "text-only",
                           "scope": scope, "scope_includes": ["LLM extraction", "deterministic state/relation/workflow views", "lexical index", "SQLite publish"] + (["real dense Embedding", "dense index write", "readable publication descriptor"] if e2e else []),
                           "scope_excludes": ["model cold loading", "warmup", "Reader", "Judge", "post-publication correctness checks"] + ([] if e2e else ["dense embedding/index"]),
                           "llm_stages": ["extract"], "not_implemented_as_llm_stages": ["resolve", "workflow"],
                           "qa_status": "not_evaluated", "replay_for_paired_methods": False,
                           "requested_concurrency": {method: 2 if method == "B3-c2" else 1 for method in methods},
                           "actual_concurrency_measurement": "per-call backend batch size; no unmeasured kernel-overlap claim",
                           "selected_windows": [spec for spec, _ in windows],
                           "code_sha256": code_hashes}
    write_json(run_root / "manifest.json", frozen_run_manifest)
    for path in code_paths:
        destination = run_root / "frozen_code" / path.relative_to(CODE_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
    write_json(run_root / "status.json", {"status": "running", "started_at": now(), "pid": os.getpid()})
    backend = TransformersQwenBackend(str(model_cfg["local_path"]), device=model_cfg.get("device", "cuda:0"),
                                      dtype=model_cfg.get("dtype") or model_cfg.get("precision") or "bfloat16",
                                      max_input_tokens=min(int(model_cfg.get("context_limit") or 8192), 8192), enable_thinking=False)
    recording = RecordingBackend(backend, run_root)
    started = time.perf_counter()
    backend._ensure_loaded()
    load_s = time.perf_counter() - started
    started = time.perf_counter()
    warmup = backend.complete(ModelRequest(messages=({"role": "user", "content": "Reply with OK only."},), temperature=0, max_tokens=8))
    warmup_s = time.perf_counter() - started
    write_json(run_root / "model_setup.json", {"load_s": load_s, "warmup_s": warmup_s, "warmup_usage": dict(warmup.usage), "fingerprint": backend.fingerprint(), "warmup_policy": "one shared resident checkpoint; both methods start after identical warmup"})
    embedding = None
    if e2e:
        embedding = TransformersEmbeddingBackend(str(embedding_cfg["local_path"]),
                      device=embedding_cfg.get("device", "cuda:1"),
                      dtype=embedding_cfg.get("dtype") or embedding_cfg.get("precision") or "bfloat16",
                      max_length=embedding_cfg["max_length"], batch_size=embedding_cfg["batch_size"])
        started = time.perf_counter()
        embedding._ensure_loaded()
        embedding_load_s = time.perf_counter() - started
        started = time.perf_counter()
        embedding_warmup = embedding.embed(["Shared dense-index warmup."])
        write_json(run_root / "embedding_setup.json", {"load_s": embedding_load_s,
                   "warmup_s": time.perf_counter() - started, "warmup_usage": dict(embedding_warmup.usage),
                   "fingerprint": embedding.fingerprint(), "settings": embedding_cfg})
        embedding = RecordingEmbedding(embedding, run_root)
    rows: list[dict[str, Any]] = []
    started_run = time.perf_counter()
    for repeat in range(1, args.repeats + 1):
        for spec, events in windows:
            # Interleave method order across windows/repeats to reduce fixed-order drift.
            order = methods if (windows.index((spec, events)) + repeat) % 2 else list(reversed(methods))
            for method in order:
                snapshot = None
                previous_cut = 0
                dense_cache = {}
                for checkpoint_index, cut in enumerate(spec["checkpoint_prefix_lengths"]):
                    method_dir = run_root / "stores" / f"repeat-{repeat}" / method / spec["window_id"]
                    method_dir.mkdir(parents=True, exist_ok=True)
                    store_path = method_dir / (f"cp-{cut}.sqlite3" if method == "B0" else "incremental.sqlite3")
                    config = {**settings, "storage_path": str(store_path)}
                    recording.context = {"method": method, "window_id": spec["window_id"], "checkpoint_prefix_length": cut,
                                         "repeat": repeat, "config_hash": config_hash, "workload_hash": workload_hash}
                    if e2e:
                        embedding.context = dict(recording.context)
                    call_start = len(recording.calls)
                    row = {**recording.context, "phase": "initial_build" if checkpoint_index == 0 else "update",
                           "storage_path": str(store_path), "cache_policy": "empty_per_checkpoint" if method == "B0" else "own_window_valid_nodes_only",
                           "prefix_events": cut, "delta_events": cut if method == "B0" else cut - previous_cut,
                           "scope": scope, "qa_status": "not_evaluated",
                           "reused_nodes": 0, "invalidated_nodes": 0, "snapshot_valid": False,
                           "status": "failed", "started_at": now()}
                    started_checkpoint = time.perf_counter_ns()
                    try:
                        if method.startswith("B3-"):
                            candidate, strong_stats = build_strong_prefix(events[:cut], recording, config,
                                                        previous=snapshot, concurrency=2 if method == "B3-c2" else 1)
                            row.update(strong_stats=strong_stats, reused_nodes=strong_stats["reused_nodes"],
                                       invalidated_nodes=strong_stats["invalidated_nodes"])
                        elif method == "B0" or snapshot is None:
                            candidate = build_fresh(events[:cut], model_backend=recording, config=config)
                        else:
                            receipt = apply_delta(snapshot, events[previous_cut:cut], model_backend=recording, config=config)
                            if not receipt.queryable or receipt.snapshot is None:
                                raise RuntimeError(f"incremental update did not publish a queryable snapshot: {receipt.error}")
                            candidate = receipt.snapshot
                            row.update(reused_nodes=len(receipt.reused_node_ids), invalidated_nodes=len(receipt.invalidated_node_ids), update_receipt=receipt.to_dict())
                        kernel_ns = time.perf_counter_ns() - started_checkpoint
                        measured_ns = kernel_ns
                        if e2e:
                            # Method/window-owned semantic embedding cache;
                            # Fresh cannot carry it to the next checkpoint.
                            if method == "B0":
                                dense_cache = {}
                            descriptor, dense_stats = publish_dense(candidate, embedding,
                                publication_dir=method_dir / "dense", cache=dense_cache)
                            measured_ns = time.perf_counter_ns() - started_checkpoint
                            read_dense(descriptor)
                            row.update(dense_descriptor=descriptor, dense_stats=dense_stats,
                                       dense_valid=True, embedding_elapsed_s=dense_stats["embed_elapsed_s"],
                                       embedding_model_calls=dense_stats["embedding_calls"],
                                       embedding_input_tokens=dense_stats["input_tokens"],
                                       new_vectors=dense_stats["new_vectors"], reused_vectors=dense_stats["reused_vectors"])
                        checks = check_publication(candidate, events[:cut], config)
                        snapshot = candidate
                        snapshot_file = run_root / "snapshots" / f"r{repeat}-{method}-{spec['window_id']}-cp{cut}.json"
                        write_json(snapshot_file, snapshot.to_dict())
                        row.update(status="completed", snapshot_valid=True, snapshot_id=snapshot.snapshot_id,
                                   snapshot_path=str(snapshot_file), included_event_frontier=dict(snapshot.published.included_event_frontier),
                                   evidence_count=len(snapshot.evidence), state_count=len(snapshot.state_view),
                                   workflow_count=sum(len(value) for value in snapshot.workflow_view.values()),
                                   **checks, kernel_elapsed_ns=kernel_ns, measured_elapsed_ns=measured_ns,
                                   semantic_hash=stable_hash({"evidence": [item.to_dict() for item in snapshot.evidence], "state": snapshot.state_view, "workflow": snapshot.workflow_view}))
                        previous_cut = cut
                    except Exception as exc:
                        row.update(error_type=type(exc).__name__, error=str(exc))
                        if hasattr(exc, "stats"):
                            row["failure_stats"] = exc.stats
                    row["elapsed_ns"] = row.get("measured_elapsed_ns", time.perf_counter_ns() - started_checkpoint)
                    row["elapsed_s"] = row["elapsed_ns"] / 1e9
                    calls = recording.calls[call_start:]
                    row.update(live_model_calls=len(calls), failed_model_calls=sum(call["status"] != "completed" for call in calls),
                               input_tokens=token_sum(calls, "input_tokens"), output_tokens=token_sum(calls, "output_tokens"),
                               model_elapsed_s=model_wall_ns(calls) / 1e9,
                               actual_concurrency=max([int(call.get("actual_batch_size") or 0) for call in calls] or [0]))
                    append_jsonl(run_root / "checkpoint_metrics.jsonl", row)
                    rows.append(row)
                    write_json(run_root / "progress.json", {"status": "running", "completed_checkpoint_attempts": len(rows), "total_checkpoint_attempts": sum(len(s["checkpoint_prefix_lengths"]) for s, _ in windows) * len(methods) * args.repeats, "last": recording.context, "updated_at": now()})
                    print(json.dumps({key: row[key] for key in ("method", "window_id", "checkpoint_prefix_length", "status", "elapsed_s", "live_model_calls", "input_tokens", "output_tokens")}, ensure_ascii=True), flush=True)
    summaries = summarize(rows, run_root=run_root, config_hash=config_hash, workload_hash=workload_hash, scope=scope)
    write_table(run_root / "summary.csv", summaries)
    write_table(args.table, summaries)
    if e2e and {"B0", "Ours-dev"}.issubset(methods):
        write_table(CODE_ROOT / "results/tables/first_compare_e2e.csv", [row for row in summaries if row["method"] in {"B0", "Ours-dev"}])
    if e2e and any(method.startswith("B3-") for method in methods):
        write_table(CODE_ROOT / "results/tables/dev_strong_compare.csv", summaries)
    pairs = []
    indexed = {(row["window_id"], row["checkpoint_prefix_length"], row["repeat"], row["method"]): row for row in rows}
    for key in sorted({(row["window_id"], row["checkpoint_prefix_length"], row["repeat"]) for row in rows}):
        left, right = indexed.get((*key, "B0")), indexed.get((*key, "Ours-dev"))
        if left and right and left["status"] == right["status"] == "completed":
            pairs.append({"window_id": key[0], "checkpoint_prefix_length": key[1], "repeat": key[2],
                          "B0_elapsed_s": left["elapsed_s"], "Ours_elapsed_s": right["elapsed_s"],
                          "latency_reduction": 1 - right["elapsed_s"] / left["elapsed_s"],
                          "B0_input_tokens": left["input_tokens"], "Ours_input_tokens": right["input_tokens"],
                          "semantic_exact_match": left["semantic_hash"] == right["semantic_hash"]})
    write_json(run_root / "paired_checkpoints.json", pairs)
    strong_pairs = []
    for reference in ("B3-c1", "B3-c2"):
        for key in sorted({(row["window_id"], row["checkpoint_prefix_length"], row["repeat"]) for row in rows}):
            left, right = indexed.get((*key, reference)), indexed.get((*key, "Ours-dev"))
            if left and right and left["status"] == right["status"] == "completed":
                strong_pairs.append({"window_id": key[0], "checkpoint_prefix_length": key[1], "repeat": key[2],
                     "reference_method": reference, "candidate_method": "Ours-dev",
                     "reference_elapsed_s": left["elapsed_s"], "candidate_elapsed_s": right["elapsed_s"],
                     "latency_reduction": 1-right["elapsed_s"]/left["elapsed_s"],
                     "reference_input_tokens": left["input_tokens"], "candidate_input_tokens": right["input_tokens"],
                     "semantic_exact_match": left["semantic_hash"] == right["semantic_hash"]})
    write_json(run_root / "strong_paired_checkpoints.json", strong_pairs)
    failures = sum(row["status"] != "completed" for row in rows)
    metrics = {"status": "completed" if not failures else "completed_with_failures", "schema_version": "fast-compare/1",
               "backend": "transformers_local", "replay_for_paired_methods": False, "scope": scope,
               "live_model_calls": len(recording.calls), "checkpoint_attempts": len(rows), "failed_checkpoints": failures,
               "paired_successful_checkpoints": len(pairs), "elapsed_s": time.perf_counter() - started_run, "summaries": summaries}
    write_json(run_root / "metrics.json", metrics)
    write_json(run_root / "status.json", {"status": metrics["status"], "updated_at": now(), "pid": os.getpid()})
    write_json(run_root / "progress.json", {"status": metrics["status"], "completed_checkpoint_attempts": len(rows),
               "total_checkpoint_attempts": len(rows), "failed_checkpoints": failures, "updated_at": now()})
    report = ["# First real construction comparison", "", f"Run: `{run_root}`", "",
              f"Derived development workload, text-only. Scope: {scope}. Model calls are independent; no replay. Cold model load, warmup, Reader and Judge are excluded equally. Dense embedding/index is {'included through readable publication' if e2e else 'excluded equally'}. These are requested checkpoint construction latencies, not streaming arrival-rate Freshness. Resolve/state/workflow are deterministic local views; only extraction uses the LLM.", "",
              f"Checkpoint attempts: {len(rows)}; failures: {failures}; jointly successful pairs: {len(pairs)}. QA: not_evaluated. P95 is descriptive for this small sample.", ""]
    report.extend([f"Workload: {len(windows)} fixed windows, {sum(len(events) for _, events in windows)} source events; source SHA256 `{workload['source_sha256']}`.",
                   f"Configuration hash: `{config_hash}`. Prompt and source-code copies are frozen under `frozen_code/`.", ""])
    for summary in summaries:
        report.append(f"- {summary['method']}: {summary['total_s']:.3f} s total, {summary['initial_build_s']:.3f} s cold-build checkpoints, {summary['update_total_s']:.3f} s later checkpoint service; {summary['live_model_calls']} live calls; {summary['input_tokens']} input / {summary['output_tokens']} output tokens; {summary['snapshot_checks_passed']}/{summary['n_checkpoints']} snapshot checks.")
    if pairs:
        left_s = sum(pair["B0_elapsed_s"] for pair in pairs)
        right_s = sum(pair["Ours_elapsed_s"] for pair in pairs)
        report.extend(["", f"Joint-success pairs only ({len(pairs)}): total latency {left_s:.3f} vs {right_s:.3f} s, {(1-right_s/left_s)*100:.2f}% reduction. Exact structured semantic matches: {sum(pair['semantic_exact_match'] for pair in pairs)}/{len(pairs)}. This is relative to repeated Fresh, not strong B3."])
        if all(pair["B0_input_tokens"] is not None and pair["Ours_input_tokens"] is not None for pair in pairs):
            left_tokens = sum(pair["B0_input_tokens"] for pair in pairs)
            right_tokens = sum(pair["Ours_input_tokens"] for pair in pairs)
            report.append(f"Joint-success input-token reduction: {(1-right_tokens/left_tokens)*100:.2f}% ({left_tokens} vs {right_tokens}); all failed checkpoints remain in the table and raw log.")
    for method in methods:
        selected = [row for row in rows if row["method"] == method]
        wall = sum(row["elapsed_s"] for row in selected)
        inference = sum(row["model_elapsed_s"] for row in selected)
        report.append(f"{method} bottleneck: {inference:.3f}/{wall:.3f} s ({inference/wall*100:.2f}%) in live extraction calls; local graph/cache/view/publish remainder {wall-inference:.3f} s.")
    for reference in ("B3-c1", "B3-c2"):
        selected = [row for row in strong_pairs if row["reference_method"] == reference]
        if selected:
            left_s = sum(row["reference_elapsed_s"] for row in selected)
            right_s = sum(row["candidate_elapsed_s"] for row in selected)
            report.append(f"Ours-dev vs strong {reference}, {len(selected)} joint-success pairs: {left_s:.3f} vs {right_s:.3f} s, {(1-right_s/left_s)*100:.2f}% candidate reduction (negative is regression); exact semantic matches {sum(row['semantic_exact_match'] for row in selected)}/{len(selected)}. No failed pairs are imputed.")
    for row in rows:
        if row["status"] != "completed":
            report.append(f"Failure retained: {row['method']} {row['window_id']} cp{row['checkpoint_prefix_length']}: {row.get('error_type')}: {row.get('error')}.")
    report.extend(["", "Next: add the same dense embedding/index publication boundary for both methods, and a legitimate conservative-partition cached B3. The largest expected component here is model extraction; inspect per-call and checkpoint model_elapsed_s before selecting the next optimization.", "",
                   f"Raw checkpoint log: `{run_root / 'checkpoint_metrics.jsonl'}`. Requests/responses: `{run_root / 'llm_calls.jsonl'}`. Snapshots and paired checks are retained under the same run.", ""])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(report), encoding="utf-8")
    (run_root / "report.md").write_text("\n".join(report), encoding="utf-8")
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--methods", default="B0,Ours-dev")
    parser.add_argument("--scope", choices=["construction_kernel", "construction_e2e"], default="construction_kernel")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit-windows", type=int)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--table", type=Path, default=CODE_ROOT / "results/tables/first_compare.csv")
    parser.add_argument("--report", type=Path, default=CODE_ROOT / "reports/first_compare.md")
    args = parser.parse_args()
    if args.repeats < 1 or (args.limit_windows is not None and args.limit_windows < 1):
        parser.error("repeats and limit-windows must be positive")
    try:
        return run(args)
    except BaseException as exc:
        if args.out.is_dir():
            write_json(args.out / "failure.json", {"error_type": type(exc).__name__, "error": str(exc), "updated_at": now()})
            write_json(args.out / "status.json", {"status": "failed", "error_type": type(exc).__name__, "error": str(exc), "updated_at": now()})
        raise


if __name__ == "__main__":
    raise SystemExit(main())
