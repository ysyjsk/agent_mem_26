"""Fixed-scale selection must not depend on model responses or run metrics."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("freeze_dev_scale", Path(__file__).parents[1] / "tools/freeze_dev_scale.py")
scale = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scale)


def test_nested_scale_preserves_fixed_windows_and_short_checkpoint_contract():
    base = scale.load_json(Path(__file__).parents[1] / "manifests/fastloop_dev_v1.json")
    twelve = scale.freeze(base, 12)
    full = scale.freeze(base, 24)
    assert twelve["windows"][:4] == base["windows"]
    assert full["windows"][:12] == twelve["windows"]
    assert len({window["trajectory_id"] for window in full["windows"]}) == 24
    assert twelve["selection"]["short_windows"] == 0
    assert full["selection"]["short_windows"] == 8
    for window in full["windows"]:
        cuts = window["checkpoint_prefix_lengths"]
        assert cuts == sorted(set(cuts))
        assert cuts[-1] == window["event_count"]
        assert 0 < cuts[0] <= cuts[-1] <= 12
    assert full["exposure"]["held_out_claim"] is False


def test_selection_verifies_source_hash():
    base = scale.load_json(Path(__file__).parents[1] / "manifests/fastloop_dev_v1.json")
    with pytest.raises(ValueError, match="hash"):
        scale.freeze({**base, "source_sha256": "0" * 64}, 12)


def test_exposure_is_mapping_based_not_official_answer_based(tmp_path):
    base = scale.load_json(Path(__file__).parents[1] / "manifests/fastloop_dev_v1.json")
    mapping = tmp_path / "small.json"
    scale.write_json(mapping, {"q1": [base["windows"][0]["trajectory_id"], "unselected"]})
    twelve = scale.freeze(base, 12, small=mapping)
    exposure = twelve["exposure"]["official_small"]
    assert exposure["n_overlap"] == 1
    assert exposure["mapping_sha256"] == hashlib.sha256(mapping.read_bytes()).hexdigest()
    assert exposure["trajectory_ids"] == [base["windows"][0]["trajectory_id"]]
