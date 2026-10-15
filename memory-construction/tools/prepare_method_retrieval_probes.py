#!/usr/bin/env python3
"""Expose fixed correction probes to the ordinary retrieval harness, full library.

No answer evidence is injected, no per-question memory built, no retrieval
parameter is changed. Gold questions are controlled-source development tests.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    probes=json.loads((ROOT/'configs/method_revision_probes.json').read_text())
    selected=[
        ('v12-web-1ad1af4b-title-replacement','v11-r1-web-1ad1af4b-title-replacement'),
        ('v12-enterprise-49f98e9e-sort-replacement','v11-new-enterprise-49f98e9e-sort-replacement'),
        ('v12-web-2e8f6477-reply-replacement','v12-web-2e8f6477-reply-replacement'),
        ('v12-enterprise-0ab99e0c-count-replacement','v12-enterprise-0ab99e0c-count-replacement'),
    ]
    extra=json.loads((ROOT/'configs/method_semantic_confirmation_probes.json').read_text())
    extra.extend(json.loads((ROOT/'configs/method_v13_confirmation_probes.json').read_text()))
    probes.extend(extra)
    selected.extend((p['run'],p['run']) for p in extra)
    for run,source in selected:
        case=next(p for p in probes if p['run']==source)
        folder=ROOT/'runs/method-first-20261015/retrieval-probe-data'/run
        if folder.exists():
            continue
        data=ROOT/'runs/dev-adapted-text-v1/data'/case['domain']
        folder.mkdir(parents=True)
        for name in ('trajectories.jsonl','screenshots','question_screenshots'):
            (folder/name).symlink_to(data/name,target_is_directory=(data/name).is_dir())
        ids=json.loads((data/'frozen_manifest.json').read_text())['shared_ordered_trajectory_ids']
        rows=[dict(id=q['id'],domain=case['domain'],environment='controlled-source-correction',
            question_type='dynamic-environment',question=q['text']+' Wrap the final short answer in \\boxed{}.',
            image=None,answer=q['answer'],
            eval_function='norm_phrase_set_match|lower=true|normalize_hyphen=true|strip_punct=true|separators=,;|require_non_empty=true')
            for q in case['questions']]
        (folder/'questions.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        (folder/'haystacks').mkdir()
        (folder/'haystacks/lme_v2_small.json').write_text(json.dumps({r['id']:ids for r in rows},indent=2)+'\n')
        (folder/'probe_manifest.json').write_text(json.dumps(dict(source_probe=source,run=run,
            scope='controlled revision QA through ordinary retrieval; not official labels',
            shared_complete_trajectory_ids=ids,query_settings='unchanged fixed normal retrieval'),indent=2)+'\n')
        print(folder.relative_to(ROOT))


if __name__=='__main__':
    main()
