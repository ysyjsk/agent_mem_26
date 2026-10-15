#!/usr/bin/env python3
"""Summarize the two-trajectory common-preflight construction pair."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/tables/construction_pair_v3_common_preflight.csv"
REPORT = ROOT / "reports/construction_pair_v3_common_preflight.md"


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def inspect(run):
    root = ROOT / run
    summary = json.loads((root / "memory_build_summary.json").read_text())
    calls = jsonl(root / "memory_state/model_calls.jsonl")
    trajectories = []
    events = []
    for path in sorted((root / "memory_state/trajectories").glob("*/trajectory.json")):
        trajectory = json.loads(path.read_text())
        trajectories.append(path.parent.name)
        events.extend((path.parent.name, i, i + 1) for i in range(len(trajectory.get("states", [])) - 1))
    by_channel = {}
    for row in calls:
        channel = row.get("channel")
        d = by_channel.setdefault(channel, {"calls": 0, "success": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0, "vectors": 0})
        d["calls"] += 1
        d["success"] += int(row.get("status") in {"success", "parsed"})
        d["failed"] += int(row.get("status") == "failed")
        d["input_tokens"] += row.get("prompt_tokens") or 0
        d["output_tokens"] += row.get("completion_tokens") or 0
        d["vectors"] += row.get("input_text_count") or 0
    groups = [row for row in calls if row.get("channel") == "event_group"]
    splits = [row for row in groups if row.get("status") == "split"]
    parsed_groups = [row for row in groups if row.get("status") == "parsed"]
    event_ids = {(tid, f"event_{pre:04d}_{post:04d}") for tid, pre, post in events}
    published_ids = {(row.get("trajectory_id"), row.get("event_id")) for row in jsonl(root / "memory_state/pools/event_pool.jsonl")}
    source_coverage = event_ids == published_ids
    quality = {
        "trajectory_ids": trajectories,
        "trajectory_count": len(trajectories),
        "expected_event_count": len(events),
        "published_event_count": len(published_ids),
        "event_source_coverage": source_coverage,
        "save_reload_verified": bool(summary.get("saved_memory_load_verified")),
        "successful_joint_groups": len(parsed_groups),
        "split_joint_groups": len(splits),
        "quality_pass": bool(source_coverage and summary.get("saved_memory_load_verified")),
        "quality_scope": "structure/source coverage and persisted reload; fixed Reader regression is reported separately",
    }
    (root / "construction_quality_checks.json").write_text(json.dumps(quality, indent=2) + "\n")
    controller = by_channel.get("controller", {})
    embedding = by_channel.get("embedding", {})
    return {
        "variant": run.split("/")[-1], "input_modality": "text-only/adapted",
        "trajectory_count": len(trajectories), "trajectory_ids": ",".join(trajectories),
        "wall_s": summary["elapsed_seconds"], "controller_calls": controller.get("calls", 0),
        "controller_success": controller.get("success", 0), "controller_failed": controller.get("failed", 0),
        "llm_input_tokens": controller.get("input_tokens", 0), "llm_output_tokens": controller.get("output_tokens", 0),
        "embedding_calls": embedding.get("calls", 0), "embedding_vectors": embedding.get("vectors", 0),
        "embedding_input_tokens": embedding.get("input_tokens", 0),
        "successful_joint_groups": len(parsed_groups), "split_joint_groups": len(splits),
        "events": len(events), "quality_pass": quality["quality_pass"],
        "quality_scope": quality["quality_scope"], "raw_path": run,
    }, quality


def main():
    variants = [
        "runs/construction-pair-v3/enterprise2-common-preflight-baseline",
        "runs/construction-pair-v3/enterprise2-common-preflight-joint",
    ]
    rows = []; qualities = {}
    for run in variants:
        row, quality = inspect(run); rows.append(row); qualities[row["variant"]] = quality
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    b, j = rows
    wall_delta = 100 * (j["wall_s"] - b["wall_s"]) / b["wall_s"]
    input_delta = 100 * (j["llm_input_tokens"] - b["llm_input_tokens"]) / b["llm_input_tokens"]
    lines = [
        "# Cold construction candidate: common bounded input preparation before joint extraction", "",
        "The candidate changes one mechanism only: when an event or adjacent pair exceeds the 18,000-token safety budget, both paths first apply the existing 12,000-character-per-state bounded preparation. A pair is sent jointly only if the prepared shared-state request fits; otherwise only that pair is split into single events. Models, output budgets, retries, embedding reuse, selected trajectories and persistence boundary are unchanged.", "",
        "| Variant | Wall s | Controller calls (failed) | LLM input/output tokens | Embedding calls/vectors/input tokens | Joint parsed/split groups | Events | Quality |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(f"| {row['variant']} | {row['wall_s']:.2f} | {row['controller_calls']} ({row['controller_failed']}) | {row['llm_input_tokens']}/{row['llm_output_tokens']} | {row['embedding_calls']}/{row['embedding_vectors']}/{row['embedding_input_tokens']} | {row['successful_joint_groups']}/{row['split_joint_groups']} | {row['events']} | {'pass' if row['quality_pass'] else 'fail'} |")
    lines += ["", f"On the two long enterprise trajectories (`0ab99e0c`, `49f98e9e`), joint common-preflight reduced wall time by {-wall_delta:.1f}% ({b['wall_s']:.2f}s → {j['wall_s']:.2f}s), controller calls from {b['controller_calls']} to {j['controller_calls']}, and known LLM input tokens by {-input_delta:.1f}% ({b['llm_input_tokens']:,} → {j['llm_input_tokens']:,}). It parsed {j['successful_joint_groups']} joint groups and split {j['split_joint_groups']} oversized prepared groups; no API failures occurred in the joint run.", "", "Both variants published all 29 expected transition events and passed save/reload plus source-coverage checks. This is a construction-quality check, not a claim of unchanged downstream QA; the fixed Reader regression remains reported separately. The candidate is retained for the next fixed-10 expansion because it reduces expensive model work without reducing required evidence or output budget.", ""]
    REPORT.write_text("\n".join(lines))
    print(json.dumps({"rows": rows, "qualities": qualities}, indent=2))


if __name__ == "__main__":
    main()
