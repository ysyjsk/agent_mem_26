#!/usr/bin/env python3
"""Freeze measured cold-construction candidates for PAPER02."""
from __future__ import annotations
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "results/tables/construction_pair_v2_full10.csv"
V3 = ROOT / "results/tables/construction_pair_v3_full10_enterprise.csv"
OUT = ROOT / "results/tables/paper02_cold_construction.csv"
REPORT = ROOT / "reports/paper02_cold_construction.md"

FIELDS = ["candidate", "data_scope", "wall_s", "controller_calls", "failed_calls",
          "llm_input_tokens", "llm_output_tokens", "embedding_calls", "embedding_vectors",
          "embedding_input_tokens", "joint_parsed", "joint_split", "events", "quality_pass", "decision", "raw_paths"]

def main() -> None:
    with V2.open(newline="") as f:
        v2 = {r["variant"]: r for r in csv.DictReader(f)}
    with V3.open(newline="") as f:
        v3 = {r["variant"]: r for r in csv.DictReader(f)}
    rows = []
    decisions = {
        "baseline": "reference",
        "joint": "negative wall-time candidate; retain as call/token ablation",
        "embed": "low-risk vector-saving ablation; no wall-time gain",
        "combined": "most measured input/call reduction; not selected because wall and one-question score regress",
    }
    for name in ("baseline", "joint", "embed", "combined"):
        r = v2[name]
        rows.append({
            "candidate": name, "data_scope": "web+enterprise / 10 complete trajectories / 91 states",
            "wall_s": r["cold_build_publish_s"], "controller_calls": r["llm_calls"], "failed_calls": r["api_failed_calls"],
            "llm_input_tokens": r["llm_input_tokens_known"], "llm_output_tokens": r["llm_output_tokens_known"],
            "embedding_calls": r["embedding_calls"], "embedding_vectors": r["embedding_vectors"],
            "embedding_input_tokens": r["embedding_input_tokens_known"], "joint_parsed": "not recorded",
            "joint_split": r["group_splits"] if name in ("joint", "combined") else 0,
            "events": r["events"], "quality_pass": r["quality_structural_pass"],
            "decision": decisions[name], "raw_paths": r["raw_paths"],
        })
    r = v3["v3-common-preflight-joint"]
    rows.append({
        "candidate": "common-preflight joint (enterprise fixed-10)",
        "data_scope": "enterprise / 5 complete trajectories / 54 states / 49 events",
        "wall_s": r["wall_s"], "controller_calls": r["controller_calls"], "failed_calls": r["controller_failed"],
        "llm_input_tokens": r["llm_input_tokens"], "llm_output_tokens": r["llm_output_tokens"],
        "embedding_calls": r["embedding_calls"], "embedding_vectors": r["embedding_vectors"],
        "embedding_input_tokens": r["embedding_input_tokens"], "joint_parsed": r["joint_parsed"], "joint_split": r["joint_split"],
        "events": r["events"], "quality_pass": r["quality_pass"],
        "decision": "negative full-10 wall-time result; retain as required ablation, do not select", "raw_paths": r["raw_path"],
    })
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    base = rows[0]; comb = rows[3]; joint = rows[1]
    def pct(a, b): return (1.0 - float(a) / float(b)) * 100.0
    lines = [
        "# PAPER02 cold-construction candidates", "",
        "All rows are local text-only/adapted measurements with resident Qwen3.5-9B/Qwen3-Embedding-8B, the frozen 18,000-token preflight, 2,048 output tokens per event, zero controller retries, and save/reload publication checks. Construction, query, Reader and official Judge are separate. The first four rows are the matched four-cell 10-trajectory matrix; the final row is the fixed-10 enterprise expansion of common-preflight joint extraction.", "",
        "| Candidate | Scope | Wall s | Controller calls (failed) | LLM input/output | Embedding calls/vectors/input | Joint parsed/split | Events | Quality | Decision |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['candidate']} | {r['data_scope']} | {float(r['wall_s']):.2f} | {r['controller_calls']} ({r['failed_calls']}) | {r['llm_input_tokens']}/{r['llm_output_tokens']} | {r['embedding_calls']}/{r['embedding_vectors']}/{r['embedding_input_tokens']} | {r['joint_parsed']}/{r['joint_split']} | {r['events']} | {'pass' if str(r['quality_pass']).lower() == 'true' else r['quality_pass']} | {r['decision']} |")
    lines += ["", "## Measured trade-offs", "",
              f"In the matched 10-trajectory matrix, joint extraction lowers controller calls by {pct(joint['controller_calls'], base['controller_calls']):.1f}% and input tokens by {pct(joint['llm_input_tokens'], base['llm_input_tokens']):.1f}%, but increases wall time by {(float(joint['wall_s'])/float(base['wall_s'])-1)*100:.1f}%. Exact embedding reuse lowers vectors from {base['embedding_vectors']} to {v2['embed']['embedding_vectors']} (8 exact hits) but raises wall time from {base['wall_s']}s to {v2['embed']['cold_build_publish_s']}s. The combined candidate gives the largest measured input/call reduction (666,712 input tokens; 76 calls) but reaches 6/8 rather than the baseline 7/8 and is slower than baseline.",
              f"The common-preflight fixed-10 enterprise expansion reduces calls from 59 to 36 ({pct(r['controller_calls'], v3['existing-v2-baseline']['controller_calls']):.1f}%) and input tokens from 495,377 to 355,456 ({pct(r['llm_input_tokens'], v3['existing-v2-baseline']['llm_input_tokens']):.1f}%), but wall time grows from 502.39s to 1,203.82s because output tokens grow to 25,824. All 49 events and source mappings pass structural/reload checks; the candidate is retained as a negative result and not selected as the final cold-build configuration.", "",
              "The paper-supported conclusion is therefore conditional: joint/preflight grouping can reduce necessary request and input work, but serialized decoding and longer multi-event responses dominate end-to-end wall time on the fixed-10 enterprise workload. The selected update mechanism is evaluated separately against these cold-build ablations."]
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT} and {REPORT}")

if __name__ == "__main__":
    main()
