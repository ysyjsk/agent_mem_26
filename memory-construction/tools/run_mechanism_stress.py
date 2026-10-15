#!/usr/bin/env python3
"""Controlled revision/scope stress workloads for the construction methods.

This runner is deliberately narrower than :mod:`run_fast_compare`.  It does
not read labels or replay recorded model responses.  A revision or a scoped
append is prepared in memory from the fixed development manifest, then each
method gets its own file-backed store and a real injected backend.  The output
is a checkpoint JSONL plus an aggregate CSV; the workload is a derived stress
protocol and must not be presented as official QA or held-out quality.

The default CLI backend is the resident local Qwen adapter from
``runtime.local.json``.  Tests can inject a small CPU backend through
``run_revision_stress``/``run_scope_isolation`` without importing torch or
loading a model.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Mapping, Sequence

CODE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_ROOT / "src"))

from workflow_memory.backends import ModelRequest, ModelResponse, backend_fingerprint
from workflow_memory.batched_extraction import prepare_batched_extractions
from workflow_memory.config import load_json, write_json
from workflow_memory.construction import Snapshot, apply_delta, build_fresh, validate_snapshot
from workflow_memory.event_store import EventStore
from workflow_memory.ir import SourceEvent, normalize_trajectory, stable_hash
from workflow_memory.local_backends import TransformersQwenBackend
from workflow_memory.strong_baseline import StrongBaselinePreparationError, build_strong_prefix


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


def load_workload(manifest: Mapping[str, Any], *, limit_windows: int | None = None) -> list[tuple[dict[str, Any], list[SourceEvent]]]:
    """Verify the declared source hash and return only manifest prefixes."""

    source = Path(str(manifest["source_file"])).expanduser().resolve()
    actual = file_hash(source)
    if actual != manifest["source_sha256"]:
        raise ValueError(f"source hash mismatch: expected {manifest['source_sha256']}, got {actual}")
    wanted = {str(item["trajectory_id"]) for item in manifest["windows"]}
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
    specs = list(manifest["windows"])
    if limit_windows is not None:
        specs = specs[:limit_windows]
    result: list[tuple[dict[str, Any], list[SourceEvent]]] = []
    for spec in specs:
        trajectory_id = str(spec["trajectory_id"])
        if trajectory_id not in records:
            raise ValueError(f"missing trajectory {trajectory_id}")
        events = normalize_trajectory(records[trajectory_id])[: int(spec["event_count"])]
        if [event.event_id for event in events] != list(spec["event_ids"]):
            raise ValueError(f"normalized event IDs disagree with manifest for {spec['window_id']}")
        checkpoints = list(spec["checkpoint_prefix_lengths"])
        if not checkpoints or checkpoints != sorted(set(checkpoints)) or checkpoints[-1] != len(events):
            raise ValueError(f"invalid checkpoints in {spec['window_id']}")
        result.append((dict(spec), events))
    return result


def position_index(n_events: int, position: str) -> int:
    """Choose a stable early/mid/late event while leaving later context."""

    if n_events < 3:
        raise ValueError("revision stress requires at least three source events")
    values = {"early": max(0, n_events // 4),
              "mid": max(0, n_events // 2),
              "late": max(0, n_events - 2)}
    if position not in values:
        raise ValueError(f"unknown revision position {position!r}; expected early, mid or late")
    return min(values[position], n_events - 1)


def revised_event(event: SourceEvent, position: str) -> SourceEvent:
    """Make a versioned in-memory revision without changing source files."""

    marker = f"revision-stress-{position}-r{event.source_revision + 1}"
    action = event.action
    if isinstance(action, Mapping):
        action = {**action, "revision_stress": marker}
    else:
        action = f"{action} [{marker}]" if action is not None else marker
    post_state = event.post_state_ref
    if isinstance(post_state, Mapping):
        post_state = {**post_state, "revision_stress": marker}
    elif post_state is not None:
        post_state = {"value": post_state, "revision_stress": marker}
    outcome = event.observed_outcome
    if isinstance(outcome, Mapping):
        outcome = {**outcome, "revision_stress": marker}
    elif outcome is not None:
        outcome = {"value": outcome, "revision_stress": marker}
    return replace(event, source_revision=event.source_revision + 1,
                   action=action, post_state_ref=post_state,
                   observed_outcome=outcome, raw_content_hash="")


def scoped_append_event(event: SourceEvent) -> SourceEvent:
    """Derive one append-only event for the controlled scope workload."""

    sequence = int(event.source_sequence) + 1
    arrival = int(event.arrival_sequence) + 1
    event_id = f"{event.trajectory_id}:mechanism-append-{sequence}"
    return replace(
        event,
        event_id=event_id,
        source_sequence=sequence,
        arrival_sequence=arrival,
        source_revision=0,
        action={"type": "mechanism_scope_append", "source": event.event_id},
        pre_state_ref=event.post_state_ref,
        post_state_ref={"mechanism_append": event.event_id},
        observed_outcome={"status": "observed", "mechanism_append": True},
        causal_predecessors=(event.event_id,),
        raw_content_hash="",
    )


def semantic_hash(snapshot: Snapshot) -> str:
    """Hash published semantics while excluding epoch/store/node identity."""

    return stable_hash({
        "events": [item.to_dict() for item in snapshot.events],
        "evidence": [item.to_dict() for item in snapshot.evidence],
        "state": snapshot.state_view,
        "workflow": snapshot.workflow_view,
        "aliases": snapshot.aliases,
        "relations": snapshot.relations,
        "index": snapshot.index,
    })


def ordered_events(events: Sequence[SourceEvent]) -> list[SourceEvent]:
    """Match construction's canonical ordering for multi-scope workloads."""

    return sorted(events, key=lambda event: (
        event.trajectory_id, event.source_sequence, event.source_revision, event.event_id
    ))


class InstrumentedBackend:
    """Record real model calls while preserving the backend capabilities."""

    def __init__(self, backend: Any, output_root: Path):
        self.backend = backend
        self.output_root = output_root
        self.calls: list[dict[str, Any]] = []
        self.batch_count = 0
        self.context: dict[str, Any] = {}

    def fingerprint(self) -> str:
        return backend_fingerprint(self.backend)

    @property
    def supports_batch_calls(self) -> bool:
        declared = getattr(self.backend, "supports_batch_calls", None)
        if declared is False:
            return False
        return callable(getattr(self.backend, "complete_batch", None))

    @property
    def max_batch_size(self) -> int:
        return int(getattr(self.backend, "max_batch_size", 1))

    def _base_row(self, request: ModelRequest, call_id: str, **extra: Any) -> dict[str, Any]:
        return {**self.context, "call_id": call_id, "request_hash": request.fingerprint,
                "request": request.to_dict(), "started_at": now(),
                "backend": backend_fingerprint(self.backend), "cache": "miss_live", **extra}

    @staticmethod
    def _usage(response: ModelResponse) -> tuple[int | None, int | None]:
        usage = dict(response.usage or {})
        input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        return (None if input_tokens is None else int(input_tokens),
                None if output_tokens is None else int(output_tokens))

    def complete(self, request: ModelRequest, **kwargs: Any) -> ModelResponse:
        call_id = f"call-{len(self.calls):06d}"
        row = self._base_row(request, call_id)
        append_jsonl(self.output_root / "model_requests.jsonl", row)
        started = time.perf_counter_ns()
        try:
            response = ModelResponse.from_any(self.backend.complete(request, **kwargs))
            input_tokens, output_tokens = self._usage(response)
            row.update(status="completed", elapsed_ns=time.perf_counter_ns() - started,
                       input_tokens=input_tokens, output_tokens=output_tokens,
                       usage=dict(response.usage or {}), model=response.model,
                       response_text=response.text, response_hash=stable_hash(response.text),
                       finish_reason=response.finish_reason,
                       actual_batch_size=int((response.raw or {}).get("batch_size", 1))
                       if isinstance(response.raw, Mapping) else 1)
        except BaseException as exc:
            row.update(status="failed", elapsed_ns=time.perf_counter_ns() - started,
                       input_tokens=None, output_tokens=None,
                       error_type=type(exc).__name__, error=str(exc))
            self.calls.append(row)
            append_jsonl(self.output_root / "model_calls.jsonl", row)
            raise
        self.calls.append(row)
        append_jsonl(self.output_root / "model_calls.jsonl", row)
        return response

    def complete_batch(self, requests: Sequence[ModelRequest], **kwargs: Any) -> tuple[ModelResponse, ...]:
        if not self.supports_batch_calls:
            raise RuntimeError("backend has no complete_batch capability")
        group = tuple(requests)
        if not group:
            return ()
        batch_id = f"batch-{self.batch_count:06d}"
        self.batch_count += 1
        rows = [self._base_row(request, f"call-{len(self.calls) + i:06d}", batch_id=batch_id)
                for i, request in enumerate(group)]
        for row in rows:
            append_jsonl(self.output_root / "model_requests.jsonl", row)
        started = time.perf_counter_ns()
        try:
            values = self.backend.complete_batch(group, **kwargs)
            responses = tuple(ModelResponse.from_any(value) for value in values)
            if len(responses) != len(group):
                raise ValueError("complete_batch returned a different number of responses")
            duration = time.perf_counter_ns() - started
            for row, response in zip(rows, responses):
                input_tokens, output_tokens = self._usage(response)
                row.update(status="completed", elapsed_ns=duration, batch_elapsed_ns=duration,
                           input_tokens=input_tokens, output_tokens=output_tokens,
                           usage=dict(response.usage or {}), model=response.model,
                           response_text=response.text, response_hash=stable_hash(response.text),
                           finish_reason=response.finish_reason,
                           actual_batch_size=int((response.raw or {}).get("batch_size", 1))
                           if isinstance(response.raw, Mapping) else 1)
        except BaseException as exc:
            duration = time.perf_counter_ns() - started
            for row in rows:
                row.update(status="failed", elapsed_ns=duration, batch_elapsed_ns=duration,
                           input_tokens=None, output_tokens=None,
                           error_type=type(exc).__name__, error=str(exc))
            for row in rows:
                self.calls.append(row)
                append_jsonl(self.output_root / "model_calls.jsonl", row)
            raise
        for row in rows:
            self.calls.append(row)
            append_jsonl(self.output_root / "model_calls.jsonl", row)
        append_jsonl(self.output_root / "model_batches.jsonl", {
            **self.context, "batch_id": batch_id, "status": "completed",
            "elapsed_ns": duration, "requested_batch_size": len(group),
            "actual_batch_size": max(int(row.get("actual_batch_size") or 0) for row in rows),
        })
        return responses


class FixtureBackend:
    """CPU-only contract backend for runner tests (never a research result)."""

    max_batch_size = 2

    def fingerprint(self) -> str:
        return "cpu-mechanism-fixture/1"

    @staticmethod
    def _response(request: ModelRequest, batch_size: int = 1) -> ModelResponse:
        event_id = str(request.metadata.get("event_id", "fixture-event"))
        try:
            value = json.loads(request.messages[-1]["content"])
        except Exception:
            value = request.messages[-1].get("content", "")
        evidence = {
            "predicate": "observed_property", "subject_ref": "page",
            "value": value, "event_kind": "observation", "source_refs": [event_id],
        }
        return ModelResponse(text=json.dumps({"evidence": [evidence]}),
                             raw={"device": "cpu", "batch_size": batch_size})

    def complete(self, request: ModelRequest, **_: Any) -> ModelResponse:
        return self._response(request)

    def complete_batch(self, requests: Sequence[ModelRequest], **_: Any) -> tuple[ModelResponse, ...]:
        values = tuple(requests)
        return tuple(self._response(request, batch_size=len(values)) for request in values)


def token_sum(rows: Sequence[Mapping[str, Any]], key: str) -> int | None:
    values = [row.get(key) for row in rows]
    if any(value is None for value in values):
        return None
    return sum(int(value) for value in values)


def model_elapsed_s(rows: Sequence[Mapping[str, Any]]) -> float:
    """Count one wall interval per serial call or actual model batch."""

    serial = sum(int(row.get("elapsed_ns", 0)) for row in rows if not row.get("batch_id"))
    batches: dict[str, int] = {}
    for row in rows:
        batch_id = row.get("batch_id")
        if batch_id:
            batches[str(batch_id)] = max(batches.get(str(batch_id), 0), int(row.get("batch_elapsed_ns", row.get("elapsed_ns", 0))))
    return (serial + sum(batches.values())) / 1e9


def snapshot_checks(snapshot: Snapshot, expected_events: Sequence[SourceEvent], config: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    report = validate_snapshot(snapshot)
    if not report.valid:
        errors.extend(str(item) for item in report.errors)
    expected_ids = [item.event_id for item in expected_events]
    actual_ids = [item.event_id for item in snapshot.events]
    if actual_ids != expected_ids or [event.to_dict() for event in snapshot.events] != [event.to_dict() for event in expected_events]:
        errors.append("source frontier differs from arrived prefix")
    covered = {source for item in snapshot.evidence for source in item.source_refs}
    missing = sorted(set(expected_ids) - covered)
    if missing:
        errors.append(f"missing source evidence: {missing}")
    if not snapshot.workflow_view:
        errors.append("workflow view is empty")
    store_path = str(config["storage_path"])
    try:
        with EventStore(store_path) as store:
            record = store.get_snapshot(snapshot.snapshot_id)
            if record is None:
                errors.append("published snapshot missing from store")
    except Exception as exc:
        errors.append(f"store check failed: {type(exc).__name__}: {exc}")
    return {
        "snapshot_valid": not errors,
        "snapshot_check_errors": errors,
        "source_events_with_evidence": len(covered),
        "source_coverage_fraction": len(covered) / len(expected_ids) if expected_ids else 1.0,
        "semantic_hash": semantic_hash(snapshot),
    }


def _phase_metrics(before_calls: int, recorder: InstrumentedBackend, *, elapsed_ns: int,
                   considered: int, cache_hits: int | None = None,
                   cache_misses: int | None = None, affected_nodes: int = 0,
                   recomputed_nodes: int | None = None) -> dict[str, Any]:
    calls = recorder.calls[before_calls:]
    live_calls = len(calls)
    if cache_misses is None:
        cache_misses = live_calls
    if cache_hits is None:
        cache_hits = max(0, int(considered) - int(cache_misses))
    model_s = model_elapsed_s(calls)
    elapsed_s = elapsed_ns / 1e9
    return {
        "live_model_calls": live_calls,
        "failed_model_calls": sum(row.get("status") != "completed" for row in calls),
        "input_tokens": token_sum(calls, "input_tokens"),
        "output_tokens": token_sum(calls, "output_tokens"),
        "cache_hits": int(cache_hits),
        "cache_misses": int(cache_misses),
        "affected_nodes": int(affected_nodes),
        "recomputed_nodes": recomputed_nodes,
        "model_elapsed_s": model_s,
        "embedding_elapsed_s": None,
        "embedding_model_calls": None,
        "embedding_input_tokens": None,
        "embedding_status": "excluded_from_construction_kernel",
        "local_elapsed_s": max(0.0, elapsed_s - model_s),
        "actual_batch_size_max": max([int(call.get("actual_batch_size") or 0) for call in calls] or [0]),
    }


def _base_row(*, scenario: str, method: str, window_id: str, position: str,
              phase: str, expected_events: Sequence[SourceEvent], source_event_id: str | None,
              config_hash: str, workload_hash: str, storage_path: Path) -> dict[str, Any]:
    return {
        "scenario": scenario, "method": method, "window_id": window_id,
        "position": position, "phase": phase,
        "source_event_id": source_event_id,
        "source_revision": None,
        "prefix_events": len(expected_events),
        "storage_path": str(storage_path), "config_hash": config_hash,
        "workload_hash": workload_hash, "scope": "construction_kernel",
        "status": "failed", "snapshot_valid": False,
        "snapshot_check_errors": [], "semantic_hash": None,
        "elapsed_s": None, "model_elapsed_s": 0.0,
        "local_elapsed_s": None, "embedding_elapsed_s": None,
        "embedding_model_calls": None, "embedding_input_tokens": None,
        "embedding_status": "excluded_from_construction_kernel",
        "live_model_calls": 0, "failed_model_calls": 0,
        "input_tokens": None, "output_tokens": None,
        "cache_hits": 0, "cache_misses": 0,
        "affected_nodes": 0, "recomputed_nodes": None,
        "source_events_with_evidence": 0, "source_coverage_fraction": 0.0,
        "error_type": None, "error": None,
    }


def method_concurrency(method: str, settings: Mapping[str, Any]) -> int:
    if method == "B3-c2":
        return 2
    if method == "Ours-dev":
        width = int(settings.get("extraction_concurrency", 2))
        if width not in {1, 2}:
            raise ValueError("Ours-dev extraction_concurrency must be 1 or 2")
        return width
    return 1


def node_work(snapshot: Snapshot, previous: Snapshot | None) -> dict[str, Any]:
    """Count actual ComputeNode instances recreated, not invalidation labels.

    ``_make_nodes`` preserves the identical Python object when a node is
    reused.  Every method still visits all planned nodes and rebuilds the
    deterministic state/workflow/index views; these costs are reported too.
    """

    old = {node.node_id: node for node in previous.nodes} if previous else {}
    counts: dict[str, int] = {}
    visits: dict[str, int] = {}
    for node in snapshot.nodes:
        visits[node.operator] = visits.get(node.operator, 0) + 1
        if old.get(node.node_id) is not node:
            counts[node.operator] = counts.get(node.operator, 0) + 1
    return {
        "recomputed_nodes": sum(counts.values()),
        "recomputed_nodes_by_operator": counts,
        "node_value_visits": len(snapshot.nodes),
        "node_value_visits_by_operator": visits,
        "recomputed_node_metric": "ComputeNode_instance_recreated_hashes_recomputed",
        "deterministic_views_rebuilt": True,
    }


def _run_pair(*, scenario: str, method: str, window_id: str, position: str,
              initial_events: Sequence[SourceEvent], revised_events: Sequence[SourceEvent],
              source_event_id: str | None, root: Path, recorder: InstrumentedBackend,
              settings: Mapping[str, Any], config_hash: str, workload_hash: str,
              append_row: Callable[[Mapping[str, Any]], None]) -> None:
    """Run initial and changed checkpoints for one method-owned store."""

    method_root = root / "stores" / scenario / window_id / position / method
    method_root.mkdir(parents=True, exist_ok=True)
    incremental_path = method_root / "incremental.sqlite3"
    initial_path = method_root / "initial.sqlite3"
    revised_path = method_root / "revised.sqlite3"
    recorder.context = {"scenario": scenario, "window_id": window_id,
                        "position": position, "method": method, "phase": "initial_build"}

    # B0 intentionally uses a distinct store for the revised Fresh checkpoint;
    # no derived cache from the initial build is allowed to hide work.
    initial_store = initial_path if method == "B0" else incremental_path
    revised_store = revised_path if method == "B0" else incremental_path
    initial_config = {**settings, "storage_path": str(initial_store)}
    revised_config = {**settings, "storage_path": str(revised_store)}
    previous: Snapshot | None = None
    for phase, events, config, source_id in (
        ("initial_build", list(initial_events), initial_config, None),
        ("revision_update" if scenario == "revision_stress" else "scope_append", list(revised_events), revised_config, source_event_id),
    ):
        expected = ordered_events(events)
        row = _base_row(scenario=scenario, method=method, window_id=window_id,
                        position=position, phase=phase, expected_events=expected,
                        source_event_id=source_id, config_hash=config_hash,
                        workload_hash=workload_hash, storage_path=Path(config["storage_path"]))
        row["source_revision"] = next((event.source_revision for event in expected
                                        if event.event_id == source_event_id), None)
        before_calls = len(recorder.calls)
        started = time.perf_counter_ns()
        recorder.context = {"scenario": scenario, "window_id": window_id,
                            "position": position, "method": method, "phase": phase}
        stats: dict[str, Any] = {}
        preparation: dict[str, Any] = {}
        try:
            if phase != "initial_build" and previous is None:
                raise RuntimeError("initial checkpoint failed; no method-owned snapshot available")
            width = method_concurrency(method, settings)
            if method == "Ours-dev" and width > 1:
                preparation = prepare_batched_extractions(expected, recorder, config, batch_size=width)
            if method.startswith("B3-"):
                candidate, strong_stats = build_strong_prefix(expected, recorder, config,
                                                              previous=previous,
                                                              concurrency=width)
                stats = strong_stats
                affected = int(strong_stats.get("invalidated_nodes", 0))
                cache_hits = int(strong_stats.get("cache_hits", 0))
                cache_misses = int(strong_stats.get("cache_misses", 0))
            elif phase == "initial_build" or method == "B0":
                candidate = build_fresh(expected, model_backend=recorder, config=config)
                affected = len(candidate.nodes)
                cache_hits = int(preparation.get("cache_hits", 0))
                cache_misses = int(preparation.get("cache_misses", len(expected)))
            elif method == "Ours-dev":
                receipt = apply_delta(previous, [event for event in expected
                                                 if event.event_id == source_event_id],
                                      model_backend=recorder, config=config)
                if receipt.snapshot is None or not receipt.queryable:
                    raise RuntimeError("incremental update did not publish a queryable snapshot")
                candidate = receipt.snapshot
                stats = receipt.to_dict()
                affected = len(receipt.invalidated_node_ids)
                cache_hits = int(preparation.get("cache_hits", max(0, len(expected) - (len(recorder.calls) - before_calls))))
                cache_misses = int(preparation.get("cache_misses", len(recorder.calls) - before_calls))
            else:
                raise ValueError(f"unsupported method {method}")
            elapsed_ns = time.perf_counter_ns() - started
            row.update(status="completed", elapsed_s=elapsed_ns / 1e9,
                       **_phase_metrics(before_calls, recorder, elapsed_ns=elapsed_ns,
                                        considered=len(expected), cache_hits=cache_hits,
                                        cache_misses=cache_misses,
                                        affected_nodes=affected))
            row.update(node_work(candidate, previous if method != "B0" else None))
            row.update(snapshot_id=candidate.snapshot_id,
                       **snapshot_checks(candidate, expected, config))
            if not row["snapshot_valid"]:
                row.update(status="failed", error_type="SnapshotValidationError",
                           error="; ".join(row["snapshot_check_errors"]))
            snapshot_path = root / "snapshots" / scenario / window_id / position / method / f"{phase}.json"
            write_json(snapshot_path, candidate.to_dict())
            row["snapshot_path"] = str(snapshot_path)
            if stats:
                row["method_stats"] = stats
            if preparation:
                row["extraction_preparation"] = preparation
            if phase != "initial_build" and scenario == "revision_stress" and method != "B0":
                with EventStore(str(config["storage_path"])) as archive:
                    versions = list(archive.iter_source_event_revisions(str(source_event_id)))
                old_revision = next(event.source_revision for event in initial_events if event.event_id == source_event_id)
                row["source_revision_archive_valid"] = any(int(item["source_revision"]) == old_revision for item in versions)
                if not row["source_revision_archive_valid"]:
                    row.update(status="failed", error_type="RevisionArchiveError", error="old source revision was not archived")
            append_row(row)
            if phase == "initial_build":
                previous = candidate
            else:
                previous = candidate
        except BaseException as exc:
            elapsed_ns = time.perf_counter_ns() - started
            row.update(error_type=type(exc).__name__, error=str(exc), elapsed_s=elapsed_ns / 1e9,
                       **_phase_metrics(before_calls, recorder, elapsed_ns=elapsed_ns,
                                        considered=len(expected)))
            if hasattr(exc, "stats"):
                row["method_stats"] = dict(exc.stats)
            if hasattr(exc, "errors"):
                row["preparation_errors"] = list(exc.errors)
            append_row(row)


def run_revision_stress(*, windows: Sequence[tuple[Mapping[str, Any], Sequence[SourceEvent]]],
                        backend: Any, settings: Mapping[str, Any], out: Path,
                        methods: Sequence[str] = ("B0", "Ours-dev", "B3-c2"),
                        positions: Sequence[str] = ("early", "mid", "late"),
                        config_hash: str = "", workload_hash: str = "") -> list[dict[str, Any]]:
    """Run early/mid/late revisions on each fixed manifest window."""

    if (out / "checkpoint_metrics.jsonl").exists() or (out / "stores").exists():
        raise ValueError(f"refuse to append to existing mechanism run: {out}")
    out.mkdir(parents=True, exist_ok=True)
    recorder = InstrumentedBackend(backend, out)
    rows: list[dict[str, Any]] = []
    append_row = lambda row: (rows.append(dict(row)), append_jsonl(out / "checkpoint_metrics.jsonl", row))
    for spec, source_events in windows:
        source_events = list(source_events)
        for position in positions:
            index = position_index(len(source_events), position)
            revised = list(source_events)
            revised[index] = revised_event(source_events[index], position)
            for method in methods:
                _run_pair(scenario="revision_stress", method=method,
                          window_id=str(spec["window_id"]), position=position,
                          initial_events=source_events, revised_events=revised,
                          source_event_id=source_events[index].event_id, root=out,
                          recorder=recorder, settings=settings,
                          config_hash=config_hash, workload_hash=workload_hash,
                          append_row=append_row)
    return rows


def run_scope_isolation(*, windows: Sequence[tuple[Mapping[str, Any], Sequence[SourceEvent]]],
                        backend: Any, settings: Mapping[str, Any], out: Path,
                        methods: Sequence[str] = ("B0", "Ours-dev", "B3-c2"),
                        config_hash: str = "", workload_hash: str = "") -> list[dict[str, Any]]:
    """Merge independent scopes, then append only to scope ``a``."""

    if len(windows) < 2:
        raise ValueError("scope_isolation requires at least two manifest windows")
    if (out / "checkpoint_metrics.jsonl").exists() or (out / "stores").exists():
        raise ValueError(f"refuse to append to existing mechanism run: {out}")
    out.mkdir(parents=True, exist_ok=True)
    recorder = InstrumentedBackend(backend, out)
    rows: list[dict[str, Any]] = []
    append_row = lambda row: (rows.append(dict(row)), append_jsonl(out / "checkpoint_metrics.jsonl", row))
    for pair_index in range(0, len(windows) - 1, 2):
        first_spec, first_events = windows[pair_index]
        second_spec, second_events = windows[pair_index + 1]
        initial = list(first_events) + list(second_events)
        appended = scoped_append_event(list(first_events)[-1])
        revised = initial + [appended]
        window_id = f"{first_spec['window_id']}__{second_spec['window_id']}"
        for method in methods:
            _run_pair(scenario="scope_isolation", method=method,
                      window_id=window_id, position="append-a",
                      initial_events=initial, revised_events=revised,
                      source_event_id=appended.event_id, root=out,
                      recorder=recorder, settings=settings,
                      config_hash=config_hash, workload_hash=workload_hash,
                      append_row=append_row)
    return rows


def write_summary(path: Path, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault((str(row["scenario"]), str(row["method"]), str(row["phase"])), []).append(row)
    summaries: list[dict[str, Any]] = []
    for (scenario, method, phase), selected in sorted(groups.items()):
        completed = [row for row in selected if row.get("status") == "completed"]
        sum_value = lambda key: sum(float(row.get(key) or 0.0) for row in selected)
        sum_int = lambda key: sum(int(row.get(key) or 0) for row in selected)
        token_values = [row.get("input_tokens") for row in selected]
        output_values = [row.get("output_tokens") for row in selected]
        summaries.append({
            "scenario": scenario, "method": method, "phase": phase,
            "n_checkpoints": len(selected), "successful_checkpoints": len(completed),
            "failed_checkpoints": len(selected) - len(completed),
            "elapsed_s_total": sum_value("elapsed_s"),
            "elapsed_s_mean": sum_value("elapsed_s") / len(selected) if selected else None,
            "model_elapsed_s_total": sum_value("model_elapsed_s"),
            "local_elapsed_s_total": sum_value("local_elapsed_s"),
            "embedding_elapsed_s_total": None,
            "embedding_status": "excluded_from_construction_kernel",
            "live_model_calls": sum_int("live_model_calls"),
            "failed_model_calls": sum_int("failed_model_calls"),
            "input_tokens": None if any(value is None for value in token_values) else sum(int(value) for value in token_values),
            "output_tokens": None if any(value is None for value in output_values) else sum(int(value) for value in output_values),
            "cache_hits": sum_int("cache_hits"), "cache_misses": sum_int("cache_misses"),
            "affected_nodes": sum_int("affected_nodes"), "recomputed_nodes": sum_int("recomputed_nodes"),
            "recomputed_nodes_status": "complete" if all(row.get("recomputed_nodes") is not None for row in selected) else "partial_missing_on_failures",
            "node_value_visits": sum_int("node_value_visits"),
            "snapshot_checks_passed": sum(bool(row.get("snapshot_valid")) for row in selected),
            "qa_status": "not_evaluated",
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(summaries[0]) if summaries else ["status"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summaries or [{"status": "missing"}])
    return summaries


def _make_local_backend(runtime: Mapping[str, Any]) -> TransformersQwenBackend:
    model_cfg = runtime["plan"]["models"]["construction"]
    return TransformersQwenBackend(
        str(model_cfg["local_path"]),
        device=model_cfg.get("device", "cuda:0"),
        dtype=model_cfg.get("dtype") or model_cfg.get("precision") or "bfloat16",
        max_input_tokens=min(int(model_cfg.get("context_limit") or 8192), 8192),
        enable_thinking=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--scenario", choices=("revision_stress", "scope_isolation", "both"), default="revision_stress")
    # The current mainline has already paid for B0/Fresh.  Keep it available
    # as an explicit method for audit/reproduction, but default the stress run
    # to the two incremental methods requested for the next mechanism round.
    parser.add_argument("--methods", default="Ours-dev,B3-c2")
    parser.add_argument("--positions", default="early,mid,late")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit-windows", type=int)
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--backend", choices=("local", "fixture"), default="local",
                        help="local uses runtime.local Qwen; fixture is CPU-only contract testing and is not a result")
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"refuse to overwrite existing output directory: {args.out}")
    runtime = load_json(args.config)
    manifest = load_json(args.manifest)
    windows = load_workload(manifest, limit_windows=args.limit_windows)
    methods = tuple(item.strip() for item in args.methods.split(",") if item.strip())
    allowed = {"B0", "Ours-dev", "B3-c1", "B3-c2"}
    if not methods or any(method not in allowed for method in methods) or len(set(methods)) != len(methods):
        parser.error("methods must be distinct values from B0,Ours-dev,B3-c1,B3-c2")
    positions = tuple(item.strip() for item in args.positions.split(",") if item.strip())
    if any(item not in {"early", "mid", "late"} for item in positions):
        parser.error("positions must be drawn from early,mid,late")
    settings = dict(manifest.get("shared_initial_settings", {}))
    if args.settings:
        settings.update(load_json(args.settings))
    model_cfg = runtime["plan"]["models"]["construction"]
    settings.update(construction_model=model_cfg["id"], strict_model_output=True,
                    extract_operator_version="qwen-fastloop-strict-v2",
                    extraction_prompt=(CODE_ROOT / "prompts/extract_evidence_v2.txt").read_text(encoding="utf-8").strip())
    if settings.get("source_literal_evidence") or settings.get("model_input_projection") == "salient-v3":
        settings["extract_operator_version"] = "qwen-quality-v3"
    workload_hash = stable_hash({"manifest": manifest, "selected_windows": [spec for spec, _ in windows]})
    code_paths = [
        Path(__file__),
        CODE_ROOT / "src/workflow_memory/construction.py",
        CODE_ROOT / "src/workflow_memory/strong_baseline.py",
        CODE_ROOT / "src/workflow_memory/batched_extraction.py",
        CODE_ROOT / "src/workflow_memory/local_backends.py",
        CODE_ROOT / "src/workflow_memory/backends.py",
        CODE_ROOT / "src/workflow_memory/ir.py",
        CODE_ROOT / "src/workflow_memory/dependency.py",
        CODE_ROOT / "src/workflow_memory/cache.py",
        CODE_ROOT / "src/workflow_memory/event_store.py",
        CODE_ROOT / "prompts/extract_evidence_v2.txt",
    ]
    if settings.get("source_literal_evidence"):
        code_paths.append(CODE_ROOT / "src/workflow_memory/source_literals.py")
    code_sha256 = {str(path.relative_to(CODE_ROOT)): file_hash(path) for path in code_paths}
    config_hash = stable_hash({"runtime_sha256": file_hash(args.config), "settings": settings,
                               "model_cfg": model_cfg, "scenario": args.scenario,
                               "methods": methods, "positions": positions,
                               "code_sha256": code_sha256})
    args.out.mkdir(parents=True)
    write_json(args.out / "manifest.json", {
        "schema_version": "mechanism-stress/1", "created_at": now(),
        "scenario": args.scenario, "methods": list(methods), "positions": list(positions),
        "config_hash": config_hash, "workload_hash": workload_hash,
        "source_sha256": manifest["source_sha256"], "source_verified": True,
        "derived_protocol": "controlled stress; no gold/raw-source reads beyond fixed manifest prefixes",
        "qa_status": "not_evaluated", "settings": settings,
        "code_sha256": code_sha256,
        "model_timing_policy": "resident local model load plus common serial/batch warmup excluded from checkpoint rows",
        "embedding_status": "excluded_from_construction_kernel; no embedding calls in this runner",
        "scope": "construction_kernel",
        "scope_includes": ["real extraction/preparation", "method-owned cache", "canonical graph/state/workflow/index", "SQLite publication"],
        "scope_excludes": ["model load", "common warmup", "Embedding/dense publication", "Reader", "Judge", "post-publication checks and snapshot file export"],
        "work_metric_definitions": {
            "cache_hits/cache_misses": "logical prefix extraction requests before preparation; does not double-count build_fresh cache reads after preparation",
            "affected_nodes": "method's graph/scope invalidation decision (policy-specific)",
            "recomputed_nodes": "actual ComputeNode instances recreated, including hashes; identified by preserved object identity, not invalidation count",
            "node_value_visits": "all _make_nodes visits; value projection still runs for reused nodes",
            "deterministic_views_rebuilt": "all methods currently rebuild state/workflow/lexical views",
        },
    })
    backend = FixtureBackend() if args.backend == "fixture" else _make_local_backend(runtime)
    setup_started = time.perf_counter()
    load_s = None
    warmup_s = None
    warmup_usage: Mapping[str, Any] = {}
    batch_warmup_s = None
    batch_warmup_usage = []
    ensure_loaded = getattr(backend, "_ensure_loaded", None)
    if callable(ensure_loaded):
        load_started = time.perf_counter()
        ensure_loaded()
        load_s = time.perf_counter() - load_started
        warmup_started = time.perf_counter()
        warmup = backend.complete(ModelRequest(
            messages=({"role": "user", "content": "Reply with OK only."},),
            temperature=0.0, max_tokens=8,
        ))
        warmup_s = time.perf_counter() - warmup_started
        warmup_usage = dict(getattr(warmup, "usage", {}) or {})
        if any(method_concurrency(method, settings) == 2 for method in methods):
            batch_started = time.perf_counter()
            batch_warmup = backend.complete_batch([
                ModelRequest(messages=({"role": "user", "content": "Reply with OK only."},), temperature=0.0, max_tokens=8),
                ModelRequest(messages=({"role": "user", "content": "Reply with READY only."},), temperature=0.0, max_tokens=8),
            ])
            batch_warmup_s = time.perf_counter() - batch_started
            batch_warmup_usage = [dict(response.usage) for response in batch_warmup]
    write_json(args.out / "model_setup.json", {
        "load_s": load_s, "warmup_s": warmup_s, "warmup_usage": warmup_usage,
        "batch_warmup_s": batch_warmup_s, "batch_warmup_usage": batch_warmup_usage,
        "setup_elapsed_s": time.perf_counter() - setup_started,
        "fingerprint": backend_fingerprint(backend),
        "backend_mode": args.backend,
        "timing_policy": "load and warmup are outside checkpoint construction latency",
    })
    frozen_root = args.out / "frozen_code"
    for path in code_paths:
        destination = frozen_root / path.relative_to(CODE_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
    all_rows: list[dict[str, Any]] = []
    if args.scenario in {"revision_stress", "both"}:
        revision_out = args.out if args.scenario == "revision_stress" else args.out / "revision_stress"
        all_rows.extend(run_revision_stress(windows=windows, backend=backend, settings=settings,
                                            out=revision_out, methods=methods, positions=positions,
                                            config_hash=config_hash, workload_hash=workload_hash))
    if args.scenario in {"scope_isolation", "both"}:
        scope_out = args.out if args.scenario == "scope_isolation" else args.out / "scope_isolation"
        all_rows.extend(run_scope_isolation(windows=windows, backend=backend, settings=settings,
                                            out=scope_out, methods=methods,
                                            config_hash=config_hash, workload_hash=workload_hash))
    summary_path = args.out / "summary.csv"
    summaries = write_summary(summary_path, all_rows)
    if args.scenario == "both":
        # The scenario sub-runners have their own JSONL; this combined file is
        # useful for an audit without changing either workload's row identity.
        with (args.out / "checkpoint_metrics.jsonl").open("w", encoding="utf-8") as handle:
            for row in all_rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_json(args.out / "metrics.json", {
        "schema_version": "mechanism-stress/1", "status": "completed_with_failures"
        if any(row.get("status") != "completed" for row in all_rows) else "completed",
        "checkpoint_attempts": len(all_rows),
        "failed_checkpoints": sum(row.get("status") != "completed" for row in all_rows),
        "summaries": summaries, "qa_status": "not_evaluated",
    })
    return 0 if not any(row.get("status") != "completed" for row in all_rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
