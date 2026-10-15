#!/usr/bin/env python3
"""Aggregate the persisted local AgentRunbook-R B3/Ours updates."""
import csv
import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def report_method_updates(run_root):
    """Finite development table: no combining incompatible historical repeats."""
    rows = []
    for path in sorted(run_root.glob('*/*/update_metrics.json')):
        m = json.loads(path.read_text())
        q = m.get('quality_checks', {})
        row = {k: m.get(k) for k in ('policy', 'case', 'trajectory_id', 'state_index',
            'delta_version', 'matched_construction_signature', 'llm_calls', 'llm_input_tokens_known',
            'llm_output_tokens_known', 'embedding_calls', 'embedding_vectors', 'embedding_tokens_known',
            'update_to_queryable_publish_s', 'artifact_build_s', 'publication_and_reload_s',
            'reextracted_event_outputs', 'edited_event_outputs', 'regenerated_notes', 'exact_request_hits',
            'edited_notes', 'api_failed_calls', 'unknown_usage_calls', 'delta_fallback_groups', 'qa_status')}
        row['run'] = path.parent.parent.name
        row['llm_total_tokens'] = m['llm_input_tokens_known'] + m['llm_output_tokens_known']
        row['derived_event_hits'] = sum(q.get('derived_event_change_hits', {}).values())
        row['derived_event_targets'] = len(q.get('derived_event_change_hits', {}))
        row['derived_notes_change_hit'] = q.get('derived_notes_change_hit')
        row['semantic_review'] = q.get('semantic_review', 'not_checked')
        review_path = path.parent / 'review_decision.json'
        row['implementation_valid'] = True
        if review_path.exists():
            review = json.loads(review_path.read_text())
            row['semantic_review'] = review.get('derived_memory_quality_pass', review.get('quality_pass', 'pending'))
            row['implementation_valid'] = review.get('implementation_valid', True)
        row['valid_cache_comparison'] = bool(m.get('matched_construction_signature'))
        row['timing_scope'] = 'overlaps_snapshot_preparation; diagnostic' if row['run'].startswith('r1-') else 'sequential_single_client'
        row['raw_path'] = str(path.parent.relative_to(ROOT))
        rows.append(row)
    if not rows:
        raise ValueError('No completed method update measurements')
    table = ROOT / 'results/tables/method_update_costs.csv'
    with table.open('w', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    lines = ['# METHOD01–02 development updates', '',
        'Primary metric: total LLM input + output tokens. Independent clones with equal legal exact-request/vector caches. '
        'Only rows with a matched construction signature are valid method comparisons. '
        'The earlier expanded20 diagnostic had no saved full requests, zero exact hits and is excluded from benefit claims. '
        'The first r1 web timing overlaps snapshot preparation and is not paired latency evidence.', '',
        '| Run | Policy | LLM in/out | Calls | Emb vectors/tokens | Publish s | Edited/re-extracted | Event checks | Note check |',
        '|---|---|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        if not r['valid_cache_comparison']:
            continue
        lines.append(f"| {r['run']} | {r['policy']} | {r['llm_input_tokens_known']}/{r['llm_output_tokens_known']} | "
            f"{r['llm_calls']} | {r['embedding_vectors']}/{r['embedding_tokens_known']} | {r['update_to_queryable_publish_s']:.2f} | "
            f"{r['edited_event_outputs']}/{r['reextracted_event_outputs']} | {r['derived_event_hits']}/{r['derived_event_targets']} | {r['derived_notes_change_hit']} |"
            + (' INVALID IMPLEMENTATION' if not r['implementation_valid'] else ''))
    lines += ['', 'Generated-memory checks exclude raw states and copied thought metadata. Lexical pass is a necessary '
        'check, not semantic quality certification. Semantic review and fixed Reader regression remain separate constraints. '
        'V5 cases are additive controlled annotations; later literal_revision cases are controlled replacements, '
        'not observed real-world updates or continuous-growth claims. No method is frozen.']
    (ROOT / 'reports/method_update_costs.md').write_text('\n'.join(lines) + '\n')
    pairs = []
    for name in sorted({r['run'] for r in rows if r['run'].startswith('v5-') and '-state' in r['run']}):
        group = {r['policy']: r for r in rows if r['run'] == name}
        if not {'b3', 'ours', 'delta_notes'} <= set(group):
            continue
        b, o, d = (group[k] for k in ('b3', 'ours', 'delta_notes'))
        pairs.append({'case': name, 'b3_tokens': b['llm_total_tokens'], 'dependency_only_tokens': o['llm_total_tokens'],
            'candidate_tokens': d['llm_total_tokens'], 'token_reduction_vs_b3_pct': 100*(1-d['llm_total_tokens']/b['llm_total_tokens']),
            'b3_publish_s': b['update_to_queryable_publish_s'], 'dependency_only_publish_s': o['update_to_queryable_publish_s'],
            'candidate_publish_s': d['update_to_queryable_publish_s'], 'b3_calls': b['llm_calls'], 'candidate_calls': d['llm_calls'],
            'b3_embedding_vectors': b['embedding_vectors'], 'candidate_embedding_vectors': d['embedding_vectors'],
            'candidate_fallback_groups': d['delta_fallback_groups'],
            'candidate_generated_event_hits': d['derived_event_hits'], 'candidate_generated_event_targets': d['derived_event_targets'],
            'candidate_notes_check': d['derived_notes_change_hit'], 'reader_status': 'pending', 'raw_path': d['raw_path']})
    if pairs:
        with (ROOT / 'results/tables/method_v5_paired.csv').open('w', newline='') as fp:
            writer = csv.DictWriter(fp, fieldnames=list(pairs[0])); writer.writeheader(); writer.writerows(pairs)
        totals = {key: sum(r[key] for r in pairs) for key in ('b3_tokens', 'dependency_only_tokens', 'candidate_tokens',
                    'b3_publish_s', 'dependency_only_publish_s', 'candidate_publish_s', 'b3_calls', 'candidate_calls',
                    'b3_embedding_vectors', 'candidate_embedding_vectors')}
        passed = sum(r['candidate_generated_event_hits'] == r['candidate_generated_event_targets']
                     and r['candidate_notes_check'] is not False for r in pairs)
        summary = ['# Matched eight-case method screen (v5)', '',
            f"Completed paired cases: {len(pairs)}/8. Necessary generated-memory checks: {passed}/{len(pairs)}. "
            'Manual review is in method_v5_quality_review.md. Includes the failed candidate/fallback, not successful-only sampling.', '',
            '| Method | Total LLM tokens | Update publication sum (s) | LLM calls | Actual Embedding vectors |',
            '|---|---:|---:|---:|---:|',
            f"| Strong B3 | {totals['b3_tokens']} | {totals['b3_publish_s']:.3f} | {totals['b3_calls']} | {totals['b3_embedding_vectors']} |",
            f"| Event dependency only | {totals['dependency_only_tokens']} | {totals['dependency_only_publish_s']:.3f} | see raw table | see raw table |",
            f"| Source observation + local note update | {totals['candidate_tokens']} | {totals['candidate_publish_s']:.3f} | {totals['candidate_calls']} | {totals['candidate_embedding_vectors']} |", '',
            'One development pass, not repeat/stability evidence. All cases start independently from the same matched snapshots; '
            'load/cache seeding is reported separately and excluded. Publication includes artifact generation, actual Embedding, '
            'merge, save and reload checks. A wall sum across cases is not a sequential evolving-memory stream or a sum of concurrent request times.', '',
            'A source-ID output mistake causes the v5 failure. The v6 repair is a separate run and does not replace this row. '
            'Do not freeze or claim overall quality preservation. All eight source edits are additive controlled annotations; '
            'replacement/revocation correctness and a deterministic source-append comparator remain necessary. Native/official Judge quality is not claimed.', '',
            'Per-case data: results/tables/method_v5_paired.csv; full input/output, calls, vectors/tokens, failures, publication and paths: '
            'results/tables/method_update_costs.csv. Fixed Reader results are in results/tables/method_v5_reader.csv as they finish.']
        (ROOT / 'reports/method_v5_main.md').write_text('\n'.join(summary) + '\n')
    reader_rows = []
    for path in sorted(run_root.glob('v5-*-state*/*/reader/aggregated_metrics.json')):
        metrics = json.loads(path.read_text())
        reader_rows.append({'case': path.parents[2].name, 'policy': path.parents[1].name,
                           **metrics['answer_status'], 'reader_input_tokens': metrics['tokens']['prompt_tokens'],
                           'reader_output_tokens': metrics['tokens']['completion_tokens'],
                           'prompt_build_s': metrics['timing']['prompt_build_wall_seconds'],
                           'reader_wall_s': metrics['timing']['reader_generation_wall_seconds'],
                           'raw_path': str(path.parent.relative_to(ROOT))})
    if reader_rows:
        with (ROOT / 'results/tables/method_v5_reader.csv').open('w', newline='') as fp:
            writer = csv.DictWriter(fp, fieldnames=list(reader_rows[0])); writer.writeheader(); writer.writerows(reader_rows)
    all_reader_rows = []
    for path in sorted(run_root.glob('*/*/reader*/aggregated_metrics.json')):
        m = json.loads(path.read_text())
        all_reader_rows.append({'case': path.parents[2].name, 'policy': path.parents[1].name,
            'reader_run': path.parent.name, **m['answer_status'],
            'reader_input_tokens': m['tokens']['prompt_tokens'], 'reader_output_tokens': m['tokens']['completion_tokens'],
            'prompt_build_s': m['timing']['prompt_build_wall_seconds'],
            'reader_wall_s': m['timing']['reader_generation_wall_seconds'],
            'raw_path': str(path.parent.relative_to(ROOT))})
    if all_reader_rows:
        with (ROOT / 'results/tables/method_reader_regression.csv').open('w', newline='') as fp:
            writer = csv.DictWriter(fp, fieldnames=list(all_reader_rows[0])); writer.writeheader(); writer.writerows(all_reader_rows)
    confirmation = []
    for name in sorted({r['run'] for r in rows if r['run'].startswith('v11-r')}):
        group = {r['policy']: r for r in rows if r['run'] == name}
        if not {'b3', 'delta_guarded'} <= set(group):
            continue
        b, d = group['b3'], group['delta_guarded']
        confirmation.append({'case': name, 'trajectory_id': d['trajectory_id'],
            'b3_tokens': b['llm_total_tokens'], 'candidate_tokens': d['llm_total_tokens'],
            'token_reduction_pct': 100*(1-d['llm_total_tokens']/b['llm_total_tokens']),
            'b3_publish_s': b['update_to_queryable_publish_s'], 'candidate_publish_s': d['update_to_queryable_publish_s'],
            'wall_reduction_pct': 100*(1-d['update_to_queryable_publish_s']/b['update_to_queryable_publish_s']),
            'b3_calls': b['llm_calls'], 'candidate_calls': d['llm_calls'],
            'b3_vectors': b['embedding_vectors'], 'candidate_vectors': d['embedding_vectors'],
            'fallbacks': d['delta_fallback_groups'],
            'b3_necessary_checks': b['derived_event_hits'] == b['derived_event_targets'],
            'candidate_necessary_checks': d['derived_event_hits'] == d['derived_event_targets'],
            'candidate_semantic_review': d['semantic_review'], 'raw_path': d['raw_path']})
    if confirmation:
        with (ROOT / 'results/tables/method_v11_repeats.csv').open('w', newline='') as fp:
            writer = csv.DictWriter(fp, fieldnames=list(confirmation[0])); writer.writeheader(); writer.writerows(confirmation)
        lines = ['# V11 development paired confirmation (not frozen)', '',
            'Primary metric: total LLM tokens. Each pair starts from independent copies of the same source and legal caches. '
            'Three fresh runs per two replacement cases, alternating B3/candidate order; no historical controls in this table. '
            'Source values are controlled counterfactual corrections, not official QA amendments.', '',
            '| Trajectory | Pairs | Mean B3/candidate tokens | Paired token reduction range | Mean B3/candidate publish s | Paired wall reduction range | Candidate necessary checks |',
            '|---|---:|---:|---:|---:|---:|---:|']
        for tid in sorted({r['trajectory_id'] for r in confirmation}):
            subset = [r for r in confirmation if r['trajectory_id'] == tid]
            mean = lambda key: statistics.mean(r[key] for r in subset)
            spread = lambda key: f"{min(r[key] for r in subset):.1f}–{max(r[key] for r in subset):.1f}%"
            lines.append(f"| {tid} | {len(subset)} | {mean('b3_tokens'):.1f}/{mean('candidate_tokens'):.1f} | "
                f"{spread('token_reduction_pct')} | {mean('b3_publish_s'):.2f}/{mean('candidate_publish_s'):.2f} | "
                f"{spread('wall_reduction_pct')} | {sum(r['candidate_necessary_checks'] for r in subset)}/{len(subset)} |")
        lines += ['', 'Necessary lexical checks are not semantic quality certification. Review generated event/state roles and notes '
            'in reports/method_literal_quality_review.md; fixed Reader regression remains independent. '
            'No cold construction or query savings are counted. All per-stage tokens, vectors, failures, setup/publication and raw paths '
            'are in results/tables/method_update_costs.csv.']
        (ROOT / 'reports/method_v11_confirmation.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'rows': len(rows), 'table': str(table)}))


def main():
    rows=[]
    for path in sorted(ROOT.glob('runs/construction-pair-v1/updates-*/**/update_metrics.json')):
        row=json.loads(path.read_text()); row['run_path']=str(path.parent.relative_to(ROOT)); rows.append(row)
    assert len(rows)>=6, f'expected at least six completed updates, got {len(rows)}'
    out=ROOT/'results/tables/agentrunbook_update_b3_ours.csv'; out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w') as fp:
        w=csv.DictWriter(fp,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    lines=['# AgentRunbook-R adapted local updates: B3 vs Ours','',
      'All six runs start from independent clones of the same persisted `screen-web-g2` snapshot. Model weights are resident; cache seeding/load is excluded from update-to-queryable wall time. Both methods retain exact valid request/vector caches; Ours additionally validates per-event dependencies and only regroups dirty adjacent outputs.', '',
      '| Case | Policy | Update→queryable s | Event outputs recomputed | Notes regenerated | LLM calls/in tokens | Embedding calls/vectors | Cache hits |','|---|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['case']} | {r['policy']} | {r['update_to_queryable_publish_s']:.2f} | {r['reextracted_event_outputs']} | {r['regenerated_notes']} | {r['llm_calls']}/{r['llm_input_tokens_known']} | {r['embedding_calls']}/{r['embedding_vectors']} | req {r['exact_request_hits']}, emb {r['embedding_hits']} |")
    lines += ['', 'Append uses a real additional official-source trajectory prefix (3 arrived states, no future state/outcome) and does not wait for later events. State revision appends one source-backed visible status. Workflow revision changes one recorded thought/workflow fragment while preserving actions, values and source evidence.', '',
      'State revision: Ours recomputes 2 event outputs vs B3 4 and publishes in11.96s vs23.47s. Workflow revision: both recompute2 events +2 notes; Ours uses less known LLM input (5891 vs9458), but wall time is roughly tied (32.95 vs32.19s). Append costs are nearly tied (18.13 vs18.48s) because both must generate the new trajectory notes/events.', '',
      'This is an adapted text-only mechanism experiment, not native Small, official Judge, or a claim that prior workflow-core B3/Ours numbers are interchangeable.']
    (ROOT/'reports/agentrunbook_update_b3_ours.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--method-root', type=Path)
    args = parser.parse_args()
    if args.method_root:
        report_method_updates(args.method_root.resolve())
    else:
        main()
