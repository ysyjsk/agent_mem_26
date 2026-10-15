#!/usr/bin/env python3
import csv, glob, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 rows=[]
 for path in sorted(glob.glob(str(ROOT/'runs/method-first-20261015/v13-repeat*-*/literal_revision-*/update_metrics.json'))):
  p=Path(path);m=json.loads(p.read_text());q=m['quality_checks']
  rows.append({'run':p.parents[2].name,'trajectory_id':m['trajectory_id'],'policy':m['policy'],
   'update_llm_tokens':m['llm_input_tokens_known']+m['llm_output_tokens_known'],'llm_calls':m['llm_calls'],
   'publish_s':m['update_to_queryable_publish_s'],'embedding_tokens':m['embedding_tokens_known'],
   'embedding_vectors':m['embedding_vectors'],'derived_checks':q['derived_automated_checks_pass'],
   'raw_path':str(p.parent.relative_to(ROOT))})
 out=ROOT/'results/tables/method_v13_repeats.csv'
 if rows:
  with out.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 lines=['# V13 paired cost repeats','','Two independent paired repeats start from the same original matched snapshots; B3/coalesced order alternates across passes. No query reruns are claimed.','', '| Run | Trajectory | Policy | Update tokens/calls | Publish s | Embedding tokens/vectors | Source-derived checks |','|---|---|---|---:|---:|---:|---|']
 for r in rows: lines.append(f"| {r['run']} | {r['trajectory_id']} | {r['policy']} | {r['update_llm_tokens']}/{r['llm_calls']} | {r['publish_s']:.3f} | {r['embedding_tokens']}/{r['embedding_vectors']} | {r['derived_checks']} |")
 for policy in ('b3','source_coalesced'):
  z=[r for r in rows if r['policy']==policy]
  lines.append(f"| **sum {policy}** | 4 paired cases | {policy} | {sum(r['update_llm_tokens'] for r in z)} | {sum(r['publish_s'] for r in z):.3f} | {sum(r['embedding_tokens'] for r in z)} | {sum(bool(r['derived_checks']) for r in z)}/{len(z)} |")
 lines += ['', 'Coalescing remains zero-update-LLM by construction. The source-derived lexical rule may flag stale prose that is explicitly labeled prior/non-authoritative; this is retained as a quality limitation, not silently counted as a pass. Reader confirmation is supplied by the sequential and held-out tables.']
 (ROOT/'reports/method_v13_repeats.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps({'rows':len(rows)}))
if __name__=='__main__': main()
