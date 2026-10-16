"""Check the fixed experiment matrix and transport bookkeeping without models."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from focused_reader_transport import configure_reader_transport
spec = importlib.util.spec_from_file_location('full_small_queue', ROOT / 'tools/run_full_small_formal.py')
queue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(queue)


def test_fixed_matrix_all_methods_repeats_and_own_sequence_sources():
    steps = queue.matrix(queue.read(queue.MANIFEST))
    assert len({s['id'] for s in steps}) == len(steps)
    seen = set()
    for step in steps:
        assert set(step['depends_on']) <= seen
        seen.add(step['id'])
    updates = [s for s in steps if s['kind'] == 'update']
    assert len(updates) == 84
    assert sum(s['phase'] == 'main' for s in updates) == 32
    assert sum(s['phase'] == 'ablation' for s in updates) == 4
    assert sum(s['phase'] == 'repeat' for s in updates) == 24
    assert sum(s['phase'] == 'sequence' for s in updates) == 24
    for step in updates:
        if step['phase'] == 'sequence':
            assert step['policy'] in step['source']
            assert len(step['depends_on']) == 2
        else:
            assert 'matched' in step['source'] or '/initial/' in step['source']


def test_reader_retries_disabled_before_client_creation(tmp_path):
    harness = SimpleNamespace(OPENAI_MAX_RETRIES=10)
    configure_reader_transport(harness, tmp_path)
    assert harness.OPENAI_MAX_RETRIES == 0
    record = json.loads((tmp_path / 'effective_reader_transport.json').read_text())
    assert record['sdk_max_retries'] == 0
    assert record['previous_sdk_max_retries'] == 10
