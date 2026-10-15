"""Query-time backfill must preserve exact source text, never insert answers."""
import importlib.util
from pathlib import Path

P = Path(__file__).resolve().parents[1] / 'runs/agentrunbook-r-native-small-20261014/local-text-only/memory_modules/source_backfill.py'
spec = importlib.util.spec_from_file_location('source_backfill', P)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_stable_lines_once_changed_fields_retained():
    records = [{'id': 't1', 'states': [
        {'state_index': 0, 'text': '[1] link comments\n[2] textbox type=old'},
        {'state_index': 1, 'text': '[8] link comments\n[9] textbox type=new'}]}]
    rows = module.source_backfill('Which "type" and comments?', records)
    text = rows[0]['value']
    assert text.count('link comments') == 1
    assert 'type=old' in text and 'type=new' in text
    assert '[t1 state 1 line 1]' in text
    assert module.source_backfill('nonmatching', records) == []


def test_bound_and_original_order():
    records = [{'id': 't', 'states': [{'state_index': 2, 'text': 'alpha item\nbeta item\ngamma item'}]}]
    text = module.source_backfill('item', records, max_lines=2)[0]['value']
    assert 'alpha item' in text and 'beta item' in text and 'gamma' not in text
    assert text.index('alpha') < text.index('beta')


def test_neighbor_context_opt_in_and_total_bound(monkeypatch):
    records = [{'id': 't', 'states': [{'state_index': 9, 'text':
                "parent explanation\n[2] link comments\nnext sentence"}]}]
    query = 'comments'
    monkeypatch.setenv('LME_BACKFILL_NEIGHBOR_LINES', '0')
    assert 'parent explanation' not in module.source_backfill(query, records)[0]['value']
    monkeypatch.setenv('LME_BACKFILL_NEIGHBOR_LINES', '1')
    text = module.source_backfill(query, records)[0]['value']
    assert text.index('parent explanation') < text.index('link comments') < text.index('next sentence')
    text = module.source_backfill(query, records, max_chars=40)[0]['value']
    assert 'parent explanation' not in text
