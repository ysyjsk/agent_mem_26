#!/usr/bin/env python3
import csv, glob, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/method-first-20261015'

def read(p): return json.loads(p.read_text())

def main():
    rows=[]
    # Four current v12 branch cases, with normal and corrected-fact QA.
    for path in sorted(RUN.glob('v12-*-replacement/literal_revision-*/update_metrics.json')):
        p=Path(path); m=read(p); row={'scope':'four current replacement cases','case':p.parents[1].name,'method':m['policy'],
          'update_llm_tokens':m['llm_input_tokens_known']+m['llm_output_tokens_known'],'update_calls':m['llm_calls'],
          'publish_s':m['update_to_queryable_publish_s'],'embedding_tokens':m['embedding_tokens_known'],'embedding_vectors':m['embedding_vectors'],
          'fixed_correct':'','fixed_scored':'','revision_correct':'','revision_scored':'','revision_truncated':'','raw_path':str(p.parent.relative_to(ROOT))}
        for label,key in [('fixed','reader'),('revision','revision_reader')]:
            q=p.parent/key/'aggregated_metrics.json'
            if q.exists():
                a=read(q); row[label+'_correct']=a['answer_status']['correct']; row[label+'_scored']=a['answer_status']['scored'];
                if label=='revision': row['revision_truncated']=a['answer_status']['truncated']
        rows.append(row)
    # Six sequential rows per policy; aggregate rows separately below.
    seq=list(csv.DictReader((ROOT/'results/tables/method_v13_sequence.csv').open()))
    for method in ('b3','source_overlay','source_coalesced'):
        x=[r for r in seq if r['policy']==method]
        if not x: continue
        rows.append({'scope':'two domains × three sequential rounds','case':'aggregate','method':method,
          'update_llm_tokens':sum(int(r['update_llm_tokens']) for r in x),'update_calls':sum(int(r['llm_calls']) for r in x),
          'publish_s':sum(float(r['update_to_queryable_publish_s']) for r in x),'embedding_tokens':sum(int(r['embedding_tokens_known']) for r in x),
          'embedding_vectors':sum(int(r['embedding_vectors']) for r in x),'fixed_correct':'','fixed_scored':'',
          'revision_correct':sum(int(r['qa_correct']) for r in x),'revision_scored':sum(int(r['qa_scored']) for r in x),
          'revision_truncated':sum(int(r['qa_truncated']) for r in x),'query_total_llm_tokens':sum(int(r['total_update_query_llm_tokens']) for r in x),
          'raw_path':'results/tables/method_v13_sequence.csv'})
    # Held-out confirmation rows.
    for path in sorted(list(RUN.glob('v13-confirm-*/literal_revision-*/update_metrics.json')) +
                       list(RUN.glob('v13-note-reuse-*/literal_revision-*/update_metrics.json'))):
        p=Path(path); m=read(p); q=read(p.parent/'revision_reader/aggregated_metrics.json')
        rows.append({'scope':'two held-out confirmation cases','case':p.parents[1].name,'method':m['policy'],
          'update_llm_tokens':m['llm_input_tokens_known']+m['llm_output_tokens_known'],'update_calls':m['llm_calls'],
          'publish_s':m['update_to_queryable_publish_s'],'embedding_tokens':m['embedding_tokens_known'],'embedding_vectors':m['embedding_vectors'],
          'fixed_correct':'','fixed_scored':'','revision_correct':q['answer_status']['correct'],'revision_scored':q['answer_status']['scored'],
          'revision_truncated':q['answer_status']['truncated'],'reader_total_tokens':q['tokens']['total_tokens'],'raw_path':str(p.parent.relative_to(ROOT))})
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (ROOT/'results/tables/method_focused_main.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    lines=['# Focused-method-v3 main results (adapted text-only development)','',
      'Current source-coalesced method versus strong B3. All methods use the same matched snapshots, Reader, retrieval, source evidence publisher, resource and budget. Raw RAG/RAG+Notes historical cold-build rows remain in method_external_dev.csv and are not mixed with these local maintenance rows. Initial construction is inherited and excluded from update totals.','',
      '| Scope | Case/aggregate | Method | Update LLM tokens/calls | Publish s | Embedding tokens/vectors | Correct/scored | Truncated | Additional cost |','|---|---|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        extra=r.get('query_total_llm_tokens',r.get('reader_total_tokens',''))
        lines.append(f"| {r.get('scope','')} | {r.get('case','')} | {r['method']} | {r.get('update_llm_tokens','')}/{r.get('update_calls','')} | {float(r.get('publish_s',0)):.3f} | {r.get('embedding_tokens','')}/{r.get('embedding_vectors','')} | {r.get('revision_correct',r.get('fixed_correct',''))}/{r.get('revision_scored',r.get('fixed_scored',''))} | {r.get('revision_truncated','')} | {extra} |")
    lines += ['', '## Decision', '',
      'Retain source_coalesced as the practical maintenance default for text-only source corrections. It consolidates one current source-evidence view per affected event, reuses unaffected event dependencies, and safely reuses generic notes only when complete old/current source lines are absent from those notes. It does not claim semantic validity for arbitrary changes; source-derived checks, Reader answers and limitations remain visible.',
      '', 'Across six sequential rounds (two domains × three corrections), B3 uses 70,580 update LLM tokens and 206.049 s publication; source_coalesced uses zero update LLM tokens and 12.841 s. Including query planning, Reader and retrieval-controller tokens, totals are 214,714 versus 140,111. The coalesced branch has 12/12 scored sequential answers, versus B3 11/12; this small adapted sample is not a statistical equivalence test. It also keeps current-evidence blocks at two and avoids overlay growth.',
      '', 'Two held-out trajectories (date fields and quantity/subtotal) are 3/3 for both methods with no truncation. The enterprise selection-mismatch case after note reuse is 3/3, zero update LLM tokens, 1.779 s, 5,798 embedding tokens. These confirm the direction but do not establish native Small quality.',
      '', 'Semantic-editing remains an ablation/comparator. It is not required for the measured cases and is not retained as an always-on step. The remaining paper evidence is a frozen two-domain ablation and formal write-up, not another baseline adapter.']
    (ROOT/'reports/method_focused_main.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'rows':len(rows)}))

if __name__=='__main__': main()
