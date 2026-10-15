"""CPU-only tests of the isolated adapted context functions, no model imports."""
import ast
from pathlib import Path
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'runs/agentrunbook-r-native-small-20261014/local-text-only/evaluation/harness.py'


def functions():
    tree = ast.parse(SOURCE.read_text())
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and
                n.name in {'_chunk_memory_context_items', 'validate_loaded_haystack'}]
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    env = {'Any': Any, 'MemoryContextItem': dict, 'require': require}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), 'exec'), env)
    return env


def test_chunk_preserves_all_text_and_interleaves():
    chunk = functions()['_chunk_memory_context_items']
    a = 'a' * 28
    b = 'b' * 21
    rows = chunk([{'type': 'text', 'value': a}, {'type': 'text', 'value': b}], target_chars=10)
    assert [r['value'][0] for r in rows] == list('ababab')
    assert ''.join(r['value'] for r in rows if r['value'][0] == 'a') == a
    assert ''.join(r['value'] for r in rows if r['value'][0] == 'b') == b
    assert all(len(r['value']) <= 10 for r in rows)


def test_chunks_keep_newlines_and_nontext_items():
    chunk = functions()['_chunk_memory_context_items']
    text = 'abcd\nefgh\nijkl\n'
    image = {'type': 'image', 'value': '/unchanged.png'}
    rows = chunk([{'type': 'text', 'value': text}, image], target_chars=9)
    assert ''.join(r['value'] for r in rows if r['type'] == 'text') == text
    assert rows[1] is image
    assert chunk([]) == []


def test_saved_subset_rejected_and_order_checked():
    validate = functions()['validate_loaded_haystack']
    memory = type('Memory', (), {'inserted_trajectory_ids': ['a', 'b']})()
    validate(memory, ['a', 'b'])
    for ids in (['a', 'b', 'c'], ['b', 'a']):
        with pytest.raises(ValueError, match='differ'):
            validate(memory, ids)
