"""CPU-only contracts for the narrow fast comparison runner."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import run_fast_compare as fast  # noqa: E402


def _row(method: str, *, status: str = "completed", elapsed: float = 2.0,
         input_tokens: int | None = 10, output_tokens: int | None = 3) -> dict:
    return {
        "method": method, "window_id": "w", "checkpoint_prefix_length": 4,
        "repeat": 1, "status": status, "phase": "initial_build",
        "elapsed_s": elapsed, "live_model_calls": 1 if status == "completed" else 0,
        "failed_model_calls": 0 if status == "completed" else 1,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "reused_nodes": 0, "invalidated_nodes": 0, "snapshot_valid": status == "completed",
    }


def test_summarize_retains_failed_checkpoint_and_latency(tmp_path: Path) -> None:
    rows = [_row("B0", elapsed=2.5), _row("B0", status="failed", elapsed=0.25,
                                            input_tokens=None, output_tokens=None)]
    result = fast.summarize(rows, run_root=tmp_path / "run", config_hash="c", workload_hash="w", scope="construction_kernel")
    assert result[0]["n_checkpoints"] == 2
    assert result[0]["successful_checkpoints"] == 1
    assert result[0]["failed_checkpoints"] == 1
    assert result[0]["total_s"] == 2.75
    assert result[0]["input_tokens"] is None
    assert result[0]["output_tokens"] is None


def test_summarize_separates_elapsed_and_token_totals(tmp_path: Path) -> None:
    rows = [_row("Ours-dev", elapsed=1.25, input_tokens=17, output_tokens=5),
            {**_row("Ours-dev", elapsed=0.75, input_tokens=11, output_tokens=4), "phase": "update",
             "live_model_calls": 2}]
    result = fast.summarize(rows, run_root=tmp_path / "run", config_hash="c", workload_hash="w", scope="construction_kernel")[0]
    assert result["initial_build_s"] == 1.25
    assert result["update_total_s"] == 0.75
    assert result["total_s"] == 2.0
    assert result["live_model_calls"] == 3
    assert result["input_tokens"] == 28
    assert result["output_tokens"] == 9


def test_failed_checkpoint_cannot_form_successful_pair() -> None:
    b0 = _row("B0", status="failed", input_tokens=None, output_tokens=None)
    ours = _row("Ours-dev")
    assert not (b0["status"] == ours["status"] == "completed")
    assert fast.token_sum([b0], "input_tokens") is None


def test_methods_share_real_batch_opportunity_without_batching_serial_baselines() -> None:
    settings = {"extraction_concurrency": 2}
    assert fast.method_concurrency("Ours-dev", settings) == 2
    assert fast.method_concurrency("B3-c2", settings) == 2
    assert fast.method_concurrency("B0", settings) == 1
    assert fast.method_concurrency("B3-c1", settings) == 1
    assert fast.method_concurrency("Ours-dev", {}) == 1
    with pytest.raises(ValueError, match="1 or 2"):
        fast.method_concurrency("Ours-dev", {"extraction_concurrency": 4})


def test_embedding_projection_is_opt_in_and_validated_before_gpu_loading() -> None:
    assert fast.dense_render_version({}) == "full-v1"
    assert fast.dense_render_version({"embedding_render_version": "source-ref-v1"}) == "source-ref-v1"
    with pytest.raises(ValueError, match="embedding_render_version"):
        fast.dense_render_version({"embedding_render_version": "not-a-projection"})
