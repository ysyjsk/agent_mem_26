"""Offline CPU fixtures for the real runner's pinned publication contract."""
from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import tempfile
import unittest

from workflow_memory.backends import EmbeddingResponse
from workflow_memory.config import load_json, write_json
from workflow_memory.construction import apply_delta, build_fresh
from workflow_memory.dense_publication import (
    EMBEDDING_RENDER_FULL_V1,
    EMBEDDING_RENDER_SOURCE_REF_V1,
    EMBEDDING_RENDER_SOURCE_REF_V2,
    publish_dense,
    read_dense,
    render_evidence,
    search_dense,
    validate_dense,
)
from workflow_memory.event_store import EventStore
from workflow_memory.ir import SourceEvent, canonical_json, stable_hash


class FixtureEmbedding:
    """Explicit deterministic test double, never used for experiment metrics."""
    batch_size = 4

    def __init__(self, fingerprint="fixture-v1", *, failure=None, vector=None, token_usage=True):
        self.identity = fingerprint
        self.failure, self.vector, self.token_usage = failure, vector, token_usage
        self.calls = []

    def fingerprint(self):
        return self.identity

    def embed(self, texts):
        self.calls.append(list(texts))
        if self.failure is not None:
            raise self.failure
        vectors = [self.vector if self.vector is not None else
                   ((1.0, 0.0) if int(stable_hash(text)[-1], 16) % 2 else (0.0, 1.0)) for text in texts]
        return EmbeddingResponse(vectors=tuple(vectors), usage={"input_tokens": 7 * len(texts)} if self.token_usage else {})


def event(*, action="east", revision=0):
    return SourceEvent(event_id="dense-test:0", trajectory_id="dense-test", environment_family="web",
                       source_sequence=0, source_revision=revision, action=action,
                       post_state_ref={"status": action}, observed_outcome="ok")


class DensePublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = {"storage_path": str(self.root / "core.sqlite3")}
        self.snapshot = build_fresh([event()], config=self.config)
        self.assertGreater(len(self.snapshot.evidence), 0)

    def test_persisted_publication_reads_same_epoch_and_actual_usage(self):
        backend = FixtureEmbedding()
        descriptor, stats = publish_dense(self.snapshot, backend, self.root / "dense")
        data = read_dense(self.root / "dense" / "published.json", snapshot=self.snapshot)
        self.assertEqual(data["snapshot_id"], self.snapshot.snapshot_id)
        self.assertEqual(data["epoch"], self.snapshot.epoch)
        self.assertEqual(data["evidence_ids"], [item.evidence_id for item in self.snapshot.evidence])
        self.assertEqual(stats["input_tokens"], 7 * stats["new_vectors"])
        self.assertEqual(stats["embedding_calls"], len(backend.calls))
        self.assertTrue(all(len(call) <= 4 for call in backend.calls))
        self.assertEqual(stats["n_texts"], len(self.snapshot.evidence))
        self.assertEqual(stats["reused_vectors"], 0)
        self.assertTrue(stats["dense_valid"])
        self.assertTrue(validate_dense(descriptor)["valid"])
        for field in ("elapsed_s", "embed_elapsed_s", "index_s", "publish_s"):
            self.assertGreaterEqual(stats[field], 0)

    def test_render_versions_preserve_full_compatibility_and_compact_fields(self):
        evidence = self.snapshot.evidence[0]
        self.assertEqual(
            render_evidence(evidence),
            canonical_json(evidence.to_dict()),
        )
        compact_payload = json.loads(render_evidence(evidence, EMBEDDING_RENDER_SOURCE_REF_V1))
        self.assertEqual(
            set(compact_payload),
            {"predicate", "value", "event_kind", "modality", "source_refs"},
        )
        self.assertEqual(compact_payload["source_refs"], list(evidence.source_refs))

    def test_source_ref_v2_keeps_generic_structure_and_pinned_public_step_labels(self):
        evidence = self.snapshot.evidence[0]
        positions = {item.event_id: index + 1 for index, item in enumerate(self.snapshot.events)}
        payload = json.loads(render_evidence(evidence, EMBEDDING_RENDER_SOURCE_REF_V2,
                                             source_positions=positions))
        self.assertEqual(
            set(payload),
            {"predicate", "value", "event_kind", "modality", "source_refs",
             "subject_ref", "source_spans", "source_steps"},
        )
        self.assertEqual(payload["source_steps"], ["source step 1"])
        self.assertEqual(payload["source_refs"], list(evidence.source_refs))
        self.assertEqual(payload["subject_ref"], evidence.subject_ref)
        self.assertEqual(payload["source_spans"], list(evidence.source_spans))
        with self.assertRaisesRegex(ValueError, "source-ref-v2 requires"):
            render_evidence(evidence, EMBEDDING_RENDER_SOURCE_REF_V2)
        structured = replace(evidence, source_spans=({"path": "post_state.accessibility_tree[7]",
                                                       "line": 7, "focused": True, "raw": "drop-me"},))
        structured_payload = json.loads(render_evidence(
            structured, EMBEDDING_RENDER_SOURCE_REF_V2, source_positions=positions))
        self.assertEqual(structured_payload["source_spans"], [{"focused": True, "line": 7,
                                                               "path": "post_state.accessibility_tree[7]"}])

    def test_compact_publication_is_versioned_readable_and_keeps_all_evidence(self):
        backend = FixtureEmbedding()
        descriptor, stats = publish_dense(
            self.snapshot,
            backend,
            self.root / "compact",
            render_version=EMBEDDING_RENDER_SOURCE_REF_V1,
        )
        data = load_json(descriptor["index_path"])
        self.assertEqual(descriptor["render_version"], EMBEDDING_RENDER_SOURCE_REF_V1)
        self.assertEqual(data["render_version"], EMBEDDING_RENDER_SOURCE_REF_V1)
        self.assertEqual(len(data["evidence_ids"]), len(self.snapshot.evidence))
        self.assertEqual(stats["n_texts"], len(self.snapshot.evidence))
        self.assertTrue(read_dense(descriptor, snapshot=self.snapshot)["vectors"])
        self.assertTrue(validate_dense(descriptor, snapshot=self.snapshot)["valid"])
        self.assertTrue(all(text != EMBEDDING_RENDER_SOURCE_REF_V1 for call in backend.calls for text in call))
        self.assertEqual(
            backend.calls[0][0],
            render_evidence(self.snapshot.evidence[0], EMBEDDING_RENDER_SOURCE_REF_V1),
        )

    def test_source_ref_v2_publication_is_readable_and_cache_is_version_isolated(self):
        cache, backend = {}, FixtureEmbedding()
        descriptor, stats = publish_dense(
            self.snapshot,
            backend,
            self.root / "hybrid",
            cache,
            render_version=EMBEDDING_RENDER_SOURCE_REF_V2,
        )
        self.assertEqual(descriptor["render_version"], EMBEDDING_RENDER_SOURCE_REF_V2)
        self.assertEqual(stats["new_vectors"], len(self.snapshot.evidence))
        data = read_dense(descriptor, snapshot=self.snapshot)
        self.assertEqual(data["render_version"], EMBEDDING_RENDER_SOURCE_REF_V2)
        self.assertEqual(len(data["vectors"]), len(self.snapshot.evidence))
        self.assertTrue(validate_dense(descriptor, snapshot=self.snapshot)["valid"])
        compact_text = render_evidence(self.snapshot.evidence[0], EMBEDDING_RENDER_SOURCE_REF_V2,
                                       source_positions={event.event_id: index + 1
                                                         for index, event in enumerate(self.snapshot.events)})
        self.assertEqual(backend.calls[0][0], compact_text)
        _, v1_stats = publish_dense(
            self.snapshot,
            backend,
            self.root / "source-ref-v1",
            cache,
            render_version=EMBEDDING_RENDER_SOURCE_REF_V1,
        )
        self.assertEqual(v1_stats["new_vectors"], len(self.snapshot.evidence))

    def test_render_version_isolated_cache_and_descriptor_index_mismatch_is_rejected(self):
        cache, backend = {}, FixtureEmbedding()
        full, full_stats = publish_dense(self.snapshot, backend, self.root / "full", cache)
        compact, compact_stats = publish_dense(
            self.snapshot,
            backend,
            self.root / "compact",
            cache,
            render_version=EMBEDDING_RENDER_SOURCE_REF_V1,
        )
        self.assertEqual(full["render_version"], EMBEDDING_RENDER_FULL_V1)
        self.assertEqual(compact["render_version"], EMBEDDING_RENDER_SOURCE_REF_V1)
        self.assertEqual(full_stats["new_vectors"], len(self.snapshot.evidence))
        self.assertEqual(compact_stats["new_vectors"], len(self.snapshot.evidence))
        self.assertEqual(compact_stats["reused_vectors"], 0)
        self.assertEqual(len(backend.calls), 2 * math.ceil(len(self.snapshot.evidence) / backend.batch_size))

        mismatched = dict(compact)
        mismatched["render_version"] = EMBEDDING_RENDER_FULL_V1
        with self.assertRaisesRegex(ValueError, "render version mismatch"):
            read_dense(mismatched)

    def test_legacy_full_index_without_render_version_remains_readable(self):
        descriptor, _ = publish_dense(self.snapshot, FixtureEmbedding(), self.root / "legacy")
        data = load_json(descriptor["index_path"])
        data.pop("render_version")
        write_json(descriptor["index_path"], data)
        legacy_descriptor = dict(descriptor)
        legacy_descriptor.pop("render_version")
        legacy_descriptor["data_hash"] = stable_hash(data)
        loaded = read_dense(legacy_descriptor, snapshot=self.snapshot)
        self.assertEqual(loaded["evidence_ids"], [item.evidence_id for item in self.snapshot.evidence])
        self.assertTrue(validate_dense(legacy_descriptor, snapshot=self.snapshot)["valid"])

    def test_compact_index_rejects_a_snapshot_from_a_different_epoch(self):
        descriptor, _ = publish_dense(
            self.snapshot,
            FixtureEmbedding(),
            self.root / "compact",
            render_version=EMBEDDING_RENDER_SOURCE_REF_V1,
        )
        revised = apply_delta(self.snapshot, [event(action="west", revision=1)], config=self.config).snapshot
        with self.assertRaisesRegex(ValueError, "supplied checkpoint snapshot"):
            read_dense(descriptor, snapshot=revised)

    def test_exact_method_owned_cache_reuses_but_backend_identity_invalidates(self):
        cache, backend = {}, FixtureEmbedding()
        first, _ = publish_dense(self.snapshot, backend, self.root / "dense", cache)
        count = len(backend.calls)
        second, stats = publish_dense(self.snapshot, backend, self.root / "dense", cache)
        self.assertEqual(first["data_hash"], second["data_hash"])
        self.assertEqual(len(backend.calls), count)
        self.assertEqual(stats["embedding_calls"], 0)
        self.assertEqual(stats["input_tokens"], 0)
        self.assertEqual(stats["reused_vectors"], len(self.snapshot.evidence))
        changed = FixtureEmbedding("fixture-v2")
        _, changed_stats = publish_dense(self.snapshot, changed, self.root / "other-model", cache)
        self.assertEqual(changed_stats["new_vectors"], len(self.snapshot.evidence))
        separate_method = FixtureEmbedding()
        _, separate_stats = publish_dense(self.snapshot, separate_method, self.root / "other-method", {})
        self.assertEqual(separate_stats["new_vectors"], len(self.snapshot.evidence))

    def test_content_revision_invalidates_cache_and_old_pinned_epoch_stays_readable(self):
        cache, backend = {}, FixtureEmbedding()
        first, _ = publish_dense(self.snapshot, backend, self.root / "dense", cache)
        revised = apply_delta(self.snapshot, [event(action="west", revision=1)], config=self.config).snapshot
        second, stats = publish_dense(revised, backend, self.root / "dense", cache)
        self.assertGreater(stats["new_vectors"], 0)
        self.assertNotEqual(first["data_hash"], second["data_hash"])
        self.assertEqual(read_dense(first)["epoch"], self.snapshot.epoch)
        self.assertEqual(read_dense(second)["epoch"], revised.epoch)
        self.assertFalse(validate_dense(first, snapshot=revised)["valid"])

    def test_model_input_settings_invalidate_the_exact_content_cache(self):
        for field, before, after in (("dtype", "bfloat16", "float32"), ("max_length", 1024, 2048),
                                     ("batch_size", 4, 2)):
            with self.subTest(field=field):
                backend, cache = FixtureEmbedding(), {}
                setattr(backend, field, before)
                first, _ = publish_dense(self.snapshot, backend, self.root / f"{field}-first", cache)
                setattr(backend, field, after)
                second, stats = publish_dense(self.snapshot, backend, self.root / f"{field}-second", cache)
                self.assertNotEqual(first["model_settings_hash"], second["model_settings_hash"])
                self.assertEqual(stats["new_vectors"], len(self.snapshot.evidence))

    def test_failed_embedding_never_publishes_or_updates_cache(self):
        cache, backend = {}, FixtureEmbedding(failure=RuntimeError("fixture embedding unavailable"))
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            publish_dense(self.snapshot, backend, self.root / "failed", cache)
        self.assertFalse((self.root / "failed" / "published.json").exists())
        self.assertEqual(cache, {})
        existing, _ = publish_dense(self.snapshot, FixtureEmbedding(), self.root / "dense")
        revised = apply_delta(self.snapshot, [event(action="west", revision=1)], config=self.config).snapshot
        with self.assertRaises(RuntimeError):
            publish_dense(revised, backend, self.root / "dense", cache)
        self.assertEqual(load_json(self.root / "dense" / "published.json"), existing)

    def test_invalid_vectors_and_corrupt_cache_cannot_be_published(self):
        for vector in ((math.nan, 1.0), (math.inf, 1.0), (0.0, 0.0), ()):
            with self.subTest(vector=vector):
                with self.assertRaises(ValueError):
                    publish_dense(self.snapshot, FixtureEmbedding(vector=vector), self.root / "invalid")
                self.assertFalse((self.root / "invalid" / "published.json").exists())
        cache = {}
        backend = FixtureEmbedding()
        publish_dense(self.snapshot, backend, self.root / "valid", cache)
        cache[next(iter(cache))] = (math.nan, 0.0)
        with self.assertRaises(ValueError):
            publish_dense(self.snapshot, backend, self.root / "corrupt-cache", cache)
        self.assertFalse((self.root / "corrupt-cache" / "published.json").exists())

    def test_index_content_hash_and_core_payload_are_both_checked(self):
        descriptor, _ = publish_dense(self.snapshot, FixtureEmbedding(), self.root / "dense")
        data = load_json(descriptor["index_path"])
        data["vectors"][0] = [0.5, 0.5]
        write_json(descriptor["index_path"], data)
        self.assertIn("content hash", validate_dense(descriptor)["errors"][0])
        descriptor, _ = publish_dense(self.snapshot, FixtureEmbedding(), self.root / "untampered")
        mutated = replace(self.snapshot, metadata={**self.snapshot.metadata, "tampered": True})
        store = EventStore(self.config["storage_path"])
        try:
            store.commit_snapshot(mutated, events=mutated.events, evidence=mutated.evidence, nodes=mutated.nodes)
        finally:
            store.close()
        self.assertIn("core snapshot payload", validate_dense(descriptor)["errors"][0])

    def test_cosine_search_uses_the_persisted_vectors_and_pinned_epoch(self):
        descriptor, _ = publish_dense(self.snapshot, FixtureEmbedding(), self.root / "dense")
        data = read_dense(descriptor)
        query = [2 * value for value in data["vectors"][0]]
        hits = search_dense(descriptor, query, top_k=2)
        self.assertGreater(len(hits), 0)
        self.assertAlmostEqual(hits[0]["score"], 1.0)
        self.assertEqual(hits[0]["snapshot_id"], self.snapshot.snapshot_id)
        self.assertEqual(hits[0]["epoch"], self.snapshot.epoch)
        self.assertEqual(search_dense(descriptor, query, top_k=0), [])
        with self.assertRaisesRegex(ValueError, "dimension"):
            search_dense(descriptor, [1.0, 0.0, 0.0])

    def test_unavailable_token_usage_remains_null_not_character_estimate(self):
        _, stats = publish_dense(self.snapshot, FixtureEmbedding(token_usage=False), self.root / "dense")
        self.assertIsNone(stats["input_tokens"])
        self.assertIn("no token usage", stats["input_tokens_reason"])


if __name__ == "__main__":
    unittest.main()
