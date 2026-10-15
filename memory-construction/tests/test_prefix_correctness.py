"""Regressions identified by the real v4 prefix comparison."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from workflow_memory.backends import ModelResponse
from workflow_memory.cache import make_cache_key
from workflow_memory import construction as core
from workflow_memory.ir import normalize_trajectory, stable_hash


class CurrentEventBackend:
    def __init__(self):
        self.calls = []

    def fingerprint(self):
        return "prefix-contract-v1"

    def complete(self, request):
        self.calls.append(request)
        event = json.loads(request.messages[1]["content"])["event"]
        return ModelResponse(text=json.dumps({"evidence": [{
            "evidence_id": "e1", "source_refs": [event["event_id"]],
            "subject_ref": "agent", "predicate": "action",
            "value": event["action"], "event_kind": "attempt",
        }]}), usage={"prompt_tokens": 10, "completion_tokens": 5})


class PrefixRegressionTests(unittest.TestCase):
    def events(self):
        return normalize_trajectory({"trajectory_id": "t", "steps": [
            {"action": "click", "post_state": {"url": "before"}},
            {"action": "fill", "post_state": {"url": "middle"}},
            {"action": "save", "post_state": {"url": "after"}},
        ]})

    def test_generic_model_ids_do_not_drop_old_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            backend = CurrentEventBackend()
            config = {"storage_path": str(Path(folder) / "ours.sqlite3"), "strict_model_output": True}
            events = self.events()
            prefix = core.build_fresh(events[:1], backend, config)
            result = core.apply_delta(prefix, events[1:], backend, config).snapshot
            self.assertEqual(len(result.evidence), 3)
            self.assertEqual({x for item in result.evidence for x in item.source_refs}, {e.event_id for e in events})
            self.assertEqual(len(backend.calls), 3)

    def test_context_revision_invalidates_dependent_extractions(self):
        with tempfile.TemporaryDirectory() as folder:
            backend = CurrentEventBackend()
            config = {"storage_path": str(Path(folder) / "revised.sqlite3"), "strict_model_output": True}
            events = self.events()
            prefix = core.build_fresh(events, backend, config)
            revision = replace(events[0], action="new-click", source_revision=1, raw_content_hash="")
            result = core.apply_delta(prefix, [revision], backend, config).snapshot
            self.assertEqual(len(backend.calls), 6)
            self.assertEqual(result.events[0].source_revision, 1)
            # A cold, explicitly pinned read must not mix in latest objects.
            old = core._resolve_snapshot(prefix.snapshot_id, config)
            self.assertEqual(old.events[0].source_revision, 0)
            self.assertEqual(old.evidence[0].value, "click")

    def test_cache_key_contains_prompt_and_output_budget(self):
        event = self.events()[0]
        backend = CurrentEventBackend()
        config = {"strict_model_output": True, "extraction_prompt": "one", "extraction_output_tokens": 256}
        first = core._extraction_cache_key(event, [event], backend, config).digest
        self.assertNotEqual(first, core._extraction_cache_key(event, [event], backend, {**config, "extraction_prompt": "two"}).digest)
        self.assertNotEqual(first, core._extraction_cache_key(event, [event], backend, {**config, "extraction_output_tokens": 128}).digest)

    def test_default_cache_identity_is_historical_but_quality_policies_are_versioned(self):
        event, backend = self.events()[0], CurrentEventBackend()
        config = {"strict_model_output": True, "extraction_prompt": "one", "extraction_output_tokens": 256}
        request = core._extraction_request(event, [event], config)
        historical = make_cache_key(
            operator="extract",
            request={"event": event.to_dict(), "context": [event.to_dict()], "model_request": request.to_dict()},
            operator_version="2", prompt_hash=stable_hash(request.messages[0]["content"]),
            model_fingerprint=backend.fingerprint(), read_versions={event.event_id: event.source_revision},
            context_rules={"window": 2, "prefix_only": True, "strict_model_output": True},
            sampling={"temperature": request.temperature, "max_tokens": request.max_tokens},
        )
        self.assertEqual(core._extraction_cache_key(event, [event], backend, config).digest, historical.digest)
        explicit_default = {**config, "model_input_projection": "compact-v2", "source_literal_evidence": False}
        self.assertEqual(core._extraction_cache_key(event, [event], backend, explicit_default).digest, historical.digest)
        for flags in ({"model_input_projection": "salient-v3"}, {"source_literal_evidence": True}):
            key = core._extraction_cache_key(event, [event], backend, {**config, **flags})
            self.assertNotEqual(key.digest, historical.digest)
            self.assertEqual(set(key.context_rules) - set(historical.context_rules),
                             {"model_input_projection", "source_literal_evidence", "source_literal_version"})
            changed = core._extraction_cache_key(event, [event], backend,
                      {**config, **flags, "source_literal_version": "future-literal-version"})
            self.assertNotEqual(changed.digest, key.digest)


if __name__ == "__main__":
    unittest.main()
