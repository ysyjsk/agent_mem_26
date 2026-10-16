#!/usr/bin/env python3
"""Aggregate frozen formal mechanism ablations without mixing versions."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAL = ROOT / "runs/focused-maintenance-v4/formal"
OUT = ROOT / "results/tables/focused-maintenance-v4"
POLICIES = ("source_overlay", "delta_guarded")
DOMAINS = ("web", "enterprise")


def load(path: Path):
    return json.loads(path.read_text())


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows: list[dict] = []
    answers: list[dict] = []
    for domain in DOMAINS:
        branch_root = FORMAL / f"{domain}-ablation-update"
        for policy in POLICIES:
            base = branch_root / f"literal_revision-{policy}"
            update = load(base / "update_metrics.json")
            reader = load(base / "revision_reader/aggregated_metrics.json")
            status = reader["answer_status"]
            tokens = reader["tokens"]
            timing = reader["timing"]
            update_tokens = (update.get("llm_input_tokens_known") or 0) + (update.get("llm_output_tokens_known") or 0)
            reader_tokens = tokens["prompt_tokens"] + tokens["completion_tokens"]
            rows.append({
                "stage": "formal_small_mechanism_ablation",
                "domain": domain,
                "history_trajectories": 10,
                "revision_id": "web:1ad1af4b/title" if domain == "web" else "enterprise:0ab99e0c/count",
                "policy": policy,
                "update_publish_s": update["update_to_queryable_publish_s"],
                "update_llm_calls": update.get("llm_calls"),
                "update_llm_input_tokens": update.get("llm_input_tokens_known"),
                "update_llm_output_tokens": update.get("llm_output_tokens_known"),
                "embedding_calls": update.get("embedding_calls"),
                "embedding_vectors": update.get("embedding_vectors"),
                "embedding_input_tokens": update.get("embedding_tokens_known"),
                "query_prompt_build_s": timing["prompt_build_wall_seconds"],
                "query_retrieval_s": reader["memory_query"]["total_seconds"],
                "reader_generation_s": timing["reader_generation_wall_seconds"],
                "query_reader_input_tokens": tokens["prompt_tokens"],
                "query_reader_output_tokens": tokens["completion_tokens"],
                "update_plus_query_llm_tokens": update_tokens + reader_tokens,
                "reader_correct": status["correct"],
                "reader_scored": status["scored"],
                "reader_complete_parseable": status["complete_parseable"],
                "reader_truncated": status["truncated"],
                "reader_service_failure": status["service_failure"],
                "reader_parse_failure": status["parse_failure"],
                "source_checks": update.get("qa_status"),
                "raw_update_path": str(base.relative_to(ROOT)),
                "raw_reader_path": str((base / "revision_reader").relative_to(ROOT)),
            })
            for line in (base / "revision_reader/per_question.jsonl").read_text().splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                answers.append({
                    "domain": domain,
                    "policy": policy,
                    "question_id": item["question_id"],
                    "answer_gold": item.get("answer_gold"),
                    "response_parsed": item.get("response_parsed_boxed"),
                    "response_raw": item.get("response_raw"),
                    "correct": item.get("score_bool"),
                    "complete": item.get("reader_answer_complete"),
                    "truncated": item.get("reader_truncated"),
                    "service_failure": item.get("reader_error_type") == "service_failure",
                    "parse_failure": item.get("reader_parse_status") not in ("boxed", "plain"),
                    "raw_path": str((base / "revision_reader/per_question.jsonl").relative_to(ROOT)),
                })
    write_csv(OUT / "formal_ablation_extended.csv", rows)
    write_csv(OUT / "formal_ablation_extended_answers.csv", answers)
    report = [
        "# Focused-maintenance-v4 formal mechanism ablations",
        "",
        "These rows use the same frozen ten-trajectory web/enterprise snapshots, revisions, Reader, retrieval, budgets and query questions as the formal B3/Source-only/source-coalesced table. They add only the predeclared source_overlay and delta_guarded mechanisms; no result is used to tune the frozen method.",
        "",
        "All update, embedding, publication, Reader, parse and source-check fields are copied from persisted metrics. A missing or failed branch remains visible rather than being replaced by a reused number.",
    ]
    (ROOT / "reports/focused-maintenance-v4-ablation.md").write_text("\n".join(report) + "\n")
    print(json.dumps({"rows": len(rows), "answers": len(answers), "table": str(OUT / "formal_ablation_extended.csv")}))


if __name__ == "__main__":
    main()
