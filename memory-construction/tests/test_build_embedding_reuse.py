"""Exact input memo contracts, no model services used by unit tests."""
import ast
import hashlib
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / 'runs/agentrunbook-r-native-small-20261014/local-text-only/memory_modules/agentrunbook_r.py'


def owner_fixture():
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AgentRunbookR')
    names = {'_construction_embedding_key', '_embed_construction_prepared'}
    defs = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    def require(ok, message):
        if not ok: raise ValueError(message)
    env = {'os': os, 'json': json, 'hashlib': hashlib, 'time': time, 'np': np,
           'require': require, '_normalize_embeddings': lambda rows: np.asarray(rows, dtype=np.float32)}
    exec(compile(ast.Module(body=defs, type_ignores=[]), str(SOURCE), 'exec'), env)
    class Owner:
        embedding_model = 'test'
        embedding_base_url = 'test://local'
        embedding_max_input_tokens = 4096
        _construction_embedding_key = env['_construction_embedding_key']
        _embed_construction_prepared = env['_embed_construction_prepared']
        def __init__(self): self._construction_embedding_memo, self.calls, self.logs = {}, [], []
        def _get_embedding_client(self): return SimpleNamespace(embeddings=SimpleNamespace(create=self.create))
        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[float(len(t)), 1]) for t in kwargs['input']])
        def _record_embedding_call(self, **kwargs): pass
        def _append_model_call_metric(self, record): self.logs.append(record)
    return Owner()


def test_dedup_scatter_changed_input_and_mutation_safety():
    owner = owner_fixture()
    result = owner._embed_construction_prepared(['same', 'same', 'different'])
    assert owner.calls[0]['input'] == ['same', 'different']
    assert result.shape == (3, 2) and (result[0] == result[1]).all()
    result[0, 0] = 99
    again = owner._embed_construction_prepared(['same'])
    assert again[0, 0] == 4 and len(owner.calls) == 1
    owner._embed_construction_prepared(['changed'])
    assert len(owner.calls) == 2


def test_model_configuration_and_independent_store_isolation():
    owner = owner_fixture()
    owner._embed_construction_prepared(['same'])
    owner.embedding_model = 'new-model'
    owner._embed_construction_prepared(['same'])
    owner.embedding_max_input_tokens = 2048
    owner._embed_construction_prepared(['same'])
    other = owner_fixture()
    other._embed_construction_prepared(['same'])
    assert len(owner.calls) == 3 and len(other.calls) == 1
