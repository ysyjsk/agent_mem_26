"""Prepare Ours' exact extraction misses in real batches, without publishing.

Raw source context is model-independent, so all prefix-visible requests can
be prepared before build_fresh/apply_delta consumes this method-owned cache.
No heuristic, replay, worker store write or inference-overlap claim is used.
"""
from __future__ import annotations

import inspect
import time
from typing import Any, Mapping, Sequence

from . import construction as core
from .backends import ModelResponse
from .ir import Evidence, SourceEvent


class BatchedExtractionPreparationError(core.ConstructionError):
    def __init__(self, errors: Sequence[Mapping[str, Any]], stats: Mapping[str, Any]):
        self.errors, self.stats = tuple(dict(error) for error in errors), dict(stats)
        super().__init__("batched extraction failed without publication: " + "; ".join(
            f"{error['event_id']}: {error['error']}" for error in self.errors))


def _valid_cached(rows: Any, event: SourceEvent, context: Sequence[SourceEvent]) -> bool:
    if not isinstance(rows, (list, tuple)):
        return False
    sources = {source.event_id: source for source in context}
    sources[event.event_id] = event
    try:
        for row in rows:
            evidence = Evidence.from_dict(row)
            if evidence.valid_scope != core._scope(event) or not evidence.source_refs:
                return False
            for ref in evidence.source_refs:
                source = sources.get(ref)
                if (source is None or core._scope(source) != core._scope(event)
                        or evidence.source_versions.get(ref) != source.source_revision):
                    return False
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def prepare_batched_extractions(events: Sequence[SourceEvent], backend: Any, config: Any,
                                batch_size: int = 2) -> dict[str, Any]:
    started = time.perf_counter()
    width = int(batch_size)
    if not 1 <= width <= 2:
        raise core.ConstructionError("batched extraction supports a bounded batch_size of 1 or 2")
    if (getattr(backend, "supports_batch_calls", False) is not True
            or not callable(getattr(backend, "complete_batch", None))
            or int(getattr(backend, "max_batch_size", 1)) < width):
        raise core.ConstructionError("batched extraction requires explicit real complete_batch capability/capacity")
    events = list(events)
    if not all(isinstance(event, SourceEvent) for event in events):
        raise core.ConstructionError("batched extraction expects normalized SourceEvent records")
    events.sort(key=core._event_sort_key)
    if len({event.event_id for event in events}) != len(events):
        raise core.ConstructionError("batched prefix must contain one active revision per event_id")
    namespace = core._store_path(config)
    if namespace == ":memory:":
        raise core.ConstructionError("batched extraction requires an explicit method-owned file-backed cache namespace")
    cache = core._cache(config)
    window = int(core._config_value(config, "source_context_window_events_default", 2) or 0)
    stats = {"n_events": len(events), "cache_namespace": namespace, "cache_hits": 0, "cache_misses": 0,
             "invalid_cache_entries": 0, "requested_concurrency": width, "backend_execution_mode": "batch",
             "batch_dispatches": 0, "model_requests": 0, "actual_batch_size": 0, "actual_concurrency": 0,
             "concurrency_measurement": "backend_reported_batch_size", "prepared_extractions": 0,
             "failed_preparations": 0, "published": False}
    jobs = []
    for index, event in enumerate(events):
        context = core._context_for_event(events, index, window)
        key = core._extraction_cache_key(event, context, backend, config)
        cached = cache.get(key)
        if cached is not None and _valid_cached(cached, event, context):
            stats["cache_hits"] += 1
            continue
        if cached is not None:
            cache.delete(key)
            stats["invalid_cache_entries"] += 1
        jobs.append((event, context, key, core._extraction_request(event, context, config)))
    stats["cache_misses"] = len(jobs)

    def fail(errors: Sequence[Mapping[str, Any]]) -> None:
        stats.update(failed_preparations=len(errors), prepare_elapsed_s=time.perf_counter() - started)
        raise BatchedExtractionPreparationError(errors, stats)

    for offset in range(0, len(jobs), width):
        group = jobs[offset : offset + width]
        stats["batch_dispatches"] += 1
        stats["model_requests"] += len(group)
        try:
            responses = backend.complete_batch([job[3] for job in group])
            if inspect.isawaitable(responses):
                raise core.ConstructionError("batched extraction requires a synchronous complete_batch adapter")
            if not isinstance(responses, (list, tuple)) or len(responses) != len(group):
                raise core.ConstructionError("batch response count differs from its requested extraction count")
            responses = [ModelResponse.from_any(response) for response in responses]
            for response in responses:
                actual = response.raw.get("batch_size") if isinstance(response.raw, Mapping) else None
                if isinstance(actual, bool) or not isinstance(actual, int) or not 1 <= actual <= len(group):
                    raise core.ConstructionError("backend must report actual batch_size for every response")
            stats["actual_batch_size"] = max(stats["actual_batch_size"], *(response.raw["batch_size"] for response in responses))
            stats["actual_concurrency"] = stats["actual_batch_size"]
        except Exception as exc:
            fail([{"event_id": job[0].event_id, "error": str(exc), "error_type": type(exc).__name__} for job in group])
        errors = []
        for (event, context, key, request), response in zip(group, responses):
            try:
                if response.request_fingerprint and response.request_fingerprint != request.fingerprint:
                    raise core.ConstructionError("batch response fingerprint does not match its requested extraction")
                parsed = core._parse_backend_evidence(event, response, context=context, strict=True)
                if parsed is None or not _valid_cached([item.to_dict() for item in parsed], event, context):
                    raise core.ConstructionError("batch response has invalid evidence/source provenance")
                cache.put(key, [item.to_dict() for item in parsed], metadata={
                    "event_id": event.event_id, "operator": "extract", "preparation": "real_batch",
                    "actual_source_versions": {source.event_id: source.source_revision for source in context}})
                stats["prepared_extractions"] += 1
            except Exception as exc:
                errors.append({"event_id": event.event_id, "error": str(exc), "error_type": type(exc).__name__})
        if errors:
            fail(errors)
    stats["prepare_elapsed_s"] = time.perf_counter() - started
    return stats


__all__ = ["prepare_batched_extractions", "BatchedExtractionPreparationError"]
