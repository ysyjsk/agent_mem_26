#!/usr/bin/env python3
"""Report measured current branches and external history without mixing scopes."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'runs/method-first-20261015'


def write_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)


def main():
    branch=[]
    for run in sorted(RUN.glob('v12-*-replacement')):
        for policy in ('b3','delta_guarded','source_overlay'):
            folder=run/f'literal_revision-{policy}'
            if not (folder/'update_metrics.json').exists():
                continue
            m=json.loads((folder/'update_metrics.json').read_text())
            row={k:m.get(k) for k in ('policy','trajectory_id','state_index','llm_calls',
                'llm_input_tokens_known','llm_output_tokens_known','embedding_calls','embedding_vectors',
                'embedding_tokens_known','update_to_queryable_publish_s','api_failed_calls','unknown_usage_calls',
                'reextracted_event_outputs','regenerated_notes','delta_fallback_groups')}
            row.update(case=run.name,scope='independent correction from common matched snapshot',raw_path=str(folder.relative_to(ROOT)),
                derived_lexical_checks=m['quality_checks']['derived_automated_checks_pass'],
                semantic_quality='not_certified_by_raw_or_regex')
            for label,sub in [('fixed','reader'),('revision_retrieval','revision_reader')]:
                p=folder/sub/'aggregated_metrics.json'
                if p.exists():
                    a=json.loads(p.read_text())
                    row.update({label+'_'+k:v for k,v in a['answer_status'].items()})
                    row[label+'_reader_input_tokens']=a['tokens']['prompt_tokens']
                    row[label+'_reader_output_tokens']=a['tokens']['completion_tokens']
                    row[label+'_prompt_wall_s']=a['timing']['prompt_build_wall_seconds']
                    row[label+'_reader_wall_s']=a['timing']['reader_generation_wall_seconds']
            branch.append(row)
    write_csv(ROOT/'results/tables/method_v12_branches.csv',branch)
    old=list(csv.DictReader((ROOT/'results/tables/dev_adapted_first_compare.csv').open()))
    # Select pre-existing frozen variants, never choose the best sampled answer.
    selected=[('M: L + lexical source backfill','Raw RAG'),
              ('O: Notes+M + query embedding reuse','RAG+Notes'),
              ('AgentRunbook-R + backfill','AgentRunbook-R')]
    external=[]
    for source,name in selected:
        r=next(x for x in old if x['method']==source)
        external.append(dict(method=name,scope='10 complete trajectories / 8 fixed questions',
            measurement='historical build and historical query; NOT rerun this round',
            build_publish_s=r['build_publish_s'],llm_calls=r['build_controller_calls'],
            input_tokens=r['build_controller_input_tokens'],output_tokens=r['build_controller_output_tokens'],
            failed_calls=r['build_controller_failed'],unknown_failed_usage=r['build_controller_unknown_input_usage_calls'],
            embedding_input_tokens=r['build_embedding_input_tokens'],correct=r['correct'],complete=r['complete'],
            questions=r['questions'],query_wall_s=r['prompt_wall_s'],reader_wall_s=r['reader_wall_s'],
            raw_build=r['build_suffix'],raw_reader=r['reader_suffix'],
            caveat='AgentRunbook historical query lacks query-embedding reuse; cost not a matched new query measurement' if name=='AgentRunbook-R' else r['configuration_caveat']))
    mf_root=ROOT/'runs/memforest-shared-dev-20261015'
    for domain in ('web','enterprise'):
        folder=mf_root/(domain+'-v1'); b=folder/'build_metrics.json'; q=folder/'query_metrics.json'
        if b.exists():
            m=json.loads(b.read_text()); a=json.loads(q.read_text()) if q.exists() else {}
            external.append(dict(method='MemForest',scope=f'{domain}: 5 complete trajectories / 4 fixed questions',
                measurement='fresh shared-library native algorithm / local text-only adapter',
                build_publish_s=m['build_publish_s'],llm_calls=m['llm_calls'],
                input_tokens=m['llm_input_tokens_known'],output_tokens=m['llm_output_tokens_known'],
                failed_calls=m['failed_calls'],unknown_failed_usage=m['unknown_usage_calls'],
                embedding_input_tokens=m['embedding_input_tokens_known'],correct=a.get('correct','pending'),
                complete=a.get('complete','pending'),questions=4,query_wall_s=a.get('retrieval_wall_s','pending'),
                reader_wall_s=a.get('reader_wall_s','pending'),raw_build=str(folder.relative_to(ROOT)),
                raw_reader=str(folder.relative_to(ROOT)),caveat='upstream tree/agentic retrieval, common Reader; no source truncation'))
    write_csv(ROOT/'results/tables/method_external_dev.csv',external)
    lines=['# Current method branches and early external development comparison','',
        'Text-only/adapted, not native Small, no external Judge. Frozen questions and full shared domain histories. '
        'Tables intentionally separate historical cold construction, new maintenance and query. Current Ours is v12 overlay/edit, NOT the old workflow-core Ours. '
        'Matched starting snapshots combine inherited history with refreshed selected partitions: their full cold cost is not newly measured here.','',
        '## Current branch comparison','',
        '| Case | Policy | Update LLM in/out | Calls | Publish s | Embedding tokens/vectors | Fixed QA | Full-retrieval revision QA | Derived lexical check |',
        '|---|---|---:|---:|---:|---:|---:|---:|---|']
    for r in branch:
        lines.append(f"| {r['trajectory_id']} | {r['policy']} | {r['llm_input_tokens_known']}/{r['llm_output_tokens_known']} | {r['llm_calls']} | {r['update_to_queryable_publish_s']:.3f} | {r['embedding_tokens_known']}/{r['embedding_vectors']} | {r.get('fixed_correct','pending')}/{r.get('fixed_scored','?')} | {r.get('revision_retrieval_correct','pending')}/{r.get('revision_retrieval_scored','?')} | {r['derived_lexical_checks']} |")
    lines += ['', 'Regex failure remains visible; old strings in explicitly superseded interpretations need version-aware semantic review. '
              'Complete response is not correctness. Fixed QA does not by itself validate the corrected value. '
              'All independent snapshots/repeated questions are reported as such, not independent statistical samples.','',
              '## External development measurements','',
              '| Method / scope | Measurement | Cold publish s | Build LLM in/out | Calls (failed) | QA | Query / Reader s |',
              '|---|---|---:|---:|---:|---:|---:|']
    for r in external:
        lines.append(f"| {r['method']} / {r['scope']} | {r['measurement']} | {float(r['build_publish_s']):.2f} | {r['input_tokens']}/{r['output_tokens']} | {r['llm_calls']} ({r['failed_calls']}) | {r['correct']}/{r['questions']} | {r['query_wall_s']} / {r['reader_wall_s']} |")
    lines += ['', 'Raw paths, usage gaps and configuration caveats are in the companion CSV files. '
              'Raw RAG/RAG+Notes historical results already make low cold cost a relevant constraint; no claim of current-method cold-build superiority. '
              'MemForest is not removed if incomplete: inspect its model_calls/build_progress and finish the shared library.','',
              '## Decision (provisional)','',
              'Retain source_overlay as the cheap candidate and delta_guarded as the semantic-edit comparator. '
              'The first two normal-regression cases tie all three branches (7/8 each, 24/24 complete). '
              'Do not freeze from these: complete other two corrections, full-retrieval changed-value probes, preselected invalidated-conclusion cases, '
              'external shared-library quality and actual sequential maintenance before selecting. No query parameter sweep.']
    (ROOT/'reports/method_external_dev.md').write_text('\n'.join(lines)+'\n')
    print(f'{len(branch)} branch rows; {len(external)} external rows')


if __name__=='__main__':
    main()
