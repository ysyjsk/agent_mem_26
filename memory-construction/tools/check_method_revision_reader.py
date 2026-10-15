#!/usr/bin/env python3
"""Eight explicit source-scope QA probes over generated memory, no retrieval.

Uses the existing frozen Reader request/parser/scorer. No raw state text or
copied thoughts are provided. This is a controlled derived-memory check, not
official QA, an external Judge, or a retrieval-performance experiment.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / 'runs/agentrunbook-r-native-small-20261014/local-text-only'
sys.path.insert(0, str(ADAPTER))
sys.path.append(str(ROOT / 'third_party/LongMemEval-V2'))
from evaluation.harness import generate_all_reader_outputs, get_system_prompt
from evaluation.qa_eval_metrics import normalize_phrase


def main():
    os.environ['LME_TEXT_ONLY'] = '1'
    run_root = ROOT / 'runs/method-first-20261015'
    probes = json.loads((ROOT / 'configs/method_revision_probes.json').read_text())
    if len(sys.argv) > 1:
        requested = set(sys.argv[1:])
        probes = [p for p in probes if p['run'] in requested]
        if len(probes) != len(requested):
            raise ValueError('unknown requested probe run')
    for case in probes:
        for policy in ('b3', 'delta_guarded', 'source_overlay'):
            folder = run_root / case['run'] / f'literal_revision-{policy}'
            if not folder.exists():
                continue
            output = folder / 'derived_reader_probe.json'
            if output.exists():
                raise FileExistsError(output)
            prior = folder / 'reader/run_args.json'
            if not prior.exists():
                prior = ROOT / 'runs/method-first-20261015/v11-new-web-2e8f6477-reply-replacement/literal_revision-delta_guarded/reader/run_args.json'
            args = argparse.Namespace(**json.loads(prior.read_text()))
            review = json.loads((folder / 'derived_quality_review.json').read_text())
            # Exclude raw and pre/post_thoughts; source IDs and actions preserve
            # the event interpretation, but cannot answer a changed-value QA.
            derived = {'events': [{k: e[k] for k in ('event_id', 'overview', 'state_transition')}
                                   for e in review['new_events']],
                       'notes': [n['note_text'] for n in review['new_notes']]}
            rows = []
            for question in case['questions']:
                rows.append({'question_id': question['id'], 'messages': [
                    {'role': 'system', 'content': get_system_prompt(case['domain'])},
                    {'role': 'user', 'content': 'Generated memory records (event_ID encodes pre-state and post-state):\n' +
                     json.dumps(derived, ensure_ascii=False) + '\nQuestion: ' + question['text'] +
                     '\nWrap your final short answer in \\boxed{}.'}]})
            responses = asyncio.run(generate_all_reader_outputs(args, rows))
            results = []
            for question, row in zip(case['questions'], rows):
                response = responses[question['id']]
                results.append({**question, **response, 'messages': row['messages'],
                    'correct': bool(response['reader_answer_complete'] and normalize_phrase(
                        response['response_parsed_boxed']) == normalize_phrase(question['answer']))})
            result = {'scope': 'controlled generated-only Reader QA; not official benchmark/not retrieval',
                      'scoring': 'normalized exact short-answer equality; extras/conflicting values fail',
                      'run': case['run'], 'policy': policy,
                      'correct': sum(r['correct'] for r in results), 'total': len(results), 'results': results}
            output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
            print(json.dumps({k: result[k] for k in ('run', 'policy', 'correct', 'total')}), flush=True)


if __name__ == '__main__':
    main()
