"""CPU contracts for the controlled revision/scope mechanism workloads."""

from __future__ import annotations

import json
from pathlib import Path

from workflow_memory.backends import ModelResponse
from workflow_memory.ir import normalize_trajectory

from tools.run_mechanism_stress import run_revision_stress, run_scope_isolation


class CountingBackend:
    def __init__(self, *, batched: bool = False):
        self.calls: list[str] = []
        self.batches: list[int] = []
        self.supports_batch_calls = batched
        self.max_batch_size = 2

    def fingerprint(self) -> str:
        return "cpu-mechanism-fixture/1"

    @staticmethod
    def _response(request) -> ModelResponse:
        event_id = request.metadata["event_id"]
        payload = json.loads(request.messages[-1]["content"])
        evidence = {
            "predicate": "observed_property",
            "subject_ref": "page",
            "value": payload,
            "event_kind": "observation",
            "source_refs": [event_id],
        }
        return ModelResponse(text=json.dumps({"evidence": [evidence]}), raw={"device": "cpu"})

    def complete(self, request):
        self.calls.append(request.metadata["event_id"])
        return self._response(request)

    def complete_batch(self, requests):
        if not self.supports_batch_calls:
            raise RuntimeError("batch capability disabled")
        self.batches.append(len(requests))
        responses = []
        for request in requests:
            self.calls.append(request.metadata["event_id"])
            response = self._response(request)
            responses.append(ModelResponse(text=response.text,
                                            raw={"device": "cpu", "batch_size": len(requests)},
                                            usage=response.usage))
        return responses


def _events(trajectory: str, count: int = 5):
    return normalize_trajectory({
        "trajectory_id": trajectory,
        "environment_family": "web",
        "steps": [{"source_sequence": i, "arrival_sequence": i,
                    "action": f"click-{i}", "post_state": {"url": f"page-{i}"}}
                   for i in range(count)],
    })


def _settings(width: int = 1):
    return {
        "strict_model_output": True,
        "source_context_window_events_default": 2,
        "extraction_output_tokens": 256,
        "model_input_char_budget": 6000,
        "extraction_concurrency": width,
    }


def test_revision_stress_records_real_reuse_and_b3_recomposition(tmp_path: Path):
    backend = CountingBackend()
    rows = run_revision_stress(
        windows=[({"window_id": "a"}, _events("a"))],
        backend=backend,
        settings=_settings(1),
        out=tmp_path / "revision",
        methods=("B0", "Ours-dev", "B3-c1"),
        positions=("early", "mid", "late"),
    )
    assert len(rows) == 18  # 3 positions x 3 methods x initial/revision
    assert all(row["status"] == "completed" for row in rows)
    assert all(row["snapshot_valid"] for row in rows)
    for position in ("early", "mid", "late"):
        ours = next(row for row in rows if row["method"] == "Ours-dev" and row["position"] == position and row["phase"] == "revision_update")
        b3 = next(row for row in rows if row["method"] == "B3-c1" and row["position"] == position and row["phase"] == "revision_update")
        fresh = next(row for row in rows if row["method"] == "B0" and row["position"] == position and row["phase"] == "revision_update")
        assert fresh["cache_hits"] == 0 and fresh["cache_misses"] == 5
        assert ours["cache_hits"] + ours["cache_misses"] == 5
        assert b3["cache_hits"] + b3["cache_misses"] == 5
        assert ours["recomputed_nodes"] <= ours["node_value_visits"]
        assert b3["recomputed_nodes"] == b3["node_value_visits"]
        assert ours["source_revision_archive_valid"]
    assert (tmp_path / "revision" / "checkpoint_metrics.jsonl").is_file()
    assert (tmp_path / "revision" / "model_requests.jsonl").is_file()


def test_scope_isolation_uses_independent_store_and_preserves_other_scope(tmp_path: Path):
    backend = CountingBackend()
    rows = run_scope_isolation(
        windows=[({"window_id": "a"}, _events("a")), ({"window_id": "b"}, _events("b"))],
        backend=backend,
        settings=_settings(1),
        out=tmp_path / "scope",
        methods=("B0", "Ours-dev", "B3-c1"),
    )
    assert len(rows) == 6
    assert all(row["status"] == "completed" and row["snapshot_valid"] for row in rows)
    ours = next(row for row in rows if row["method"] == "Ours-dev" and row["phase"] == "scope_append")
    b3 = next(row for row in rows if row["method"] == "B3-c1" and row["phase"] == "scope_append")
    assert ours["cache_hits"] == 10 and ours["cache_misses"] == 1
    assert b3["cache_hits"] == 10 and b3["cache_misses"] == 1
    assert ours["recomputed_nodes"] < ours["node_value_visits"]
    assert b3["recomputed_nodes"] == b3["node_value_visits"]


def test_ours_and_b3_c2_report_actual_batch_width(tmp_path: Path):
    backend = CountingBackend(batched=True)
    rows = run_revision_stress(
        windows=[({"window_id": "a"}, _events("a", count=4))],
        backend=backend,
        settings=_settings(2),
        out=tmp_path / "batch",
        methods=("Ours-dev", "B3-c2"),
        positions=("mid",),
    )
    assert all(row["status"] == "completed" for row in rows)
    assert backend.batches
    assert all(width <= 2 for width in backend.batches)
    assert any(row["actual_batch_size_max"] == 2 for row in rows)
    assert all(row["embedding_status"] == "excluded_from_construction_kernel" for row in rows)

