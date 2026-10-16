#!/usr/bin/env python3
"""Finite frozen maintenance experiment queue, using existing model entrypoints.

This is the explicit experiment matrix, not a new worker/service. Run through
execution/launch_detached.sh. Only one subprocess can consume model services.
Completed stages are reused; partial/failed outputs are retained for diagnosis.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PYTHON = '/data/predator/ly/Mem/.venv/bin/python'
BASE = Path('runs/focused-maintenance-v4/full-small-recovery-v1')
MANIFEST = Path('manifests/focused-maintenance-v4/full-small-recovery-v1/data_manifest.json')
CONTROL = Path('execution/full-small-recovery-v1')
POLICIES = ['raw_rag', 'rag_notes', 'b3', 'source_coalesced', 'source_only', 'source_overlay']
OFFICIAL = 'third_party/LongMemEval-V2/data/longmemeval-v2/trajectories.jsonl'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads((ROOT / path).read_text())


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def write_new(path, value):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def memory_for(domain, policy):
    if policy in ('raw_rag', 'rag_notes'):
        return BASE / 'initial' / f'{domain}-{policy}' / 'memory_state'
    return BASE / 'matched' / domain / 'memory_state'


def matrix(manifest):
    steps = []

    def add(name, command, kind, marker, deps=(), **metadata):
        steps.append(dict(id=name, command=[str(x) for x in command], kind=kind,
                          marker=str(marker), depends_on=list(deps), **metadata))
        return name

    initial = []
    for domain in ('web', 'enterprise'):
        for architecture in ('agentrunbook', 'raw_rag', 'rag_notes'):
            if architecture == 'agentrunbook':
                source = f'runs/focused-maintenance-v4/formal/matched-{domain}/memory_state'
            else:
                suffix = 'rag-raw-optL' if architecture == 'raw_rag' else 'rag-notes'
                source = f'runs/dev-adapted-text-v1/results/{domain}-expanded20-{suffix}-v1/memory_state'
            out = BASE / 'initial' / f'{domain}-{architecture}'
            name = add(f'expand-{domain}-{architecture}', [PYTHON, 'tools/extend_full_small_memory.py',
                '--domain', domain, '--source', source, '--output', out, '--manifest', MANIFEST],
                'expansion', out / 'full_history_verified.json', domain=domain, memory=str(out / 'memory_state'))
            if architecture == 'agentrunbook':
                targets = sorted({c['trajectory_id'] for c in manifest['cases'] if c['domain'] == domain})
                matched = BASE / 'matched' / domain
                name = add(f'prepare-{domain}', [PYTHON, 'tools/run_agentrunbook_updates.py',
                    '--source', out / 'memory_state', '--output', matched, '--prepare-trajectories', *targets],
                    'preparation', matched / 'preparation_metrics.json', [name], domain=domain,
                    memory=str(matched / 'memory_state'))
            initial.append(name)
    gate = add('freeze-runtime', [], 'freeze', BASE / 'runtime_manifest.json', initial)

    def query(name, domain, policy, memory, questions, out, depends, query_kind):
        if policy in ('raw_rag', 'rag_notes'):
            cmd = [PYTHON, 'tools/run_rag_maintenance_reader.py', '--domain', domain,
                   '--memory-dir', memory, '--questions-path', questions, '--output', out]
        else:
            # The existing AR Reader appends <domain>-<policy> to its root.
            cmd = [PYTHON, 'tools/run_focused_formal_reader.py', '--domain', domain, '--policy', policy,
                   '--memory-dir', memory, '--questions-path', questions, '--output-root', out,
                   '--trajectories-path', OFFICIAL]
            out = out / f'{domain}-{policy}'
        return add(name, cmd, 'reader', out / 'aggregated_metrics.json', depends,
                   domain=domain, policy=policy, memory=str(memory), reader=str(out),
                   questions=str(questions), query_kind=query_kind)

    # One initial normal-QA measurement per architecture; AR policies share it.
    for domain in ('web', 'enterprise'):
        for policy in ('raw_rag', 'rag_notes', 'b3'):
            query(f'initial-query-{domain}-{policy}', domain, policy, memory_for(domain, policy),
                  manifest['data'][domain]['normal_questions'], BASE / 'initial-query' / f'{domain}-{policy}',
                  [gate], 'initial_normal_shared_reference')

    def update(name, domain, policy, source, revision, out, deps, phase, case_id, repeat=1, round_number=1):
        rev = read(revision)
        if policy in ('raw_rag', 'rag_notes'):
            cmd = [PYTHON, 'tools/run_rag_updates.py', '--source', source, '--output', out, '--revision-file', revision]
        else:
            cmd = [PYTHON, 'tools/run_agentrunbook_updates.py', '--source', source, '--output', out,
                   '--trajectory-id', rev['trajectory_id'], '--state-index', rev['source_edits'][0]['state_index'],
                   '--revision-file', revision, '--cases', 'literal_revision', '--policy-order', policy,
                   '--current-state-evidence']
            out = out / f'literal_revision-{policy}'
        uid = add(name, cmd, 'update', out / 'update_metrics.json', deps,
                  domain=domain, policy=policy, source=str(source), memory=str(out / 'memory_state'),
                  revision=str(revision), phase=phase, case_id=case_id, repeat=repeat, round=round_number)
        return uid, out

    main = {}
    main_queries = {}
    for case in manifest['cases']:
        domain, cid = case['domain'], case['id']
        methods = manifest['main_methods'] + (manifest['ablation_methods'] if cid in manifest['ablation_cases'] else [])
        for policy in methods:
            uid, out = update(f'main-{cid}-{policy}', domain, policy, memory_for(domain, policy),
                case['revision'], BASE / 'main' / cid / policy,
                [gate, f'initial-query-{domain}-{policy if policy in ("raw_rag", "rag_notes") else "b3"}'],
                'main' if policy in manifest['main_methods'] else 'ablation', cid)
            main[cid, policy] = (uid, out)
            main_queries[cid, policy] = query(uid + '-revision-query', domain, policy, out / 'memory_state', case['questions'],
                                              out / 'revision-reader', [uid], 'revision')
            query(uid + '-normal-query', domain, policy, out / 'memory_state', manifest['data'][domain]['normal_questions'],
                  out / 'normal-reader', [uid], 'normal_after_revision')

    # Three total matched update timings, including the main run as repetition1.
    for repetition in range(2, manifest['total_repeats'] + 1):
        order = list(reversed(POLICIES)) if repetition % 2 == 0 else POLICIES
        for cid in manifest['representative_repeat_cases']:
            case = next(c for c in manifest['cases'] if c['id'] == cid)
            for policy in order:
                uid, out = update(f'repeat{repetition}-{cid}-{policy}', case['domain'], policy,
                    memory_for(case['domain'], policy), case['revision'], BASE / 'repeats' / f'r{repetition}' / cid / policy,
                    [gate, main_queries[cid, policy]], 'repeat', cid, repeat=repetition)
                query(uid + '-revision-query', case['domain'], policy, out / 'memory_state', case['questions'],
                      out / 'revision-reader', [uid], 'revision_repeat')

    for cid in manifest['sequence_cases']:
        case = next(c for c in manifest['cases'] if c['id'] == cid)
        domain = case['domain']
        for policy in POLICIES:
            # Same actual source edits: legitimately reuse main round1 update.
            first = Path(f'runs/focused-maintenance-v4/dev/sequence-final/{domain}-r1/revision.json')
            # One historical count edit spells out four anchors, while the
            # main manifest replaces the same five numeric occurrences.
            # Compare the actual revised source, never merely the labels.
            from run_agentrunbook_updates import changed_trajectory
            source = ROOT / f'runs/focused-maintenance-v4/formal/matched-{domain}/memory_state'
            revised = []
            for revision in (first, case['revision']):
                spec = read(revision)
                changed, _ = changed_trajectory(source, 'literal_revision', spec['trajectory_id'],
                                                spec['source_edits'][0]['state_index'], revision_spec=spec)
                revised.append(changed)
            assert revised[0] == revised[1], 'Round1 source differs: cannot reuse main update'
            def question_signature(path):
                return [(q['question'], q['answer'], q['eval_function'])
                        for q in map(json.loads, (ROOT / path).read_text().splitlines())]
            first_questions = first.parent / 'data/questions.jsonl'
            assert question_signature(first_questions) == question_signature(case['questions'])
            previous, previous_out = main[cid, policy]
            previous_query = main_queries[cid, policy]
            for round_number in range(2, manifest['sequence_rounds'] + 1):
                data = Path(f'runs/focused-maintenance-v4/dev/sequence-final/{domain}-r{round_number}')
                uid, out = update(f'sequence-r{round_number}-{cid}-{policy}', domain, policy,
                    previous_out / 'memory_state', data / 'revision.json', BASE / 'sequence' / f'r{round_number}' / cid / policy,
                    [previous, previous_query], 'sequence', cid, round_number=round_number)
                previous_query = query(uid + '-revision-query', domain, policy, out / 'memory_state', data / 'data/questions.jsonl',
                                       out / 'revision-reader', [uid], 'sequence_revision')
                previous, previous_out = uid, out
    add('aggregate-formal-evidence', [PYTHON, 'tools/report_full_small_formal.py'],
        'report', 'reports/execution-recovery-20261016/full-small-v1/report.json')
    return steps


def input_hashes(steps):
    files = {str(MANIFEST), 'execution/experiment_contract.json'}
    for step in steps:
        files.update(step[k] for k in ('questions', 'revision') if k in step)
    files.update(read(MANIFEST)['files'])
    for domain in ('web', 'enterprise'):
        prefix = f'runs/focused-maintenance-v4/dev/sequence-final/{domain}-r1'
        files.update((prefix + '/revision.json', prefix + '/data/questions.jsonl'))
    code = ['tools/run_agentrunbook_updates.py', 'tools/run_rag_updates.py', 'tools/extend_full_small_memory.py',
            'tools/focused_runtime.py', 'tools/run_focused_formal_reader.py', 'tools/run_rag_maintenance_reader.py',
            'tools/run_full_small_formal.py', 'tools/focused_reader_transport.py']
    for folder in ('runs/agentrunbook-r-native-small-20261014/local-text-only/memory_modules',
                   'runs/agentrunbook-r-native-small-20261014/local-text-only/evaluation',
                   'third_party/LongMemEval-V2/memory_modules', 'third_party/LongMemEval-V2/evaluation'):
        code.extend(str(p.relative_to(ROOT)) for p in (ROOT / folder).rglob('*.py'))
    files.update(code)
    return {f: sha(f) for f in sorted(files)}


def validate_memory(memory, domain):
    expected = set(read(MANIFEST)['data'][domain]['trajectory_ids'])
    observed = read(Path(memory) / 'index.json')['inserted_trajectory_ids']
    if len(observed) != len(set(observed)) or set(observed) != expected:
        raise ValueError(f'Loaded history not complete official {domain}: {memory}')


def verify_official_sources():
    expected = {tid: value for d in read(MANIFEST)['data'].values()
                for tid, value in d['trajectory_content_sha256'].items()}
    observed = set()
    with (ROOT / OFFICIAL).open() as stream:
        for line in stream:
            trajectory = json.loads(line)
            tid = trajectory['id']
            if tid not in expected:
                continue
            digest = hashlib.sha256(json.dumps(trajectory, sort_keys=True).encode()).hexdigest()
            if digest != expected[tid]:
                raise ValueError(f'Official trajectory changed since data freeze: {tid}')
            if tid in observed:
                raise ValueError(f'Duplicate official trajectory: {tid}')
            observed.add(tid)
    if observed != set(expected):
        raise ValueError('Missing frozen official trajectory content')
    return {'verified_at': stamp(), 'verified_complete_trajectory_contents': len(observed),
            'manifest_sha256': sha(MANIFEST)}


def validate(step):
    record = read(step['marker'])
    if step['kind'] in ('expansion', 'preparation', 'update', 'reader'):
        validate_memory(step['memory'], step['domain'])
    if step['kind'] == 'preparation' and record['no_change_real_calls'] != 0:
        raise ValueError('Strong baseline unchanged rebuild made model calls')
    if step['kind'] == 'update' and not record.get('load_verified'):
        raise ValueError('Published update has not passed save/reload check')
    if step['kind'] == 'reader':
        transport = read(Path(step['reader']) / 'effective_reader_transport.json')
        if transport['sdk_max_retries'] != 0:
            raise ValueError('Reader unrecorded transport retries are enabled')
        questions = [json.loads(l) for l in (ROOT / step['questions']).open() if l.strip()]
        answers = [json.loads(l) for l in (ROOT / step['reader'] / 'per_question.jsonl').open() if l.strip()]
        if sorted(q['id'] for q in questions) != sorted(q['question_id'] for q in answers):
            raise ValueError('Reader fixed denominator differs from manifest')
        subprocess.run([PYTHON, 'execution/verify_evidence.py', '--reader-dir', step['reader']], cwd=ROOT, check=True)


def freeze_runtime(plan):
    source_verification = verify_official_sources()
    snapshots = {}
    for domain in ('web', 'enterprise'):
        for policy in ('raw_rag', 'rag_notes', 'b3'):
            memory = memory_for(domain, policy)
            validate_memory(memory, domain)
            snapshots[f'{domain}-{policy}'] = {
                'path': str(memory), 'index_sha256': sha(memory / 'index.json'),
                'config': read(memory / 'memory_config.json'),
                'construction_config': read(memory / 'construction_config.json') if (ROOT / memory / 'construction_config.json').exists() else None,
                'cost_scope': 'own historical initial partitions + expansion + matched preparation; NOT fresh cold build'}
    write_new(BASE / 'runtime_manifest.json', {
        'status': 'frozen_before_formal_maintenance', 'frozen_at': stamp(),
        'plan_sha256': sha(CONTROL / 'experiment_plan.json'), 'data_manifest_sha256': sha(MANIFEST),
        'contract': read('execution/experiment_contract.json'), 'code_and_input_sha256': plan['input_sha256'],
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_diff_sha256': hashlib.sha256(subprocess.check_output(['git', 'diff', '--no-ext-diff'], cwd=ROOT)).hexdigest(),
        'initial_snapshots': snapshots, 'cache': 'independent clones; own exact requests/vectors retained; no output re-keying',
        'official_source_verification': source_verification,
        'timing': 'update build+index+save+reload, setup separately; query controller and Reader included; initial separate',
        'quality': 'fixed scoring; correctness checks are not equivalence tests; exposed workload; all failures retained',
        'query_workload': 'main: case-specific questions plus all four normal questions/domain; repeats and sequence: case-specific only',
        'repeat_order': read(MANIFEST)['repeat_order'],
        'continuous_round1': 'reuse main update and its case-specific query; identical source edits, not a second independent measurement'})


def wait_for_job(name):
    job = ROOT / 'execution/background' / name
    pid = int((job / 'pid').read_text())
    print(json.dumps({'waiting_for_existing_job': name, 'pid': pid}), flush=True)
    while True:
        status = (job / 'status').read_text().strip()
        if status in ('completed', 'failed'):
            if status != 'completed' or int((job / 'exit_code').read_text()) != 0:
                raise RuntimeError(f'Prior expansion failed; preserve partial state: {name}')
            return
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            # Re-read final receipt after checking the actual process handle.
            time.sleep(1)
            if (job / 'status').read_text().strip() == 'completed':
                continue
            raise RuntimeError(f'Prior job handle vanished without completion: {name}')
        time.sleep(5)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--register', action='store_true')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--after-job')
    args = p.parse_args()
    steps = matrix(read(MANIFEST))
    summary = {kind: sum(s['kind'] == kind for s in steps) for kind in dict.fromkeys(s['kind'] for s in steps)}
    if not args.register and not args.execute:
        print(json.dumps({'steps': len(steps), 'kinds': summary, 'main_updates': sum(s.get('phase') == 'main' for s in steps),
                          'ablation_updates': sum(s.get('phase') == 'ablation' for s in steps), 'data_manifest': str(MANIFEST)}))
        return
    if args.register:
        write_new(CONTROL / 'experiment_plan.json', {'registered_at': stamp(), 'status': 'registered_not_completed',
            'manifest': str(MANIFEST), 'steps': steps, 'counts': summary, 'input_sha256': input_hashes(steps),
            'official_source_verification': verify_official_sources(),
            'failure_policy': 'retain partial outputs, skip dependent tasks, run other independent units; no best-of reruns'})
    if not args.execute:
        return
    plan = read(CONTROL / 'experiment_plan.json')
    if plan['steps'] != steps:
        raise ValueError('Registered experiment matrix changed')
    if args.after_job:
        wait_for_job(args.after_job)
    states = {}
    for step in steps:
        receipt = CONTROL / 'units' / (step['id'] + '.json')
        if (ROOT / receipt).exists():
            old = read(receipt)
            if old['status'] == 'completed':
                validate(step)
                states[step['id']] = 'completed'
                continue
            raise RuntimeError(f'Prior failed/partial receipt requires diagnosis, not blind replay: {receipt}')
        result = dict(id=step['id'], started_at=stamp(), command=step['command'], status='running')
        if any(states.get(d) != 'completed' for d in step['depends_on']):
            result['status'] = 'blocked_by_failed_dependency'
        else:
            try:
                if input_hashes(steps) != plan['input_sha256']:
                    raise ValueError('Frozen code/input changed during queue')
                print(json.dumps({'starting': step['id'], 'command': step['command']}), flush=True)
                if step['kind'] == 'freeze':
                    freeze_runtime(plan)
                else:
                    subprocess.run(step['command'], cwd=ROOT, check=True)
                validate(step)
                result['status'] = 'completed'
            except Exception as exc:
                result.update(status='failed', error=repr(exc))
        result['finished_at'] = stamp()
        states[step['id']] = result['status']
        write_new(receipt, result)
        print(json.dumps(result), flush=True)
    write_new(CONTROL / f'completion-{time.time_ns()}.json', {'finished_at': stamp(), 'states': states,
        'scope': 'execution receipts only; semantic review, accounting, figures and paper acceptance still required'})
    if any(s != 'completed' for s in states.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
