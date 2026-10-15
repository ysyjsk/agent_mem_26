"""Conservative prefix recomposition with a method-owned exact-request cache.

This is the narrow B3 construction baseline, not the precise invalidation
method. Every checkpoint rechecks the complete arrived prefix and recomposes
the canonical deterministic views. A trajectory/environment partition is
conservatively invalidated when any of its source records or extraction keys
change, but an invalidated partition does not throw away still-valid model
requests. Only extraction cache misses call the supplied live backend.

Preparation workers never publish. All required evidence must be prepared
successfully before one coordinator calls the existing ``build_fresh`` and its
atomic EventStore publication. The caller must allocate a distinct file-backed
store per B3 window/repeat; no other method's cache or recorded responses are
consulted. There is no replay backend or hidden heuristic substitution here.

``concurrency > 1`` requires an explicit backend capability. The ordinary
local eager Transformers adapter does not declare one and is therefore serial.
Parallel request count is not a claim about GPU kernel overlap; batch mode
records the actual batch size separately.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import inspect
import threading
import time
from typing import Any, Mapping, Sequence

from . import construction as core
from .backends import ModelResponse, backend_fingerprint
from .cache import CacheKey
from .ir import Evidence, SourceEvent, normalize_trajectory


class StrongBaselinePreparationError(core.ConstructionError):
    """Preparation failed; successful cache entries may remain, no new epoch."""

    def __init__(self, errors: Sequence[Mapping[str, Any]], stats: Mapping[str, Any]):
        self.errors = tuple(dict(item) for item in errors)
        self.stats = dict(stats)
        super().__init__("B3 preparation failed without publication: " + "; ".join(
            f"{item['event_id']}: {item['error']}" for item in self.errors
        ))


class _PreparedOnlyBackend:
    """Keep original cache identity and fail if recomposition finds a miss."""

    def __init__(self, backend: Any):
        self.identity = backend_fingerprint(backend)

    def fingerprint(self) -> str:
        return self.identity

    def complete(self, request: Any, **kwargs: Any) -> ModelResponse:
        raise core.ConstructionError("B3 recomposition encountered an unprepared extraction request")


def _execution_mode(backend: Any, concurrency: int) -> str:
    if concurrency == 1:
        return "serial"
    if (getattr(backend, "supports_batch_calls", False) is True
            and callable(getattr(backend, "complete_batch", None))
            and not callable(getattr(backend, "extract_event", None))):
        capacity = int(getattr(backend, "max_batch_size", concurrency))
        if capacity >= concurrency:
            return "batch"
    if (getattr(backend, "supports_parallel_calls", False) is True
            and int(getattr(backend, "max_parallel_calls", concurrency)) >= concurrency):
        return "parallel_calls"
    raise core.ConstructionError(
        f"B3 concurrency={concurrency} requires explicit supports_parallel_calls "
        "with sufficient capacity, or supports_batch_calls and complete_batch(). "
        "The serial local backend must be evaluated at c=1."
    )


def _reported_batch_size(responses: Sequence[Any], dispatched: int) -> int:
    """Use backend execution evidence, never the requested scheduling width."""

    observed: list[int] = []
    for response in responses:
        raw = ModelResponse.from_any(response).raw
        reported = raw.get("batch_size") if isinstance(raw, Mapping) else None
        if isinstance(reported, bool) or not isinstance(reported, int) or not 1 <= reported <= dispatched:
            raise core.ConstructionError("B3 batch backend must report its actual batch_size per response")
        observed.append(reported)
    return max(observed, default=0)


def _cached_output_valid(value: Any, event: SourceEvent, context: Sequence[SourceEvent]) -> bool:
    if not isinstance(value, (list, tuple)):
        return False
    sources = {item.event_id: item for item in context}
    sources[event.event_id] = event
    try:
        for raw in value:
            if not isinstance(raw, Mapping):
                return False
            item = Evidence.from_dict(raw)
            if item.valid_scope != core._scope(event) or not item.source_refs:
                return False
            for ref in item.source_refs:
                source = sources.get(ref)
                if (source is None or core._scope(source) != core._scope(event)
                        or item.source_versions.get(ref) != source.source_revision):
                    return False
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def _partition_changes(events: Sequence[SourceEvent], previous: core.Snapshot | None,
                       misses: Sequence[tuple[SourceEvent, Sequence[SourceEvent], CacheKey]]) -> list[str]:
    if previous is None:
        return sorted({core._scope(item) for item in events})
    before = {item.event_id: item for item in previous.events}
    after = {item.event_id: item for item in events}
    changed: set[str] = set()
    for event_id in set(before) | set(after):
        old, new = before.get(event_id), after.get(event_id)
        if old is None or new is None or old.to_dict() != new.to_dict():
            changed.update(core._scope(item) for item in (old, new) if item is not None)
    # Prompt/model/context policy changes are also partition invalidations.
    changed.update(core._scope(event) for event, _, _ in misses)
    return sorted(changed)


def build_strong_prefix(history: Any, backend: Any, config: Any,
                        previous: core.Snapshot | None = None, concurrency: int = 1
                        ) -> tuple[core.Snapshot, dict[str, Any]]:
    """Prepare legal misses and publish one complete conservative B3 prefix.

    Returns ``(snapshot, stats)``. Failed preparation raises
    :class:`StrongBaselinePreparationError` with retained diagnostics. Cached
    successes from that attempt are reusable but no checkpoint is reported as
    completed. One caller/coordinator owns the store; concurrent checkpoint
    calls sharing that store are intentionally unsupported.
    """

    started = time.perf_counter()
    concurrency = int(concurrency)
    if concurrency < 1:
        raise core.ConstructionError("B3 concurrency must be positive")
    if backend is None:
        raise core.ConstructionError("B3 requires an injected construction backend")
    mode = _execution_mode(backend, concurrency)
    store_path = core._store_path(config)
    if store_path == ":memory:":
        raise core.ConstructionError("B3 requires its own explicit file-backed storage_path")
    if previous is not None and previous.store_path != store_path:
        raise core.ConstructionError("B3 previous snapshot belongs to a different method store")
    events = (list(history) if isinstance(history, (list, tuple))
              and all(isinstance(item, SourceEvent) for item in history)
              else normalize_trajectory(history))
    events.sort(key=core._event_sort_key)
    if len({item.event_id for item in events}) != len(events):
        raise core.ConstructionError("B3 prefix must contain one active revision per event_id")
    cache = core._cache(config)
    window = int(core._config_value(config, "source_context_window_events_default", 2) or 0)
    misses: list[tuple[SourceEvent, Sequence[SourceEvent], CacheKey]] = []
    cached_ids: list[str] = []
    invalid_cache_entries = 0
    for index, event in enumerate(events):
        context = core._context_for_event(events, index, window)
        # Exactly the same prompt/model/read-version/budget identity as Fresh.
        key = core._extraction_cache_key(event, context, backend, config)
        cached = cache.get(key)
        if cached is not None and _cached_output_valid(cached, event, context):
            cached_ids.append(event.event_id)
        else:
            if cached is not None:
                cache.delete(key)  # only this corrupt entry, never valid hits
                invalid_cache_entries += 1
            misses.append((event, context, key))
    invalidated_partitions = _partition_changes(events, previous, misses)
    stats: dict[str, Any] = {
        "method": "B3", "strategy": "conservative_scope_recomposition_with_exact_request_cache",
        "partition_granularity": "trajectory_environment_scope", "n_events": len(events),
        "n_partitions": len({core._scope(item) for item in events}),
        "invalidated_partitions": invalidated_partitions,
        "cache_hits": len(cached_ids), "cache_misses": len(misses),
        "invalid_cache_entries": invalid_cache_entries, "cache_namespace": store_path,
        "requested_concurrency": concurrency, "backend_execution_mode": mode,
        "peak_in_flight_calls": 0, "actual_batch_size": 0, "actual_concurrency": 0,
        "concurrency_measurement": "backend_reported_batch_size" if mode == "batch" else "client_call_in_flight",
        "prepared_extractions": 0, "failed_preparations": 0,
        "reused_nodes": len(cached_ids), "reused_node_kind": "exact_request_extraction",
        "published": False, "previous_snapshot_id": previous.snapshot_id if previous else None,
    }
    errors: list[dict[str, str]] = []
    active = 0
    lock = threading.Lock()

    def prepare(job: tuple[SourceEvent, Sequence[SourceEvent], CacheKey]) -> list[Evidence]:
        nonlocal active
        event, context, _ = job
        with lock:
            active += 1
            stats["peak_in_flight_calls"] = max(stats["peak_in_flight_calls"], active)
        try:
            return core._backend_evidence(event, backend, config, context=context)
        finally:
            with lock:
                active -= 1

    def save(job: tuple[SourceEvent, Sequence[SourceEvent], CacheKey], result: Sequence[Evidence]) -> None:
        event, context, key = job
        rows = [item.to_dict() for item in result]
        if not _cached_output_valid(rows, event, context):
            raise core.ConstructionError("B3 preparation returned evidence with invalid source provenance/scope")
        cache.put(key, rows, metadata={"event_id": event.event_id, "operator": "extract", "method": "B3"})
        stats["prepared_extractions"] += 1

    if mode == "batch":
        for offset in range(0, len(misses), concurrency):
            jobs = misses[offset:offset + concurrency]
            try:
                requests = [core._extraction_request(event, context, config) for event, context, _ in jobs]
                responses = backend.complete_batch(requests)
                if inspect.isawaitable(responses):
                    raise core.ConstructionError("B3 needs a synchronous complete_batch adapter")
                if not isinstance(responses, (list, tuple)) or len(responses) != len(jobs):
                    raise core.ConstructionError("B3 batch response count does not match requests")
                actual_batch_size = _reported_batch_size(responses, len(jobs))
                stats["actual_batch_size"] = max(stats["actual_batch_size"], actual_batch_size)
            except Exception as exc:
                errors.extend({"event_id": job[0].event_id, "error": str(exc)} for job in jobs)
                continue
            for job, response in zip(jobs, responses):
                try:
                    event, context, _ = job
                    parsed = core._parse_backend_evidence(event, response, context=context,
                                                         strict=core._strict_output_enabled(config))
                    if parsed is None:
                        raise core.ConstructionError("B3 batch returned unparseable evidence")
                    save(job, parsed)
                except Exception as exc:
                    errors.append({"event_id": job[0].event_id, "error": str(exc)})
    elif mode == "parallel_calls" and misses:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(prepare, job): job for job in misses}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    save(job, future.result())
                except Exception as exc:
                    errors.append({"event_id": job[0].event_id, "error": str(exc)})
    else:
        for job in misses:
            try:
                save(job, prepare(job))
            except Exception as exc:
                errors.append({"event_id": job[0].event_id, "error": str(exc)})
    stats["prepare_elapsed_s"] = time.perf_counter() - started
    stats["failed_preparations"] = len(errors)
    stats["actual_concurrency"] = (stats["actual_batch_size"] if mode == "batch"
                                   else stats["peak_in_flight_calls"])
    if errors:
        stats["total_s"] = time.perf_counter() - started
        raise StrongBaselinePreparationError(errors, stats)

    publish_started = time.perf_counter()
    snapshot = core.build_fresh(events, model_backend=_PreparedOnlyBackend(backend), config=config)
    stats["recompose_publish_elapsed_s"] = time.perf_counter() - publish_started
    stats["recomposed_nodes"] = len(snapshot.nodes)
    stats["invalidated_nodes"] = sum(
        node.operator == "publish" or any(scope in invalidated_partitions for scope in node.predicate_scopes)
        for node in snapshot.nodes
    )
    stats["published"] = True
    stats["snapshot_id"] = snapshot.snapshot_id
    stats["total_s"] = time.perf_counter() - started
    return snapshot, stats


__all__ = ["build_strong_prefix", "StrongBaselinePreparationError"]
