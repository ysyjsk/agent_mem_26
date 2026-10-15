from __future__ import annotations

import unittest

from workflow_memory.ir import normalize_trajectory
from workflow_memory.source_literals import VERSION, literal_evidence


class SourceLiteralTests(unittest.TestCase):
    def test_preserves_exact_action_url_failure_and_control_state(self):
        event = normalize_trajectory({
            "trajectory_id": "t",
            "steps": [{
                "action": "click('submit')",
                "post_state": {
                    "url": "https://example.test/a?x=1",
                    "accessibility_tree": (
                        "combobox 'Serial number' value='' selected=False\n"
                        "StaticText 'You cannot post more. Wait a while before trying again.'\n"
                        "operator 'starts with'"
                    ),
                },
            }],
        })[0]
        rows = literal_evidence(event)
        facts = {(row.predicate, row.value) for row in rows}
        self.assertIn(("action_command", "click('submit')"), facts)
        self.assertIn(("observed_url", "https://example.test/a?x=1"), facts)
        self.assertTrue(any(row.predicate == "error_span" and "cannot post" in str(row.value) for row in rows))
        self.assertTrue(any(row.predicate == "control_state" for row in rows))
        self.assertTrue(all(row.source_spans[0]["version"] == VERSION for row in rows))

    def test_is_bounded_and_deterministic(self):
        event = normalize_trajectory({"trajectory_id": "t", "steps": [{"action": "x", "post_state": {"url": "https://a"}}]})[0]
        left = [row.to_dict() for row in literal_evidence(event)]
        right = [row.to_dict() for row in literal_evidence(event)]
        self.assertEqual(left, right)
        self.assertLessEqual(len(left), 24)

    def test_current_control_values_beat_generic_accessibility_options(self):
        event = normalize_trajectory({
            "trajectory_id": "t",
            "goal": "State is Consumed and Serial number is empty",
            "steps": [{
                "action": "click('field')",
                "post_state": {"accessibility_tree": "\n".join([
                    "[1] option 'State', selected=False",
                    "[2] combobox 'State' value='-- None --'",
                    "[3] option 'Consumed', selected=False",
                    "[4] combobox 'Serial number' value='starts with'",
                    "[5] option 'starts with', selected=True",
                ])},
            }],
        })[0]
        values = [str(row.value) for row in literal_evidence(event)]
        self.assertTrue(any("-- None --" in value for value in values))
        self.assertTrue(any("Consumed" in value and "selected=False" in value for value in values))
        self.assertTrue(any("starts with" in value for value in values))


if __name__ == "__main__":
    unittest.main()
