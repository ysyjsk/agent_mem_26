#!/usr/bin/env python3
"""Versioned offline report; never overwrites old measurements or counts builds anew."""
import argparse
import csv
import json
from pathlib import Path
from focused_evidence import costs, fact_roles, jsonl

ROOT = Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--reader-root', action='append', default=[])
    p.add_argument('--reader-dir', action='append', default=[])
    p.add_argument('--legacy', action='store_true')
    p.add_argument('--output', required=True)
    args=p.parse_args()
    output=Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    dirs=[]
    dirs.extend(Path(path)/'aggregated_metrics.json' for path in args.reader_dir)
    for root in args.reader_root:
        dirs.extend(Path(root).glob('*/aggregated_metrics.json'))
    if args.legacy:
        dirs.extend((ROOT/'runs/focused-maintenance-v4/formal').glob('*-update/literal_revision-*/revision_reader/aggregated_metrics.json'))
    rows=[]
    for metric in sorted(set(dirs)):
        reader=metric.parent
        run=json.loads((reader/'run_args.json').read_text())
        update_dir=Path(run['load_memory_dir']).parent
        update=json.loads((update_dir/'update_metrics.json').read_text())
        qa=json.loads(metric.read_text())
        row={'domain':run['domain'], 'policy':update['policy'],
             'history_trajectories':len(json.loads((update_dir/'memory_state/index.json').read_text())['inserted_trajectory_ids']),
             'query_configuration':'noncompliant_legacy' if args.legacy else 'repaired_text_only',
             'update_cost_origin':'reused_actual_measurement_not_new_update',
             'fixed_questions':len(jsonl(reader/'per_question.jsonl')),
             'update_publish_s':update['update_to_queryable_publish_s'],
             'update_embedding_calls':update['embedding_calls'],
             'update_embedding_vectors':update['embedding_vectors'],
             'update_embedding_tokens_known':update['embedding_tokens_known'],
             'regenerated_notes':update['regenerated_notes'],
             'raw_update_path':str(update_dir.relative_to(ROOT)),
             'raw_reader_path':str(reader.resolve().relative_to(ROOT))}
        row.update(costs(update_dir,reader))
        row.update({'reader_'+k:v for k,v in qa['answer_status'].items()})
        row['query_prompt_build_s']=qa['timing']['prompt_build_wall_seconds']
        row['query_reader_generation_s']=qa['timing']['reader_generation_wall_seconds']
        review=json.loads((update_dir/'derived_quality_review.json').read_text())
        trajectory=json.loads((update_dir/'update_input.json').read_text())['trajectory']
        quality=fact_roles(review,trajectory,update['policy'])
        label=run['domain']+'-'+update['policy']
        (output/(label+'-fact-roles.json')).write_text(json.dumps(quality,ensure_ascii=False,indent=2)+'\n')
        rows.append(row)
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (output/'cost_quality.csv').open('x') as stream:
        w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
    lines=['# Query configuration recovery: measured results','',
           'Development-scale histories only (10/domain). Update costs are reused from saved paired runs; only queries were newly executed. Initial cost is excluded. Questions are already exposed. No quality equivalence or full-Small completion is claimed.','',
           '| Domain | Policy | Update tokens | Controller tokens | Reader tokens | Total LLM tokens | Correct / fixed | Truncated |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    def tokens(r,prefix):
        a,b=r[prefix+'_input_tokens'],r[prefix+'_output_tokens']
        return 'unknown' if a is None or b is None else a+b
    for r in rows:
        lines.append(f"| {r['domain']} | {r['policy']} | {tokens(r,'update_llm')} | {tokens(r,'query_controller')} | {tokens(r,'query_reader')} | {r['update_plus_query_llm_tokens']} | {r['reader_correct']}/{r['fixed_questions']} | {r['reader_truncated']} |")
    lines += ['', 'Role-specific quality files preserve the previous checks. Changed evidence, unchanged full-event facts and stale source lines are separated; semantic attribution remains pending.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'rows':len(rows),'output':str(output)}))


if __name__=='__main__':
    main()
