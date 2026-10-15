from __future__ import annotations

import json

from workflow_memory import construction as core
from workflow_memory.ir import normalize_trajectory


def _event():
    middle = "\n".join(
        [
            "HEAD boundary",
            "x" * 1600,
            "[99] combobox 'State', value='-- None --', selected=false",
            "[100] option 'Consumed', selected=false",
            "[101] option 'In use', selected=true",
            "[102] combobox 'Serial number', value='starts with'",
            "[103] status 'You cannot post more. Wait a while before trying again.'",
            "TAIL boundary",
        ]
    )
    return normalize_trajectory(
        {
            "trajectory_id": "projection",
            "steps": [
                {
                    "action": "click('submit')",
                    "post_state": {
                        "url": "https://example.test/exact/record?id=42",
                        "accessibility_tree": middle,
                    },
                }
            ],
        }
    )[0]


def test_salient_projection_keeps_middle_failure_url_control_and_operator_literals():
    event = _event()
    payload = core._model_event_payload(event, [event], char_budget=6000, projection="salient-v3")
    state = payload["event"]["post_state"]
    signals = state["evidence_signals"]
    assert payload["projection_version"] == "salient-v3"
    assert signals["observed_url"][0]["value"] == "https://example.test/exact/record?id=42"
    assert any("You cannot post more" in row["value"] for row in signals["error_span"])
    assert any(row.get("control_selected") is False and row.get("control_value") == "-- None --"
               for row in signals["controls"])
    assert any("starts with" in row["value"] for row in signals["operator"])


def test_compact_projection_is_default_and_does_not_add_literal_side_channel():
    event = _event()
    payload = core._model_event_payload(event, [event], char_budget=6000)
    assert "projection_version" not in payload
    assert "evidence_signals" not in payload["event"]["post_state"]


def test_projection_mode_changes_request_and_cache_identity():
    event = _event()
    compact = core._extraction_request(event, [event], {"strict_model_output": True})
    salient = core._extraction_request(
        event,
        [event],
        {"strict_model_output": True, "model_input_projection": "salient-v3"},
    )
    compact_payload = json.loads(compact.messages[1]["content"])
    salient_payload = json.loads(salient.messages[1]["content"])
    assert "projection_version" not in compact_payload
    assert salient_payload["projection_version"] == "salient-v3"
    assert compact.fingerprint != salient.fingerprint
    assert salient.metadata["model_input_projection"] == "salient-v3"


def test_salient_projection_does_not_promote_thought_or_goal_plans():
    event = normalize_trajectory({
        "trajectory_id": "projection-plan",
        "goal": "SECRET_GOAL_PLAN",
        "steps": [{
            "action": "click('current')",
            "post_state": {
                "thought": "SECRET_FUTURE_ACTION click('future') https://future.invalid/should-not-enter",
                "accessibility_tree": "[1] button 'Current', expanded=False",
            },
        }],
    })[0]
    payload = core._model_event_payload(event, [event], char_budget=6000, projection="salient-v3")
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "SECRET_FUTURE_ACTION" not in serialized
    assert "future.invalid" not in serialized


def test_salient_serialized_payload_respects_declared_budget_with_context():
    events = normalize_trajectory({"trajectory_id": "budget", "steps": [{
        "action": "click('field')",
        "pre_state": {"url": "https://example.test/" + "x" * 120,
                      "accessibility_tree": "[9] option 'Selected', selected=True\n" * 300},
        "post_state": {"url": "https://example.test/" + "y" * 120,
                       "accessibility_tree": "[10] combobox 'State' value='-- None --'\n" * 300},
    } for _ in range(3)]})
    payload = core._model_event_payload(events[-1], events, char_budget=6000, projection="salient-v3")
    assert len(core.canonical_json(payload)) <= 6000
