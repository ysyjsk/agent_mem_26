#!/usr/bin/env python3
"""Run the frozen focused-maintenance-v4 development sequence.

This reuses the predeclared v13 cases/questions but writes a new versioned
path because the Notes rule and Source-only policy are now part of the frozen
runner. No historical output is overwritten.
"""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tools/run_method_v13_sequence.py'
spec = importlib.util.spec_from_file_location('v13_sequence_reference', RUNNER)
ref = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ref)
ref.RUN = ROOT / 'runs/focused-maintenance-v4/dev/sequence-final'
ref.POLICIES = ('b3', 'source_only', 'source_coalesced')

PY = sys.executable
RUN = ref.RUN
CASES = ref.CASES

def run(cmd):
    print(json.dumps({'command': [str(x) for x in cmd]}, ensure_ascii=False), flush=True)
    subprocess.run([str(x) for x in cmd], cwd=ROOT, check=True)

def main():
    ref.prepare()
    for domain, tid, state, field, values in CASES:
        for n in range(1, 4):
            folder = RUN / f'{domain}-r{n}'
            order = ref.POLICIES if n % 2 else tuple(reversed(ref.POLICIES))
            for policy in order:
                output = folder / f'literal_revision-{policy}'
                source = (ROOT / f'runs/method-first-20261015/matched-{domain}-v1/memory_state' if n == 1 else
                          RUN / f'{domain}-r{n-1}' / f'literal_revision-{policy}' / 'memory_state')
                if not (output / 'update_metrics.json').exists():
                    run([PY, '-u', 'tools/run_agentrunbook_updates.py', '--source', source, '--output', folder,
                         '--trajectory-id', tid, '--state-index', state, '--cases', 'literal_revision',
                         '--revision-file', folder / 'revision.json', '--current-state-evidence', '--policy-order', policy])
                if not (output / 'revision_reader' / 'aggregated_metrics.json').exists():
                    run([PY, '-u', 'runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py',
                         '--data-root', folder / 'data', '--domain', domain, '--method', 'agentrunbook_r',
                         '--output-dir', output / 'revision_reader', '--load-memory-dir', output / 'memory_state',
                         '--text-only', '--controller-disable-thinking', '--no-reader-enable-thinking',
                         '--max-completion-tokens', '2048', '--memory-context-max-tokens', '12000',
                         '--reader-max-concurrent-requests', '1', '--prompt-build-max-workers', '1',
                         '--event-concurrency', '1', '--event-group-size', '2', '--event-output-tokens', '2048',
                         '--event-max-input-tokens', '18000', '--controller-max-retries', '0', '--reuse-build-embedding',
                         '--chunk-memory-context', '--cache-context-tokenizer', '--lexical-backfill', '--reuse-query-embedding'])
                print(json.dumps({'completed': domain, 'round': n, 'policy': policy}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
