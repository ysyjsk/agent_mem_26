#!/usr/bin/env python3
"""Combine compatible repaired queries and real public maintenance measurements."""
import csv
import json
from pathlib import Path
from focused_evidence import costs,jsonl

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/focused-maintenance-v4'
OUT=ROOT/'reports/execution-recovery-20261016/public-v1'


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    rows=[]
    for domain in ['web','enterprise']:
        for policy in ['raw_rag','rag_notes','b3','source_coalesced','source_only','source_overlay']:
            if policy in ('raw_rag','rag_notes'):
                update=RUN/f'public-repair-20261016/paired10/{domain}-{policy}'
                diagnostic=update/'diagnostic-reader';normal=update/'normal-reader'
            else:
                update=RUN/f'formal/{domain}-'+Path('') if False else RUN/f'formal/{domain}-update/literal_revision-{policy}'
                if policy=='source_overlay':update=RUN/f'formal/{domain}-ablation-update/literal_revision-{policy}'
                folder='pair-v1' if policy in ('b3','source_coalesced') else 'remaining-v1'
                diagnostic=RUN/f'repair-20261016/{folder}/{domain}-{policy}'
                normal=RUN/f'repair-20261016/normal-v1/{domain}-{policy}'
            u=json.loads((update/'update_metrics.json').read_text())
            a,b=costs(update,diagnostic),costs(update,normal)
            # One update, then both distinct fixed query sets. Never double
            # count the same update just because two reports reference it.
            row={'domain':domain,'policy':policy,'history_trajectories':10,
                 'update_origin':'new_public_maintenance' if policy in ('raw_rag','rag_notes') else 'reused_update_measurement',
                 'update_publish_s':u['update_to_queryable_publish_s']}
            for key in ['update_llm_calls','update_llm_input_tokens','update_llm_output_tokens']:
                row[key]=a[key]
            for prefix in ['query_controller','query_reader']:
                for suffix in ['input_tokens','output_tokens']:
                    key=prefix+'_'+suffix
                    row[key]=None if a[key] is None or b[key] is None else a[key]+b[key]
            components=[row[p+'_'+s] for p in ['update_llm','query_controller','query_reader'] for s in ['input_tokens','output_tokens']]
            row['update_plus_query_llm_tokens']=None if None in components else sum(components)
            row['update_embedding_vectors']=u['embedding_vectors'];row['update_embedding_tokens_known']=u['embedding_tokens_known']
            row['query_embedding_vectors']=a['query_embedding_vectors']+b['query_embedding_vectors']
            row['query_embedding_input_tokens']=a['query_embedding_input_tokens']+b['query_embedding_input_tokens']
            row['update_plus_queries_stage_wall_s']=a['update_query_stage_wall_s']+b['update_query_stage_wall_s']-u['update_to_queryable_publish_s']
            for name,path in [('diagnostic',diagnostic),('normal',normal)]:
                qa=json.loads((path/'aggregated_metrics.json').read_text())['answer_status']
                row[name+'_fixed_questions']=len(jsonl(path/'per_question.jsonl'))
                for k,v in qa.items():row[name+'_'+k]=v
            row['raw_update_path']=str(update.relative_to(ROOT));row['raw_diagnostic_path']=str(diagnostic.relative_to(ROOT));row['raw_normal_path']=str(normal.relative_to(ROOT))
            rows.append(row)
    with (OUT/'public_main.csv').open('x') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    totals=[]
    for policy in dict.fromkeys(r['policy'] for r in rows):
        selected=[r for r in rows if r['policy']==policy]
        totals.append({'policy':policy,**{k:sum(r[k] for r in selected) for k in ['update_publish_s','update_llm_input_tokens','update_llm_output_tokens','update_plus_query_llm_tokens','diagnostic_correct','diagnostic_fixed_questions','normal_correct','normal_fixed_questions']}})
    lines=['# Repaired public development maintenance comparison','',
           'Two shared 10-trajectory histories; one revision/domain; four exposed diagnostic and eight fixed normal questions. Original retrieval designs retained; common text-only Reader/chunk/backfill settings. Update measured once per branch and reused for both question sets. Not full Small or independent confirmation.','',
           '| Method | Update publish sum (s) | Update LLM tokens | Update + all fixed queries tokens | Diagnostic | Normal |',
           '|---|---:|---:|---:|---:|---:|']
    for r in totals:lines.append(f"| {r['policy']} | {r['update_publish_s']:.3f} | {r['update_llm_input_tokens']+r['update_llm_output_tokens']} | {r['update_plus_query_llm_tokens']} | {r['diagnostic_correct']}/{r['diagnostic_fixed_questions']} | {r['normal_correct']}/{r['normal_fixed_questions']} |")
    lines+=['','No equivalence claim on this small exposed set. Literal source revisions do not change the existing note-generation request; exact request reuse is legal. Workflow-intent updates are separately predeclared for the formal matrix.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(totals))


if __name__=='__main__':main()
