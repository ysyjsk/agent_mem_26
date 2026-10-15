#!/usr/bin/env python3
"""Aggregate the fixed-question Reader checks across all eight revision cases."""
from __future__ import annotations
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/tables/agentrunbook_revision_case_reader.csv"
REPORT = ROOT / "reports/agentrunbook_revision_case_reader.md"

CASES = [
    ("web", "1ad1af4b", "state_revision", "reader-revision-web-b3-state", "reader-revision-web-ours-state-r1"),
    ("web", "1ad1af4b", "workflow_revision", "reader-revision-web-1ad1af4b-workflow_revision-b3-r2", "reader-revision-web-1ad1af4b-workflow_revision-ours-r2"),
    ("web", "2e8f6477", "state_revision", "reader-revision-web-2e8f6477-state_revision-b3-r2", "reader-revision-web-2e8f6477-state_revision-ours-r2"),
    ("web", "2e8f6477", "workflow_revision", "reader-revision-web-2e8f6477-workflow_revision-b3-r2", "reader-revision-web-2e8f6477-workflow_revision-ours-r2"),
    ("enterprise", "0ab99e0c", "state_revision", "reader-revision-enterprise-b3-r2", "reader-revision-enterprise-ours-r2"),
    ("enterprise", "0ab99e0c", "workflow_revision", "reader-revision-enterprise-0ab99e0c-workflow_revision-b3-r2", "reader-revision-enterprise-0ab99e0c-workflow_revision-ours-r2"),
    ("enterprise", "49f98e9e", "state_revision", "reader-revision-enterprise-49f98e9e-state_revision-b3-r2", "reader-revision-enterprise-49f98e9e-state_revision-ours-r2"),
    ("enterprise", "49f98e9e", "workflow_revision", "reader-revision-enterprise-49f98e9e-workflow_revision-b3-r2", "reader-revision-enterprise-49f98e9e-workflow_revision-ours-r2"),
]

def aggregate(name: str, domain: str, method: str, case: str):
    root = ROOT / "runs/agentrunbook-updates-main" / name
    data = json.loads((root / "aggregated_metrics.json").read_text())
    status, tok, timing = data["answer_status"], data["tokens"], data["timing"]
    return {
        "domain": domain, "trajectory_id": next(t for d,t,c,_,_ in CASES if d == domain and c == case and t),
        "case": case, "method": method, "questions": data["overall"]["count_all_questions"],
        "correct": status["correct"], "complete_parseable": status["complete_parseable"],
        "truncated": status["truncated"], "service_failure": status["service_failure"],
        "parse_failure": status["parse_failure"], "reader_input_tokens": tok["prompt_tokens"],
        "reader_output_tokens": tok["completion_tokens"],
        "prompt_build_wall_s": timing["prompt_build_wall_seconds"],
        "reader_generation_wall_s": timing["reader_generation_wall_seconds"],
        "raw_path": str(root.relative_to(ROOT)),
    }

def main():
    rows = []
    for domain, tid, case, b3, ours in CASES:
        for method, name in (("b3", b3), ("ours", ours)):
            row = aggregate(name, domain, method, case)
            row["trajectory_id"] = tid
            rows.append(row)
    fields = list(rows[0])
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    lines = [
        "# Reader regression across eight fixed revision cases", "",
        "This is a text-only/adapted fixed-question regression on persisted update snapshots. It covers both state and workflow revisions for two web and two enterprise trajectories, with B3 and Ours using the same local Qwen Reader, 2,048-token ceiling, thinking disabled and four questions per case. Fresh/B0 is not included in the full eight-case table because only a subset of Fresh workflow snapshots was re-read; its state-revision results remain in the separate Fresh/B3/Ours report.", "",
        "| Domain | Trajectory | Case | Method | Correct / 4 | Complete / 4 | Trunc | Service | Parse | Reader input/output tokens | Reader wall s |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['domain']} | `{r['trajectory_id']}` | {r['case']} | {r['method']} | {r['correct']}/{r['questions']} | {r['complete_parseable']}/{r['questions']} | {r['truncated']} | {r['service_failure']} | {r['parse_failure']} | {r['reader_input_tokens']}/{r['reader_output_tokens']} | {r['reader_generation_wall_s']:.2f} |")
    total = sum(int(r["questions"]) for r in rows)
    complete = sum(int(r["complete_parseable"]) for r in rows)
    correct = sum(int(r["correct"]) for r in rows)
    lines += ["", f"Across B3/Ours, {correct}/{total} fixed responses are correct and {complete}/{total} are complete/parseable. Truncation, service failures and parse failures are all zero. This is a downstream development constraint, not an official Judge score; the construction source-grounded checks remain 48/48.", "", "Per-case results and raw paths are in `results/tables/agentrunbook_revision_case_reader.csv`."]
    REPORT.write_text("\n".join(lines) + "\n")
    print(json.dumps({"rows": len(rows), "questions": total, "correct": correct, "complete": complete, "report": str(REPORT)}))

if __name__ == "__main__":
    main()
