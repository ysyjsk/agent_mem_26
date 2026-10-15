"""CPU contracts for public ordinal retrieval and its information boundary."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from workflow_memory.construction import build_fresh
from workflow_memory.ir import Evidence, canonical_json, normalize_trajectory
from workflow_memory.temporal_retrieval import public_step_numbers, query_public_steps


class TemporalRetrievalTests(unittest.TestCase):
    class _GuardedEvent:
        """Expose only the ordinal identity to catch raw-source reads."""

        def __init__(self, event_id: str) -> None:
            self.event_id = event_id

        def __getattr__(self, name: str):
            raise AssertionError(f"temporal retrieval read raw source field: {name}")

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def snapshot(self, event_count: int = 12):
        source = normalize_trajectory(
            {
                "trajectory_id": "t",
                "steps": [
                    {
                        "action": f"SECRET_GOLD_ACTION_{index}",
                        "post_state": {"url": f"https://secret.invalid/{index}"},
                    }
                    for index in range(event_count)
                ],
            }
        )
        snapshot = build_fresh(
            source,
            config={"storage_path": str(Path(self._tmp.name) / "snapshot.sqlite3")},
        )
        evidence = []
        for ordinal, event in enumerate(snapshot.events, 1):
            for suffix in range(3):
                evidence.append(
                    Evidence(
                        evidence_id=f"public-{ordinal}-{suffix}",
                        source_refs=(event.event_id,),
                        predicate="action_command",
                        value=f"public-action-{ordinal}-{suffix}",
                        event_kind="attempt",
                        valid_scope="t/trajectory",
                    )
                )
        # Keep the fixture's source events intentionally sensitive.  Replacing
        # them with ordinal-only guards makes any raw action/state read fail
        # loudly while retaining the provenance mapping needed by retrieval.
        return replace(
            snapshot,
            events=tuple(self._GuardedEvent(event.event_id) for event in snapshot.events),
            evidence=tuple(evidence),
            state_view={},
            aliases={},
            relations={},
            workflow_view={},
        )

    def test_step_parser_handles_compact_lists_but_not_checkpoint_count(self):
        self.assertEqual(public_step_numbers("source steps11 and12"), (11, 12))
        self.assertEqual(public_step_numbers("list steps 11, 12, and 13"), (11, 12, 13))
        # The checkpoint size is not a requested source ordinal.  Generated
        # questions also contain a later explicit ``source step N`` clause.
        self.assertEqual(public_step_numbers("checkpoint containing 12 source steps"), ())

    def test_temporal_filter_does_not_read_gold_or_raw_source_fields(self):
        snapshot = self.snapshot(2)
        bundle, plan = query_public_steps(snapshot, "What action was attempted at source step 1?", 8)
        serialized = canonical_json({"bundle": bundle.to_dict(), "plan": plan})
        self.assertNotIn("SECRET_GOLD_ACTION", serialized)
        self.assertNotIn("secret.invalid", serialized)
        self.assertEqual(plan["selected_source_positions"], [1])
        self.assertEqual(plan["checks"]["selected_from_snapshot_evidence"], True)

    def test_out_of_prefix_and_unrepresented_steps_return_empty_bundle(self):
        snapshot = self.snapshot(2)
        bundle, plan = query_public_steps(snapshot, "What action was attempted at source step 3?", 8)
        self.assertEqual(bundle.evidence, ())
        self.assertEqual(plan["strategy"], "public_step_filter_no_match")
        self.assertEqual(plan["fallback_reason"], "no_derived_evidence_for_public_steps")
        self.assertEqual(plan["out_of_prefix_positions"], [3])

        # Even for an arrived step, an absent derived fact must not trigger a
        # broad lexical query that could return a neighboring step.
        only_first = replace(snapshot, evidence=tuple(item for item in snapshot.evidence if item.source_refs == ("t:0",)))
        bundle, plan = query_public_steps(only_first, "What action was attempted at source step 2?", 8)
        self.assertEqual(bundle.evidence, ())
        self.assertEqual(plan["strategy"], "public_step_filter_no_match")

    def test_budget_round_robin_preserves_each_requested_step(self):
        snapshot = self.snapshot(2)
        bundle, plan = query_public_steps(snapshot, "List action commands at source steps 1 and 2.", 2)
        self.assertEqual(len(bundle.evidence), 2)
        self.assertEqual(plan["selected_source_positions"], [1, 2])
        self.assertEqual(len(plan["selected_evidence_ids"]), len(set(plan["selected_evidence_ids"])))

    def test_no_explicit_step_uses_core_lexical_fallback(self):
        snapshot = self.snapshot(2)
        bundle, plan = query_public_steps(snapshot, "public-action-2-1", 1)
        self.assertEqual(plan["strategy"], "core_lexical_fallback")
        self.assertEqual(plan["fallback_reason"], "no_explicit_step_numbers")
        self.assertEqual(len(bundle.evidence), 1)


if __name__ == "__main__":
    unittest.main()
