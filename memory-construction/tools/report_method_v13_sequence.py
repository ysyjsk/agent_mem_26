#!/usr/bin/env python3
"""Measured continuous-history costs, including retrieval and Reader work."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'runs/method-first-20261015/v13-sequential'
MARK = '\nCURRENT STATE OBSERVATIONS (authoritative for the listed fields; pre-state and post-state are independent, not a claim that values persist):\n'
POLICIES = ('b3', 'source_overlay', 'source_coalesced')


def read(path):
    return json.loads(path.read_text())


def rows_jsonl(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def main():
    rows = []
    for domain in ('web', 'enterprise'):
        for n in (1, 2, 3):
            for policy in POLICIES:
                folder = RUN/f'{domain}-r{n}'/f'literal_revision-{policy}'
                if not (folder/'update_metrics.json').exists():
                    continue
                m = read(folder/'update_metrics.json')
                r = {'domain': domain, 'round': n, 'policy': policy, 'raw_path': str(folder.relative_to(ROOT))}
                for k in ('llm_calls', 'llm_input_tokens_known', 'llm_output_tokens_known', 'embedding_calls',
                          'embedding_vectors', 'embedding_tokens_known', 'update_to_queryable_publish_s',
                          'api_failed_calls', 'unknown_usage_calls', 'reextracted_event_outputs', 'regenerated_notes',
                          'published_event_chars', 'published_note_chars', 'current_evidence_blocks'):
                    r[k] = m[k]
                r['update_llm_tokens'] = m['llm_input_tokens_known']+m['llm_output_tokens_known']
                tr = read(folder/'update_input.json')['trajectory']
                review = read(folder/'derived_quality_review.json')
                r['notes_preserved_exactly'] = review['new_notes'] == review['old_notes']
                invalid, total = [], 0
                for event in review['new_events']:
                    for part in event['state_transition'].split(MARK)[1:]:
                        observations, _ = json.JSONDecoder().raw_decode(part)
                        for obs in observations:
                            current = set(x.strip() for x in tr['states'][obs['state_index']]['text'].splitlines())
                            for line in obs['current_evidence'].splitlines():
                                total += 1
                                if line.strip() and line.strip() not in current:
                                    invalid.append((event['event_id'], obs['state_index'], line))
                r['obsolete_lines_labeled_current'] = len(invalid)
                r['current_evidence_lines_checked'] = total
                r['quality_scope'] = 'Exact current source-role evidence + preserved generated notes; semantic review and QA separate'
                qfile = folder/'revision_reader/aggregated_metrics.json'
                if qfile.exists():
                    q = read(qfile)
                    r.update({'qa_'+k: v for k,v in q['answer_status'].items()})
                    r['reader_input_tokens'] = q['tokens']['prompt_tokens']
                    r['reader_output_tokens'] = q['tokens']['completion_tokens']
                    r['query_wall_s'] = q['timing']['prompt_build_wall_seconds']
                    r['reader_wall_s'] = q['timing']['reader_generation_wall_seconds']
                    calls = [c for c in rows_jsonl(folder/'memory_state/model_calls.jsonl')
                             if c.get('query_invocation_id') and c['timestamp_epoch'] >= m['completed_epoch']]
                    llm = [c for c in calls if c['channel'] == 'controller']
                    emb = [c for c in calls if c['channel'] == 'embedding']
                    r['retrieval_llm_input_tokens'] = sum(c.get('prompt_tokens') or 0 for c in llm)
                    r['retrieval_llm_output_tokens'] = sum(c.get('completion_tokens') or 0 for c in llm)
                    r['retrieval_llm_calls'] = len(llm)
                    r['retrieval_embedding_tokens'] = sum(c.get('prompt_tokens') or 0 for c in emb)
                    r['retrieval_embedding_vectors'] = sum(c.get('input_text_count') or 0 for c in emb)
                    r['retrieval_unknown_usage_calls'] = sum(c.get('prompt_tokens') is None for c in llm+emb)
                    r['retrieval_failed_calls'] = sum(c.get('status') == 'failed' for c in llm+emb)
                    r['total_update_query_llm_tokens'] = r['update_llm_tokens']+r['reader_input_tokens']+r['reader_output_tokens']+r['retrieval_llm_input_tokens']+r['retrieval_llm_output_tokens']
                    r['total_update_query_wall_s'] = r['update_to_queryable_publish_s']+r['query_wall_s']+r['reader_wall_s']
                rows.append(r)
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (ROOT/'results/tables/method_v13_sequence.csv').open('w', newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    lines = ['# V13: continuous correction cost and current evidence', '',
        'Text-only/adapted development. Two shared full-domain histories, three controlled corrections per selected state; '
        'each branch carries its own published snapshot and all legal exact caches into the next round. '
        'Initial construction is inherited and excluded, NOT zero-cost cold construction. '
        'All current lines below are generated-event evidence, not merely saved raw text. Notes and unchanged facts require separate semantic review.', '',
        '| Domain/round | Policy | Update LLM tokens/calls | Publish s | Embed tokens/vectors | Event chars | Obsolete lines labeled current | QA correct/scored; truncated | Query+Reader LLM tokens |',
        '|---|---|---:|---:|---:|---:|---:|---|---:|']
    for r in rows:
        query = r.get('total_update_query_llm_tokens', 0)-r['update_llm_tokens'] if 'qa_correct' in r else 'pending'
        lines.append(f"| {r['domain']}/{r['round']} | {r['policy']} | {r['update_llm_tokens']}/{r['llm_calls']} | {r['update_to_queryable_publish_s']:.3f} | {r['embedding_tokens_known']}/{r['embedding_vectors']} | {r['published_event_chars']} | {r['obsolete_lines_labeled_current']} | {r.get('qa_correct','pending')}/{r.get('qa_scored','?')}; {r.get('qa_truncated','?')} | {query} |")
    lines += ['', 'Primary metric is update LLM tokens. Coalescing and append-only overlay both use zero update LLM; '
              'any additional gain is in evidence validity, embedding/context length or actual query cost, not a further reduction below zero. '
              'Cumulative curves include retrieval-controller and Reader tokens plus update tokens. '
              'Cost sums are actual sequential phases, not a sum of concurrent request durations. '
              'Question repeats/controlled source revisions are not independent samples or proof of statistical quality equivalence.']
    (ROOT/'reports/method_v13_sequence.md').write_text('\n'.join(lines)+'\n')
    complete = [r for r in rows if 'qa_correct' in r]
    print(json.dumps({'updates': len(rows), 'query_runs_complete': len(complete)}, ensure_ascii=False))
    if len(complete) < 18:
        return
    # Emit a dependency-free SVG; plotting packages are not part of the
    # resident experiment environment.
    colors = {'b3':'#2563eb', 'source_overlay':'#dc2626', 'source_coalesced':'#16a34a'}
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="720">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<text x="30" y="28" font-size="18">V13 sequential maintenance (initial construction excluded)</text>']
    for i, domain in enumerate(('web', 'enterprise')):
        for j, field in enumerate(('total_update_query_llm_tokens', 'published_event_chars')):
            x0, y0 = 70 + j*470, 80 + i*290
            svg += [f'<line x1="{x0}" y1="{y0+190}" x2="{x0+410}" y2="{y0+190}" stroke="#555"/>',
                    f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0+190}" stroke="#555"/>',
                    f'<text x="{x0+160}" y="{y0+215}" font-size="12">{domain}</text>']
            allvals = []
            series = {}
            for policy in POLICIES:
                rr = sorted((r for r in complete if r['domain']==domain and r['policy']==policy), key=lambda r:r['round'])
                vals = [float(r[field]) for r in rr]
                if field == 'total_update_query_llm_tokens': vals = [sum(vals[:k+1]) for k in range(len(vals))]
                series[policy] = vals; allvals += vals
            lo, hi = min(allvals), max(allvals); span = max(hi-lo, 1.0)
            for policy, vals in series.items():
                pts=[]
                for k, value in enumerate(vals):
                    px=x0+(k/2)*410; py=y0+190-((value-lo)/span)*190; pts.append(f'{px:.1f},{py:.1f}')
                svg.append(f'<polyline fill="none" stroke="{colors[policy]}" stroke-width="2" points="{" ".join(pts)}"/>')
            label = 'cumulative update+query LLM tokens' if j == 0 else 'published event characters'
            svg.append(f'<text x="{x0+8}" y="{y0+16}" font-size="11">{label}</text>')
    svg.append('<text x="70" y="690" font-size="11">blue=B3; red=source_overlay; green=source_coalesced; each point is a correction round</text></svg>')
    (ROOT/'results/figures').mkdir(exist_ok=True)
    (ROOT/'results/figures/method_v13_cumulative.svg').write_text('\n'.join(svg))


if __name__=='__main__':
    main()
