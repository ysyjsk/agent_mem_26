#!/usr/bin/env python3
"""Versioned reuse of the existing v13 confirmation; no new inference."""
import json
from pathlib import Path

from focused_evidence import jsonl
from report_full_small_formal import dump, load, quality_record, table, total, update_evidence

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/execution-recovery-20261016/confirmation-reuse-v1'


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    rows,answers,checks=[],[],[]
    for domain,label,tid in [('web','date','2a99f536'),('enterprise','quantity','12c22166')]:
        cid=f'v13-confirm-{domain}-{tid}-{label}'
        pair_signatures=[]
        for policy in ('b3','source_coalesced'):
            folder=Path('runs/method-first-20261015')/cid/f'literal_revision-{policy}'
            reader=folder/'revision_reader'
            prompts=jsonl(ROOT/reader/'prompt_rows.jsonl')
            assert not any(item.get('type')=='image_url' for row in prompts for msg in row['messages']
                           for item in msg.get('content',[]) if isinstance(item,dict))
            args=load(ROOT/reader/'run_args.json')
            for key,value in {'reader_enable_thinking':False,'max_completion_tokens':2048,'memory_context_max_tokens':12000,
                              'temperature':.6,'top_p':.95,'top_k':20}.items():assert args[key]==value
            qids={r['query_invocation_id'] for r in prompts}
            controller=[r for r in jsonl(ROOT/folder/'memory_state/model_calls.jsonl')
                        if r.get('query_invocation_id') in qids and r['channel']=='controller']
            assert controller and all(r.get('enable_thinking') is False for r in controller)
            m=load(ROOT/folder/'update_metrics.json')
            pair_signatures.append((m['starting_snapshot'],m['matched_construction_signature'],m['runner_sha256']))
            step={'id':cid+'-'+policy,'domain':domain,'policy':policy,'phase':'historical_confirmation',
                  'case_id':cid,'repeat':1,'round':1,'marker':str(folder/'update_metrics.json')}
            query={'id':step['id']+'-query','domain':domain,'policy':policy,'reader':str(reader),
                   'memory':str(folder/'memory_state'),'questions':args['questions_path'],
                   'marker':str(reader/'aggregated_metrics.json'),'query_kind':'historical_confirmation'}
            row,qa,_=update_evidence(step,[query])
            row['actual_images']=0
            row['source_version']='a04bcf7c v13 core; before rejected notes heuristic; old Source-only not involved'
            row['exposure']='historically designated confirmation; now exposed/reused; NOT new held-out v4 evidence'
            rows.append(row);answers.extend(qa);checks.append(quality_record(step))
        assert pair_signatures[0]==pair_signatures[1],(cid,'unmatched construction')
    table(OUT/'confirmation.csv',rows);table(OUT/'per_question.csv',answers);dump(OUT/'generated_memory_checks.json',checks)
    totals=[]
    for policy in ('b3','source_coalesced'):
        selected=[r for r in rows if r['policy']==policy]
        totals.append({'policy':policy,**{k:total(r[k] for r in selected) for k in
            ('update_llm_tokens','update_publish_s','update_plus_query_llm_tokens','update_plus_query_wall_s','correct','fixed_questions')}})
    dump(OUT/'totals.json',totals)
    lines=['# Reused historical v13 confirmation','',
        'Existing date/quantity cases are retained with their original version and exposure. '
        'Both branches share a starting snapshot/construction signature and runner. Actual Reader messages are text-only, '
        'Reader settings match2048/12000/thinking-off, and query controller thinking is disabled. No new calls were made. '
        'The old report describes preselection outside the original four-case tuning; this reuse does not create '
        'new independent confirmation or retroactively certify selection history.','',
        '| Policy | Update tokens | Publish sum s | Update+query tokens | Correct |',
        '|---|---:|---:|---:|---:|']
    for r in totals:lines.append(f"| {r['policy']} | {r['update_llm_tokens']} | {r['update_publish_s']:.3f} | {r['update_plus_query_llm_tokens']} | {r['correct']}/{r['fixed_questions']} |")
    lines+=['','New totals include retrieval controllers. Historical SDK retries lack an independent attempt ledger; '
        'Reader costs are recorded response usage. Generated event/Notes checks and original negative evidence are retained. '
        'Formal full-history execution still evaluates these now-exposed cases, including workflow updates; '
        'the historical6/6 is not pooled into its denominator or claimed statistically equivalent.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(totals,indent=2))


if __name__=='__main__':main()
