"""CPU-only contracts for adjacent extraction; real costs come from live runs."""
import ast
import asyncio
import json
import os
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parents[1] / 'runs/agentrunbook-r-native-small-20261014/local-text-only/memory_modules/agentrunbook_r.py'


def owner_fixture():
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AgentRunbookR')
    names = {'_build_event_group_messages', '_extract_event_group_async'}
    defs = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    prompt = next(n.value.value for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'EVENT_GENERATION_SYSTEM_PROMPT' for t in n.targets))
    def require(ok, message):
        if not ok: raise ValueError(message)
    env = {'os': os, 'json': json, 'Any': Any, 'Path': Path, 'EVENT_GENERATION_SYSTEM_PROMPT': prompt,
           'require': require, '_full_action_sequence_text': lambda s: 'shared action trace',
           '_state_text': lambda s: s['text'], '_state_url': lambda s: 'url', '_state_thoughts': lambda s: 'thought',
           '_json_candidates': lambda text: [text],
           '_parse_single_event_response': lambda text: {k: v for k, v in json.loads(text).items() if k in ('overview', 'state_transition') and v}}
    exec(compile(ast.Module(body=defs, type_ignores=[]), str(SOURCE), 'exec'), env)
    class Owner:
        _build_event_group_messages = env['_build_event_group_messages']
        _extract_event_group_async = env['_extract_event_group_async']
        tokens = 100
        bad = False
        def __init__(self): self.calls, self.logs, self.singles = [], [], []
        def _event_group_input_tokens(self, messages): return self.tokens
        def _request_shape(self, messages): return {'text_sha256': 'test'}
        def _append_model_call_metric(self, record): self.logs.append(record)
        async def _call_controller_text_async(self, messages, **kwargs):
            self.calls.append(kwargs)
            return json.dumps({'events': [{'event_id': e, 'overview': 'o', 'state_transition': 's'} for e in (['bad', 'b'] if self.bad else ['a', 'b'])]})
        async def _extract_single_event_fields_async(self, **kwargs):
            self.singles.append(kwargs['spec']['event_id'])
            return {'overview': 'o', 'state_transition': 's'}
    specs = [dict(event_id=e, trajectory_id='t', pre_state_index=i, post_state_index=i+1,
                  local_action=f'action{i}', pre_incoming_action='initial', transition_number=i+1, transition_count=2)
             for i, e in enumerate(['a', 'b'])]
    trajectory = {'goal': 'task', 'start_url': 'url', 'states': [{'state_index': i, 'text': f'UNIQUE_STATE_{i}'} for i in range(3)]}
    return Owner(), {'trajectory_dir': Path('.'), 'simplified_trajectory': trajectory, 'specs': specs}


def test_joint_request_shares_middle_state_and_preserves_schema(monkeypatch):
    monkeypatch.setenv('LME_EVENT_OUTPUT_TOKENS', '2048')
    owner, args = owner_fixture()
    messages = owner._build_event_group_messages(**args)
    serialized = json.dumps(messages)
    assert all(serialized.count(f'UNIQUE_STATE_{i}') == 1 for i in range(3))
    rows = asyncio.run(owner._extract_event_group_async(**args))
    assert len(rows) == 2 and len(owner.calls) == 1 and not owner.singles
    assert owner.calls[0]['max_completion_tokens'] == 4096
    assert owner.logs[0]['status'] == 'parsed'


def test_context_split_and_bad_ids_only_fall_back_affected_group():
    owner, args = owner_fixture()
    owner.tokens = 32769
    assert len(asyncio.run(owner._extract_event_group_async(**args))) == 2
    assert not owner.calls and owner.singles == ['a', 'b']
    owner, args = owner_fixture()
    owner.bad = True
    asyncio.run(owner._extract_event_group_async(**args))
    assert len(owner.calls) == 1 and owner.singles == ['a', 'b']
    assert owner.logs[-1]['reason'] == 'group_parse_failure'


def test_arrived_singleton_does_not_wait_for_future_event():
    owner, args = owner_fixture()
    args['specs'] = args['specs'][:1]
    assert len(asyncio.run(owner._extract_event_group_async(**args))) == 1
    assert not owner.calls and owner.singles == ['a']
