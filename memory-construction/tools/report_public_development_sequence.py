#!/usr/bin/env python3
"""Reuse the measured five-trajectory/domain sequence; never call models."""
import argparse
import hashlib
import json
from pathlib import Path

from focused_evidence import jsonl
from report_full_small_formal import continuous_figure, evidence_figure, dump, load, quality_record, table, total, update_evidence

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/execution-recovery-20261016/public-sequence-v1'
POLICIES = ['raw_rag', 'rag_notes', 'b3', 'source_only', 'source_coalesced']


def source_text_signature(trajectory):
    # Absolute screenshot filenames legitimately differ across clones. They
    # are not inputs in this text-only sequence. Include all textual fields.
    def no_images(value):
        if isinstance(value, dict):
            return {k:no_images(v) for k,v in value.items() if k not in ('screenshot', 'screenshot_path', 'image', 'image_path')}
        if isinstance(value, list):
            return [no_images(v) for v in value]
        return value
    return hashlib.sha256(json.dumps(no_images(trajectory), sort_keys=True).encode()).hexdigest()


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    OUT = ROOT / args.output
    OUT.mkdir(parents=True, exist_ok=False)
    rows, qa, reviews, evidence = [], [], [], []
    for domain in ('web', 'enterprise'):
        for n in (1,2,3):
            shared = Path(f'runs/focused-maintenance-v4/dev/sequence-final/{domain}-r{n}')
            expected_history, expected_source = None, None
            for policy in POLICIES:
                path = (Path(f'runs/focused-maintenance-v4/public-repair-20261016/sequence/{domain}-r{n}-{policy}')
                        if policy in ('raw_rag','rag_notes') else shared / f'literal_revision-{policy}')
                history=load(ROOT/path/'memory_state/index.json')['inserted_trajectory_ids']
                source=source_text_signature(load(ROOT/path/'update_input.json')['trajectory'])
                if expected_history is None:
                    expected_history, expected_source = history, source
                assert history == expected_history and len(history) == 5, (domain, n, policy, 'history differs')
                assert source == expected_source, (domain, n, policy, 'revised text differs')
                reader=path/'revision_reader'
                prompts=jsonl(ROOT/reader/'prompt_rows.jsonl')
                images=[item for r in prompts for message in r['messages'] for item in message.get('content', [])
                        if isinstance(item, dict) and item.get('type') in ('image_url','image','input_image')]
                assert not images, (domain, n, policy, 'non-text-only')
                args=load(ROOT/reader/'run_args.json')
                for key,value in {'reader_enable_thinking':False, 'max_completion_tokens':2048,
                                  'memory_context_max_tokens':12000, 'temperature':.6, 'top_p':.95, 'top_k':20}.items():
                    assert args[key] == value, (domain,n,policy,key)
                ids={r['query_invocation_id'] for r in prompts}
                calls=[r for r in jsonl(ROOT/path/'memory_state/model_calls.jsonl') if r.get('query_invocation_id') in ids]
                assert all(r.get('enable_thinking') is False for r in calls if r['channel']=='controller')
                step={'id':f'{domain}-r{n}-{policy}', 'marker':str(path/'update_metrics.json'),
                      'domain':domain,'policy':policy,'case_id':f'{domain}-r{n}','phase':'development_sequence',
                      'repeat':1,'round':n}
                query={'id':step['id']+'-query','reader':str(reader),'memory':str(path/'memory_state'),
                       'marker':str(reader/'aggregated_metrics.json'), 'domain':domain,'policy':policy,
                       'questions':str(shared/'data/questions.jsonl'),'query_kind':'sequence_revision'}
                row,answers,_=update_evidence(step,[query])
                row['scope']='development shared5/domain; 3 sequential revisions/target; no independent-sample claim'
                row['reader_transport']='historical SDK retry allowance; hidden retry attempts not independently logged'
                rows.append(row);qa.extend(answers);reviews.append(quality_record(step))
                evidence.append({'unit':step['id'],'history_ids':history,'updated_text_sha256':source,
                                 'actual_reader_image_count':len(images),'reader_settings_checked':True,
                                 'actual_query_controller_thinking_disabled':True,'prompt_sha256':hashlib.sha256((ROOT/reader/'prompt_rows.jsonl').read_bytes()).hexdigest()})
    table(OUT/'sequence_units.csv',rows);table(OUT/'per_question.csv',qa)
    dump(OUT/'compatibility.json',evidence);dump(OUT/'generated_memory_checks.json',reviews)
    totals=[]
    keys=['update_llm_tokens','update_llm_calls','update_publish_s','reextracted_events','regenerated_notes',
          'update_embedding_vectors','update_embedding_input_tokens','query_controller_input_tokens',
          'query_controller_output_tokens','query_reader_input_tokens','query_reader_output_tokens',
          'query_embedding_vectors','query_embedding_input_tokens','update_plus_query_llm_tokens',
          'update_plus_query_wall_s','fixed_questions','correct','complete_answers','pending','truncated',
          'service_failures','parse_failures']
    for policy in POLICIES:
        selected=[r for r in rows if r['policy']==policy]
        totals.append({'policy':policy,'updates':len(selected),'unique_target_trajectories':2,
                       'history_trajectories_per_domain':5, **{k:total(r.get(k) for r in selected) for k in keys}})
    table(OUT/'public_sequence.csv',totals)
    steady=[]
    for policy in POLICIES:
        selected=[r for r in rows if r['policy']==policy and r['round']>1]
        steady.append({'policy':policy,'updates':len(selected),
                       'scope':'rounds2-3 only; inherited own prior published snapshot; round1 costs remain in full table',
                       **{k:total(r.get(k) for r in selected) for k in keys}})
    table(OUT/'rounds2_3_component.csv',steady)
    continuous=[]
    for domain in ('web','enterprise'):
        for policy in POLICIES:
            previous_tokens=0;previous_wall=0
            for r in sorted((r for r in rows if r['domain']==domain and r['policy']==policy),key=lambda r:r['round']):
                previous_tokens=total([previous_tokens,r['update_plus_query_llm_tokens']])
                previous_wall=total([previous_wall,r['update_plus_query_wall_s']])
                continuous.append({'domain':domain,'policy':policy,'round':r['round'],
                    'cumulative_update_query_llm_tokens':previous_tokens,'cumulative_update_query_wall_s':previous_wall,
                    'published_event_chars':r['published_event_chars'],'current_evidence_blocks':r['current_evidence_blocks'],
                    'target_stored_event_chars':r['target_stored_event_chars'],
                    'target_query_eligible_event_chars':r['target_query_eligible_event_chars'],
                    'target_current_evidence_blocks':r['target_current_evidence_blocks'],
                    'raw_path':r['raw_update_path']})
    table(OUT/'continuous_cost.csv',continuous)
    continuous_figure(OUT/'continuous_cost.svg',continuous,
                      title='Development histories (5/domain): measured continuous maintenance',policies=POLICIES)
    evidence_figure(OUT/'evidence_size.svg',continuous,
                    title='Development histories (5/domain): published event size',
                    policies=['b3','source_coalesced','source_only'])
    lines=['# Public development sequential maintenance','',
        'Five complete trajectories/domain, two existing targets, three dependent revisions/target. '
        'All five methods have the same revised textual source, histories, fixed questions and Reader generation settings; '
        'actual messages have no images and query controllers disable thinking. Original retrieval designs retained. '
        'This is not full Small, an independent confirmation, or a fresh experiment. Initial construction is excluded.','',
        '| Method | Update LLM tokens | Update publication sum s | Update+query LLM tokens | Complete | Correct |',
        '|---|---:|---:|---:|---:|---:|']
    for r in totals:
        lines.append(f"| {r['policy']} | {r['update_llm_tokens']} | {r['update_publish_s']:.3f} | {r['update_plus_query_llm_tokens']} | {r['complete_answers']}/{r['fixed_questions']} | {r['correct']}/{r['fixed_questions']} |")
    lines+=['','Costs match query IDs to actual controller/embedding records. Historical Reader SDK retry allowance was not accompanied '
        'by a per-attempt transport ledger; displayed Reader usage is the recorded returned usage, not a claim to recover invisible retry costs. '
        'New formal transport disables those retries uniformly.','',
        'RAG+Notes round1 made two calls/domain: a new note request and JSON-format repair. The inherited5-trajectory '
        'snapshot contains matching request text but no recorded finish_reason or thinking value, so its old responses were not '
        'silently re-keyed as confirmed stop/thinking-off responses. Rounds2-3 each reuse both newly recorded responses and make '
        'zero note calls. Thus the round1 note cost is a provenance/cache-start transition, not evidence that literal source corrections '
        'intrinsically require note regeneration. The main table retains that actual cost; rounds2_3_component.csv isolates the later '
        'warm-cache phase without dropping round1 from lifecycle accounting. Formal full-history results are separately measured.','',
        'Generated event/Notes checks are exported separately; their pending semantic labels are not quality passes. '
        'Fixed answers and failures are retained. Repeated corrections do not increase independent target count.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(totals,indent=2))


if __name__=='__main__':main()
