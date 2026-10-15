#!/usr/bin/env python3
"""Aggregate the persisted local AgentRunbook-R B3/Ours updates."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


if __name__=='__main__': main()
