#!/usr/bin/env python3
"""Freeze the original required full histories and a fixed maintenance workload.

Selection is by the previously specified page types/complete source coverage,
not method scores. All reused diagnostic cases are explicitly exposed.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'manifests/focused-maintenance-v4/full-small-recovery-v1'
DATA=ROOT/'third_party/LongMemEval-V2/data/longmemeval-v2'
SCORE='norm_phrase_set_match|lower=true|normalize_hyphen=true|strip_punct=true|separators=,;|require_non_empty=true'


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f: json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')


def save_questions(path,rows):
    with path.open('x') as f:
        for row in rows: f.write(json.dumps(row,ensure_ascii=False)+'\n')


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    official=json.loads((DATA/'haystacks/lme_v2_small.json').read_text())
    questions=[json.loads(l) for l in (DATA/'questions.jsonl').open()]
    history={d:sorted({tid for q in questions if q['domain']==d and q['id'] in official for tid in official[q['id']]}) for d in ('web','enterprise')}
    assert all(len(ids)==100 for ids in history.values())
    wanted=set(sum(history.values(),[]));trajectories={}
    for line in (DATA/'trajectories.jsonl').open():
        row=json.loads(line)
        if row['id'] in wanted: trajectories[row['id']]=row
    assert set(trajectories)==wanted
    from run_agentrunbook_updates import changed_trajectory
    probes=json.loads((ROOT/'configs/method_revision_probes.json').read_text())
    probes+=json.loads((ROOT/'configs/method_v13_confirmation_probes.json').read_text())
    specs=[('web','title','1ad1af4b','method_web_title_replacement.json','v11-r1-web-1ad1af4b-title-replacement'),
           ('web','date','2a99f536','method_v13_confirm_web_date.json','v13-confirm-web-2a99f536-date'),
           ('enterprise','count','0ab99e0c','method_enterprise_count_replacement.json','v11-r1-enterprise-0ab99e0c-count-replacement'),
           ('enterprise','quantity','12c22166','method_v13_confirm_enterprise_quantity.json','v13-confirm-enterprise-12c22166-quantity')]
    OUT.mkdir(parents=True)
    cases=[]
    for domain,label,tid,revision_name,probe_name in specs:
        rev=json.loads((ROOT/'configs'/revision_name).read_text())
        source=ROOT/f'runs/focused-maintenance-v4/formal/matched-{domain}/memory_state'
        changed_trajectory(source,'literal_revision',tid,rev['source_edits'][0]['state_index'],revision_spec=rev)
        probe=next(q for q in probes if q['run']==probe_name)
        rows=[dict(id=f'{label}-{q["id"]}',domain=domain,environment='controlled-maintenance',question_type='dynamic-environment',
                   question=q['text']+' Wrap the final short answer in \\boxed{}.',image=None,answer=q['answer'],eval_function=SCORE) for q in probe['questions']]
        cid=f'{domain}-{label}'
        save(OUT/(cid+'-revision.json'),rev);save_questions(OUT/(cid+'-questions.jsonl'),rows)
        cases.append(dict(id=cid,domain=domain,trajectory_id=tid,kind='literal_state_revision',
            revision=str((OUT/(cid+'-revision.json')).relative_to(ROOT)),questions=str((OUT/(cid+'-questions.jsonl')).relative_to(ROOT)),
            exposure='previously observed development/confirmation; not new held-out',
            selection='pre-existing complete form/list/report/catalog trajectories, length and page-type coverage; not selected by method winner'))
        original=json.loads((source/'trajectories'/tid/'trajectory.json').read_text())
        idx=rev['source_edits'][0]['state_index'];old=original['states'][idx]['thoughts']
        assert old
        clarification=' Workflow clarification: verify the required field before proceeding to the next form field.'
        workflow={'trajectory_id':tid,'selection_reason':'Paired workflow-intent revision on the same preselected trajectory and state; no state/action changes.',
                  'source_edits':[{'state_index':idx,'field':'thoughts','old':old,'new':old+clarification}],
                  'derived_rules':[{'target':'notes','required':['required','before|prior'],'forbidden':[]}],
                  'manual_checks':['Generated notes must preserve the added verification and its ordering. This is recorded intent, not evidence the action was executed.','Original source state and actions remain unchanged.']}
        cid+='-workflow'
        save(OUT/(cid+'-revision.json'),workflow)
        rows=[dict(id=cid,domain=domain,environment='controlled-maintenance',question_type='procedure',
                   question=f"For the task {original['goal']!r}, according to the recorded workflow clarification, what must be verified before proceeding to the next form field? Answer with the noun phrase only, wrapped in \\boxed{{}}.",
                   image=None,answer='required field',eval_function=SCORE)]
        save_questions(OUT/(cid+'-questions.jsonl'),rows)
        cases.append(dict(id=cid,domain=domain,trajectory_id=tid,kind='workflow_intent_revision',
            revision=str((OUT/(cid+'-revision.json')).relative_to(ROOT)),questions=str((OUT/(cid+'-questions.jsonl')).relative_to(ROOT)),
            exposure='predeclared workload on exposed trajectories; no independent-generalization claim',
            selection='Same four trajectories; every selected trajectory receives both state and workflow revision'))
    data={}
    for domain,ids in history.items():
        p=OUT/(domain+'-normal-questions.jsonl')
        rows=[json.loads(l) for l in (ROOT/f'runs/dev-adapted-text-v1/data-expanded20/{domain}/questions.jsonl').open()]
        save_questions(p,rows)
        data[domain]={'trajectory_ids':ids,'trajectory_count':len(ids),'state_count':sum(len(trajectories[t]['states']) for t in ids),
                      'normal_questions':str(p.relative_to(ROOT)),'normal_question_count':len(rows),
                      'trajectory_content_sha256':{t:hashlib.sha256(json.dumps(trajectories[t],sort_keys=True).encode()).hexdigest() for t in ids}}
    manifest={'version':'full-small-recovery-v1','status':'data_frozen_before_new_full_history_runs',
              'scope':'complete official Small history IDs, text-only/adapted fixed local maintenance; not native multimodal or all official QA',
              'data':data,'cases':cases,'main_methods':['raw_rag','rag_notes','b3','source_coalesced'],
              'ablation_methods':['source_only','source_overlay'], 'ablation_cases':['web-title','enterprise-count'],
              'sequence_cases':['web-title','enterprise-count'],'sequence_rounds':3,
              'representative_repeat_cases':['web-title','enterprise-count'],'total_repeats':3,
              'repeat_order':'reverse method order on even repetition; all results retained',
              'exposure':'Existing diagnostics/normal questions are exposed; historical confirmation stays versioned. Full histories increase distractors, not independent revision sample count.',
              'question_count_unique':sum(len([json.loads(l) for l in (ROOT/c['questions']).open()]) for c in cases)+8,
              'case_count':len(cases),'selection_criterion':'Fixed four complete trajectories from existing requested set; paired state/workflow changes, group-internal and boundary positions.',
              'official_haystack_sha256':digest(DATA/'haystacks/lme_v2_small.json'),
              'scoring':'Frozen existing deterministic short-answer rule plus separate pending/manual event/notes semantic review; full fixed denominator and failures separate',
              'runtime_manifest':'must be recorded from actual loaded objects and requests before interpretation; this data manifest alone is not runtime freeze',
              'files':{str(p.relative_to(ROOT)):digest(p) for p in OUT.iterdir() if p.is_file()}}
    save(OUT/'data_manifest.json',manifest)
    print(json.dumps({'manifest':str(OUT/'data_manifest.json'),'history':{d:len(ids) for d,ids in history.items()},'cases':len(cases),'unique_questions':manifest['question_count_unique']}))


if __name__=='__main__':main()
