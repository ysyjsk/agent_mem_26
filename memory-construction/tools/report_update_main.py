#!/usr/bin/env python3
"""Report the multi-trajectory B3/Ours update experiment.

This report intentionally keeps the fixed Reader regression separate: source-grounded
checks are construction/update invariants, while Reader answers are a downstream
quality sample and are never inferred from save/load success.
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_ROOTS = [
    ROOT / "runs/agentrunbook-updates-main",
    ROOT / "runs/agentrunbook-updates-fresh-fixed",
]
TABLE = ROOT / "results/tables/agentrunbook_update_main.csv"
REPORT = ROOT / "reports/agentrunbook_update_main.md"
SVG = ROOT / "reports/agentrunbook_update_cumulative.svg"
FRESH_SVG = ROOT / "reports/agentrunbook_update_fresh_comparison.svg"
REPEAT_TABLE = ROOT / "results/tables/agentrunbook_update_repeat_summary.csv"


def load_rows():
    rows = []
    for path in sorted(p for run_root in RUN_ROOTS for p in run_root.glob("**/update_metrics.json")):
        parent = path.parent
        if "reader-regression" in str(parent):
            continue
        if "state4-r1" in str(parent):
            # Retain the historical pre-fix checker record on disk, but use
            # the corrected paired rerun in the paper-facing main table.
            continue
        row = json.loads(path.read_text())
        row["run_path"] = str(parent.relative_to(ROOT))
        row["domain"] = "enterprise" if "enterprise" in str(row.get("starting_snapshot", "")) else "web"
        if "repeat3-" in row["run_path"]:
            row["repeat"] = 3
        elif "repeat2-" in row["run_path"]:
            row["repeat"] = 2
        elif "repeat-" in row["run_path"]:
            row["repeat"] = 1
        else:
            row["repeat"] = 0
        quality = dict(row.get("quality_checks") or {})
        # v2 correction for trajectory growth: the original checker compared
        # every unchanged-looking event byte-for-byte, even when the conservative
        # dependency key had invalidated it and the implementation regenerated it.
        # Consult the actual dependency-validation record; only check output
        # completeness for outputs that were genuinely reused. Preserve raw metrics.
        if row.get("case") == "trajectory_growth" and row.get("policy") == "ours":
            calls_path = parent / "update_calls.json"
            calls = json.loads(calls_path.read_text()) if calls_path.is_file() else []
            dependency_rows = [c for c in calls if c.get("channel") == "update_event_dependency" and c.get("status") == "validated"]
            actual_reused = sum(int(c.get("reused") or 0) for c in dependency_rows)
            row["actual_dependency_reused_events"] = actual_reused
            quality["reused_event_count"] = actual_reused
            if actual_reused == 0 and dependency_rows:
                quality["reused_joint_events_complete"] = "not_applicable_no_exact_reuse"
                quality["quality_pass"] = all(bool(quality.get(k)) for k in (
                    "new_fact_present", "old_fact_retained", "untouched_facts_retained", "event_source_coverage"))
            recheck = {
                "checker_version": "growth-quality-v2-actual-cache-hit-scope",
                "raw_quality_check": row.get("quality_checks"),
                "actual_dependency_reused_events": actual_reused,
                "dependency_validation_records": dependency_rows,
                "rechecked_quality": quality,
                "note": "No exact cache hit means regenerated events are not judged as reused outputs; raw metrics remain unchanged.",
            }
            (parent / "quality_recheck.json").write_text(json.dumps(recheck, indent=2) + "\n")
        elif row.get("policy") == "ours":
            calls_path = parent / "update_calls.json"
            calls = json.loads(calls_path.read_text()) if calls_path.is_file() else []
            dependency_rows = [c for c in calls if c.get("channel") == "update_event_dependency" and c.get("status") == "validated"]
            row["actual_dependency_reused_events"] = sum(int(c.get("reused") or 0) for c in dependency_rows) if dependency_rows else ""
        row["quality_pass"] = bool(quality.get("quality_pass"))
        row["quality_new_fact"] = bool(quality.get("new_fact_present"))
        row["quality_old_fact"] = bool(quality.get("old_fact_retained"))
        row["quality_untouched"] = bool(quality.get("untouched_facts_retained"))
        row["quality_event_coverage"] = bool(quality.get("event_source_coverage"))
        row["quality_reuse"] = quality.get("reused_joint_events_complete")
        row["quality_reused_event_count"] = quality.get("reused_event_count", "")
        rows.append(row)
    if len(rows) < 16:
        raise SystemExit(f"expected at least 16 main update rows, found {len(rows)}")
    return rows


def write_table(rows):
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "domain", "trajectory_id", "state_index", "case", "policy", "repeat",
        "update_to_queryable_publish_s", "llm_calls", "llm_input_tokens_known",
        "llm_output_tokens_known", "reextracted_event_outputs", "regenerated_notes",
        "embedding_calls", "embedding_vectors", "embedding_tokens_known",
        "api_failed_calls", "unknown_usage_calls", "load_verified",
        "quality_pass", "quality_new_fact", "quality_old_fact",
        "quality_untouched", "quality_event_coverage", "quality_reuse",
        "actual_dependency_reused_events", "run_path"
    ]
    with TABLE.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_repeat_summary(rows):
    selected = [r for r in rows if r["case"] in ("state_revision", "workflow_revision") and r["policy"] in ("b3", "ours")]
    summaries = []
    for repeat in sorted({int(r["repeat"]) for r in selected}):
        for policy in ("b3", "ours"):
            group = [r for r in selected if int(r["repeat"]) == repeat and r["policy"] == policy]
            if not group:
                continue
            summaries.append({
                "pass": "primary" if repeat == 0 else f"repeat-{repeat}",
                "repeat_id": repeat, "method": policy, "cases": len(group),
                "update_to_publish_s_sum": sum(float(r["update_to_queryable_publish_s"]) for r in group),
                "controller_calls": sum(int(r["llm_calls"]) for r in group),
                "llm_input_tokens": sum(int(r["llm_input_tokens_known"]) for r in group),
                "llm_output_tokens": sum(int(r["llm_output_tokens_known"]) for r in group),
                "reextracted_event_outputs": sum(int(r["reextracted_event_outputs"]) for r in group),
                "regenerated_notes": sum(int(r["regenerated_notes"]) for r in group),
                "embedding_vectors": sum(int(r["embedding_vectors"]) for r in group),
                "failed_calls": sum(int(r["api_failed_calls"]) for r in group),
                "quality_pass": sum(bool(r["quality_pass"]) for r in group),
                "raw_paths": ";".join(r["run_path"] for r in group),
            })
    fields = list(summaries[0]) if summaries else []
    with REPEAT_TABLE.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(summaries)
    return summaries


def summary(rows):
    groups = {}
    for row in rows:
        key = (row["domain"], row["case"], row["policy"], int(row["repeat"]))
        groups.setdefault(key, []).append(row)
    out = []
    for key, values in sorted(groups.items()):
        times = [float(v["update_to_queryable_publish_s"]) for v in values]
        out.append({
            "domain": key[0], "case": key[1], "policy": key[2], "repeat": key[3],
            "n": len(values), "time_mean": statistics.mean(times),
            "time_min": min(times), "time_max": max(times),
            "llm_calls": statistics.mean(float(v["llm_calls"]) for v in values),
            "llm_input": statistics.mean(float(v["llm_input_tokens_known"]) for v in values),
            "events": statistics.mean(float(v["reextracted_event_outputs"]) for v in values),
            "notes": statistics.mean(float(v["regenerated_notes"]) for v in values),
            "quality": sum(bool(v["quality_pass"]) for v in values),
        })
    return out


def write_svg(rows):
    # Cumulative cost over the eight fixed cases; primary and repeat are shown
    # separately through their two series, preserving actual execution order.
    order = [
        ("web", "1ad1af4b", "state_revision"), ("web", "1ad1af4b", "workflow_revision"),
        ("web", "2e8f6477", "state_revision"), ("web", "2e8f6477", "workflow_revision"),
        ("enterprise", "0ab99e0c", "state_revision"), ("enterprise", "0ab99e0c", "workflow_revision"),
        ("enterprise", "49f98e9e", "state_revision"), ("enterprise", "49f98e9e", "workflow_revision"),
        ("web", "1ad1af4b", "trajectory_growth"),
        ("enterprise", "0ab99e0c", "trajectory_growth"),
    ]
    series = {}
    lookup = {(r["domain"], r["trajectory_id"], r["case"], r["policy"], int(r["repeat"])): float(r["update_to_queryable_publish_s"]) for r in rows}
    for repeat in (0, 1, 2, 3):
        for policy in ("b3", "ours"):
            total = 0.0; points = []
            case_order = [key for key in order if any((*key, candidate, repeat) in lookup for candidate in ("b3", "ours"))]
            for i, key in enumerate(case_order, 1):
                total += lookup[(*key, policy, repeat)]; points.append((i, total))
            series[(policy, repeat)] = points
    width, height, left, bottom = 760, 430, 70, 350
    max_y = max((p[1] for ps in series.values() for p in ps), default=1.0) * 1.08
    def xy(x, y): return left + (x - 1) * (width - left - 30) / max(1, len(order) - 1), bottom - y * 280 / max_y
    colors = {("b3", 0): "#4263eb", ("ours", 0): "#d9480f", ("b3", 1): "#74c0fc", ("ours", 1): "#ff922b", ("b3", 2): "#91a7ff", ("ours", 2): "#ffa94d", ("b3", 3): "#bac8ff", ("ours", 3): "#ffc078"}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="70" y="28" font-size="18">Cumulative update-to-queryable cost: 8 revisions + up to 2 growth cases</text>', f'<line x1="{left}" y1="70" x2="{left}" y2="{bottom}" stroke="#333"/><line x1="{left}" y1="{bottom}" x2="{width-30}" y2="{bottom}" stroke="#333"/>']
    for i in range(1, len(order) + 1):
        x, _ = xy(i, 0); parts.append(f'<line x1="{x:.1f}" y1="{bottom}" x2="{x:.1f}" y2="{bottom+5}" stroke="#333"/><text x="{x-3:.1f}" y="{bottom+20}" font-size="11">{i}</text>')
    for (policy, repeat), points in series.items():
        d = " ".join(("M" if i == 0 else "L") + f" {xy(x,y)[0]:.1f},{xy(x,y)[1]:.1f}" for i,(x,y) in enumerate(points))
        label = f"{policy.upper()} {'primary' if repeat == 0 else f'r{repeat}'}"
        parts += [f'<path d="{d}" fill="none" stroke="{colors[(policy,repeat)]}" stroke-width="3"/>', f'<text x="{left+20 + (0 if policy=="b3" else 125)}" y="{55 + repeat*16 + (0 if policy=="b3" else 0)}" fill="{colors[(policy,repeat)]}" font-size="11">{label}</text>']
    parts += ['<text x="12" y="210" transform="rotate(-90 12,210)" font-size="12">cumulative seconds</text>', '<text x="350" y="405" font-size="12">fixed update case index</text>', '</svg>']
    SVG.write_text("".join(parts))


def write_fresh_comparison_svg(rows):
    """Write the eight-case Fresh/B0, B3 and Ours aggregate comparison.

    Fresh is intentionally labelled touched-partition rebuild: it is not a full
    domain rebuild. The chart uses the same primary revision cases for all
    methods and keeps the unit as aggregate wall-clock seconds.
    """
    cases = [("web", "1ad1af4b", "state"), ("web", "1ad1af4b", "workflow"),
             ("web", "2e8f6477", "state"), ("web", "2e8f6477", "workflow"),
             ("enterprise", "0ab99e0c", "state"), ("enterprise", "0ab99e0c", "workflow"),
             ("enterprise", "49f98e9e", "state"), ("enterprise", "49f98e9e", "workflow")]
    lookup = {(r["domain"], r["trajectory_id"], r["case"], r["policy"], int(r["repeat"])): r for r in rows}
    methods = ("fresh", "b3", "ours")
    totals = {m: [] for m in methods}
    running = {m: 0.0 for m in methods}
    for domain, tid, label in cases:
        case = f"{label}_revision"
        for method in methods:
            row = lookup.get((domain, tid, case, method, 0))
            running[method] += float(row["update_to_queryable_publish_s"]) if row else 0.0
            totals[method].append(running[method])
    width, height, left, bottom = 820, 430, 75, 350
    max_y = max((v for vals in totals.values() for v in vals), default=1.0) * 1.08
    def xy(i, y):
        return left + (i - 1) * (width - left - 35) / max(1, len(cases) - 1), bottom - y * 275 / max_y
    colors = {"fresh": "#868e96", "b3": "#4263eb", "ours": "#d9480f"}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<text x="75" y="28" font-size="18">Fresh/B0 touched-partition vs incremental updates</text>',
             '<text x="75" y="48" font-size="11">Primary eight state/workflow revisions; aggregate update-to-queryable seconds</text>',
             f'<line x1="{left}" y1="70" x2="{left}" y2="{bottom}" stroke="#333"/><line x1="{left}" y1="{bottom}" x2="{width-35}" y2="{bottom}" stroke="#333"/>']
    for i in range(1, len(cases) + 1):
        x, _ = xy(i, 0)
        parts.append(f'<line x1="{x:.1f}" y1="{bottom}" x2="{x:.1f}" y2="{bottom+5}" stroke="#333"/><text x="{x-3:.1f}" y="{bottom+18}" font-size="10">{i}</text>')
    for method in methods:
        pts = totals[method]
        d = " ".join(("M" if i == 0 else "L") + f" {xy(i+1, y)[0]:.1f},{xy(i+1, y)[1]:.1f}" for i, y in enumerate(pts))
        parts.append(f'<path d="{d}" fill="none" stroke="{colors[method]}" stroke-width="3"/>')
    for j, method in enumerate(methods):
        parts.append(f'<text x="{left+20+j*145}" y="62" fill="{colors[method]}" font-size="11">{method.upper()} ({"touched partition" if method == "fresh" else "cached update"})</text>')
    parts += ['<text x="14" y="210" transform="rotate(-90 14,210)" font-size="12">cumulative seconds</text>', '<text x="385" y="405" font-size="12">revision case index</text>', '</svg>']
    FRESH_SVG.write_text("".join(parts))


def write_report(rows):
    lines = [
        "# AgentRunbook-R adapted local multi-trajectory updates", "",
        "All cases start from independent copies of the same combined web/enterprise starting snapshot; ‘combined’ identifies the source artifact, not a claim that it is the quality-optimal configuration. B3 and Ours preserve the same legal request/vector caches, while Fresh/B0 clears the cloned touched-partition build caches and reconstructs that trajectory partition. Model load/cache seeding is excluded from update-to-queryable wall time, while save/reload publication is included. The eight revision cases and two same-trajectory growth cases remain distinct workloads.", "",
        "The four trajectories were selected by domain, length and page family: web `1ad1af4b` (8 states, forum form) and `2e8f6477` (11 states, forum thread); enterprise `0ab99e0c` (16 states, ServiceNow change-request flow) and `49f98e9e` (15 states, ServiceNow asset flow). State/workflow patches cover interior and pair-boundary positions.", "",
        "| Domain | Trajectory | Case | Policy | Pass | Publish s | LLM calls / input/output tokens | Events | Notes | Embedding vectors | Exact reused events | Quality |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|"
    ]
    for r in sorted(rows, key=lambda x: (x["repeat"], x["domain"], x["trajectory_id"], x["case"], x["policy"] )):
        run_label = 'primary' if int(r['repeat']) == 0 else f"r{int(r['repeat'])}"
        lines.append(f"| {r['domain']} | `{r['trajectory_id']}` | {r['case']} | {r['policy']} | {run_label} | {float(r['update_to_queryable_publish_s']):.2f} | {r['llm_calls']} / {r['llm_input_tokens_known']}/{r['llm_output_tokens_known']} | {r['reextracted_event_outputs']} | {r['regenerated_notes']} | {r['embedding_vectors']} | {r.get('actual_dependency_reused_events', '')} | {'pass' if r['quality_pass'] else 'fail'} |")
    fresh_rows = [r for r in rows if r["policy"] == "fresh" and r["case"] in ("state_revision", "workflow_revision")]
    if fresh_rows:
        lookup = {(r["domain"], r["trajectory_id"], r["case"], r["policy"], int(r["repeat"])): r for r in rows}
        lines += ["", "## Fresh/B0 touched-partition rebuild comparison", "",
                  "Fresh/B0 starts from the same persisted source memory but clears the cloned controller-response, event-output, and construction-embedding caches before rebuilding the touched trajectory partition. It is a no-build-cache partition-rebuild reference, not a full rebuild of every trajectory in the domain. B3/Ours values below are matched primary rows; their separate order-reversed repetitions are retained in the full table.", ""]
        sums = {p: {k: 0.0 for k in ("update_to_queryable_publish_s", "llm_calls", "llm_input_tokens_known", "llm_output_tokens_known", "embedding_vectors")} for p in ("fresh", "b3", "ours")}
        matched = 0
        for f in fresh_rows:
            pair = [lookup.get((f["domain"], f["trajectory_id"], f["case"], p, 0)) for p in ("b3", "ours")]
            if not all(pair):
                continue
            matched += 1
            for p, row in zip(("fresh", "b3", "ours"), [f, *pair]):
                for metric in sums[p]:
                    sums[p][metric] += float(row[metric])
        if matched:
            lines.append(f"Matched fixed revisions: {matched}. Aggregate update-to-publication totals (not a per-request latency sum):")
            for p in ("fresh", "b3", "ours"):
                values = sums[p]
                lines.append(f"- {p}: {values['update_to_queryable_publish_s']:.2f}s; {values['llm_calls']:.0f} controller calls; {values['llm_input_tokens_known']:.0f}/{values['llm_output_tokens_known']:.0f} input/output tokens; {values['embedding_vectors']:.0f} embedding vectors.")
            lines.append("All displayed Fresh/B0, B3 and Ours update-quality checks are retained per row; fixed Reader regression remains a separate downstream check.")
    growth = [r for r in rows if r["case"] == "trajectory_growth" and not r["repeat"]]
    if growth:
        lines += ["", "## Same-trajectory growth (separate from new-trajectory append)", "",
                  "One real follow-up state was appended to an existing trajectory while preserving its identity and prior snapshot. The current global action/step dependency key changes, so the Ours implementation may conservatively regenerate old event outputs; no global dependency was removed. This workload is not pooled into the eight revision cases or the cross-trajectory append result.", ""]
        by_pair = {(r["domain"], r["policy"]): r for r in growth}
        for domain in ("web", "enterprise"):
            b, o = by_pair.get((domain, "b3")), by_pair.get((domain, "ours"))
            if b and o:
                reuse = o.get("dependency_reused_event_ids", [])
                reuse_count = o.get('actual_dependency_reused_events', '')
                lines.append(f"- {domain}: B3 {float(b['update_to_queryable_publish_s']):.2f}s / {b['llm_calls']} calls / {b['llm_input_tokens_known']} input and {b['llm_output_tokens_known']} output tokens; Ours {float(o['update_to_queryable_publish_s']):.2f}s / {o['llm_calls']} calls / {o['llm_input_tokens_known']} input and {o['llm_output_tokens_known']} output tokens. Ours regenerated {o['reextracted_event_outputs']} event outputs and exactly reused {reuse_count} prior event outputs; embedding work was {o['embedding_vectors']} vectors. Source-grounded content/event coverage: {'pass' if o['quality_pass'] and b['quality_pass'] else 'check retained'}. One paired run is descriptive, not a stable latency estimate.")
        repeat_growth = {(r["domain"], r["policy"]): r for r in rows if r["case"] == "trajectory_growth" and r["repeat"]}
        if repeat_growth:
            lines.append("- Reverse-order repeat: " + "; ".join(
                f"{domain} Ours {float(repeat_growth[(domain, 'ours')]['update_to_queryable_publish_s']):.2f}s vs B3 {float(repeat_growth[(domain, 'b3')]['update_to_queryable_publish_s']):.2f}s, both with {repeat_growth[(domain, 'ours')]['llm_calls']} / {repeat_growth[(domain, 'b3')]['llm_calls']} calls and zero exact event reuse"
                for domain in ("web", "enterprise") if (domain, 'ours') in repeat_growth and (domain, 'b3') in repeat_growth
            ) + ". The order-reversed repeats confirm large wall variance and do not establish a growth speedup.")
    repeat_rows = write_repeat_summary(rows)
    by_repeat = {}
    for item in repeat_rows:
        by_repeat.setdefault(int(item["repeat_id"]), {})[item["method"]] = item
    lines += ["", "## Matched update repeats: eight fixed revisions", "",
              "Each row aggregates the same eight revision cases from a fresh independent copy of the same combined starting snapshot. The runs are sequential on the resident model service; setup/cache seeding is excluded and publish includes save/reload verification. Actual policy order: primary B3→Ours, repeat-1 Ours→B3, repeat-2 Ours→B3 (order mistake retained), repeat-3 B3→Ours. Repeat-3 balances the order; the r2 run is not silently discarded.", "",
              "| Pass | B3 wall s | Ours wall s | Ours vs B3 | Calls B3/Ours | Input tokens B3/Ours | Events B3/Ours | Quality checks B3/Ours |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for repeat, methods in sorted(by_repeat.items()):
        if "b3" not in methods or "ours" not in methods:
            continue
        b, o = methods["b3"], methods["ours"]
        delta = (float(o["update_to_publish_s_sum"]) / float(b["update_to_publish_s_sum"]) - 1) * 100
        lines.append(f"| {b['pass']} | {float(b['update_to_publish_s_sum']):.2f} | {float(o['update_to_publish_s_sum']):.2f} | {delta:+.1f}% | {b['controller_calls']}/{o['controller_calls']} | {b['llm_input_tokens']}/{o['llm_input_tokens']} | {b['reextracted_event_outputs']}/{o['reextracted_event_outputs']} | {b['quality_pass']}/{o['quality_pass']} |")
    lines += ["", f"Structured per-pass totals: `{REPEAT_TABLE.relative_to(ROOT)}`. These totals show whether the observed update-work savings survive order changes; the r2 B3 recomputation/cost spike remains included."]
    for reader_report in (ROOT / "reports/agentrunbook_revision_case_reader.md", ROOT / "reports/agentrunbook_revision_reader_regression.md", ROOT / "reports/agentrunbook_growth_reader_regression.md"):
      if reader_report.is_file():
        reader_lines = reader_report.read_text().splitlines()
        if reader_lines:
            reader_lines[0] = reader_lines[0].replace("# ", "## ", 1)
        lines += ["", *reader_lines, ""]
    lines += ["", "## Paired interpretation", ""]
    for domain in ("web", "enterprise"):
        for case in ("state_revision", "workflow_revision"):
            prim = {(r["trajectory_id"], r["policy"]): r for r in rows if r["domain"] == domain and r["case"] == case and not r["repeat"]}
            rep = {(r["trajectory_id"], r["policy"]): r for r in rows if r["domain"] == domain and r["case"] == case and r["repeat"]}
            for tid in sorted({k[0] for k in prim}):
                if (tid, "b3") not in prim or (tid, "ours") not in prim: continue
                p_b, p_o = prim[(tid,"b3")], prim[(tid,"ours")]
                repeats = [int(r['repeat']) for r in rows if r['domain'] == domain and r['case'] == case and r['trajectory_id'] == tid and int(r['repeat']) > 0]
                latest = max(repeats) if repeats else None
                q_b = next((r for r in rows if r['domain'] == domain and r['case'] == case and r['trajectory_id'] == tid and r['policy'] == 'b3' and int(r['repeat']) == latest), None) if latest is not None else None
                q_o = next((r for r in rows if r['domain'] == domain and r['case'] == case and r['trajectory_id'] == tid and r['policy'] == 'ours' and int(r['repeat']) == latest), None) if latest is not None else None
                suffix = f"r{latest}" if latest is not None else "no repeat"
                repeat_text = f"{suffix} Ours vs B3 wall {float(q_o['update_to_queryable_publish_s'])-float(q_b['update_to_queryable_publish_s']):+.2f}s" if q_b and q_o else f"{suffix} unavailable"
                lines.append(f"- `{domain}/{tid}/{case}` primary Ours vs B3 wall {float(p_o['update_to_queryable_publish_s'])-float(p_b['update_to_queryable_publish_s']):+.2f}s; input-token delta {int(p_o['llm_input_tokens_known'])-int(p_b['llm_input_tokens_known']):+d}. {repeat_text}.")
    passed = sum(bool(r["quality_pass"]) for r in rows)
    legacy = " The historical pre-fix checker rows remain under runs/agentrunbook-updates-main but are excluded from this table; the corrected paired rerun is included."
    lines += ["", f"Source-grounded checks pass in {passed}/{len(rows)} persisted rows (new fact, old fact handling, untouched facts, complete event coverage; Ours additionally checks only actually reused joint events).{legacy} These checks do not establish Reader quality. The fixed B3/Ours Reader regression covers eight revision cases (64/64 complete parseable answers, 42/64 correct, zero truncation/service/parse failures); both methods score 21/32 overall, with web 12/16 vs 13/16 and enterprise 9/16 vs 8/16. Fresh/B0 Reader coverage is partial and is not pooled into this matched table. The append result remains an arrival-of-a-new-trajectory case, distinct from same-trajectory growth. Growth quality rechecks are written beside raw run metrics; raw measurements and original checker output are preserved.", ""]
    REPORT.write_text("\n".join(lines))


def main():
    rows = load_rows()
    write_table(rows)
    write_repeat_summary(rows)
    write_svg(rows)
    write_fresh_comparison_svg(rows)
    write_report(rows)
    print(json.dumps({"rows": len(rows), "table": str(TABLE), "report": str(REPORT), "svg": str(SVG), "fresh_svg": str(FRESH_SVG)}))


if __name__ == "__main__":
    main()
