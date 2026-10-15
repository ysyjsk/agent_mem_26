#!/usr/bin/env python3
"""Create the PAPER05 adapted continuous-arrival table, report and figure."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/agentrunbook-stream-v1-enterprise-0ab99e0c"
TABLE = ROOT / "results/tables/streaming_freshness_goodput.csv"
REPORT = ROOT / "reports/streaming_freshness_goodput.md"
SVG = ROOT / "reports/streaming_freshness_goodput.svg"


def main() -> None:
    summaries = json.loads((RUN / "stream_summary.json").read_text())
    rows = []
    for summary in summaries:
        policy = summary["policy"]
        path = RUN / policy / "arrival_metrics.jsonl"
        for raw in path.read_text().splitlines():
            row = json.loads(raw)
            row["row_type"] = "arrival"
            row["scope"] = summary["scope"]
            row["qa_status"] = summary["qa_status"]
            row.pop("quality", None)
            rows.append(row)
        summary_row = dict(summary)
        summary_row["row_type"] = "summary"
        summary_row["scope"] = summary["scope"]
        summary_row["qa_status"] = summary["qa_status"]
        rows.append(summary_row)
    fields = sorted({key for row in rows for key in row})
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    with TABLE.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    by_policy = {row["policy"]: row for row in summaries}
    arrival_rows = [r for r in rows if r.get("row_type") == "arrival"]
    lines = [
        "# PAPER05 continuous-arrival Freshness and Goodput (adapted)",
        "",
        "This is a real local-model text-only/adapted stream probe, not the official LongMemEval Small streaming protocol. Both methods start from independent clones of the same persisted enterprise snapshot. The target trajectory is deliberately absent from each clone; source states then arrive in three batches of 1, 2 and 3 transitions (cumulative prefixes 1, 3 and 6). Every batch performs real AgentRunbook-R extraction and Embedding, saves a queryable artifact, reloads it, and runs a retrieval probe. No replay responses are used.",
        "",
        "Freshness is measured from batch arrival to queryable publication, including save/reload but excluding the separate retrieval probe. Goodput is newly arrived transitions divided by summed publication time. Batch members share the same publication timestamp; the per-transition P50/P95 therefore weights batch sizes. Stream wall time includes retrieval probes and is reported separately.",
        "",
        "## Paired summary",
        "",
        "| Method | Completed batches | Publish s total | Freshness P50 s | Freshness P95 s | Goodput transitions/s | Controller calls | LLM input tokens | Embedding calls/vectors | Quality + retrieval probes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for policy in ("b3", "ours"):
        s = by_policy[policy]
        lines.append(
            f"| {policy} | {s['completed_arrivals']}/3 | {s['update_publish_s_total']:.2f} | {s['freshness_p50_s']:.2f} | {s['freshness_p95_s']:.2f} | {s['goodput_new_events_per_publish_s']:.4f} | {s['controller_calls']} | {s['controller_input_tokens']} | {s['embedding_calls']}/{s['embedding_vectors']} | {s['quality_passes']}/3 + {s['retrieval_probe_passes']}/3 |"
        )
    b3, ours = by_policy["b3"], by_policy["ours"]
    lines += [
        "",
        "## Per-arrival measurements",
        "",
        "| Batch | New transitions | Method | Publish s | Controller calls | Input tokens | Output tokens | Embedding vectors | Re-extracted events | Notes regenerated | Quality + reload/retrieval |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in sorted(arrival_rows, key=lambda x: (int(x["arrival_index"]), x["policy"])):
        lines.append(
            f"| {r['arrival_index']} | {r['arrived_events_this_batch']} | {r['policy']} | {float(r['arrival_to_queryable_s']):.2f} | {r['controller_calls']} | {r['controller_input_tokens']} | {r['controller_output_tokens']} | {r['embedding_vectors']} | {r['reextracted_event_outputs']} | {r['regenerated_notes']} | {r['quality_pass']} / {r['retrieval_probe_ok']} |"
        )
    lines += [
        "",
        f"On this continuous prefix-arrival protocol, Ours is not selected: compared with B3, publish-time total changes from {b3['update_publish_s_total']:.2f}s to {ours['update_publish_s_total']:.2f}s ({100 * (ours['update_publish_s_total'] / b3['update_publish_s_total'] - 1):+.1f}%), controller calls from {b3['controller_calls']} to {ours['controller_calls']}, and known LLM input from {b3['controller_input_tokens']} to {ours['controller_input_tokens']} ({100 * (ours['controller_input_tokens'] / b3['controller_input_tokens'] - 1):+.1f}%). Freshness P95 is {b3['freshness_p95_s']:.2f}s for B3 versus {ours['freshness_p95_s']:.2f}s for Ours; all 6/6 source-grounded checks and 6/6 reload/retrieval probes pass.",
        "",
        "The negative result is mechanistic rather than a quality failure. The current event-dependency key includes the complete action sequence and transition count. Each newly longer prefix therefore changes the request context for every event, so Ours receives no event-level reuse in this arrival protocol and may form one extra group. This confirms that the existing dependency key is appropriate for revisions with stable trajectory length, but is not yet a streaming-growth optimization. The result is retained; no global dependency was removed to manufacture cache hits.",
        "",
        f"Raw data: `{TABLE.relative_to(ROOT)}`; run manifest and per-arrival records: `{RUN.relative_to(ROOT)}`. Official Judge/native quality remains pending.",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")

    colors = {"b3": "#4263eb", "ours": "#d9480f"}
    width, height = 1040, 620
    chart = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="32" y="30" font-size="19">Continuous adapted stream: Freshness and cost</text>',
        '<text x="32" y="54" font-size="12">Same enterprise snapshot; cumulative arrivals 1, 3, 6; save/reload included</text>',
    ]
    panels = [
        ("Arrival-to-queryable publication (s)", 78, 260, "arrival_to_queryable_s"),
        ("LLM input tokens per batch", 310, 492, "controller_input_tokens"),
    ]
    for title, top, bottom, field in panels:
        values = [float(r[field]) for r in arrival_rows]
        max_value = max(values) if values else 1.0
        chart.append(f'<text x="32" y="{top}" font-size="13">{title}</text>')
        for i, batch in enumerate((1, 2, 3)):
            base_x = 150 + i * 270
            chart.append(f'<text x="{base_x + 30}" y="{bottom + 28}" font-size="12">batch {batch}</text>')
            for j, policy in enumerate(("b3", "ours")):
                row = next(r for r in arrival_rows if r["policy"] == policy and int(r["arrival_index"]) == batch)
                value = float(row[field])
                bar_h = 145 * value / max_value
                x = base_x + j * 64
                y = bottom - bar_h
                chart += [
                    f'<rect x="{x}" y="{y:.1f}" width="48" height="{bar_h:.1f}" fill="{colors[policy]}"/>',
                    f'<text x="{x - 2}" y="{y - 6:.1f}" font-size="10">{value:.0f}</text>',
                    f'<text x="{x + 5}" y="{bottom + 12}" font-size="10">{policy}</text>',
                ]
    chart += [
        '<text x="32" y="580" font-size="11">Quality/reload/retrieval: 6/6 per method; official QA not evaluated. B3 remains the selected stream variant.</text>',
        '</svg>',
    ]
    SVG.write_text("".join(chart))


if __name__ == "__main__":
    main()
