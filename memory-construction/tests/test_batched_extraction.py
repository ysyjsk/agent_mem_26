"""CPU-only exact-cache preparation tests; fixtures are not live measurements."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from workflow_memory import construction as core
from workflow_memory.backends import ModelResponse
from workflow_memory.batched_extraction import BatchedExtractionPreparationError, prepare_batched_extractions
from workflow_memory.event_store import EventStore
from workflow_memory.ir import normalize_trajectory


class FixtureBatchBackend:
    supports_batch_calls = True
    max_batch_size = 2

    def __init__(self):
        self.batches, self.requests = [], []
        self.fail_batch = None
        self.invalid_ids = set()
        self.actual_width = None
        self.bad_count = False
        self.bad_fingerprint = False
        self.missing_width = False

    def fingerprint(self):
        return "offline-batch-contract-v1"

    def complete(self, request):
        raise AssertionError("prepared cache must prevent serial model calls")

    def complete_batch(self, requests):
        self.batches.append(list(requests))
        self.requests.extend(requests)
        if self.fail_batch == len(self.batches):
            raise RuntimeError("fixture batch failure")
        responses = []
        for request in requests:
            current = json.loads(request.messages[1]["content"])["event"]
            evidence = {"source_refs": [current["event_id"]], "predicate": "action", "event_kind": "attempt",
                        "value": current["action"], "subject_ref": "agent"}
            text = "invalid JSON" if current["event_id"] in self.invalid_ids else json.dumps({"evidence": [evidence]})
            responses.append(ModelResponse(text=text, finish_reason="stop",
                                           usage={"prompt_tokens": 10, "completion_tokens": 5},
                                           raw={} if self.missing_width else {
                                               "batch_size": len(requests) if self.actual_width is None else self.actual_width},
                                           request_fingerprint="wrong" if self.bad_fingerprint else request.fingerprint))
        return responses[:-1] if self.bad_count else responses


def events(n=5):
    return normalize_trajectory({"trajectory_id": "t", "environment_family": "web", "steps": [
        {"source_sequence": index, "action": f"action-{index}", "post_state": {"url": f"page-{index}"}}
        for index in range(n)]})


class BatchedExtractionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = {"storage_path": str(self.root / "ours.sqlite3"), "strict_model_output": True,
                       "source_context_window_events_default": 2, "extraction_output_tokens": 256}
        self.events, self.backend = events(), FixtureBatchBackend()

    def test_sorted_prefix_append_has_exact_core_keys_and_no_serial_model_calls(self):
        stats = prepare_batched_extractions(list(reversed(self.events[:2])), self.backend, self.config)
        self.assertEqual([request.metadata["event_id"] for request in self.backend.requests], ["t:0", "t:1"])
        self.assertEqual(stats["batch_dispatches"], 1)
        self.assertEqual(stats["model_requests"], 2)
        self.assertEqual(stats["actual_concurrency"], 2)
        self.assertFalse(stats["published"])
        self.assertFalse(Path(self.config["storage_path"]).exists())
        snapshot = core.build_fresh(self.events[:2], self.backend, self.config)
        stats = prepare_batched_extractions(self.events[:3], self.backend, self.config)
        self.assertEqual(stats["cache_hits"], 2)
        self.assertEqual(stats["cache_misses"], 1)
        self.assertEqual(stats["actual_concurrency"], 1)
        updated = core.apply_delta(snapshot, self.events[2:3], self.backend, self.config).snapshot
        self.assertEqual(len(updated.evidence), 3)
        self.assertTrue(core.validate_snapshot(updated).valid)
        self.assertEqual([len(batch) for batch in self.backend.batches], [2, 1])
        cached = core._cache(self.config)
        for index, source in enumerate(self.events[:3]):
            context = core._context_for_event(self.events[:3], index, 2)
            rows = cached.get(core._extraction_cache_key(source, context, self.backend, self.config))
            self.assertEqual(rows[0]["source_versions"], {source.event_id: source.source_revision})

    def test_context_revision_invalidates_only_real_dependent_requests(self):
        config = {**self.config, "source_context_window_events_default": 1}
        prepare_batched_extractions(self.events, self.backend, config)
        revised = [replace(self.events[0], source_revision=1, action="revised", raw_content_hash=""), *self.events[1:]]
        stats = prepare_batched_extractions(revised, self.backend, config)
        self.assertEqual(stats["cache_hits"], 3)
        self.assertEqual(stats["cache_misses"], 2)
        self.assertEqual([request.metadata["event_id"] for request in self.backend.requests][-2:], ["t:0", "t:1"])
        context = core._context_for_event(revised, 0, 1)
        row = core._cache(config).get(core._extraction_cache_key(revised[0], context, self.backend, config))[0]
        self.assertEqual(row["source_versions"], {"t:0": 1})

    def test_prompt_and_output_budget_are_not_free_cache_reuse(self):
        prefix = self.events[:2]
        prepare_batched_extractions(prefix, self.backend, self.config)
        changed_prompt = {**self.config, "extraction_prompt": "Return the strict evidence JSON schema."}
        stats = prepare_batched_extractions(prefix, self.backend, changed_prompt)
        self.assertEqual(stats["cache_misses"], 2)
        stats = prepare_batched_extractions(prefix, self.backend, {**changed_prompt, "extraction_output_tokens": 128})
        self.assertEqual(stats["cache_misses"], 2)
        self.assertEqual([request.max_tokens for request in self.backend.batches[-1]], [128, 128])

    def test_inserted_source_changes_visible_context_without_future_leak(self):
        prepare_batched_extractions([self.events[0], self.events[2]], self.backend, self.config)
        stats = prepare_batched_extractions(self.events[:3], self.backend, self.config)
        self.assertEqual(stats["cache_hits"], 1)
        self.assertEqual(stats["cache_misses"], 2)
        for request in self.backend.requests:
            payload = json.loads(request.messages[1]["content"])
            sequence = payload["event"]["source_sequence"]
            self.assertTrue(all(source["source_sequence"] < sequence for source in payload["context"]))

    def test_later_batch_failure_keeps_previous_valid_cache_without_snapshot(self):
        self.backend.fail_batch = 2
        with self.assertRaises(BatchedExtractionPreparationError) as failure:
            prepare_batched_extractions(self.events, self.backend, self.config)
        self.assertEqual(failure.exception.stats["prepared_extractions"], 2)
        self.assertEqual(failure.exception.stats["failed_preparations"], 2)
        self.assertFalse(failure.exception.stats["published"])
        self.assertEqual(len(core._cache(self.config)), 2)
        self.assertFalse(Path(self.config["storage_path"]).exists())
        self.backend.fail_batch = None
        stats = prepare_batched_extractions(self.events, self.backend, self.config)
        self.assertEqual(stats["cache_hits"], 2)
        self.assertEqual(stats["cache_misses"], 3)
        self.assertEqual([len(batch) for batch in self.backend.batches][-2:], [2, 1])

    def test_failed_preparation_cannot_move_existing_published_epoch(self):
        prepare_batched_extractions(self.events[:2], self.backend, self.config)
        snapshot = core.build_fresh(self.events[:2], self.backend, self.config)
        self.backend.fail_batch = 2
        with self.assertRaises(core.ConstructionError):
            prepare_batched_extractions(self.events, self.backend, self.config)
        store = EventStore(self.config["storage_path"])
        try:
            self.assertEqual(store.latest_snapshot()["snapshot_id"], snapshot.snapshot_id)
            self.assertEqual(len(list(store.iter_snapshots())), 1)
        finally:
            store.close()

    def test_strict_parse_failure_keeps_valid_peer_without_heuristic(self):
        self.backend.invalid_ids = {"t:1"}
        with self.assertRaises(BatchedExtractionPreparationError) as failure:
            prepare_batched_extractions(self.events[:2], self.backend, self.config)
        self.assertEqual(failure.exception.stats["prepared_extractions"], 1)
        self.assertEqual(failure.exception.errors[0]["event_id"], "t:1")
        self.assertEqual(len(core._cache(self.config)), 1)
        self.assertFalse(Path(self.config["storage_path"]).exists())

    def test_invalid_source_versions_in_cache_are_recomputed_not_reused(self):
        prepare_batched_extractions(self.events[:2], self.backend, self.config)
        cache = core._cache(self.config)
        context = core._context_for_event(self.events[:2], 0, 2)
        key = core._extraction_cache_key(self.events[0], context, self.backend, self.config)
        rows = cache.get(key)
        rows[0]["source_versions"]["t:0"] = 999
        cache.put(key, rows)
        stats = prepare_batched_extractions(self.events[:2], self.backend, self.config)
        self.assertEqual(stats["invalid_cache_entries"], 1)
        self.assertEqual(stats["cache_hits"], 1)
        self.assertEqual(stats["cache_misses"], 1)

    def test_backend_response_evidence_defines_actual_not_requested_concurrency(self):
        self.backend.actual_width = 1
        stats = prepare_batched_extractions(self.events[:3], self.backend, self.config)
        self.assertEqual(stats["requested_concurrency"], 2)
        self.assertEqual(stats["actual_batch_size"], 1)
        self.assertEqual(stats["actual_concurrency"], 1)
        self.assertEqual(stats["concurrency_measurement"], "backend_reported_batch_size")

    def test_bad_response_count_metadata_or_fingerprint_never_publish(self):
        for field in ("bad_count", "missing_width", "bad_fingerprint"):
            with self.subTest(field=field):
                backend = FixtureBatchBackend()
                setattr(backend, field, True)
                config = {**self.config, "storage_path": str(self.root / f"{field}.sqlite3")}
                with self.assertRaises(BatchedExtractionPreparationError):
                    prepare_batched_extractions(self.events[:2], backend, config)
                self.assertEqual(len(core._cache(config)), 0)
                self.assertFalse(Path(config["storage_path"]).exists())

    def test_capability_width_namespace_and_duplicate_identity_guards(self):
        self.backend.supports_batch_calls = False
        with self.assertRaisesRegex(core.ConstructionError, "capability"):
            prepare_batched_extractions(self.events[:2], self.backend, self.config)
        self.backend.supports_batch_calls = True
        for width in (0, 3):
            with self.assertRaisesRegex(core.ConstructionError, "bounded"):
                prepare_batched_extractions(self.events[:2], self.backend, self.config, width)
        with self.assertRaisesRegex(core.ConstructionError, "method-owned"):
            prepare_batched_extractions(self.events[:2], self.backend, {"storage_path": ":memory:"})
        with self.assertRaisesRegex(core.ConstructionError, "one active revision"):
            prepare_batched_extractions([self.events[0], self.events[0]], self.backend, self.config)
        self.assertEqual(self.backend.requests, [])


if __name__ == "__main__":
    unittest.main()
