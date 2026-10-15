#!/usr/bin/env python3
"""Freeze the already measured local text-only/adapted comparison into a paper table."""
from __future__ import annotations
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/tables/dev_adapted_first_compare.csv"
OUT = ROOT / "results/tables/paper03_local_adapted_main.csv"
REPORT = ROOT / "reports/paper03_local_adapted_main.md"

SELECT = [
    ("AgentRunbook-R", "AgentRunbook-R"),
    ("RAG+Notes", "RAG+Notes"),
    ("RAG raw", "Raw RAG"),
    ("RAG+Notes + backfill", "RAG+Notes + backfill"),
    ("Strong B3-c1 + backfill", "Strong B3"),
    ("Ours-dev + backfill", "Ours"),
]

FIELDS = [
    "method", "data_scope", "input_modality", "questions", "trajectories", "states",
    "build_publish_s", "build_controller_calls", "build_controller_failed",
    "build_controller_input_tokens", "build_controller_output_tokens",
    "build_embedding_calls", "build_embedding_input_tokens", "build_embedding_failed",
    "prompt_wall_s", "reader_wall_s", "reader_calls", "reader_input_tokens",
    "reader_output_tokens", "complete", "correct", "wrong", "pending",
    "truncated", "service_failure", "parse_failure", "qa_scope",
    "source_build_suffix", "source_reader_suffix", "configuration_caveat",
]

def main() -> None:
    with SOURCE.open(newline="") as f:
        rows = list(csv.DictReader(f))
    by_name = {r["method"]: r for r in rows}
    chosen = []
    for source_name, label in SELECT:
        if source_name not in by_name:
            raise SystemExit(f"missing measured row: {source_name}")
        r = by_name[source_name]
        chosen.append({
            "method": label,
            "data_scope": "10 complete trajectories / 91 states / 8 fixed questions",
            "input_modality": "text-only/adapted",
            "questions": r["questions"], "trajectories": r["trajectories"], "states": r["states"],
            "build_publish_s": r["build_publish_s"],
            "build_controller_calls": r["build_controller_calls"],
            "build_controller_failed": r["build_controller_failed"],
            "build_controller_input_tokens": r["build_controller_input_tokens"],
            "build_controller_output_tokens": r["build_controller_output_tokens"],
            "build_embedding_calls": r["build_embedding_calls"],
            "build_embedding_input_tokens": r["build_embedding_input_tokens"],
            "build_embedding_failed": r["build_embedding_failed"],
            "prompt_wall_s": r["prompt_wall_s"], "reader_wall_s": r["reader_wall_s"],
            "reader_calls": r["reader_calls"], "reader_input_tokens": r["reader_input_tokens"],
            "reader_output_tokens": r["reader_output_tokens"],
            "complete": r["complete"], "correct": r["correct"], "wrong": r["wrong"], "pending": r["pending"],
            "truncated": r["truncated"], "service_failure": r["service_failure"], "parse_failure": r["parse_failure"],
            "qa_scope": r["qa_scope"], "source_build_suffix": r["build_suffix"], "source_reader_suffix": r["reader_suffix"],
            "configuration_caveat": r["configuration_caveat"],
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader(); w.writerows(chosen)
    lines = [
        "# PAPER03 local text-only/adapted main comparison", "",
        "This table freezes measured rows from the existing 10-trajectory, 91-state, eight-question development corpus. It is not native multimodal Small and has no verified external Judge. Build wall time ends at persisted/reload-verified memory publication; prompt/retrieval and Reader time are reported separately.", "",
        "| Method | Build→publish s | Build LLM calls (failed) | Build input/output tokens | Embedding calls/input tokens | Complete | Correct | Pending | Prompt / Reader wall s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in chosen:
        lines.append(f"| {r['method']} | {float(r['build_publish_s']):.2f} | {r['build_controller_calls']} ({r['build_controller_failed']}) | {r['build_controller_input_tokens']}/{r['build_controller_output_tokens']} | {r['build_embedding_calls']}/{r['build_embedding_input_tokens']} | {r['complete']}/{r['questions']} | {r['correct']}/{r['questions']} | {r['pending']} | {r['prompt_wall_s'] or 'n/a'} / {r['reader_wall_s'] or 'n/a'} |")
    lines += ["", "## Interpretation", "",
              "The table keeps AgentRunbook-R/RAG baselines separate from the matched structured-source Strong B3/Ours mechanism pair. Strong B3 and Ours use the same adapted representation, Reader, model service, budgets and common lexical backfill; they differ only in their construction/update mechanism and independent caches. The existing measurements show both at 6/8 correct with 8/8 complete answers, while B3 has lower cold-build wall time (537.68s vs 690.42s) and identical build-controller call/input-token counts (91 / 181,191), so this table does not support a claim that Ours reduces expensive cold-build model work.", "",
              "RAG+Notes + backfill reaches 8/8 in the recorded stochastic Reader run at 243.53s construction, but it is a query/retrieval baseline rather than a matched mechanism comparison. All rows are adapted text-only development evidence; failures and the unavailable native/Judge route remain outside this table."]
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT} and {REPORT}")

if __name__ == "__main__":
    main()
