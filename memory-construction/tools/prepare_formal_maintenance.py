#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/focused-maintenance-v4/formal/query-data'
PROBES = json.loads((ROOT/'configs/method_revision_probes.json').read_text())
CASES = {
    'web': ('1ad1af4b', 'title', ['Cyberpunk','Neon Harbor','Cedar Point','Silver Cove'], 'v11-r1-web-1ad1af4b-title-replacement'),
    'enterprise': ('0ab99e0c', 'count', ['101','103','105','107'], 'v11-r1-enterprise-0ab99e0c-count-replacement'),
}

def main():
    for domain, (tid, field, values, run_id) in CASES.items():
        src = ROOT/f'runs/dev-adapted-text-v1/data-expanded20/{domain}'
        out = OUT/domain
        out.mkdir(parents=True, exist_ok=True)
        for name in ('trajectories.jsonl', 'screenshots', 'question_screenshots'):
            target = out/name
            if target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(src/name, target_is_directory=(src/name).is_dir())
        ids = json.loads((src/'frozen_manifest.json').read_text())['shared_ordered_trajectory_ids']
        probe = next(p for p in PROBES if p['run'] == run_id)
        rows=[]
        for q in probe['questions']:
            rows.append({'id': q['id'], 'domain': domain, 'environment': 'focused-maintenance-v4-formal', 'question_type': 'dynamic-environment', 'question': q['text']+' Wrap the final short answer in \\boxed{}.', 'image': None, 'answer': q['answer'], 'eval_function': 'norm_phrase_set_match|lower=true|normalize_hyphen=true|strip_punct=true|separators=,;|require_non_empty=true'})
        (out/'questions.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
        (out/'haystacks').mkdir(exist_ok=True)
        (out/'haystacks/lme_v2_small.json').write_text(json.dumps({r['id']: ids for r in rows}, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({'domain':domain,'trajectories':len(ids),'questions':len(rows),'output':str(out)}))

if __name__ == '__main__': main()
