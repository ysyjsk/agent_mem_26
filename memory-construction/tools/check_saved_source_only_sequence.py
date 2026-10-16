#!/usr/bin/env python3
"""Read-only checks of real Source-only sequence snapshots and Reader contexts."""
import argparse
import json
from pathlib import Path
import re

import numpy as np

from focused_evidence import jsonl
from report_full_small_formal import dump, load, table

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/execution-recovery-20261016/source-only-saved-sequence-v1'


def event_results(items):
    result=[]
    for item in items:
        if item.get('type')!='text':continue
        text=item.get('value',item.get('text',''))
        if not text.startswith('### Event result'):continue
        header=text.split('\n\nDescription',1)[0]
        tid=re.search(r'^- Trajectory: (\S+)',header,re.M)
        transition=re.search(r'- Transition: state (\d+) -> .* -> state (\d+)',header,re.S)
        if not tid or not transition:raise ValueError(f'Unparsed saved event header: {header}')
        result.append((tid[1],int(transition[1]),int(transition[2])))
    return result


def snapshot(memory,name,vector):
    entries=jsonl(memory/'pools'/f'{name}_pool.jsonl')
    vectors=np.load(memory/'embeddings'/vector,allow_pickle=False)
    if len(entries)!=len(vectors):raise ValueError('Pool/vector mismatch')
    return {e['entry_id']:(e,v) for e,v in zip(entries,vectors)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT)
    out=parser.parse_args().output
    out.mkdir(parents=True,exist_ok=False)
    queries=[];snapshots=[]
    for domain in ('web','enterprise'):
        for n in (1,2,3):
            folder=ROOT/f'runs/focused-maintenance-v4/dev/sequence-final/{domain}-r{n}/literal_revision-source_only'
            metric=load(folder/'update_metrics.json');old=Path(metric['starting_snapshot']);new=folder/'memory_state'
            tid=metric['trajectory_id'];review=load(folder/'derived_quality_review.json')
            before=snapshot(old,'event','event.npy');after=snapshot(new,'event','event.npy')
            retired={(e['trajectory_id'],e['pre_state_index'],e['post_state_index']) for e,v in after.values()
                     if e.get('validity_status')=='invalidated_source_change'}
            old_retired={key for key,(e,v) in before.items() if e.get('validity_status')=='invalidated_source_change'}
            remain_retired=all(after[key][0].get('validity_status')=='invalidated_source_change' for key in old_retired)
            unchanged=[key for key,(e,v) in after.items() if e.get('validity_status')!='invalidated_source_change']
            unchanged_events_preserved=all(before[key][0]['description']==after[key][0]['description'] and
                                            np.array_equal(before[key][1],after[key][1]) for key in unchanged)
            note_checks=[]
            for name,vec in [('procedure_note','procedure_notes.npy'),('hint_note','hint_notes.npy')]:
                a=snapshot(old,name,vec);b=snapshot(new,name,vec)
                note_checks.append(a.keys()==b.keys() and all(a[k][0]==b[k][0] and np.array_equal(a[k][1],b[k][1]) for k in a))
            source=load(folder/'update_input.json')['trajectory'];stored=load(new/'trajectories'/tid/'trajectory.json')
            raw='\n'.join(e.get('slice_axtree_text','') for e in jsonl(new/'pools/raw_state_pool.jsonl') if e['trajectory_id']==tid)
            edits=review['workload']['source_edits']
            changed_lines={line.strip() for e in edits if e['field']=='text' for line in e['new'].splitlines() if line.strip()}
            raw_published=all(line in raw for line in changed_lines)
            one={'domain':domain,'round':n,'raw_path':str(folder.relative_to(ROOT)),
                 'source_roundtrip':source==stored,'prior_retired_events_remain_retired':remain_retired,
                 'retired_events':len(retired),'unchanged_event_descriptions_and_vectors_preserved':unchanged_events_preserved,
                 'notes_and_vectors_preserved':all(note_checks),'corrected_source_lines_in_raw_pool':raw_published}
            snapshots.append(one)
            answers={a['question_id']:a for a in jsonl(folder/'revision_reader/per_question.jsonl')}
            for row in jsonl(folder/'revision_reader/prompt_rows.jsonl'):
                results=event_results(row['memory_context'])
                actual_text='\n'.join(part.get('text','') for msg in row['messages'] for part in msg.get('content',[]) if isinstance(part,dict))
                hits=retired & set(results)
                present_lines=sorted(line for line in changed_lines if line in actual_text)
                missing_lines=sorted(changed_lines-set(present_lines))
                answer=answers[row['question_id']]
                queries.append({'domain':domain,'round':n,'question_id':row['question_id'],
                    'retrieved_event_count':len(results),'invalidated_event_retrievals':len(hits),
                    'all_changed_source_lines_in_actual_reader_text':all(line in actual_text for line in changed_lines),
                    'changed_source_line_count':len(changed_lines),
                    'changed_source_lines_present':len(present_lines),
                    'present_changed_lines':json.dumps(present_lines,ensure_ascii=False),
                    'missing_changed_lines':json.dumps(missing_lines,ensure_ascii=False),
                    'target_state_source_excerpts':json.dumps([
                        line.strip() for line in actual_text.splitlines()
                        if any(f"[{tid} state {edit['state_index']} line " in line for edit in edits)
                    ],ensure_ascii=False),
                    'answer':answer.get('response_parsed_boxed'),
                    'gold':answer.get('answer_gold'),'score':answer.get('score'),
                    'reader_complete':answer.get('reader_answer_complete'),
                    'reader_output_truncated':answer.get('reader_truncated'),
                    'memory_context_budget_pruned':row.get('memory_context_was_truncated'),
                    'raw_path':str((folder/'revision_reader/prompt_rows.jsonl').relative_to(ROOT)),
                    'scope':'Changed-line recall is a query diagnostic, not required for an unrelated question; old values in untouched states are not automatically stale.'})
    table(out/'snapshots.csv',snapshots);table(out/'queries.csv',queries)
    result={'snapshots':len(snapshots),'saved_queries':len(queries),
            'invalidated_event_retrievals':sum(q['invalidated_event_retrievals'] for q in queries),
            'all_snapshot_structural_checks':all(all(v for k,v in r.items() if isinstance(v,bool)) for r in snapshots),
            'queries_containing_all_changed_lines':sum(q['all_changed_source_lines_in_actual_reader_text'] for q in queries),
            'queries_containing_any_changed_line':sum(q['changed_source_lines_present']>0 for q in queries),
            'scored_correct':sum(q['score']==1 for q in queries),
            'scored_incorrect_with_some_changed_lines':sum(q['score']==0 and q['changed_source_lines_present']>0 for q in queries),
            'no_new_model_calls':True,'scope':'real saved same-state3-round sequence; cross-state save/reload separately covered by CPU regression',
            'semantic_quality_equivalence':False}
    dump(out/'report.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
