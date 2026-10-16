#!/usr/bin/env python3
"""Aggregate the frozen focused-maintenance formal Small results.

The report intentionally keeps update cost, retrieval/Reader cost, embedding
cost, source-grounded checks, and downstream answer quality in separate
columns.  It never fills missing costs with zero and preserves raw paths.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAL = ROOT / "runs/focused-maintenance-v4/formal"
OUT = ROOT / "results/tables/focused-maintenance-v4"
FIG = ROOT / "results/figures/focused-maintenance-v4"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

POLICIES = ("b3", "source_only", "source_coalesced")
DOMAINS = ("web", "enterprise")


def load(path: Path):
    return json.loads(path.read_text())


def initial_info(domain: str) -> tuple[str, str | float | None]:
    if domain == "web":
        p = FORMAL / "web-initial/memory_build_summary.json"
        return "fresh_10_trajectory_build", load(p)["elapsed_seconds"]
    return ("reused_10_trajectory_snapshot; selected partition preparation only", None)


def rows() -> tuple[list[dict], list[dict]]:
    main: list[dict] = []
    answers: list[dict] = []
    for domain in DOMAINS:
        init_scope, init_s = initial_info(domain)
        for policy in POLICIES:
            base = FORMAL / f"{domain}-update/literal_revision-{policy}"
            update = load(base / "update_metrics.json")
            reader = load(base / "revision_reader/aggregated_metrics.json")
            status = reader["answer_status"]
            tokens = reader["tokens"]
            timing = reader["timing"]
            update_tokens = (update["llm_input_tokens_known"] or 0) + (update["llm_output_tokens_known"] or 0)
            reader_tokens = tokens["prompt_tokens"] + tokens["completion_tokens"]
            main.append({
                "stage": "formal_small_maintenance",
                "domain": domain,
                "history_trajectories": 10,
                "revision_id": "web:1ad1af4b/title" if domain == "web" else "enterprise:0ab99e0c/count",
                "policy": policy,
                "initial_cost_scope": init_scope,
                "initial_build_s": init_s,
                "update_publish_s": update["update_to_queryable_publish_s"],
                "update_llm_calls": update["llm_calls"],
                "update_llm_input_tokens": update["llm_input_tokens_known"],
                "update_llm_output_tokens": update["llm_output_tokens_known"],
                "embedding_calls": update["embedding_calls"],
                "embedding_vectors": update["embedding_vectors"],
                "embedding_input_tokens": update["embedding_tokens_known"],
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
                "source_checks": update["qa_status"],
                "raw_update_path": str(base.relative_to(ROOT)),
                "raw_reader_path": str((base / "revision_reader").relative_to(ROOT)),
            })
            for line in (base / "revision_reader/per_question.jsonl").read_text().splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                answers.append({
                    "domain": domain, "policy": policy,
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
    return main, answers


def write_csv(path: Path, data: list[dict]) -> None:
    fields = list(data[0]) if data else []
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)


def write_svg(main: list[dict]) -> None:
    # Stacked bars: update LLM tokens (dark) + query/Reader LLM tokens (light).
    width, height = 980, 560
    left, top, plot_w, plot_h = 100, 55, 820, 385
    maxv = max(r["update_plus_query_llm_tokens"] for r in main) * 1.18
    bar_w = 92
    gap = 38
    colors = {"b3": "#315b9a", "source_only": "#d47b2c", "source_coalesced": "#3b8f6b"}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<style>text{font-family:Arial,sans-serif;fill:#222}.small{font-size:12px}.axis{stroke:#777;stroke-width:1}.grid{stroke:#ddd;stroke-width:1}</style>',
             '<text x="100" y="25" font-size="18" font-weight="bold">Formal maintenance cost: update + fixed Reader tokens</text>']
    for i in range(5):
        y = top + plot_h - i * plot_h / 4
        value = maxv * i / 4
        parts.append(f'<line class="grid" x1="{left}" x2="{left+plot_w}" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text class="small" x="{left-8}" y="{y+4:.1f}" text-anchor="end">{value/1000:.0f}k</text>')
    parts.append(f'<line class="axis" x1="{left}" x2="{left}" y1="{top}" y2="{top+plot_h}"/><line class="axis" x1="{left}" x2="{left+plot_w}" y1="{top+plot_h}" y2="{top+plot_h}"/>')
    x = left + 40
    for domain in DOMAINS:
        parts.append(f'<text x="{x+bar_w+gap}" y="{top+plot_h+38}" text-anchor="middle" font-weight="bold">{domain}</text>')
        for policy in POLICIES:
            row = next(r for r in main if r["domain"] == domain and r["policy"] == policy)
            total = row["update_plus_query_llm_tokens"]
            update = (row["update_llm_input_tokens"] or 0) + (row["update_llm_output_tokens"] or 0)
            query = total - update
            h_update = update / maxv * plot_h
            h_query = query / maxv * plot_h
            y0 = top + plot_h
            if h_update:
                parts.append(f'<rect x="{x}" y="{y0-h_update:.1f}" width="{bar_w}" height="{h_update:.1f}" fill="{colors[policy]}"/>')
            parts.append(f'<rect x="{x}" y="{y0-h_update-h_query:.1f}" width="{bar_w}" height="{h_query:.1f}" fill="{colors[policy]}" opacity="0.35"/>')
            parts.append(f'<text class="small" x="{x+bar_w/2}" y="{y0-h_update-h_query-6:.1f}" text-anchor="middle">{total/1000:.1f}k</text>')
            parts.append(f'<text class="small" x="{x+bar_w/2}" y="{top+plot_h+18}" text-anchor="middle">{policy.replace("source_","")}</text>')
            x += bar_w + 16
        x += gap
    parts.append(f'<text class="small" transform="translate(20,{top+plot_h/2}) rotate(-90)" text-anchor="middle">tokens</text>')
    parts.append('<text class="small" x="560" y="535" text-anchor="middle">dark = update LLM tokens; translucent = query/Reader LLM tokens</text>')
    parts.append('</svg>')
    (FIG / "focused-maintenance-v4-formal-cumulative.svg").write_text("\n".join(parts))


def main() -> None:
    main_rows, answer_rows = rows()
    write_csv(OUT / "public_main.csv", main_rows)
    compare = []
    for domain in DOMAINS:
        domain_rows = [r for r in main_rows if r["domain"] == domain]
        b3 = next(r for r in domain_rows if r["policy"] == "b3")
        b3_update = (b3["update_llm_input_tokens"] or 0) + (b3["update_llm_output_tokens"] or 0)
        for r in domain_rows:
            update_tokens = (r["update_llm_input_tokens"] or 0) + (r["update_llm_output_tokens"] or 0)
            compare.append({
                "domain": domain, "method": r["policy"],
                "update_llm_tokens": update_tokens,
                "update_publish_s": r["update_publish_s"],
                "embedding_input_tokens": r["embedding_input_tokens"],
                "fixed_reader_tokens": r["query_reader_input_tokens"] + r["query_reader_output_tokens"],
                "reader_correct": f"{r["reader_correct"]}/{r["reader_scored"]}",
                "complete_parseable": f"{r["reader_complete_parseable"]}/{r["reader_scored"]}",
                "update_token_delta_vs_b3": update_tokens - b3_update,
                "publish_delta_s_vs_b3": r["update_publish_s"] - b3["update_publish_s"],
                "source_checks": r["source_checks"],
                "raw_update_path": r["raw_update_path"],
                "raw_reader_path": r["raw_reader_path"],
            })
    write_csv(OUT / "source_only_compare.csv", compare)
    write_csv(OUT / "formal_reader_answers.csv", answer_rows)

    ablation = []
    for domain in DOMAINS:
        domain_rows = [r for r in main_rows if r["domain"] == domain]
        for policy in POLICIES:
            r = next(x for x in domain_rows if x["policy"] == policy)
            b3 = next(x for x in domain_rows if x["policy"] == "b3")
            ablation.append({
                "domain": domain, "component": policy,
                "update_llm_tokens": (r["update_llm_input_tokens"] or 0) + (r["update_llm_output_tokens"] or 0),
                "update_publish_s": r["update_publish_s"],
                "embedding_input_tokens": r["embedding_input_tokens"],
                "fixed_query_reader_tokens": r["query_reader_input_tokens"] + r["query_reader_output_tokens"],
                "fixed_reader_correct": f"{r["reader_correct"]}/{r["reader_scored"]}",
                "delta_update_tokens_vs_b3": ((r["update_llm_input_tokens"] or 0) + (r["update_llm_output_tokens"] or 0)) - ((b3["update_llm_input_tokens"] or 0) + (b3["update_llm_output_tokens"] or 0)),
                "delta_publish_s_vs_b3": r["update_publish_s"] - b3["update_publish_s"],
                "source_checks": r["source_checks"],
            })
    write_csv(OUT / "ablation.csv", ablation)
    write_svg(main_rows)

    report = [
        "# Focused-maintenance-v4 formal Small maintenance",
        "",
        "Scope: frozen text-only/adapted Small history libraries, 10 complete trajectories per domain, one predeclared revision and two fixed dynamic questions per domain. Reader is Qwen3.5-9B, thinking disabled, 2,048 completion tokens and 12,000 memory-context tokens. The enterprise initial snapshot is a legal reused 10-trajectory build; its historical construction cost is not silently presented as a new cold-build measurement.",
        "",
        "## Main result",
        "",
        "The formal update cost is strongly lower for Source-only and source_coalesced than B3: both use zero update LLM calls on these fixed literal corrections. Source-only uses fewer embedding vectors than the coalesced representation, while coalesced preserves current evidence blocks and 13 unaffected event dependencies. The downstream Reader constraint is not maintained uniformly: web scores are B3 2/2, Source-only 0/2, coalesced 1/2; enterprise scores are 1/2 for all three. All 12 responses are complete and parseable with zero truncation, service failures, or parse failures. Therefore the formal result supports a cost reduction, but not a claim of quality equivalence or a universally superior method.",
        "",
        "## Quality and failure interpretation",
        "",
        "Source-grounded checks pass for both Source-only formal branches and fail the predeclared coalesced lexical rule on both domains because the generated event text does not retain every requested neighboring fact. This is retained as a limitation rather than repaired after looking at scores. The fixed Reader answers are recorded per question in `results/tables/focused-maintenance-v4/formal_reader_answers.csv`; semantic Judge scoring is not used.",
        "",
        "## Cost accounting",
        "",
        "Update wall time includes artifact construction, embedding, save/reload and queryable publication. Reader prompt construction, retrieval and Reader generation are reported separately; the cumulative figure adds update LLM tokens to fixed Reader prompt/output tokens and never substitutes embedding tokens for LLM tokens. Raw paths in `public_main.csv` point to the persisted metrics and Reader records.",
        "",
        "## Reproducibility and boundary",
        "",
        "This is a formal adapted maintenance experiment, not native multimodal Small and not a cold-construction comparison. The public Raw RAG/RAG+Notes maintenance adapters remain deferred under execution-ready-r2-freeze; no incompatible historical row is mixed into this table.",
    ]
    (ROOT / "reports/focused-maintenance-v4-formal.md").write_text("\n".join(report) + "\n")
    print(json.dumps({"rows": len(main_rows), "answers": len(answer_rows), "table": str(OUT / "public_main.csv"), "figure": str(FIG / "focused-maintenance-v4-formal-cumulative.svg")}))


if __name__ == "__main__":
    main()
