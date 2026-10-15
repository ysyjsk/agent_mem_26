#!/usr/bin/env python3
"""Append one evidence-based paired development iteration, never synthesize runs."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from workflow_memory.config import load_json


def metric_rows(run: Path, method: str):
    manifest = load_json(run / "manifest.json")
    if manifest.get("replay_for_paired_methods") is not False:
        raise ValueError(f"{run}: performance comparison cannot use replay/unknown backend")
    rows = [json.loads(line) for line in (run / "checkpoint_metrics.jsonl").open() if line.strip()]
    selected = [row for row in rows if row["method"] == method]
    if not selected or sum(row["live_model_calls"] for row in selected) < 1:
        raise ValueError(f"{run}/{method}: no real construction measurements")
    indexed = {(row["window_id"], row["checkpoint_prefix_length"], row["repeat"]): row for row in selected}
    if len(indexed) != len(selected):
        raise ValueError("duplicate checkpoint pairing key")
    return manifest, selected, indexed


def comparison(reference: Path, candidate: Path, reference_method: str, candidate_method: str, **labels):
    lm, left, li = metric_rows(reference, reference_method)
    rm, right, ri = metric_rows(candidate, candidate_method)
    if lm["workload_hash"] != rm["workload_hash"] or lm["scope"] != rm["scope"]:
        raise ValueError("paired iteration requires the same workload and timing scope")
    if set(li) != set(ri):
        raise ValueError("paired iteration requires identical requested checkpoint keys")
    pairs = [(li[key], ri[key]) for key in sorted(li) if li[key]["status"] == ri[key]["status"] == "completed"]
    left_s = sum(a["elapsed_s"] for a, _ in pairs)
    right_s = sum(b["elapsed_s"] for _, b in pairs)

    def tokens(side, field):
        rows = [pair[side] for pair in pairs]
        return None if any(row.get(field) is None for row in rows) else sum(row[field] for row in rows)

    return {**labels, "reference_run": reference.name, "candidate_run": candidate.name,
            "reference_method": reference_method, "candidate_method": candidate_method,
            "scope": lm["scope"], "workload_hash": lm["workload_hash"],
            "reference_config_hash": lm["config_hash"], "candidate_config_hash": rm["config_hash"],
            "n_requested_pairs": len(li), "n_successful_pairs": len(pairs),
            "reference_failed_checkpoints": sum(row["status"] != "completed" for row in left),
            "candidate_failed_checkpoints": sum(row["status"] != "completed" for row in right),
            "paired_reference_total_s": left_s, "paired_candidate_total_s": right_s,
            "latency_reduction_pct": (1-right_s/left_s)*100 if left_s else None,
            "reference_input_tokens": tokens(0, "input_tokens"), "candidate_input_tokens": tokens(1, "input_tokens"),
            "reference_output_tokens": tokens(0, "output_tokens"), "candidate_output_tokens": tokens(1, "output_tokens"),
            "reference_live_calls": sum(a["live_model_calls"] for a, _ in pairs),
            "candidate_live_calls": sum(b["live_model_calls"] for _, b in pairs),
            "semantic_exact_matches": sum(a.get("semantic_hash") == b.get("semantic_hash") for a, b in pairs),
            "candidate_source_coverage_min": min((b.get("source_coverage_fraction", 0) for _, b in pairs), default=None),
            "candidate_actual_concurrency_max": max((b.get("actual_concurrency", 1) for _, b in pairs), default=None),
            "reference_metrics": str(reference.resolve() / "checkpoint_metrics.jsonl"),
            "candidate_metrics": str(candidate.resolve() / "checkpoint_metrics.jsonl")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--reference-method", default="Ours-dev")
    parser.add_argument("--candidate-method", default="Ours-dev")
    parser.add_argument("--iteration", required=True)
    parser.add_argument("--change", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--qa-status", default="not_evaluated")
    parser.add_argument("--table", type=Path, default=ROOT / "results/tables/dev_iterations.csv")
    args = parser.parse_args()
    row = comparison(args.reference.resolve(), args.candidate.resolve(), args.reference_method, args.candidate_method,
                     iteration=args.iteration, change=args.change, decision=args.decision, qa_status=args.qa_status)
    previous = []
    if args.table.is_file():
        with args.table.open(newline="", encoding="utf-8") as handle:
            previous = list(csv.DictReader(handle))
        if previous and set(previous[0]) != set(row):
            raise ValueError("iteration CSV schema changed; use a new table or explicit migration")
        identity = (row["iteration"], row["reference_run"], row["candidate_run"], row["reference_method"], row["candidate_method"])
        if any(tuple(p[key] for key in ("iteration", "reference_run", "candidate_run", "reference_method", "candidate_method")) == identity for p in previous):
            raise ValueError("duplicate iteration row; existing evidence was not overwritten")
    args.table.parent.mkdir(parents=True, exist_ok=True)
    with args.table.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        if not previous:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()
    print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
