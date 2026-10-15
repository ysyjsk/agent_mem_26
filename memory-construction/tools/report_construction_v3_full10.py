#!/usr/bin/env python3
"""Record the fixed-10 enterprise expansion of common-preflight joint extraction."""
from __future__ import annotations
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/tables/construction_pair_v3_full10_enterprise.csv"
REPORT = ROOT / "reports/construction_pair_v3_full10_enterprise.md"


def rows(path):
    return [json.loads(line) for line in (Path(path) / "memory_state/model_calls.jsonl").read_text().splitlines() if line.strip()]


def inspect(name, path):
    root = Path(path)
    summary = json.loads((root / "memory_build_summary.json").read_text())
    calls = rows(path)
    controller = [r for r in calls if r.get("channel") == "controller"]
    embedding = [r for r in calls if r.get("channel") == "embedding"]
    groups = [r for r in calls if r.get("channel") == "event_group"]
    preflight = [r for r in calls if r.get("channel") == "event_preflight"]
    trajectories = []
    expected = set()
    for p in sorted((root / "memory_state/trajectories").glob("*/trajectory.json")):
        t = json.loads(p.read_text()); trajectories.append(p.parent.name)
        expected |= {(p.parent.name, f"event_{i:04d}_{i+1:04d}") for i in range(len(t.get("states", [])) - 1)}
    published = {(r.get("trajectory_id"), r.get("event_id")) for r in
                 [json.loads(line) for line in (root / "memory_state/pools/event_pool.jsonl").read_text().splitlines() if line.strip()]}
    quality = {"trajectory_count": len(trajectories), "expected_events": len(expected),
               "published_events": len(published), "event_source_coverage": expected == published,
               "save_reload_verified": bool(summary.get("saved_memory_load_verified")),
               "quality_pass": bool(expected == published and summary.get("saved_memory_load_verified")),
               "quality_scope": "structure/source coverage and persisted reload; no fixed Reader rerun"}
    (root / "construction_quality_checks.json").write_text(json.dumps(quality, indent=2) + "\n")
    return {"variant": name, "trajectory_count": len(trajectories), "wall_s": summary["elapsed_seconds"],
            "controller_calls": len(controller), "controller_failed": sum(r.get("status") == "failed" for r in controller),
            "llm_input_tokens": sum(r.get("prompt_tokens") or 0 for r in controller),
            "llm_output_tokens": sum(r.get("completion_tokens") or 0 for r in controller),
            "embedding_calls": len(embedding), "embedding_vectors": sum(r.get("input_text_count") or 0 for r in embedding),
            "embedding_input_tokens": sum(r.get("prompt_tokens") or 0 for r in embedding),
            "joint_parsed": sum(r.get("status") == "parsed" for r in groups),
            "joint_split": sum(r.get("status") == "split" for r in groups),
            "bounded_preflight": sum(r.get("status") == "bounded_existing_fallback" for r in preflight),
            "events": len(expected), "quality_pass": quality["quality_pass"], "raw_path": str(root),
            "quality_scope": quality["quality_scope"]}


def main():
    candidate = inspect("v3-common-preflight-joint", ROOT / "runs/construction-pair-v3/full10-enterprise-common-preflight-joint")
    baseline = inspect("existing-v2-baseline", ROOT / "runs/construction-pair-v2/full10-enterprise-baseline")
    output = [baseline, candidate]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(output[0])); w.writeheader(); w.writerows(output)
    b, c = output
    wall = (c["wall_s"] / b["wall_s"] - 1) * 100
    inp = (1 - c["llm_input_tokens"] / b["llm_input_tokens"]) * 100
    calls = (1 - c["controller_calls"] / b["controller_calls"]) * 100
    lines = [
        "# Fixed-10 enterprise expansion: common-preflight joint extraction", "",
        "The two-trajectory screen was positive for wall time and LLM work, so the same code/configuration was expanded to the frozen five-trajectory enterprise workload (49 transitions). The existing V2 baseline is directly reusable: the candidate only changes joint-group preparation, while single-event preparation, model, output budget, retries, embedding reuse and persistence boundary remain matched.", "",
        "| Variant | Wall s | Controller calls (failed) | LLM input/output | Embedding vectors/input | Joint parsed/split | Events | Quality |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in output:
        lines.append(f"| {r['variant']} | {r['wall_s']:.2f} | {r['controller_calls']} ({r['controller_failed']}) | {r['llm_input_tokens']}/{r['llm_output_tokens']} | {r['embedding_vectors']}/{r['embedding_input_tokens']} | {r['joint_parsed']}/{r['joint_split']} | {r['events']} | {'pass' if r['quality_pass'] else 'fail'} |")
    lines += ["", f"The candidate reduces controller calls by {calls:.1f}% and known LLM input tokens by {inp:.1f}%, but wall time increases {wall:.1f}% (502.39→1203.82s) because joint responses produce 25,824 output tokens versus 11,014 for baseline. All 49 transition events and source mappings are present and save/reload checks pass. This is retained as a negative wall-time result: the method reduces necessary request/input work but does not yet reduce end-to-end construction latency on the full enterprise workload.", "", "Decision: do not expand this exact candidate to web or call it the final configuration. Return to update cost/quality and output-length control; any later output-budget change must preserve the required per-event evidence and be measured as a new candidate.", ""]
    REPORT.write_text("\n".join(lines))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
