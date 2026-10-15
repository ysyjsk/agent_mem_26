#!/usr/bin/env python3
"""One fixed expansion: retain 8 questions and add 5 full distractors/domain."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'third_party/LongMemEval-V2/data/longmemeval-v2'
BASE = ROOT / 'runs/dev-adapted-text-v1/data'
DEST = ROOT / 'runs/dev-adapted-text-v1/data-expanded20'


def main():
    if DEST.exists():
        raise RuntimeError(f'Refusing to overwrite frozen data: {DEST}')
    official = json.loads((SOURCE / 'haystacks/lme_v2_small.json').read_text())
    specs = {}
    for domain in ('enterprise', 'web'):
        manifest = json.loads((BASE / domain / 'frozen_manifest.json').read_text())
        qids = [q['question_id'] for q in manifest['questions_with_evidence']]
        existing = manifest['shared_ordered_trajectory_ids']
        candidates = set.intersection(*(set(official[q]) for q in qids)) - set(existing)
        added = sorted(candidates, key=lambda t: hashlib.sha256(('expanded20-v1:' + t).encode()).hexdigest())[:5]
        assert len(added) == 5
        specs[domain] = (manifest, qids, existing + added, added)
    wanted = {tid for _, _, tids, _ in specs.values() for tid in tids}
    records = {}
    with (SOURCE / 'trajectories.jsonl').open() as f:
        for line in f:
            record = json.loads(line)
            if record['id'] in wanted:
                records[record['id']] = record
    assert set(records) == wanted
    for domain, (manifest, qids, tids, added) in specs.items():
        dest = DEST / domain
        (dest / 'haystacks').mkdir(parents=True)
        (dest / 'questions.jsonl').write_bytes((BASE / domain / 'questions.jsonl').read_bytes())
        (dest / 'trajectories.jsonl').write_text(''.join(json.dumps(records[t], ensure_ascii=False) + '\n' for t in tids))
        (dest / 'haystacks/lme_v2_small.json').write_text(json.dumps({q: tids for q in qids}, indent=2) + '\n')
        for name in ('screenshots', 'question_screenshots'):
            (dest / name).symlink_to(SOURCE / name, target_is_directory=True)
        manifest.update(trajectory_count=len(tids), shared_ordered_trajectory_ids=tids,
                        state_count=sum(len(records[t]['states']) for t in tids),
                        full_trajectory_state_counts={t: len(records[t]['states']) for t in tids},
                        distractor_trajectory_ids=manifest['distractor_trajectory_ids'] + added,
                        expansion_rule='Retain all 8 fixed questions; append first 5 common-haystack candidates per domain sorted by SHA256(expanded20-v1:ID), without inspecting answers or outcomes.',
                        added_distractor_trajectory_ids=added,
                        expansion_kind='corpus/distractor scaling; NOT independent question generalization')
        manifest['data_sha256'] = {n: hashlib.sha256((dest / n).read_bytes()).hexdigest() for n in ('questions.jsonl', 'trajectories.jsonl', 'haystacks/lme_v2_small.json')}
        (dest / 'frozen_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(domain, len(qids), 'questions', len(tids), 'trajectories', manifest['state_count'], 'states', flush=True)


if __name__ == '__main__':
    main()
