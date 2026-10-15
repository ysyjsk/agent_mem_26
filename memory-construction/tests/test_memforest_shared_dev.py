"""No inference: transport accounting and full-input adapter guarantees."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace as NS

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'tools'))
    spec=importlib.util.spec_from_file_location('mf_shared',ROOT/'tools/run_memforest_shared_dev.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_complete_state_text_is_not_smoke_truncated(runner):
    text='x'*13000+' END_EVIDENCE'
    turns,meta=runner._trajectory_to_turns(dict(id='t',goal='g',states=[dict(state_index=0,accessibility_tree=text)]),max_chars_per_state=None)
    assert text in turns[0]['content']
    assert not meta['prefix_truncated']
    assert turns[0]['metadata']['trajectory_id']=='t'


def test_http_budget_thinking_and_usage_are_recorded(runner,tmp_path):
    captured={}
    def create(**kwargs):
        captured.update(kwargs)
        return NS(choices=[NS(message=NS(content='{"summary":"ok"}'),finish_reason='stop')],
                  usage=NS(prompt_tokens=17,completion_tokens=8))
    runner.LEDGER=runner.Ledger(tmp_path/'calls.jsonl');runner.LEDGER.stage='build'
    cfg=NS(url='http://localhost:8023/v1',model_name='m',max_token=4096,topk=20,temperature=0,top_p=.8)
    client=NS(chat=NS(completions=NS(create=create)))
    response=runner.ServiceChat(cfg,client=client).generate_json(system_prompt='s',user_prompt='u',max_tokens=200)
    assert response=={'summary':'ok'}
    assert captured['max_tokens']==200
    assert captured['extra_body']['chat_template_kwargs']['enable_thinking'] is False
    totals=runner.LEDGER.totals('build')
    assert totals['llm_calls']==1 and totals['llm_input_tokens_known']==17
    assert totals['llm_output_tokens_known']==8 and totals['failed_calls']==0


def test_failure_without_usage_is_unknown_not_free(runner,tmp_path):
    def create(**kwargs):
        raise RuntimeError('test service failure')
    runner.LEDGER=runner.Ledger(tmp_path/'calls.jsonl');runner.LEDGER.stage='build'
    cfg=NS(url='http://localhost:8023/v1',model_name='m',max_token=4096,topk=20,temperature=0,top_p=.8)
    with pytest.raises(RuntimeError):
        runner.ServiceChat(cfg,client=NS(chat=NS(completions=NS(create=create)))).generate_json(system_prompt='s',user_prompt='u')
    totals=runner.LEDGER.totals('build')
    assert totals['failed_calls']==1 and totals['unknown_usage_calls']==1
