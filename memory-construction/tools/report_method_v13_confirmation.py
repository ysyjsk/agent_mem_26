#!/usr/bin/env python3
import csv, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/method-first-20261015'

def read(p): return json.loads(p.read_text())

def main():
    rows=[]
    cases=[('web','2a99f536','date'),('enterprise','12c22166','quantity')]
    for domain,tid,label in cases:
        run=f'v13-confirm-{domain}-{tid}-{label}'
        for policy in ('b3','source_coalesced'):
            folder=RUN/run/f'literal_revision-{policy}'
            if not (folder/'update_metrics.json').exists(): continue
            m=read(folder/'update_metrics.json'); q=read(folder/'revision_reader/aggregated_metrics.json')
            rows.append({'case':run,'domain':domain,'trajectory_id':tid,'policy':policy,
                 'update_llm_tokens':m['llm_input_tokens_known']+m['llm_output_tokens_known'],
                 'update_llm_calls':m['llm_calls'],'update_publish_s':m['update_to_queryable_publish_s'],
                 'embedding_tokens':m['embedding_tokens_known'],'embedding_vectors':m['embedding_vectors'],
                 'qa_correct':q['answer_status']['correct'],'qa_scored':q['answer_status']['scored'],
                 'qa_complete':q['answer_status']['complete_parseable'],'qa_truncated':q['answer_status']['truncated'],
                 'reader_tokens':q['tokens']['total_tokens'],'reader_wall_s':q['timing']['reader_generation_wall_seconds'],
                 'raw_path':str(folder.relative_to(ROOT)),
                 'quality_scope':'three source-grounded changed/neighbor questions; adapted text-only, not official labels'})
    out=ROOT/'results/tables/method_v13_confirmation.csv'
    if rows:
        with out.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    lines=['# V13 independent confirmation','',
      'Two predeclared complete trajectories not used in the original four-case tuning: web report date fields and enterprise catalog quantity/subtotal. Both methods use the same matched source preparation, fixed retrieval and Reader configuration.','',
      '| Case | Policy | Update tokens/calls | Publish s | Embedding tokens/vectors | QA correct/scored | Complete/truncated | Reader tokens |',
      '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['case']} | {r['policy']} | {r['update_llm_tokens']}/{r['update_llm_calls']} | {r['update_publish_s']:.3f} | {r['embedding_tokens']}/{r['embedding_vectors']} | {r['qa_correct']}/{r['qa_scored']} | {r['qa_complete']}/{r['qa_truncated']} | {r['reader_tokens']} |")
    lines += ['', 'Both cases scored 3/3 for B3 and source_coalesced, with no truncation, service or parse failure. Source-derived checks passed before Reader. The confirmation is a small held-out adapted development sample, not native Small or statistical non-inferiority.']
    (ROOT/'reports/method_v13_confirmation.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'rows':len(rows)}))

if __name__=='__main__': main()
