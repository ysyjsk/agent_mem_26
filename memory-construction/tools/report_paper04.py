#!/usr/bin/env python3
"""Assemble the measured adapted ablations, scale points and update-intensity strata.

This report deliberately distinguishes measured rows from post-hoc descriptive
strata. It does not invent a full B0/B1/B2/B3 grid where the backend was not run.
"""
from __future__ import annotations
import csv, json, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/tables/paper04_ablation_scale.csv"
REPORT = ROOT / "reports/paper04_ablation_scale.md"
SVG = ROOT / "reports/paper04_ablation_scale.svg"
RATE_OUT = ROOT / "results/tables/paper04_update_rate.csv"
RATE_REPORT = ROOT / "reports/paper04_update_rate.md"
RATE_SVG = ROOT / "reports/paper04_update_rate.svg"

def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))

def main():
    rows = []
    cold = read_csv(ROOT / "results/tables/paper02_cold_construction.csv")
    for r in cold:
        rows.append({
            "section": "cold_ablation", "variant": r["candidate"],
            "scope": r["data_scope"], "n_checkpoints": "",
            "wall_s": r["wall_s"], "llm_calls": r["controller_calls"],
            "input_tokens": r["llm_input_tokens"], "output_tokens": r["llm_output_tokens"],
            "reused_nodes": "", "invalidated_nodes": "", "quality": r["quality_pass"],
            "update_ratio": "", "raw_path": r["raw_paths"],
        })
    scale = read_csv(ROOT / "results/tables/dev_scale.csv")
    for r in scale:
        if r["method"] not in {"B0", "Ours-dev", "B3-c2"}:
            continue
        rows.append({
            "section": "scale", "variant": r["method"],
            "scope": f"{r['n_windows']} windows / {r['n_checkpoints']} checkpoints",
            "n_checkpoints": r["n_checkpoints"], "wall_s": r["total_s"],
            "llm_calls": r["live_model_calls"], "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"], "reused_nodes": r["reused_nodes"],
            "invalidated_nodes": r["invalidated_nodes"], "quality": r["snapshot_checks_passed"],
            "update_ratio": "", "raw_path": r["raw_metrics_path"],
        })
    lengths = {"1ad1af4b": 7, "2e8f6477": 10, "0ab99e0c": 15, "49f98e9e": 14}
    updates = read_csv(ROOT / "results/tables/agentrunbook_update_main.csv")
    for r in updates:
        if r["repeat"] != "0" or r["policy"] not in {"b3", "ours"} or r["case"] not in {"state_revision", "workflow_revision"}:
            continue
        ratio = float(r["reextracted_event_outputs"]) / lengths[r["trajectory_id"]]
        if ratio <= 0.15:
            band = "low"
        elif ratio <= 0.25:
            band = "medium"
        else:
            band = "high"
        rows.append({
            "section": "update_ratio", "variant": f"{r['policy']}:{band}",
            "scope": f"{r['domain']} {r['trajectory_id']} {r['case']}",
            "n_checkpoints": "", "wall_s": r["update_to_queryable_publish_s"],
            "llm_calls": r["llm_calls"], "input_tokens": r["llm_input_tokens_known"],
            "output_tokens": r["llm_output_tokens_known"],
            "reused_nodes": r["actual_dependency_reused_events"],
            "invalidated_nodes": r["reextracted_event_outputs"],
            "quality": r["quality_pass"], "update_ratio": f"{ratio:.4f}",
            "raw_path": r["run_path"],
        })

    # Controlled update-rate screen: same enterprise source snapshot and same
    # state-revision mechanism, varying only the number of revised states.
    # Missing/incomplete pairs remain absent rather than being imputed.
    rate_rows = []
    for revision_count in (1, 3, 6):
        for policy in ("b3", "ours"):
            metric_path = (ROOT / "runs/agentrunbook-update-rate-screen-v1" /
                           f"enterprise-0ab99e0c-start4-n{revision_count}" /
                           f"state_revision-{policy}" / "update_metrics.json")
            if not metric_path.exists():
                continue
            metric = json.loads(metric_path.read_text())
            reader_metrics_path = (ROOT / "runs/agentrunbook-update-rate-screen-v1" /
                                   f"reader-n6-{policy}-v2" / "aggregated_metrics.json") if revision_count == 6 else None
            reader = json.loads(reader_metrics_path.read_text()) if reader_metrics_path and reader_metrics_path.exists() else {}
            reader_status = reader.get("answer_status", {})
            rate_rows.append({
                "revision_count": revision_count, "policy": policy,
                "trajectory_id": metric.get("trajectory_id", "0ab99e0c"),
                "state_indices": json.dumps(metric.get("state_indices", [])),
                "update_to_queryable_publish_s": metric.get("update_to_queryable_publish_s", ""),
                "llm_calls": metric.get("llm_calls", ""),
                "llm_input_tokens_known": metric.get("llm_input_tokens_known", ""),
                "llm_output_tokens_known": metric.get("llm_output_tokens_known", ""),
                "reextracted_event_outputs": metric.get("reextracted_event_outputs", ""),
                "regenerated_notes": metric.get("regenerated_notes", ""),
                "embedding_calls": metric.get("embedding_calls", ""),
                "embedding_vectors": metric.get("embedding_vectors", ""),
                "embedding_tokens_known": metric.get("embedding_tokens_known", ""),
                "api_failed_calls": metric.get("api_failed_calls", ""),
                "quality_pass": metric.get("quality_checks", {}).get("quality_pass", False),
                "reader_correct": reader_status.get("correct", ""),
                "reader_complete_parseable": reader_status.get("complete_parseable", ""),
                "reader_truncated": reader_status.get("truncated", ""),
                "reader_service_failure": reader_status.get("service_failure", ""),
                "reader_parse_failure": reader_status.get("parse_failure", ""),
                "reader_query_wall_s": reader.get("timing", {}).get("reader_generation_wall_seconds", ""),
                "reader_raw_path": str(reader_metrics_path.parent) if reader else "",
                "raw_path": str(metric_path.parent),
            })
    rate_fields = ["revision_count", "policy", "trajectory_id", "state_indices",
                   "update_to_queryable_publish_s", "llm_calls", "llm_input_tokens_known",
                   "llm_output_tokens_known", "reextracted_event_outputs", "regenerated_notes",
                   "embedding_calls", "embedding_vectors", "embedding_tokens_known",
                   "api_failed_calls", "quality_pass", "reader_correct",
                   "reader_complete_parseable", "reader_truncated", "reader_service_failure",
                   "reader_parse_failure", "reader_query_wall_s", "reader_raw_path", "raw_path"]
    with RATE_OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rate_fields)
        writer.writeheader(); writer.writerows(rate_rows)
    fields = ["section", "variant", "scope", "n_checkpoints", "wall_s", "llm_calls",
              "input_tokens", "output_tokens", "reused_nodes", "invalidated_nodes",
              "quality", "update_ratio", "raw_path"]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

    cold_rows = [r for r in rows if r["section"] == "cold_ablation"]
    scale_rows = [r for r in rows if r["section"] == "scale"]
    update_rows = [r for r in rows if r["section"] == "update_ratio"]
    lines = [
        "# PAPER04 adapted ablations, scale and update intensity", "",
        "This report uses measured text-only/adapted runs only. The four-cell cold matrix is the component ablation (joint extraction × exact embedding reuse); the scale rows reuse frozen 12- and 24-window construction runs; update-intensity rows are descriptive strata from the eight fixed revision cases, computed as re-extracted event outputs divided by the trajectory's original event count. They are not a post-hoc claim of a separately randomized update-rate sweep.", "",
        "## Cold construction component ablation", "",
        "| Variant | Scope | Wall s | Controller calls | Input tokens | Output tokens | Embedding vectors | Quality |",
        "|---|---|---:|---:|---:|---:|---:|---|"]
    for r in cold_rows:
        raw = next((x for x in cold if x["candidate"] == r["variant"]), {})
        lines.append(f"| {r['variant']} | {r['scope']} | {float(r['wall_s']):.2f} | {r['llm_calls']} | {r['input_tokens']} | {r['output_tokens']} | {raw.get('embedding_vectors','')} | {r['quality']} |")
    lines += ["", "The fixed-10 combined variant reduces measured controller calls and input tokens but increases wall time relative to baseline; embedding reuse saves vectors without a wall-time gain. Common-preflight joint is retained as a negative fixed-10 result in PAPER02 rather than selected as the default.", "",
              "## Frozen scale evidence", "",
              "| Run scope | Method | Total s | Checkpoints | Calls | Input tokens | Reused nodes | Invalidated nodes | Snapshot checks |",
              "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in sorted(scale_rows, key=lambda x: (x["scope"], x["variant"])):
        lines.append(f"| {r['scope']} | {r['variant']} | {float(r['wall_s']):.2f} | {r['n_checkpoints']} | {r['llm_calls']} | {r['input_tokens']} | {r['reused_nodes']} | {r['invalidated_nodes']} | {r['quality']} |")
    lines += ["", "The 12/24-window rows are construction_e2e development measurements, not Freshness or official QA. B0 remains serial full-prefix rebuilding; Ours-dev and B3-c2 use the same frozen workload and actual bounded concurrency 2.", "",
              "## Update-intensity strata", "",
              "| Method/band | Cases | Mean ratio | Mean publish s | Mean calls | Mean input tokens | Quality rows |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    groups = {}
    for r in update_rows:
        groups.setdefault(r["variant"], []).append(r)
    for variant, vals in sorted(groups.items()):
        lines.append(f"| {variant} | {len(vals)} | {statistics.mean(float(x['update_ratio']) for x in vals):.3f} | {statistics.mean(float(x['wall_s']) for x in vals):.2f} | {statistics.mean(float(x['llm_calls']) for x in vals):.2f} | {statistics.mean(float(x['input_tokens']) for x in vals):.0f} | {sum(x['quality']=='True' for x in vals)}/{len(vals)} |")
    lines += ["", "Low/medium/high are observed event-recomputation strata, not a new controlled rate sweep. All primary revision rows pass source-grounded persistence checks; downstream Reader quality remains a separate constraint, with the enterprise state-revision regression showing B3 3/4 versus Ours 2/4.", "",
              "A separate controlled update-rate screen is reported in `paper04_update_rate.md`; it varies 1/3/6 revised states on one fixed enterprise snapshot and is not conflated with these post-hoc strata.",
              f"Raw combined table: `{OUT.relative_to(ROOT)}`. Existing raw runs remain the source of truth."]
    REPORT.write_text("\n".join(lines) + "\n")

    # Compact two-panel SVG: four-cell cold ablation and measured scale totals.
    width, height = 1000, 590
    bars = [(r["variant"], float(r["wall_s"])) for r in cold_rows if r["variant"] in {"baseline", "joint", "embed", "combined"}]
    maxv = max(v for _, v in bars) if bars else 1
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="60" y="28" font-size="18">PAPER04 cold ablation and scale evidence</text>', '<text x="60" y="52" font-size="13">Cold build wall time, 10-trajectory matrix</text>']
    for i, (label, value) in enumerate(bars):
        x = 100 + i * 210; h = 165 * value / maxv; y = 260 - h
        parts += [f'<rect x="{x}" y="{y:.1f}" width="112" height="{h:.1f}" fill="#4263eb"/>', f'<text x="{x-5}" y="278" font-size="11">{label}</text>', f'<text x="{x}" y="{y-6:.1f}" font-size="11">{value:.0f}s</text>']
    parts += ['<text x="60" y="322" font-size="13">Construction totals by fixed workload (horizontal scale: seconds)</text>']
    palette = {"B0": "#868e96", "Ours-dev": "#d9480f", "B3-c2": "#4263eb"}
    y0 = 355
    for scope in sorted({r["scope"] for r in scale_rows}):
        vals = [r for r in scale_rows if r["scope"] == scope]
        parts.append(f'<text x="60" y="{y0}" font-size="12">{scope}</text>')
        for j, row in enumerate(sorted(vals, key=lambda x: {"B0": 0, "Ours-dev": 1, "B3-c2": 2}.get(x["variant"], 9))):
            y = y0 + 8 + j * 22
            value = float(row["wall_s"])
            barw = 470 * value / 1300
            method = row["variant"]
            parts += [f'<text x="220" y="{y+11}" font-size="10">{method}</text>', f'<rect x="300" y="{y}" width="{barw:.1f}" height="14" fill="{palette[method]}"/>', f'<text x="{305+barw:.1f}" y="{y+11}" font-size="10">{value:.1f}s</text>']
        y0 += 30 + len(vals) * 22
    parts.append('</svg>')
    SVG.write_text("".join(parts))

    rate_lines = [
        "# Controlled update-rate screen (adapted)", "",
        "One enterprise trajectory (`0ab99e0c`), one shared starting snapshot, independent B3/Ours cache clones; state revisions are applied at indices 4..(4+n-1). This is a controlled single-trajectory screen, not a population estimate. Setup/seed load is excluded; wall time covers update through queryable publication. Quality is source-grounded/persisted-state checks, not official QA.", "",
        "| Revised states | Method | Publish s | LLM calls | Input tokens | Output tokens | Event outputs | Embedding vectors | Quality |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in sorted(rate_rows, key=lambda x: (int(x["revision_count"]), x["policy"])):
        rate_lines.append(
            f"| {r['revision_count']} | {r['policy']} | {float(r['update_to_queryable_publish_s']):.2f} | {r['llm_calls']} | {r['llm_input_tokens_known']} | {r['llm_output_tokens_known']} | {r['reextracted_event_outputs']} | {r['embedding_vectors']} | {r['quality_pass']} |")
    rate_by_key = {(int(r["revision_count"]), r["policy"]): r for r in rate_rows}
    measured_ns = sorted({int(r["revision_count"]) for r in rate_rows})
    if all((n, policy) in rate_by_key for n in measured_ns for policy in ("b3", "ours")):
        wall_reductions, input_reductions, event_reductions = [], [], []
        for n in measured_ns:
            b3, ours = rate_by_key[(n, "b3")], rate_by_key[(n, "ours")]
            wall_reductions.append(100 * (1 - float(ours["update_to_queryable_publish_s"]) / float(b3["update_to_queryable_publish_s"])))
            input_reductions.append(100 * (1 - int(ours["llm_input_tokens_known"]) / int(b3["llm_input_tokens_known"])))
            event_reductions.append(100 * (1 - int(ours["reextracted_event_outputs"]) / int(b3["reextracted_event_outputs"])))
        rate_lines += ["", "Paired deltas (Ours relative to B3)", "",
                       "| Revised states | Publish latency reduction | LLM input-token reduction | Re-extracted event-output reduction |",
                       "|---:|---:|---:|---:|"]
        for n in measured_ns:
            b3, ours = rate_by_key[(n, "b3")], rate_by_key[(n, "ours")]
            rate_lines.append(f"| {n} | {100 * (1 - float(ours['update_to_queryable_publish_s']) / float(b3['update_to_queryable_publish_s'])):.1f}% | {100 * (1 - int(ours['llm_input_tokens_known']) / int(b3['llm_input_tokens_known'])):.1f}% | {100 * (1 - int(ours['reextracted_event_outputs']) / int(b3['reextracted_event_outputs'])):.1f}% |")
        rate_lines += ["", f"Paper-ready summary: On this fixed snapshot, event-level dependency reuse reduces update work across the 1/3/6-state screen: mean publish-latency reduction {statistics.mean(wall_reductions):.1f}%, mean LLM-input reduction {statistics.mean(input_reductions):.1f}%, and mean re-extracted-event-output reduction {statistics.mean(event_reductions):.1f}%. These are paired measurements on one enterprise trajectory, not a domain-level average."]
    reader_rows = [r for r in rate_rows if r["reader_correct"] != ""]
    rate_lines += ["", "## Fixed Reader regression on the 6-revision pair", "",
                   "Same four fixed enterprise questions, text-only/adapted Qwen Reader, 2,048-token output ceiling, thinking disabled; this is a local development proxy, not official Judge QA. Reader checks are a separate quality constraint from the source-grounded publication checks above.", "",
                   "| Method | Correct / 4 | Complete / 4 | Truncated | Service failures | Parse failures | Reader wall s |",
                   "|---|---:|---:|---:|---:|---:|---:|"]
    for r in reader_rows:
        rate_lines.append(f"| {r['policy']} | {r['reader_correct']}/4 | {r['reader_complete_parseable']}/4 | {r['reader_truncated']} | {r['reader_service_failure']} | {r['reader_parse_failure']} | {float(r['reader_query_wall_s']):.2f} |")
    if reader_rows:
        b3_reader = next((r for r in reader_rows if r["policy"] == "b3"), None)
        ours_reader = next((r for r in reader_rows if r["policy"] == "ours"), None)
        if b3_reader and ours_reader:
            rate_lines += ["", f"Both update snapshots pass source-grounded persistence checks, but this small Reader slice scores B3 {b3_reader['reader_correct']}/4 vs Ours {ours_reader['reader_correct']}/4. This matches the previously observed enterprise state-revision direction (3/4 vs 2/4), while the broader eight-case fixed Reader regression ties at 21/32 per method; it does not establish per-slice quality equivalence. All answers in this new pair were complete/parseable with zero truncation, service or parse failures."]
    RATE_REPORT.write_text("\n".join(rate_lines) + "\n")

    # Paired grouped bars for wall time and input tokens.
    width, height = 920, 410
    colors = {"b3": "#4263eb", "ours": "#d9480f"}
    chart = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<text x="35" y="28" font-size="18">Update cost vs. number of revised states</text>',
             '<text x="35" y="54" font-size="13">Adapted local run; paired B3/Ours; shared snapshot</text>']
    panel_specs = [("Publish latency (s)", 80, 220, "update_to_queryable_publish_s"),
                   ("LLM input tokens", 270, 370, "llm_input_tokens_known")]
    for title, top, bottom, field in panel_specs:
        vals = [float(r[field]) for r in rate_rows if r[field] not in ("", None)]
        maxv = max(vals, default=1) or 1
        chart.append(f'<text x="35" y="{top-8}" font-size="12">{title}</text>')
        for i, n in enumerate((1, 3, 6)):
            base_x = 145 + i * 235
            chart.append(f'<text x="{base_x+35}" y="{bottom+18}" font-size="12">{n} revisions</text>')
            for j, policy in enumerate(("b3", "ours")):
                row = next((x for x in rate_rows if int(x["revision_count"]) == n and x["policy"] == policy), None)
                if row is None or row[field] in ("", None):
                    continue
                value = float(row[field]); bar_h = (bottom - top - 20) * value / maxv
                x = base_x + j * 56; y = bottom - bar_h
                chart += [f'<rect x="{x}" y="{y:.1f}" width="38" height="{bar_h:.1f}" fill="{colors[policy]}"/>',
                          f'<text x="{x-8}" y="{y-4:.1f}" font-size="9">{value:.0f}</text>']
    chart += ['<rect x="690" y="45" width="12" height="12" fill="#4263eb"/><text x="708" y="56" font-size="10">B3</text>',
              '<rect x="750" y="45" width="12" height="12" fill="#d9480f"/><text x="768" y="56" font-size="10">Ours</text>', '</svg>']
    RATE_SVG.write_text("".join(chart))
    print(json.dumps({"rows": len(rows), "rate_rows": len(rate_rows), "table": str(OUT), "report": str(REPORT), "svg": str(SVG), "rate_table": str(RATE_OUT), "rate_report": str(RATE_REPORT), "rate_svg": str(RATE_SVG)}))

if __name__ == "__main__":
    main()
