#!/usr/bin/env python3
"""Fix nested development windows before measurement; never select by results."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from workflow_memory.config import load_json, write_json
from workflow_memory.ir import normalize_trajectory


def freeze(base: dict, count: int, *, small: Path | None = None,
           medium: Path | None = None) -> dict:
    source = Path(base["source_file"])
    if hashlib.sha256(source.read_bytes()).hexdigest() != base["source_sha256"]:
        raise ValueError("development source hash differs from fixed v1 manifest")
    records = [json.loads(line) for line in source.open() if line.strip()]
    events = [normalize_trajectory(row) for row in records]
    by_id = {items[0].trajectory_id: items for items in events if items}
    if len(by_id) != len(events):
        raise ValueError("duplicate/empty development trajectories")
    windows = deepcopy(base["windows"])
    selected = {window["trajectory_id"] for window in windows}
    if not len(windows) <= count <= len(by_id):
        raise ValueError("requested count must retain v1 and fit the source")
    rank = lambda tid: hashlib.sha256(("17:" + tid).encode()).hexdigest()
    pending = sorted(set(by_id) - selected, key=lambda tid: (len(by_id[tid]) < 8, rank(tid)))
    # Balance families while preferring >=8-event windows; deterministic
    # short trajectories enter only after the available long-window pool.
    while len(windows) < count:
        family_counts = Counter(window["environment_family"] for window in windows)
        long_available = any(len(by_id[tid]) >= 8 for tid in pending)
        eligible = [tid for tid in pending if not long_available or len(by_id[tid]) >= 8]
        tid = min(eligible, key=lambda item: (family_counts[by_id[item][0].environment_family], rank(item)))
        prefix = by_id[tid][:12]
        cuts = sorted({min(4, len(prefix)), min(8, len(prefix)), len(prefix)})
        windows.append({"window_id": f"{tid}-prefix{len(prefix)}", "trajectory_id": tid,
                        "environment_family": prefix[0].environment_family,
                        "event_ids": [event.event_id for event in prefix], "event_count": len(prefix),
                        "checkpoint_prefix_lengths": cuts})
        pending.remove(tid)
    out = deepcopy(base)
    out.update(schema_version="fastloop-dev-scale/1", scope="construction_e2e", windows=windows,
               purpose="preselected nested development scale; not held-out or official QA",
               methods=["B0", "Ours-dev", "B3-c2"], base_manifest_hash=hashlib.sha256(
                   json.dumps(base, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    out["selection"] = {"seed": 17, "requested_windows": count, "max_prefix_events": 12,
                        "order": "retain v1; balance family; prefer >=8 events, then sha256(17:trajectory_id)",
                        "short_windows": sum(window["event_count"] < 8 for window in windows),
                        "no_performance_or_model_answer_selection": True}
    exposure = {"development": "all selected trajectories exposed by definition", "held_out_claim": False}
    for name, mapping_path in (("official_small", small), ("official_medium", medium)):
        if mapping_path is None:
            exposure[name] = {"status": "mapping_not_supplied"}
            continue
        mapping = load_json(mapping_path)
        ids = {str(tid) for group in mapping.values() for tid in group}
        overlap = sorted({window["trajectory_id"] for window in windows} & ids)
        exposure[name] = {"mapping_path": str(mapping_path.resolve()),
                          "mapping_sha256": hashlib.sha256(mapping_path.read_bytes()).hexdigest(),
                          "n_overlap": len(overlap), "trajectory_ids": overlap,
                          "status": "benchmark_exposure_audited_not_held_out"}
    out["exposure"] = exposure
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "manifests/fastloop_dev_v1.json")
    parser.add_argument("--windows", type=int, choices=(12, 24), required=True)
    parser.add_argument("--small", type=Path)
    parser.add_argument("--medium", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("refuse to overwrite a fixed development manifest")
    result = freeze(load_json(args.base), args.windows, small=args.small, medium=args.medium)
    write_json(args.out, result)
    print(json.dumps({"manifest": str(args.out), "windows": len(result["windows"]),
                      "events": sum(w["event_count"] for w in result["windows"]),
                      "checkpoints": sum(len(w["checkpoint_prefix_lengths"]) for w in result["windows"]),
                      "short_windows": result["selection"]["short_windows"], "exposure": result["exposure"]}))


if __name__ == "__main__":
    main()
