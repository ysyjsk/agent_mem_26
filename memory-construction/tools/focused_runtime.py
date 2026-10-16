"""Shared frozen query settings; configure before importing the adapter harness.

Runtime observations describe configuration, not experiment success. Actual
serialized messages must still be checked by execution/verify_evidence.py.
"""
import hashlib
import json
import os
from pathlib import Path


def configure(root):
    path = Path(root)/'execution/experiment_contract.json'
    contract = json.loads(path.read_text(encoding='utf-8'))
    for name, value in contract['common_environment'].items():
        os.environ[name] = str(value)
    return contract


def reader_arguments(contract):
    args = []
    for key, value in contract['reader'].items():
        if key == 'reader_enable_thinking':
            if value is not False:
                raise ValueError('This frozen protocol requires Reader thinking disabled.')
            args.append('--reader-disable-thinking')
        else:
            args.extend(['--'+key.replace('_', '-'), str(value)])
    return args


def configure_loaded_query(memory, contract, output_dir):
    """Restore query-only flags after validating the saved construction config.

    Never rewrite the persisted snapshot or its construction/cache signature.
    The harness loads before creating clients; all methods use this same hook.
    """
    observed = {}
    for name, value in contract.get('query_runtime', {}).items():
        if not hasattr(memory, name):
            raise ValueError(f'Loaded memory lacks required query setting: {name}')
        observed[name] = {'saved': getattr(memory, name), 'effective': value}
        setattr(memory, name, value)
    path = Path(output_dir)/'effective_query_runtime.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump({'origin': 'observed_loaded_memory', 'settings': observed}, stream, indent=2)
        stream.write('\n')
    return memory


def record_observed_runtime(root, output_dir, contract, argv):
    root, output = Path(root), Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    record = {
        'origin': 'observed_runtime',
        'execution_revision': contract['execution_revision'],
        'contract_sha256': hashlib.sha256((root/'execution/experiment_contract.json').read_bytes()).hexdigest(),
        'environment': {name: os.environ.get(name) for name in contract['common_environment']},
        'harness_argv': argv,
        'note': 'Captured after resolving runtime settings; verify prompt_rows.messages after real execution. Not a completion receipt.'
    }
    with (output/'effective_runtime.json').open('x', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
