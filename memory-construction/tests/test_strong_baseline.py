"""CPU contracts for legitimate retained-cache conservative B3 execution."""

from dataclasses import replace
import json
from pathlib import Path
import threading

import pytest

from workflow_memory import build_fresh, normalize_trajectory, validate_snapshot
from workflow_memory.backends import ModelResponse
from workflow_memory.construction import ConstructionError
from workflow_memory.event_store import EventStore
from workflow_memory.strong_baseline import StrongBaselinePreparationError, build_strong_prefix


class CountingBackend:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_ids: set[str] = set()

    def fingerprint(self) -> str:
        return "cpu-b3-contract/1"

    def complete(self, request) -> ModelResponse:
        event_id = request.metadata["event_id"]
        self.calls.append(event_id)
        if event_id in self.fail_ids:
            raise RuntimeError("test preparation failure")
        # Depend on every visible input, so changing a prefix context can
        # change the output even when the current SourceEvent is unchanged.
        output = {
            "predicate": "observed_property", "subject_ref": "page",
            "value": json.loads(request.messages[-1]["content"]),
            "event_kind": "observation", "source_refs": [event_id],
        }
        return ModelResponse(text=json.dumps({"evidence": [output]}), raw={"device": "cpu"})


def events(trajectory: str = "t", n: int = 4):
    return normalize_trajectory({
        "trajectory_id": trajectory, "environment_family": "web",
        "steps": [{"source_sequence": i, "arrival_sequence": i,
                   "action": f"click-{i}", "post_state": {"url": f"page-{i}"}}
                  for i in range(n)],
    })


def config(path: Path, **overrides):
    return {"storage_path": str(path), "strict_model_output": True,
            "source_context_window_events_default": 2,
            "extraction_output_tokens": 256, "model_input_char_budget": 6000,
            **overrides}


def semantic(snapshot):
    return {
        "events": [item.to_dict() for item in snapshot.events],
        "evidence": [item.to_dict() for item in snapshot.evidence],
        "state": snapshot.state_view, "workflow": snapshot.workflow_view,
        "relations": snapshot.relations, "aliases": snapshot.aliases,
        "index": snapshot.index,
    }


def test_b3_retains_valid_cache_and_matches_fresh(tmp_path: Path):
    backend = CountingBackend()
    prefix = events()
    settings = config(tmp_path / "b3.sqlite3")
    first, first_stats = build_strong_prefix(prefix[:2], backend, settings)
    assert backend.calls == ["t:0", "t:1"]
    assert first_stats["cache_hits"] == 0
    second, stats = build_strong_prefix(prefix, backend, settings, previous=first)
    assert backend.calls == ["t:0", "t:1", "t:2", "t:3"]
    assert stats["cache_hits"] == 2
    assert stats["cache_misses"] == 2
    assert stats["invalidated_partitions"] == ["t/trajectory"]
    assert stats["published"] and validate_snapshot(second).valid
    reference = build_fresh(prefix, model_backend=CountingBackend(),
                            config=config(tmp_path / "fresh.sqlite3"))
    assert semantic(second) == semantic(reference)
    assert second.store_path != reference.store_path


def test_b3_rechecks_revision_and_unchanged_dependent_context(tmp_path: Path):
    prefix = events(n=4)
    backend = CountingBackend()
    settings = config(tmp_path / "b3.sqlite3", source_context_window_events_default=1)
    old, _ = build_strong_prefix(prefix, backend, settings)
    changed = [replace(prefix[0], source_revision=1, action="revised", raw_content_hash=""), *prefix[1:]]
    updated, stats = build_strong_prefix(changed, backend, settings, previous=old)
    # Event t:1 has not changed, but it reads the revised t:0 context.
    assert backend.calls == ["t:0", "t:1", "t:2", "t:3", "t:0", "t:1"]
    assert stats["cache_hits"] == 2 and stats["cache_misses"] == 2
    reference = build_fresh(changed, model_backend=CountingBackend(),
                            config=config(tmp_path / "fresh.sqlite3", source_context_window_events_default=1))
    assert semantic(updated) == semantic(reference)
    with EventStore(settings["storage_path"]) as store:
        archived = list(store.iter_source_event_revisions("t:0"))
        assert archived[0]["source_revision"] == 0


def test_b3_context_policy_and_budget_changes_are_real_misses(tmp_path: Path):
    prefix = events(n=3)
    backend = CountingBackend()
    path = tmp_path / "b3.sqlite3"
    first, _ = build_strong_prefix(prefix, backend, config(path, source_context_window_events_default=0))
    second, stats = build_strong_prefix(prefix, backend, config(path, source_context_window_events_default=1), previous=first)
    assert stats["cache_misses"] >= 2
    assert backend.calls.count("t:1") == 2 and backend.calls.count("t:2") == 2
    _, budget_stats = build_strong_prefix(prefix, backend,
                                          config(path, source_context_window_events_default=1,
                                                 extraction_output_tokens=128), previous=second)
    assert budget_stats["cache_misses"] == len(prefix)


def test_b3_same_revision_changed_content_invalidates_request(tmp_path: Path):
    prefix = events(n=2)
    backend = CountingBackend()
    settings = config(tmp_path / "b3.sqlite3", source_context_window_events_default=0)
    first, _ = build_strong_prefix(prefix, backend, settings)
    changed = [replace(prefix[0], action="changed without revision", raw_content_hash=""), prefix[1]]
    _, stats = build_strong_prefix(changed, backend, settings, previous=first)
    assert stats["cache_misses"] == 1
    assert backend.calls == ["t:0", "t:1", "t:0"]


def test_b3_inserted_source_changes_later_prefix_context(tmp_path: Path):
    prefix = events(n=3)
    backend = CountingBackend()
    settings = config(tmp_path / "b3.sqlite3")
    first, _ = build_strong_prefix([prefix[0], prefix[2]], backend, settings)
    second, stats = build_strong_prefix(prefix, backend, settings, previous=first)
    assert stats["cache_hits"] == 1 and stats["cache_misses"] == 2
    assert backend.calls == ["t:0", "t:2", "t:1", "t:2"]
    reference = build_fresh(prefix, model_backend=CountingBackend(),
                            config=config(tmp_path / "fresh.sqlite3"))
    assert semantic(second) == semantic(reference)


def test_b3_unrelated_partition_keeps_legal_requests(tmp_path: Path):
    prefix = events("a", n=2) + events("b", n=2)
    backend = CountingBackend()
    settings = config(tmp_path / "b3.sqlite3")
    first, _ = build_strong_prefix(prefix, backend, settings)
    _, stats = build_strong_prefix(events("a", n=3) + events("b", n=2), backend,
                                    settings, previous=first)
    assert stats["invalidated_partitions"] == ["a/trajectory"]
    assert stats["cache_hits"] == 4 and stats["cache_misses"] == 1
    assert backend.calls.count("b:0") == 1 and backend.calls.count("b:1") == 1


def test_b3_failed_preparation_does_not_publish_and_keeps_valid_successes(tmp_path: Path):
    prefix = events(n=4)
    backend = CountingBackend()
    settings = config(tmp_path / "b3.sqlite3")
    first, _ = build_strong_prefix(prefix[:2], backend, settings)
    backend.fail_ids = {"t:2"}
    with pytest.raises(StrongBaselinePreparationError) as failure:
        build_strong_prefix(prefix, backend, settings, previous=first)
    assert failure.value.stats["published"] is False
    assert failure.value.stats["failed_preparations"] == 1
    with EventStore(settings["storage_path"]) as store:
        assert store.latest_snapshot()["snapshot_id"] == first.snapshot_id
        assert len(list(store.iter_snapshots())) == 1
    backend.fail_ids.clear()
    second, stats = build_strong_prefix(prefix, backend, settings, previous=first)
    assert stats["cache_hits"] == 3 and stats["cache_misses"] == 1
    assert backend.calls.count("t:3") == 1
    assert backend.calls.count("t:2") == 2
    assert second.epoch == first.epoch + 1


def test_b3_parallel_requires_capability_and_counts_actual_calls(tmp_path: Path):
    serial = CountingBackend()
    settings = config(tmp_path / "serial.sqlite3")
    with pytest.raises(ConstructionError, match="requires explicit"):
        build_strong_prefix(events(n=2), serial, settings, concurrency=2)
    assert serial.calls == []
    assert not (tmp_path / "serial.sqlite3").exists()

    class ParallelBackend(CountingBackend):
        supports_parallel_calls = True
        max_parallel_calls = 2

        def __init__(self):
            super().__init__()
            self.barrier = threading.Barrier(2, timeout=5)
            self.lock = threading.Lock()
            self.active = 0
            self.peak = 0

        def complete(self, request):
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            try:
                self.barrier.wait()
                return super().complete(request)
            finally:
                with self.lock:
                    self.active -= 1

    parallel = ParallelBackend()
    snapshot, stats = build_strong_prefix(events(n=4), parallel,
                                          config(tmp_path / "parallel.sqlite3"), concurrency=2)
    assert validate_snapshot(snapshot).valid
    assert parallel.peak == 2
    assert stats["peak_in_flight_calls"] == 2
    assert stats["actual_concurrency"] == 2
    assert len(parallel.calls) == 4


def test_b3_batch_support_is_real_and_preserves_per_request_output(tmp_path: Path):
    class BatchBackend(CountingBackend):
        supports_batch_calls = True
        max_batch_size = 2

        def __init__(self):
            super().__init__()
            self.batch_sizes = []

        def complete_batch(self, requests):
            self.batch_sizes.append(len(requests))
            return [replace(super(BatchBackend, self).complete(request),
                            raw={"device": "cpu", "batch_size": len(requests)})
                    for request in requests]

    backend = BatchBackend()
    snapshot, stats = build_strong_prefix(events(n=3), backend,
                                          config(tmp_path / "batch.sqlite3"), concurrency=2)
    assert backend.batch_sizes == [2, 1]
    assert stats["backend_execution_mode"] == "batch"
    assert stats["actual_batch_size"] == 2
    assert stats["concurrency_measurement"] == "backend_reported_batch_size"
    assert len(snapshot.evidence) == 3
    reference = build_fresh(events(n=3), model_backend=CountingBackend(),
                            config=config(tmp_path / "fresh.sqlite3"))
    assert semantic(snapshot) == semantic(reference)


def test_b3_does_not_infer_actual_batch_width_from_requested_concurrency(tmp_path: Path):
    class SerialBatchBackend(CountingBackend):
        supports_batch_calls = True
        max_batch_size = 2

        def complete_batch(self, requests):
            return [replace(super(SerialBatchBackend, self).complete(request),
                            raw={"device": "cpu", "batch_size": 1})
                    for request in requests]

    snapshot, stats = build_strong_prefix(events(n=2), SerialBatchBackend(),
                                          config(tmp_path / "serial-batch.sqlite3"), concurrency=2)
    assert validate_snapshot(snapshot).valid
    assert stats["requested_concurrency"] == 2
    assert stats["actual_batch_size"] == 1 and stats["actual_concurrency"] == 1


def test_b3_store_scope_and_duplicate_identity_guards(tmp_path: Path):
    backend = CountingBackend()
    with pytest.raises(ConstructionError, match="file-backed"):
        build_strong_prefix(events(n=1), backend, {})
    first, _ = build_strong_prefix(events(n=1), backend, config(tmp_path / "own.sqlite3"))
    with pytest.raises(ConstructionError, match="different method store"):
        build_strong_prefix(events(n=2), backend, config(tmp_path / "other.sqlite3"), previous=first)
    with pytest.raises(ConstructionError, match="one active revision"):
        build_strong_prefix([first.events[0], first.events[0]], backend,
                            config(tmp_path / "own.sqlite3"), previous=first)
