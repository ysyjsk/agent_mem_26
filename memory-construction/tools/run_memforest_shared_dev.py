#!/usr/bin/env python3
"""Pinned MemForest, one shared forest per domain, full V2 text and fixed QA.

Adaptations: existing HTTP services, thinking off, bounded client concurrency,
4096-dimensional embeddings, common 2048-output/12000-context Reader. All
upstream tree/extraction/dedup/agentic retrieval and incremental APIs retained.
No state truncation or per-question/per-trajectory isolated memory libraries.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
MF = ROOT / 'third_party/MemForest'
ADAPTER = ROOT / 'runs/agentrunbook-r-native-small-20261014/local-text-only'
sys.path.insert(0, str(MF))
sys.path.insert(0, str(ADAPTER))
sys.path.append(str(ROOT / 'third_party/LongMemEval-V2'))
from openai import OpenAI
import yaml
from run_memforest_local_smoke import _trajectory_to_turns, _sha256_file
from src.api.client import _parse_json_object

LEDGER = None
CHAT_CACHE = {}
BOUND_SUMMARIES = False


def request_key(request):
    return hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def restore_configured_fanout():
    """Fix native API losing configured fanout when a tree starts with one fact.

    Initial small-tree layout is unchanged. Persistent insertion capacity must
    be configured k, not the temporary effective fanout of that initial batch.
    This is a labeled adapter bugfix, not a new tree/retrieval algorithm.
    """
    import src.build.tree_builder as builder
    for name in ('build_tree_from_facts','build_tree_from_cells'):
        original = getattr(builder,name)
        def build(*args, _original=original, **kwargs):
            tree, requests = _original(*args, **kwargs)
            tree.k = max(2,int(kwargs['k']))
            return tree, requests
        setattr(builder,name,build)


def bounded_segments(text, tokenizer, budget=8000):
    """Lossless contiguous character segments; no source is discarded."""
    result=[]
    while text:
        lo,hi=1,len(text)
        while lo<hi:
            mid=(lo+hi+1)//2
            if len(tokenizer.encode(text[:mid],add_special_tokens=False))<=budget:
                lo=mid
            else:
                hi=mid-1
        end=lo
        if end<len(text):
            newline=text.rfind('\n',0,end)
            if newline>max(1,end//2):end=newline+1
        result.append(text[:end]);text=text[end:]
    return result


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


class Ledger:
    def __init__(self, path):
        self.path = path
        self.stage = 'setup'
        self.item = None
        self.rows = []
        self.lock = threading.Lock()

    def add(self, row):
        row.update(stage=self.stage, item=self.item)
        with self.lock:
            self.rows.append(row)
            with self.path.open('a') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(json.dumps({k: row.get(k) for k in ('stage','item','kind','step','status','input_tokens','output_tokens','vectors','elapsed_s')}, ensure_ascii=False), flush=True)

    def totals(self, stage):
        rows = [r for r in self.rows if r['stage'] == stage]
        out = {'failed_calls': sum(r['status'] != 'ok' for r in rows),
               'unknown_usage_calls': sum(r.get('input_tokens') is None for r in rows),
               'truncated_calls': sum(r.get('finish_reason') == 'length' for r in rows),
               'invalid_json_calls': sum(r.get('valid_json') is False for r in rows)}
        for kind in ('llm', 'embedding'):
            rr = [r for r in rows if r['kind'] == kind]
            out[kind + '_calls'] = len(rr)
            out[kind + '_input_tokens_known'] = sum(r.get('input_tokens') or 0 for r in rr)
            out[kind + '_output_tokens_known'] = sum(r.get('output_tokens') or 0 for r in rr)
            out[kind + '_elapsed_sum_s_not_wall'] = sum(r['elapsed_s'] for r in rr)
        out['embedding_vectors'] = sum(r.get('vectors', 0) for r in rows)
        reused=[r for r in rows if r['kind']=='llm_cache']
        out['historical_chat_requests_reused']=len(reused)
        out['historical_input_tokens_reused']=sum(r.get('historical_input_tokens') or 0 for r in reused)
        out['historical_output_tokens_reused']=sum(r.get('historical_output_tokens') or 0 for r in reused)
        return out


class ServiceChat:
    def __init__(self, config, *, client=None, api_logger=None):
        self.config = config
        self.client = client or OpenAI(base_url=config.url, api_key='EMPTY', max_retries=0, timeout=600)
        self.tokenizer = None

    def generate_json(self, *, system_prompt, user_prompt, model_name=None,
                      temperature=None, max_tokens=None, top_p=None, timeout=None,
                      step_label='llm', trace=None):
        request = dict(model=model_name or self.config.model_name,
            messages=[{'role':'system','content':system_prompt},{'role':'user','content':user_prompt}],
            temperature=self.config.temperature if temperature is None else temperature,
            max_tokens=self.config.max_token if max_tokens is None else max_tokens,
            top_p=self.config.top_p if top_p is None else top_p,
            response_format={'type':'json_object'},
            extra_body={'top_k': self.config.topk, 'chat_template_kwargs': {'enable_thinking': False}})
        if BOUND_SUMMARIES and step_label=='tree_summary':
            if self.tokenizer is None:
                from transformers import AutoTokenizer
                self.tokenizer=AutoTokenizer.from_pretrained('/data/predator/ly/Mem/models/Qwen3.5-9B')
            rendered=self.tokenizer.apply_chat_template(request['messages'],tokenize=False,
                         add_generation_prompt=True,enable_thinking=False)
            if len(self.tokenizer.encode(rendered,add_special_tokens=False))>18000:
                # Only overflowing summary requests: same model/prompt contract,
                # contiguous segments then one native-format parent summary.
                # The raw cells/facts and original tree topology remain intact.
                segments=bounded_segments(user_prompt,self.tokenizer)
                assert ''.join(segments)==user_prompt
                partials=[]
                for i,segment in enumerate(segments):
                    result=self.generate_json(system_prompt=system_prompt,
                        user_prompt=f'Contiguous evidence segment {i+1}/{len(segments)} for the requested node. Preserve exact fields, values, outcomes and source/state distinctions.\n'+segment,
                        model_name=model_name,temperature=temperature,max_tokens=max_tokens,top_p=top_p,
                        timeout=timeout,step_label='tree_summary_segment',trace={**(trace or {}),'segment':i})
                    summary=str(result.get('summary') or '').strip()
                    if not summary:raise ValueError('resource split produced empty summary')
                    partials.append(summary)
                return self.generate_json(system_prompt=system_prompt,
                    user_prompt='Summarize the same tree node from these ordered contiguous-segment summaries. '
                                'Preserve state/source distinctions and do not invent persistence across states.\n'+
                                '\n\n'.join(f'Segment {i+1}: {s}' for i,s in enumerate(partials)),
                    model_name=model_name,temperature=temperature,max_tokens=max_tokens,top_p=top_p,
                    timeout=timeout,step_label='tree_summary_merge',trace={**(trace or {}),'resource_split_segments':len(segments)})
        key=request_key(request)
        cached=CHAT_CACHE.get(key)
        if cached is not None:
            LEDGER.add(dict(kind='llm_cache',step=step_label,status='ok',input_tokens=0,output_tokens=0,
                elapsed_s=0,request_sha256=key,source=cached['source'],
                historical_input_tokens=cached['input_tokens'],historical_output_tokens=cached['output_tokens']))
            return _parse_json_object(cached['response'])
        started = time.perf_counter()
        row = dict(kind='llm',step=step_label,request=request,trace=trace,
                   status='error',input_tokens=None,output_tokens=None)
        try:
            response = self.client.chat.completions.create(**request, timeout=timeout or 600)
            content = response.choices[0].message.content or ''
            usage = response.usage
            row.update(status='ok', response=content, finish_reason=response.choices[0].finish_reason,
                input_tokens=usage.prompt_tokens if usage else None,
                output_tokens=usage.completion_tokens if usage else None)
            try:
                raw = content.strip()
                if raw.startswith('```'):
                    raw = '\n'.join(raw.splitlines()[1:-1])
                row['valid_json'] = isinstance(json.loads(raw), dict)
            except ValueError:
                row['valid_json'] = False
            # Preserve upstream parsing and its summary salvage, with failures visible.
            return _parse_json_object(content)
        except Exception as exc:
            row['error'] = repr(exc)
            raise
        finally:
            row['elapsed_s'] = time.perf_counter() - started
            LEDGER.add(row)


class ServiceEmbedding:
    def __init__(self, config, *, client=None):
        self.config = config
        self.client = client or OpenAI(base_url=config.url, api_key='EMPTY', max_retries=0, timeout=600)

    def embed_texts(self, texts, *, batch_size=256):
        result = []
        for i in range(0, len(texts), min(batch_size, 32)):
            batch = list(texts[i:i + min(batch_size,32)])
            started = time.perf_counter()
            row = dict(kind='embedding',step='embedding',status='error',input_tokens=None,
                       output_tokens=0,vectors=0,requested_vectors=len(batch),inputs=batch)
            try:
                response = self.client.embeddings.create(model=self.config.model_name, input=batch)
                vectors = [list(x.embedding) for x in sorted(response.data, key=lambda x:x.index)]
                if len(vectors) != len(batch):
                    raise ValueError('embedding response count mismatch')
                result.extend(vectors)
                row.update(status='ok',vectors=len(vectors),
                    input_tokens=response.usage.prompt_tokens if response.usage else None)
            except Exception as exc:
                row['error'] = repr(exc)
                raise
            finally:
                row['elapsed_s'] = time.perf_counter() - started
                LEDGER.add(row)
        return result


def config_for(output):
    from src.config.config import load_default_config
    payload = yaml.safe_load((MF / 'src/config/default_4b.yaml').read_text())
    payload['model']['llm']['global'].update(url='http://localhost:8023/v1',model_name='Qwen/Qwen3.5-9B',key='EMPTY')
    payload['model']['embedding']['global'].update(url='http://localhost:8114/v1',model_name='Qwen/Qwen3-Embedding-8B',key='EMPTY',dimension=4096)
    payload['query']['node_index_vector_dim'] = 4096
    payload['extraction'].update(max_workers=1,max_inflight_requests=1)
    payload['tree']['summary_manager'].update(max_inflight=1)
    payload['query']['browse']['max_workers'] = 1
    payload['logger']['api']['path'] = str(output / 'upstream_api.jsonl')
    payload['logger']['extraction']['path'] = str(output / 'upstream_extraction.jsonl')
    path = output / 'effective_config.yaml'
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return load_default_config(path)


def main():
    global LEDGER, BOUND_SUMMARIES, CHAT_CACHE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', choices=['web','enterprise'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--query-only', action='store_true', help='Reuse a fully saved shared forest; never rebuild')
    parser.add_argument('--restore-configured-fanout',action='store_true',help='Preserve configured insertion capacity after small-tree initialization')
    parser.add_argument('--bound-summary-input',action='store_true',help='Overflow-only lossless evidence segmentation at the shared18000-token safe input limit; every extra call counted')
    parser.add_argument('--reuse-exact-chat-from',type=Path,help='Repair run only: reuse exact successful prior request/response records; NOT a fresh cold measurement')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and not args.query_only:
        raise FileExistsError(output)
    output.mkdir(parents=True, exist_ok=True)
    LEDGER = Ledger(output / ('query_model_calls.jsonl' if args.query_only else 'model_calls.jsonl'))
    BOUND_SUMMARIES=args.bound_summary_input
    if args.reuse_exact_chat_from:
        for number,line in enumerate(args.reuse_exact_chat_from.read_text().splitlines(),1):
            row=json.loads(line)
            if row.get('kind')=='llm' and row.get('status')=='ok' and row.get('finish_reason')=='stop' and row.get('valid_json'):
                CHAT_CACHE[request_key(row['request'])]={**row,'source':f'{args.reuse_exact_chat_from}:{number}'}
    if args.restore_configured_fanout:
        restore_configured_fanout()
    import src.api.client as api_client
    api_client.OpenAIChatClient = ServiceChat
    api_client.OpenAIEmbeddingClient = ServiceEmbedding
    from src.forest.memforest import MemForest
    from src.config.config import load_default_config
    config = load_default_config(output / 'effective_config.yaml') if args.query_only else config_for(output)
    data_root = ROOT / 'runs/dev-adapted-text-v1/data' / args.domain
    trajectories = [json.loads(x) for x in (data_root / 'trajectories.jsonl').read_text().splitlines() if x.strip()]
    questions = [json.loads(x) for x in (data_root / 'questions.jsonl').read_text().splitlines() if x.strip()]
    frozen = json.loads((data_root / 'frozen_manifest.json').read_text())
    assert [r['id'] for r in trajectories] == frozen['shared_ordered_trajectory_ids']
    manifest = dict(scope='text-only/adapted development, not native/official Small',
        method='MemForest',commit='2b5af6d9f92618b30f3e8b7eb99412c1d5eddd6d',domain=args.domain,
        trajectory_ids=[r['id'] for r in trajectories],question_ids=[q['id'] for q in questions],
        state_count=sum(len(r['states']) for r in trajectories),
        data_sha256={n:_sha256_file(data_root/n) for n in ('trajectories.jsonl','questions.jsonl')},
        config_sha256=_sha256_file(output/'effective_config.yaml'),
        adaptations=['one shared user per domain, one session per complete trajectory',
            'no state text truncation; native memcell chunker',
            'existing 9B chat/8B embedding services; thinking off; concurrency1',
            'upstream4B topology/prompts/sampling/output budgets; embedding dimension4096',
            'same frozen Reader/12000 context/2048 output; native agentic retrieval unchanged'],
        initial_build_reused=args.query_only,configured_fanout_fix=args.restore_configured_fanout,
        overflow_summary_segments=args.bound_summary_input,
        exact_chat_reuse_source=str(args.reuse_exact_chat_from) if args.reuse_exact_chat_from else None,
        cost_scope='repair_with_exact_historical_request_reuse_NOT_cold' if args.reuse_exact_chat_from else 'fresh')
    if not args.query_only:
        write_json(output/'manifest.json',manifest)
    user = 'shared-' + args.domain
    forest = MemForest(output/'memory_state',config=config,max_workers=1)
    forest.register_user(user, load_existing=args.query_only)
    if not args.query_only:
        LEDGER.stage = 'build'
        build_started = time.perf_counter()
        per_trajectory = []
        for trajectory in trajectories:
            LEDGER.item = trajectory['id']
            turns, source = _trajectory_to_turns(trajectory, max_chars_per_state=None)
            started = time.perf_counter()
            ingest = forest.ingest_session(user, trajectory['id'], turns)
            forest.save(user)
            row = dict(trajectory_id=trajectory['id'],source=source,ingest=asdict(ingest),
                       publish_s=time.perf_counter()-started)
            per_trajectory.append(row)
            write_json(output/'build_progress.json',dict(completed=len(per_trajectory),total=len(trajectories),
                       trajectories=per_trajectory,cost=LEDGER.totals('build')))
            print(json.dumps({'published':trajectory['id'],'count':len(per_trajectory),'publish_s':row['publish_s']}),flush=True)
        # Native save/reload verification is included in publication, not a query.
        forest = MemForest(output/'memory_state',config=config,max_workers=1)
        forest.register_user(user,load_existing=True)
        uf = forest._get_user(user)
        assert {t['id'] for t in trajectories}.issubset(uf._registry.list_active_sessions())
        nodes=[n for tree in uf._tree_builder.trees.values() for n in tree.nodes.values()]
        write_json(output/'build_metrics.json',dict(build_publish_s=time.perf_counter()-build_started,
            load_verified=True,trajectories=per_trajectory,cost_scope=manifest['cost_scope'],
            dirty_internal_nodes=sum(n.summary_dirty for n in nodes if n.level>0),
            facts=len(list(uf._fact_manager.iter_facts())),trees=len(uf._tree_builder.trees),
            **LEDGER.totals('build')))
    os.environ.update(LME_TEXT_ONLY='1',LME_CHUNK_MEMORY_CONTEXT='1',LME_CACHE_CONTEXT_TOKENIZER='1')
    from evaluation.harness import (build_messages, get_system_prompt, truncate_memory_context,
        generate_all_reader_outputs, eval_from_spec, score_to_bool)
    template = ROOT/'runs/method-first-20261015/v12-web-2e8f6477-reply-replacement/literal_revision-b3/reader/run_args.json'
    reader_args = argparse.Namespace(**json.loads(template.read_text()))
    reader_args.domain = args.domain
    write_json(output/'reader_args.json',vars(reader_args))
    per_question_path = output / ('per_question_query_only.jsonl' if args.query_only else 'per_question.jsonl')
    if per_question_path.exists():
        raise FileExistsError(per_question_path)
    rows = []
    for q in questions:
        LEDGER.stage = 'retrieval'
        LEDGER.item = q['id']
        started = time.perf_counter()
        result = forest.query(user,q['question'])
        retrieval_s = time.perf_counter() - started
        context = [{'type':'text','value':f.fact_text} for f in result.top_facts]
        context, original_tokens, kept_tokens = truncate_memory_context(context,max_tokens=12000,question_id=q['id'])
        messages,_ = build_messages(get_system_prompt(args.domain),q['question'],None,context)
        started = time.perf_counter()
        responses = asyncio.run(generate_all_reader_outputs(reader_args,[{'question_id':q['id'],'messages':messages}]))
        response = responses[q['id']]
        reader_wall_s = time.perf_counter() - started
        # The frozen eight questions all have deterministic programmatic scorers.
        assert q['eval_function'].startswith('norm_phrase_set_match|')
        correct = bool(response['reader_answer_complete'] and score_to_bool(eval_from_spec(q['eval_function'],response['response_parsed_boxed'],q['answer'])))
        row = dict(question_id=q['id'],question=q['question'],answer_gold=q['answer'],
            eval_function=q['eval_function'],correct=correct,score=correct,**response,
            retrieval_s=retrieval_s,reader_wall_s=reader_wall_s,messages=messages,
            retrieved_facts=[asdict(f) for f in result.top_facts],
            original_context_tokens=original_tokens,context_tokens=kept_tokens)
        with per_question_path.open('a') as f:
            f.write(json.dumps(row,ensure_ascii=False,default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x))+'\n')
        rows.append(row)
        print(json.dumps({'question_id':q['id'],'answer':response['response_parsed_boxed'],'complete':response['reader_answer_complete'],'correct':correct}),flush=True)
    write_json(output/('query_only_metrics.json' if args.query_only else 'query_metrics.json'),dict(
        questions=len(rows),complete=sum(r['reader_answer_complete'] for r in rows),correct=sum(r['correct'] for r in rows),
        truncated=sum(r['reader_truncated'] for r in rows),service_failure=sum(r['reader_status']!='ok' for r in rows),
        parse_failure=sum(r['reader_parse_status']=='parse_failure' for r in rows),pending=0,
        retrieval_wall_s=sum(r['retrieval_s'] for r in rows),reader_wall_s=sum(r['reader_wall_s'] for r in rows),
        reader_input_tokens=sum(r['usage']['prompt_tokens'] for r in rows),reader_output_tokens=sum(r['usage']['completion_tokens'] for r in rows),
        retrieval_cost=LEDGER.totals('retrieval')))


if __name__ == '__main__':
    main()
