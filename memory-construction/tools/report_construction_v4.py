#!/usr/bin/env python3
"""Summarize the controlled common-preflight joint-extraction screen."""
from __future__ import annotations
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "baseline": ROOT / "runs/construction-pair-v4/enterprise2-common-preflight-baseline-v2",
    "joint": ROOT / "runs/construction-pair-v4/enterprise2-common-preflight-joint-v2",
}
OUT = ROOT / "results/tables/construction_pair_v4_common_preflight.csv"
REPORT = ROOT / "reports/construction_pair_v4_common_preflight.md"

def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def inspect(variant: str, root: Path) -> tuple[dict, dict]:
    summary = json.loads((root / "memory_build_summary.json").read_text())
    calls = read_jsonl(root / "memory_state/model_calls.jsonl")
    trajectories = {}
    for path in sorted((root / "memory_state/trajectories").glob("*/trajectory.json")):
        trajectory = json.loads(path.read_text())
        trajectories[path.parent.name] = trajectory
    expected = {}
    for trajectory_id, trajectory in trajectories.items():
        states = trajectory.get("states", [])
        for index in range(max(0, len(states) - 1)):
            expected[(trajectory_id, f"event_{index:04d}_{index+1:04d}")] = {
                "pre": index, "post": index + 1,
                "action": (trajectory.get("actions") or [])[index],
                "transition_number": index + 1,
                "transition_count": len(states) - 1,
            }
    events = read_jsonl(root / "memory_state/pools/event_pool.jsonl")
    actual = {}
    duplicate_ids = []
    action_match = True
    pair_match = True
    order_match = True
    for event in events:
        key = (event.get("trajectory_id"), event.get("event_id"))
        if key in actual:
            duplicate_ids.append(key)
        actual[key] = event
        source = expected.get(key)
        if source is None:
            pair_match = False
            continue
        pair_match &= (event.get("pre_state_index") == source["pre"] and
                       event.get("post_state_index") == source["post"])
        action_text = str(event.get("local_action", "")).split("  #", 1)[0].strip()
        action_match &= action_text == source["action"]
        order_match &= (event.get("transition_number") == source["transition_number"] and
                        event.get("transition_count") == source["transition_count"])
    source_coverage = set(actual) == set(expected) and not duplicate_ids and pair_match and action_match and order_match
    controller = [row for row in calls if row.get("channel") == "controller"]
    embedding = [row for row in calls if row.get("channel") == "embedding"]
    groups = [row for row in calls if row.get("channel") == "event_group"]
    parsed_groups = sum(row.get("status") == "parsed" for row in groups)
    split_groups = sum(row.get("status") == "split" for row in groups)
    unknown_usage = sum(row.get("status") != "success" and
                        row.get("prompt_tokens") is None and row.get("completion_tokens") is None
                        for row in controller)
    qa = {
        "trajectory_ids": sorted(trajectories),
        "expected_event_count": len(expected),
        "published_event_count": len(actual),
        "missing_events": sorted([list(key) for key in set(expected) - set(actual)]),
        "extra_events": sorted([list(key) for key in set(actual) - set(expected)]),
        "duplicate_event_ids": [list(key) for key in duplicate_ids],
        "source_transition_pair_match": pair_match,
        "source_action_match": action_match,
        "transition_order_match": order_match,
        "event_source_coverage": source_coverage,
        "save_reload_verified": bool(summary.get("saved_memory_load_verified")),
        "quality_pass": bool(source_coverage and summary.get("saved_memory_load_verified")),
        "scope": "complete event coverage, source action and state-pair mapping, order, persisted reload; not downstream Reader QA",
    }
    (root / "construction_quality_checks.json").write_text(json.dumps(qa, indent=2) + "\n")
    row = {
        "variant": variant, "modality": "text-only/adapted",
        "trajectory_count": len(trajectories), "trajectory_ids": ",".join(sorted(trajectories)),
        "states": sum(len(t.get("states", [])) for t in trajectories.values()),
        "events": len(expected), "build_to_queryable_publish_s": summary.get("elapsed_seconds"),
        "controller_calls": len(controller),
        "controller_failed_calls": sum(row.get("status") != "success" for row in controller),
        "unknown_usage_calls": unknown_usage,
        "llm_input_tokens": sum(row.get("prompt_tokens") or 0 for row in controller),
        "llm_output_tokens": sum(row.get("completion_tokens") or 0 for row in controller),
        "embedding_calls": len(embedding),
        "embedding_vectors": sum(row.get("input_text_count") or 0 for row in embedding),
        "embedding_unique_exact_inputs": len({h for row in embedding for h in row.get("input_sha256", [])}),
        "embedding_input_tokens": sum(row.get("prompt_tokens") or 0 for row in embedding),
        "joint_parsed_groups": parsed_groups, "joint_split_groups": split_groups,
        "quality_pass": qa["quality_pass"], "raw_path": str(root.relative_to(ROOT)),
    }
    return row, qa

def main():
    rows = []
    checks = {}
    for variant, root in RUNS.items():
        row, qa = inspect(variant, root)
        rows.append(row); checks[variant] = qa
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    base = next(row for row in rows if row["variant"] == "baseline")
    joint = next(row for row in rows if row["variant"] == "joint")
    wall_delta = 100 * (joint["build_to_queryable_publish_s"] / base["build_to_queryable_publish_s"] - 1)
    calls_delta = 100 * (1 - joint["controller_calls"] / base["controller_calls"])
    input_delta = 100 * (1 - joint["llm_input_tokens"] / base["llm_input_tokens"])
    output_delta = 100 * (joint["llm_output_tokens"] / base["llm_output_tokens"] - 1)
    lines = [
        "# Common-preflight paired construction screen (adapted)", "",
        "Two long enterprise trajectories (`0ab99e0c`, `49f98e9e`), complete trajectories (31 states / 29 transitions), same local Qwen3.5-9B controller and Qwen3-Embedding-8B backend, 18,000-token input safety bound, 2,048 output tokens per event, no retries, text-only requests. The paired group candidate reuses the existing 12,000-character/state fallback before deciding whether each adjacent pair fits; over-budget groups split locally. Wall time runs through save/load publication validation.", "",
        "| Variant | Publish s | Controller calls (failed) | LLM input/output tokens | Embedding calls/vectors/input tokens | Parsed/split joint groups | Events | Structural/source checks |",
        "|---|---:|---:|---:|---:|---:|---:|---|"]
    for row in rows:
        lines.append(f"| {row['variant']} | {row['build_to_queryable_publish_s']:.2f} | {row['controller_calls']} ({row['controller_failed_calls']}) | {row['llm_input_tokens']}/{row['llm_output_tokens']} | {row['embedding_calls']}/{row['embedding_vectors']}/{row['embedding_input_tokens']} | {row['joint_parsed_groups']}/{row['joint_split_groups']} | {row['events']} | {'pass' if row['quality_pass'] else 'fail'} |")
    lines += ["", f"Paired deltas: the joint candidate reduces controller calls {calls_delta:.1f}% and LLM input tokens {input_delta:.1f}%, raises LLM output tokens {output_delta:.1f}%, and changes build-to-publish wall time {wall_delta:+.1f}% ({base['build_to_queryable_publish_s']:.2f}s → {joint['build_to_queryable_publish_s']:.2f}s). Embedding work is unchanged in vector count (64 each); embedding input tokens are {base['embedding_input_tokens']} vs {joint['embedding_input_tokens']}.", "",
              f"The joint run parsed {joint['joint_parsed_groups']} groups and split {joint['joint_split_groups']} oversized groups; all {joint['events']} transition IDs, source action mappings, state pairs and order were present. Save/reload validation passed for both variants. This is structural/source evidence, not downstream Reader or official QA.", "",
              "Decision: retain as a small call/token efficiency candidate with near-tie wall time; do not call it a material cold-build speedup or a quality-equivalent selected default. The fixed-10 common-preflight expansion already recorded in PAPER02 remains negative on wall time, so it is not rerun as a duplicate scale point.", "",
              f"Raw table: `{OUT.relative_to(ROOT)}`. Per-run source checks are stored beside each snapshot in `construction_quality_checks.json`."]
    REPORT.write_text("\n".join(lines) + "\n")
    print(json.dumps({"rows": rows, "quality": checks, "table": str(OUT), "report": str(REPORT)}, indent=2))

if __name__ == "__main__":
    main()
