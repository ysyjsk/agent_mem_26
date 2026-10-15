from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from workflow_memory import construction as core
from workflow_memory.backends import ModelResponse
from workflow_memory.ir import normalize_trajectory, stable_hash


def _events(count: int = 3):
    return normalize_trajectory(
        {
            "trajectory_id": "request-cache",
            "environment_family": "web",
            "steps": [
                {
                    "source_sequence": index,
                    "action": f"click-{index}",
                    "post_state": {"url": f"https://example.test/{index}"},
                }
                for index in range(count)
            ],
        }
    )


class _CountingBackend:
    def __init__(self) -> None:
        self.calls = []
        self.input_tokens = 0
        self.output_tokens = 0

    def fingerprint(self) -> str:
        return "request-cache-backend-v1"

    def complete(self, request):
        self.calls.append(request)
        self.input_tokens += 17
        self.output_tokens += 5
        payload = json.loads(request.messages[1]["content"])
        event_id = payload["event"]["event_id"]
        return ModelResponse(
            text=json.dumps(
                {
                    "evidence": [
                        {
                            "source_refs": [event_id],
                            "predicate": "action",
                            "value": payload["event"]["action"],
                            "event_kind": "attempt",
                            "subject_ref": "agent",
                        }
                    ]
                }
            ),
            usage={"prompt_tokens": 17, "completion_tokens": 5},
            request_fingerprint=request.fingerprint,
        )


def _clear() -> None:
    core._clear_extraction_request_memo()


def test_cache_is_opt_in_and_reuses_exact_request_bytes(tmp_path: Path) -> None:
    _clear()
    event = _events(1)[0]
    disabled = {"storage_path": str(tmp_path / "disabled.sqlite3"), "strict_model_output": True}
    first = core._extraction_request(event, [event], disabled)
    second = core._extraction_request(event, [event], disabled)
    assert first is not second
    assert first.to_dict() == second.to_dict()
    assert first.fingerprint == second.fingerprint
    assert core._REQUEST_MEMOS == {}

    enabled = {**disabled, "extraction_request_cache": True}
    cached_first = core._extraction_request(event, [event], enabled)
    cached_second = core._extraction_request(event, [event], enabled)
    assert cached_first is cached_second
    assert cached_first.to_dict() == first.to_dict()
    assert cached_first.fingerprint == first.fingerprint


def test_revision_context_and_request_parameters_invalidate(tmp_path: Path) -> None:
    _clear()
    events = _events(3)
    config = {
        "storage_path": str(tmp_path / "memo.sqlite3"),
        "strict_model_output": True,
        "extraction_request_cache": True,
    }
    target = events[1]
    core._extraction_request(target, events[:2], config)
    namespace = core._extraction_request_memo_namespace(config)
    assert len(core._REQUEST_MEMOS[namespace]) == 1

    revised = replace(events[0], source_revision=1, action="revised-action", raw_content_hash="")
    core._extraction_request(target, [revised, target], config)
    assert len(core._REQUEST_MEMOS[namespace]) == 2

    for changed in (
        {**config, "extraction_prompt": "Use only exact observations."},
        {**config, "construction_model": "other-model"},
        {**config, "extraction_output_tokens": 128},
        {**config, "temperature": 0.4},
        {**config, "model_input_projection": "salient-v3"},
    ):
        core._extraction_request(target, events[:2], changed)
    assert len(core._REQUEST_MEMOS[namespace]) == 7


def test_nested_source_mutation_is_not_hidden_by_request_memo(tmp_path: Path) -> None:
    """SourceEvent is frozen, but its JSON-like state refs may be mutable."""

    _clear()
    event = _events(1)[0]
    config = {
        "storage_path": str(tmp_path / "nested.sqlite3"),
        "strict_model_output": True,
        "extraction_request_cache": True,
    }
    first = core._extraction_request(event, [event], config)
    namespace = core._extraction_request_memo_namespace(config)
    assert len(core._REQUEST_MEMOS[namespace]) == 1
    assert isinstance(event.post_state_ref, dict)
    event.post_state_ref["url"] = "https://example.test/revised-in-place"
    second = core._extraction_request(event, [event], config)
    assert second.fingerprint != first.fingerprint
    assert len(core._REQUEST_MEMOS[namespace]) == 2


def test_lru_bound_and_method_store_namespaces(tmp_path: Path) -> None:
    _clear()
    events = _events(3)
    config = {
        "storage_path": str(tmp_path / "bounded.sqlite3"),
        "strict_model_output": True,
        "extraction_request_cache": True,
        "extraction_request_cache_max_entries": 2,
    }
    for event in events:
        core._extraction_request(event, [event], config)
    namespace = core._extraction_request_memo_namespace(config)
    assert len(core._REQUEST_MEMOS[namespace]) == 2

    ours = {**config, "method": "Ours"}
    b3 = {**config, "method": "B3"}
    ours_request = core._extraction_request(events[0], [events[0]], ours)
    b3_request = core._extraction_request(events[0], [events[0]], b3)
    assert ours_request is not b3_request
    assert core._extraction_request_memo_namespace(ours) != core._extraction_request_memo_namespace(b3)
    assert len(core._REQUEST_MEMOS[core._extraction_request_memo_namespace(ours)]) == 1
    assert len(core._REQUEST_MEMOS[core._extraction_request_memo_namespace(b3)]) == 1

    other_store = {**config, "storage_path": str(tmp_path / "other.sqlite3")}
    other_request = core._extraction_request(events[0], [events[0]], other_store)
    assert other_request is not ours_request


def test_cache_enabled_build_matches_disabled_backend_and_snapshot(tmp_path: Path) -> None:
    _clear()
    events = _events(3)
    disabled_config = {
        "storage_path": str(tmp_path / "disabled-build.sqlite3"),
        "strict_model_output": True,
    }
    enabled_config = {
        "storage_path": str(tmp_path / "enabled-build.sqlite3"),
        "strict_model_output": True,
        "extraction_request_cache": True,
    }
    disabled_backend = _CountingBackend()
    enabled_backend = _CountingBackend()
    disabled = core.build_fresh(events, disabled_backend, disabled_config)
    enabled = core.build_fresh(events, enabled_backend, enabled_config)

    disabled_hashes = [request.fingerprint for request in disabled_backend.calls]
    enabled_hashes = [request.fingerprint for request in enabled_backend.calls]
    assert enabled_hashes == disabled_hashes
    assert len(enabled_backend.calls) == len(disabled_backend.calls) == len(events)
    assert (enabled_backend.input_tokens, enabled_backend.output_tokens) == (
        disabled_backend.input_tokens,
        disabled_backend.output_tokens,
    )
    semantic_fields = lambda snapshot: {
        "evidence": [item.to_dict() for item in snapshot.evidence],
        "state": snapshot.state_view,
        "workflow": snapshot.workflow_view,
        "relations": snapshot.relations,
        "index": snapshot.index,
    }
    assert stable_hash(semantic_fields(enabled)) == stable_hash(semantic_fields(disabled))
    assert [node.to_dict() for node in enabled.nodes] == [node.to_dict() for node in disabled.nodes]
    assert [node.content_hash for node in enabled.nodes] == [node.content_hash for node in disabled.nodes]
    assert [node.provenance_hash for node in enabled.nodes] == [node.provenance_hash for node in disabled.nodes]
