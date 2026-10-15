#!/usr/bin/env python3
"""Aggregate real development checkpoints; cluster bootstrap is not QA/Freshness."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_fast_compare import file_hash, percentile, summarize, write_table

NOTE = "development only; successful paired checkpoints; not Freshness; no official QA/non-inferiority claim"


def read_run(run):
    run = Path(run).resolve()
    manifest = json.loads((run / "manifest.json").read_text())
    status = json.loads((run / "status.json").read_text())["status"]
    if status not in {"completed", "completed_with_failures"} or manifest.get("replay_for_paired_methods") is not False:
        raise ValueError(f"{run}: unfinished or replay/unknown run")
    rows = [json.loads(line) for line in (run / "checkpoint_metrics.jsonl").read_text().splitlines() if line.strip()]
    keys = [(r["method"], r["window_id"], r["checkpoint_prefix_length"], r["repeat"]) for r in rows]
    if not rows or len(keys) != len(set(keys)) or sum(r["live_model_calls"] for r in rows) < 1:
        raise ValueError(f"{run}: empty/non-live or duplicate checkpoints")
    expected = {(method, w["window_id"], cut, repeat) for method in manifest["methods"] for w in manifest["selected_windows"]
                for cut in w["checkpoint_prefix_lengths"] for repeat in range(1, max(r["repeat"] for r in rows) + 1)}
    if set(keys) != expected or any(r["status"] not in {"completed", "failed"} for r in rows):
        raise ValueError(f"{run}: missing/unexpected or unfinished checkpoints")
    if any(r.get(k) != manifest[k] for r in rows for k in ("config_hash", "workload_hash", "scope")):
        raise ValueError(f"{run}: checkpoint hashes/scope differ from manifest")
    if any(not math.isfinite(r["elapsed_s"]) or r["elapsed_s"] < 0 for r in rows):
        raise ValueError(f"{run}: invalid latency")
    source = manifest["workload"]
    if file_hash(Path(source["source_file"])) != source["source_sha256"]:
        raise ValueError(f"{run}: source hash mismatch")
    for name, digest in manifest["code_sha256"].items():
        if file_hash(run / "frozen_code" / name) != digest:
            raise ValueError(f"{run}: frozen code hash mismatch: {name}")
    return manifest, rows, {"manifest_sha256": file_hash(run / "manifest.json"),
                            "raw_metrics_sha256": file_hash(run / "checkpoint_metrics.jsonl"),
                            "source_sha256": source["source_sha256"], "evaluation_note": NOTE}


def paired_statistics(manifest, rows, reference, *, seed=17, samples=2000):
    if samples < 1:
        raise ValueError("bootstrap samples must be positive")
    key = lambda r: (r["window_id"], r["checkpoint_prefix_length"], r["repeat"])
    left = {key(r): r for r in rows if r["method"] == reference}
    right = {key(r): r for r in rows if r["method"] == "Ours-dev"}
    if set(left) != set(right):
        raise ValueError("paired methods require identical requested checkpoint keys")
    trajectories = {w["window_id"]: w["trajectory_id"] for w in manifest["selected_windows"]}
    groups = defaultdict(list)
    for k in sorted(left):
        if left[k]["status"] == right[k]["status"] == "completed":
            groups[trajectories[k[0]]].append((left[k], right[k]))
    pairs = [p for g in groups.values() for p in g]
    result = {"reference_method": reference, "candidate_method": "Ours-dev", "n_requested_pairs": len(left),
              "n_successful_pairs": len(pairs), "reference_failed_checkpoints": sum(r["status"] != "completed" for r in left.values()),
              "candidate_failed_checkpoints": sum(r["status"] != "completed" for r in right.values()), "n_trajectory_units": len(groups),
              "semantic_exact_matches": sum(bool(a.get("semantic_hash")) and a["semantic_hash"] == b.get("semantic_hash") for a, b in pairs),
              "bootstrap_unit": "trajectory_all_checkpoints_and_repeats", "seed": seed, "bootstrap_samples": samples,
              "latency_ratio": None, "latency_ratio_ci_low": None, "latency_ratio_ci_high": None,
              "checkpoint_p95_difference_s": None, "checkpoint_p95_difference_ci_low_s": None, "checkpoint_p95_difference_ci_high_s": None}
    def statistic(selected):
        a, b = ([p[i]["elapsed_s"] for p in selected] for i in (0, 1))
        if sum(a) <= 0:
            raise ValueError("paired reference latency must be positive")
        return sum(b) / sum(a), percentile(b, .95) - percentile(a, .95)
    if pairs:
        ratio, difference = statistic(pairs)
        rng = random.Random(seed)
        units = sorted(groups)
        draws = [statistic([p for _ in units for p in groups[rng.choice(units)]]) for _ in range(samples)]
        result.update(latency_ratio=ratio, checkpoint_p95_difference_s=difference,
                      latency_ratio_ci_low=percentile([v[0] for v in draws], .025), latency_ratio_ci_high=percentile([v[0] for v in draws], .975),
                      checkpoint_p95_difference_ci_low_s=percentile([v[1] for v in draws], .025), checkpoint_p95_difference_ci_high_s=percentile([v[1] for v in draws], .975))
    return result


def collect(runs, *, seed=17, samples=2000):
    if len(set(map(lambda p: str(Path(p).resolve()), runs))) != len(runs):
        raise ValueError("duplicate run input")
    summaries, stats = [], []
    for path in runs:
        run = Path(path).resolve()
        manifest, rows, evidence = read_run(run)
        summaries.extend({**s, **evidence} for s in summarize(rows, run_root=run, config_hash=manifest["config_hash"], workload_hash=manifest["workload_hash"], scope=manifest["scope"]))
        for reference in (m for m in manifest["methods"] if m.startswith("B3-") and "Ours-dev" in manifest["methods"]):
            stats.append({"run_id": run.name, "config_hash": manifest["config_hash"], "workload_hash": manifest["workload_hash"],
                          "scope": manifest["scope"], "raw_metrics_path": str(run / "checkpoint_metrics.jsonl"), **evidence,
                          **paired_statistics(manifest, rows, reference, seed=seed, samples=samples)})
    return summaries, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", type=Path, required=True)
    parser.add_argument("--table", type=Path, default=ROOT / "results/tables/dev_scale.csv")
    parser.add_argument("--statistics", type=Path, default=ROOT / "results/tables/dev_paired_statistics.csv")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--samples", type=int, default=2000)
    args = parser.parse_args()
    summaries, stats = collect(args.runs, seed=args.seed, samples=args.samples)
    write_table(args.table, summaries)
    write_table(args.statistics, stats)
    print(json.dumps({"rows": len(summaries), "paired_comparisons": len(stats), "evaluation_note": NOTE,
                      "missing_B0_runs": [str(r) for r in args.runs if "B0" not in json.loads((r / "manifest.json").read_text())["methods"]]}))


if __name__ == "__main__":
    main()
