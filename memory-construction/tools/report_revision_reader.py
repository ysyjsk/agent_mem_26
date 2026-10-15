#!/usr/bin/env python3
"""Summarize Reader regression on persisted state-revision update snapshots."""
from __future__ import annotations
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/tables/agentrunbook_revision_reader_regression.csv"
DETAIL = ROOT / "results/tables/agentrunbook_revision_reader_per_question.csv"
REPORT = ROOT / "reports/agentrunbook_revision_reader_regression.md"
RUNS = [
    ("web", "fresh", "r1", "reader-revision-web-fresh-state"),
    ("web", "b3", "r1", "reader-revision-web-b3-state"),
    ("web", "ours", "r1", "reader-revision-web-ours-state-r1"),
    ("enterprise", "fresh", "r1", "reader-revision-enterprise-fresh-state"),
    ("enterprise", "fresh", "r2", "reader-revision-enterprise-fresh-r2"),
    ("enterprise", "b3", "r1", "reader-revision-enterprise-b3-state"),
    ("enterprise", "b3", "r2", "reader-revision-enterprise-b3-r2"),
    ("enterprise", "ours", "r1", "reader-revision-enterprise-ours-state"),
    ("enterprise", "ours", "r2", "reader-revision-enterprise-ours-r2"),
]

def main() -> None:
    rows, details = [], []
    for domain, method, repeat, name in RUNS:
        root = ROOT / "runs/agentrunbook-updates-main" / name
        agg = json.loads((root / "aggregated_metrics.json").read_text())
        status, tok, timing = agg["answer_status"], agg["tokens"], agg["timing"]
        rows.append({
            "domain": domain, "method": method, "repeat": repeat,
            "questions": agg["overall"]["count_all_questions"],
            "complete_parseable": status["complete_parseable"], "correct": status["correct"],
            "truncated": status["truncated"], "service_failure": status["service_failure"],
            "parse_failure": status["parse_failure"], "reader_input_tokens": tok["prompt_tokens"],
            "reader_output_tokens": tok["completion_tokens"],
            "prompt_build_wall_s": timing["prompt_build_wall_seconds"],
            "reader_generation_wall_s": timing["reader_generation_wall_seconds"],
            "raw_path": str(root.relative_to(ROOT)),
        })
        for line in (root / "per_question.jsonl").read_text().splitlines():
            q = json.loads(line)
            details.append({
                "domain": domain, "method": method, "repeat": repeat,
                "question_id": q["question_id"], "gold": q.get("answer_gold"),
                "answer": q.get("response_parsed_boxed"), "correct": q.get("score_bool"),
                "reader_status": q.get("reader_status"), "truncated": q.get("reader_truncated"),
                "parse_status": q.get("reader_parse_status"),
            })
    for path, fields, data in ((OUT, list(rows[0]), rows), (DETAIL, list(details[0]), details)):
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(data)
    lines = [
        "# Reader regression on state-revision update snapshots", "",
        "This is a text-only/adapted downstream quality check using the fixed four questions per domain after a controlled state revision. It reuses persisted update snapshots and does not add construction work. All answers use a 2,048-token Reader ceiling, thinking disabled, and the same local Qwen service.", "",
        "| Domain | Method | Repeat | Correct / 4 | Complete / 4 | Trunc | Service | Parse | Reader input/output tokens | Prompt / Reader wall s |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(f"| {r['domain']} | {r['method']} | {r['repeat']} | {r['correct']}/{r['questions']} | {r['complete_parseable']}/{r['questions']} | {r['truncated']} | {r['service_failure']} | {r['parse_failure']} | {r['reader_input_tokens']}/{r['reader_output_tokens']} | {r['prompt_build_wall_s']:.2f} / {r['reader_generation_wall_s']:.2f} |")
    lines += ["", "All 36 scored responses (9 rows × 4 questions) were complete, boxed and service-successful, with zero truncation, service failure or parse failure. Web is 3/4 for all three methods. Enterprise is 2/4 for Fresh in both repeats, 3/4 for B3 in both repeats, and 2/4 for Ours in both repeats. The stable enterprise gap is therefore a quality constraint on this representative state-revision snapshot, not evidence of quality preservation for Ours.", "",
              "The misses are concentrated in dynamic/procedure questions and vary in answer wording; source-grounded construction checks still pass. We retain the negative result and do not select Ours as a quality-equivalent update method until a broader Reader/QA evaluation is completed.", "",
              f"Raw aggregate: `{OUT.relative_to(ROOT)}`. Per-question answers: `{DETAIL.relative_to(ROOT)}`."]
    REPORT.write_text("\n".join(lines) + "\n")
    print(json.dumps({"rows": len(rows), "details": len(details), "report": str(REPORT)}))

if __name__ == "__main__":
    main()
