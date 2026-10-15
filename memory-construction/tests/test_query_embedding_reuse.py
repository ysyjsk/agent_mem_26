"""Exact query-local memoization; no provider calls in these CPU tests."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import time

import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / 'runs/agentrunbook-r-native-small-20261014/local-text-only/memory_modules/agentrunbook_r.py'


def make_owner():
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AgentRunbookR')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_embed_texts')
    env = {'np': np, 'time': time, 'os': os,
           '_normalize_embeddings': lambda values: np.asarray(values, dtype=np.float32)}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(SOURCE), 'exec'), env)
    calls, cache_hits = [], []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0, 2.0]) for _ in kwargs['input']])
    class Owner:
        embedding_model = 'test-model'
        embedding_base_url = 'http://test-only'
        query_id = 'q1'
        _runtime_local = SimpleNamespace()
        _embed_texts = env['_embed_texts']
        def get_query_context(self): return {'query_invocation_id': self.query_id}
        def _format_query_for_embedding(self, text): return 'query:' + text
        def _truncate_for_embedding(self, text): return text
        def _get_embedding_client(self): return SimpleNamespace(embeddings=SimpleNamespace(create=create))
        def _record_embedding_call(self, **kwargs): pass
        def _append_model_call_metric(self, row): cache_hits.append(row)
    return Owner(), calls, cache_hits


def test_cache_exact_key_invocation_and_mutation_isolation(monkeypatch):
    monkeypatch.setenv('LME_REUSE_QUERY_EMBEDDING', '1')
    owner, calls, hits = make_owner()
    a = owner._embed_texts(['question'], is_query=True)
    a[0, 0] = 99
    b = owner._embed_texts(['question'], is_query=True)
    assert len(calls) == 1 and len(hits) == 1
    assert b.tolist() == [[1, 2]]
    owner._embed_texts(['different question'], is_query=True)
    owner.embedding_model = 'changed-model'
    owner._embed_texts(['question'], is_query=True)
    owner.query_id = 'q2'
    owner._embed_texts(['question'], is_query=True)
    assert len(calls) == 4


def test_no_build_crossquery_or_disabled_reuse(monkeypatch):
    owner, calls, hits = make_owner()
    monkeypatch.setenv('LME_REUSE_QUERY_EMBEDDING', '1')
    for _ in range(2): owner._embed_texts(['state'], is_query=False)
    owner.query_id = None
    for _ in range(2): owner._embed_texts(['question'], is_query=True)
    owner.query_id = 'q'
    monkeypatch.setenv('LME_REUSE_QUERY_EMBEDDING', '0')
    for _ in range(2): owner._embed_texts(['question'], is_query=True)
    assert len(calls) == 6 and not hits
