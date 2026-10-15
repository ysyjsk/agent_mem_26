#!/usr/bin/env python3
"""Finite three-round correction comparison using existing update/Reader paths.

Primary: cumulative update LLM tokens; constraint: normal changed-fact QA and
derived current-state evidence. Secondary: publish/embedding/query cost and
memory growth. Coalescing vs append-only overlay changes only evidence merge.
All branches start at the same matched snapshot, then keep their OWN history.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'runs/method-first-20261015/v13-sequential'
PY = sys.executable
POLICIES = ('b3', 'source_overlay', 'source_coalesced')
CASES = (
    ('web', '1ad1af4b', 4, 'title', ['Cyberpunk', 'Neon Harbor', 'Cedar Point', 'Silver Cove']),
    ('enterprise', '0ab99e0c', 5, 'count', ['101', '103', '105', '107']),
)


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def prepare():
    manifest = {'version': 'focused-v13-current-evidence', 'cases': CASES, 'rounds': 3,
        'selection': 'Two pre-existing complete trajectories: web form field / enterprise list count; not selected by branch win.',
        'scope': 'Controlled sequential revisions of a fixed state, NOT new trajectories or streaming growth.',
        'primary': 'cumulative update LLM input+output tokens',
        'secondary': 'update publish wall, embedding work, all query costs, current evidence length',
        'quality_constraint': 'All latest values and unchanged-field probes; no service/parse failures; current evidence retired correctly; inspect derived notes/events.',
        'decision': 'Keep coalescing only if current evidence quality survives with reduced accumulated context/work. Do not claim further LLM saving against zero-LLM overlay.',
        'cache': 'Common initial matched snapshot; independent method history and all lawful exact request/vector caches; never use another method outputs.',
        'frozen_query': 'Existing 12000-token memory, 2048 Reader output, no thinking; chunk/tokenizer/lexical/query-embedding reuse unchanged'}
    existing = RUN/'manifest.json'
    if existing.exists():
        assert json.loads(existing.read_text()) == json.loads(json.dumps(manifest))
        return
    save(existing, manifest)
    probes = json.loads((ROOT/'configs/method_revision_probes.json').read_text())
    for domain, tid, state, field, values in CASES:
        template = json.loads((ROOT/f'configs/method_{domain}_{field}_replacement.json').read_text())
        probe = next(p for p in probes if p['run'] == f'v11-r1-{domain}-{tid}-{field}-replacement')
        data = ROOT/'runs/dev-adapted-text-v1/data'/domain
        ids = json.loads((data/'frozen_manifest.json').read_text())['shared_ordered_trajectory_ids']
        for n in range(1, 4):
            folder = RUN/f'{domain}-r{n}'
            rev = copy.deepcopy(template)
            rev['selection_reason'] = manifest['selection'] + f' Sequential round {n}; values fixed before execution.'
            for edit, original in zip(rev['source_edits'], template['source_edits']):
                edit['old'] = original['old'].replace(values[0], values[n-1])
                edit['new'] = original['new'].replace(values[1], values[n])
            if field == 'count':
                # Anchor full source lines: numeric values such as105 can also
                # occur inside unrelated node IDs (a1051/a1053).
                original_tr = json.loads((ROOT/f'runs/method-first-20261015/matched-{domain}-v1/memory_state/trajectories/{tid}/trajectory.json').read_text())
                rev['source_edits'] = [dict(state_index=state, field='text',
                    old=line.replace(values[0], values[n-1]), new=line.replace(values[0], values[n]))
                    for line in original_tr['states'][state]['text'].splitlines() if values[0] in line]
            for rule in rev['derived_rules']:
                rule['required'] = [r.replace(values[1], values[n]) for r in rule.get('required', [])]
            save(folder/'revision.json', rev)
            probe_dir = folder/'data'
            probe_dir.mkdir()
            for name in ('trajectories.jsonl', 'screenshots', 'question_screenshots'):
                (probe_dir/name).symlink_to(data/name, target_is_directory=(data/name).is_dir())
            rows = []
            for q in probe['questions']:
                rows.append(dict(id=q['id'], domain=domain, environment='controlled-sequential-source-correction',
                    question_type='dynamic-environment', question=q['text']+' Wrap the final short answer in \\boxed{}.',
                    image=None, answer=q['answer'].replace(values[1], values[n]),
                    eval_function='norm_phrase_set_match|lower=true|normalize_hyphen=true|strip_punct=true|separators=,;|require_non_empty=true'))
            (probe_dir/'questions.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
            save(probe_dir/'haystacks/lme_v2_small.json', {r['id']: ids for r in rows})


def run(command):
    print(json.dumps({'command': [str(x) for x in command]}, ensure_ascii=False), flush=True)
    subprocess.run([str(x) for x in command], cwd=ROOT, check=True)


def main():
    prepare()  # Freeze all round edits/questions before any model request.
    for domain, tid, state, field, values in CASES:
        for n in range(1, 4):
            folder = RUN/f'{domain}-r{n}'
            # Alternating order, not choosing a best sampled run.
            order = POLICIES if n % 2 else tuple(reversed(POLICIES))
            for policy in order:
                output = folder/f'literal_revision-{policy}'
                source = (ROOT/f'runs/method-first-20261015/matched-{domain}-v1/memory_state' if n == 1 else
                          RUN/f'{domain}-r{n-1}'/f'literal_revision-{policy}'/'memory_state')
                if not (output/'update_metrics.json').exists():
                    run([PY, '-u', 'tools/run_agentrunbook_updates.py', '--source', source, '--output', folder,
                         '--trajectory-id', tid, '--state-index', state, '--cases', 'literal_revision',
                         '--revision-file', folder/'revision.json', '--current-state-evidence', '--policy-order', policy])
                if not (output/'revision_reader/aggregated_metrics.json').exists():
                    run([PY, '-u', 'runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py',
                         '--data-root', folder/'data', '--domain', domain, '--method', 'agentrunbook_r',
                         '--output-dir', output/'revision_reader', '--load-memory-dir', output/'memory_state',
                         '--text-only', '--controller-disable-thinking', '--no-reader-enable-thinking',
                         '--max-completion-tokens', '2048', '--memory-context-max-tokens', '12000',
                         '--reader-max-concurrent-requests', '1', '--prompt-build-max-workers', '1',
                         '--event-concurrency', '1', '--event-group-size', '2', '--event-output-tokens', '2048',
                         '--event-max-input-tokens', '18000', '--controller-max-retries', '0', '--reuse-build-embedding',
                         '--chunk-memory-context', '--cache-context-tokenizer', '--lexical-backfill', '--reuse-query-embedding'])
                print(json.dumps({'completed': domain, 'round': n, 'policy': policy}), flush=True)


if __name__ == '__main__':
    main()
