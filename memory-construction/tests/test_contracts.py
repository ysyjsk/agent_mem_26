from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workflow_memory.backends import ModelResponse
from workflow_memory.construction import ConstructionError, _model_event_payload
from workflow_memory import (
    DeterministicReplayBackend,
    ReplayMissError,
    apply_delta,
    build_fresh,
    normalize_trajectory,
    plan_graph,
    query,
    validate_snapshot,
)


class WorkflowMemoryContractTests(unittest.TestCase):
    def test_normalize_prefix_and_failure_semantics(self) -> None:
        events = normalize_trajectory(
            {
                "trajectory_id": "episode-1",
                "environment_family": "web",
                "environment_instance_id": "browser-1",
                "states": [{"page": "a"}, {"page": "b"}],
                "actions": ["click"],
                "future_label": "must-not-be-an-outcome",
            }
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].pre_state_ref, {"page": "a"})
        self.assertEqual(events[0].post_state_ref, {"page": "b"})
        self.assertIsNone(events[0].observed_outcome)
        self.assertEqual(len(events[0].raw_content_hash), 64)

    def test_fresh_incremental_query_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = {"storage_path": str(Path(directory) / "memory.sqlite3")}
            events = normalize_trajectory(
                {
                    "trajectory_id": "t",
                    "environment_family": "web",
                    "steps": [
                        {"source_sequence": 0, "action": "open", "post_state": {"url": "a"}},
                        {"source_sequence": 1, "action": "save", "outcome": "failed"},
                    ],
                }
            )
            prefix = build_fresh(events[:1], config=config)
            receipt = apply_delta(prefix, events[1:], config=config)
            self.assertTrue(receipt.accepted and receipt.prepared and receipt.committed and receipt.queryable)
            self.assertIsNotNone(receipt.snapshot_id)
            self.assertTrue(validate_snapshot(receipt.snapshot_id, config=config).valid)
            bundle = query(receipt.snapshot_id, "url", 4)
            self.assertTrue(bundle.evidence)

    def test_graph_does_not_connect_trajectory_scopes(self) -> None:
        events = normalize_trajectory(
            [
                {"trajectory_id": "a", "source_sequence": 0, "action": "one"},
                {"trajectory_id": "b", "source_sequence": 0, "action": "two"},
            ]
        )
        graph = plan_graph(events)
        self.assertFalse(any("event:a:0" in dependency and "event:b:0" in dependency for node in graph.nodes.values() for dependency in node.read_dependencies))

    def test_replay_is_content_addressed(self) -> None:
        backend = DeterministicReplayBackend(strict=True)
        backend.record("hello", {"content": "world"})
        self.assertEqual(backend.complete("hello").text, "world")
        with self.assertRaises(ReplayMissError):
            backend.complete("different")

    def test_model_response_text_is_used_when_raw_is_backend_metadata(self) -> None:
        class TextBackend:
            def complete(self, request):
                return ModelResponse(
                    text='{"evidence":[{"predicate":"status","value":"ready","event_kind":"confirmation"}]}',
                    raw={"device": "cpu", "model_path": "/tmp/qwen"},
                )

        with tempfile.TemporaryDirectory() as directory:
            event = normalize_trajectory({
                "trajectory_id": "model-text",
                "environment_family": "web",
                "steps": [{"action": "open", "post_state": {"url": "https://example.test"}}],
            })
            snapshot = build_fresh(
                event,
                model_backend=TextBackend(),
                config={"storage_path": str(Path(directory) / "memory.sqlite3"), "strict_model_output": True},
            )
            self.assertEqual(len(snapshot.evidence), 1)
            self.assertEqual(snapshot.evidence[0].value, "ready")
            self.assertTrue(snapshot.evidence[0].subject_ref.startswith("model-text/trajectory:"))

    def test_strict_model_output_accepts_fenced_json_and_rejects_prose(self) -> None:
        class FencedBackend:
            def __init__(self, text):
                self.text = text

            def complete(self, request):
                return ModelResponse(text=self.text, raw={"device": "cpu"})

        event = normalize_trajectory({"trajectory_id": "strict", "steps": [{"action": "click"}]})
        with tempfile.TemporaryDirectory() as directory:
            config = {"storage_path": str(Path(directory) / "fenced.sqlite3"), "strict_model_output": True}
            fenced = FencedBackend('```json\n{"evidence": []}\n```')
            snapshot = build_fresh(event, model_backend=fenced, config=config)
            self.assertEqual(snapshot.evidence, ())
            with self.assertRaises(ConstructionError):
                build_fresh(
                    event,
                    model_backend=FencedBackend("not json"),
                    config={"storage_path": str(Path(directory) / "bad.sqlite3"), "strict_model_output": True},
                )

    def test_model_payload_keeps_state_boundaries(self) -> None:
        event = normalize_trajectory({
            "trajectory_id": "payload",
            "states": [
                {"state_index": 0, "step": 0, "url": "before", "action": None, "accessibility_tree": "before tree"},
                {"state_index": 1, "step": 1, "url": "after", "action": "click", "accessibility_tree": "after tree"},
            ],
        })[0]
        payload = _model_event_payload(event, [event], char_budget=6000)
        self.assertIn("pre_state", payload["event"])
        self.assertIn("post_state", payload["event"])
        self.assertIn("accessibility_tree", payload["event"]["pre_state"])
        self.assertIn("accessibility_tree", payload["event"]["post_state"])
        self.assertEqual(payload["context"], [])


if __name__ == "__main__":
    unittest.main()
