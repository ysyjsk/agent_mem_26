#!/usr/bin/env python3
"""Thin history-revision adapter for the existing Raw RAG / RAG+Notes path.

Only replace the touched trajectory partition. Retain actual-input embeddings
and exact note requests. No events, new memory algorithm or query redesign.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'runs/agentrunbook-r-native-small-20261014/local-text-only'))
sys.path.append(str(ROOT/'third_party/LongMemEval-V2'))
import numpy as np
from memory_modules.memory import load_memory, save_memory
from memory_modules.rag import RagMemory
from memory_modules.agentrunbook_r import AgentRunbookR
from run_agentrunbook_updates import changed_trajectory
from focused_evidence import jsonl, usage
from focused_runtime import configure


def request_fingerprint(record):
    # Historical RAG logs contain the SHA of actual request text, even when
    # full messages were not retained. Bind that SHA to generation settings.
    fields=('model','base_url','max_completion_tokens','temperature','top_p','top_k','enable_thinking')
    shape=record.get('request_shape') or {}
    if not shape.get('text_sha256') or shape.get('image_count',0):
        return None
    return hashlib.sha256(json.dumps([shape]+[record.get(k) for k in fields],sort_keys=True).encode()).hexdigest()


class UpdateRag(RagMemory):
    _construction_embedding_key = AgentRunbookR._construction_embedding_key
    _embed_construction_prepared = AgentRunbookR._embed_construction_prepared

    def _call_controller_text(self, messages, *, disable_thinking=None, max_completion_tokens=None):
        request=self._build_controller_request(messages,
            disable_thinking=self.controller_disable_thinking if disable_thinking is None else disable_thinking,
            max_completion_tokens=max_completion_tokens)
        extra=request.get('extra_body') or {}
        record=dict(model=request['model'],base_url=self.controller_base_url,
            max_completion_tokens=request.get('max_completion_tokens',request.get('max_tokens')),
            temperature=request.get('temperature'),top_p=request.get('top_p'),top_k=extra.get('top_k'),
            enable_thinking=extra.get('enable_thinking',(extra.get('chat_template_kwargs') or {}).get('enable_thinking')),
            request_shape=self._request_shape(messages))
        key=request_fingerprint(record)
        if key and key in self.exact_requests:
            self._append_model_call_metric({'channel':'update_request_cache','status':'hit','key':key,'stage':'notes'})
            return self.exact_requests[key]
        text=super()._call_controller_text(messages,disable_thinking=disable_thinking,max_completion_tokens=max_completion_tokens)
        # Cache only confirmed non-truncated responses, including on later rounds.
        latest=[r for r in jsonl(self.workspace_dir/'model_calls.jsonl') if r.get('channel')=='controller'][-1]
        if key and latest.get('finish_reason')=='stop': self.exact_requests[key]=text
        self.update_notes_regenerated=2
        return text


def seed(memory):
    memory.exact_requests={}
    for record in jsonl(memory.workspace_dir/'model_calls.jsonl'):
        if record.get('channel')!='controller' or record.get('query_invocation_id'):
            continue
        key=request_fingerprint(record)
        if key and record.get('status')=='success' and record.get('finish_reason')=='stop':
            memory.exact_requests[key]=record['response_text']
    memory._construction_embedding_memo={}
    memo=memory.workspace_dir/'embeddings/exact_input_memo.npz'
    if memo.exists():
        with np.load(memo,allow_pickle=False) as loaded:
            memory._construction_embedding_memo={key:loaded[key].copy() for key in loaded.files}
    for name,field in [('raw_state','slice_axtree_text'),('procedure_note','note_text'),('hint_note','note_text')]:
        entries=getattr(memory,name+'_entries')
        vectors=getattr(memory,name+'_embeddings')
        for entry,vector in zip(entries,vectors):
            text=memory._truncate_for_embedding(entry[field])
            memory._construction_embedding_memo[memory._construction_embedding_key(text)]=vector.copy()
    memory.update_notes_regenerated=0


def replace_partition(memory,trajectory,bundle):
    tid=trajectory['id']
    pools=[('raw_state',bundle['raw_state_entries'],bundle['raw_state_embeddings'])]
    if memory.enable_notes:
        pools += [(name,[bundle[name+'_entry']],bundle[name+'_embedding']) for name in ('procedure_note','hint_note')]
    for name,new_entries,new_vectors in pools:
        entries=getattr(memory,name+'_entries');vectors=getattr(memory,name+'_embeddings')
        out_entries=[];out_vectors=[];inserted=False
        for entry,vector in zip(entries,vectors):
            if entry['trajectory_id']==tid:
                if not inserted:
                    out_entries.extend(new_entries);out_vectors.extend(new_vectors);inserted=True
            else: out_entries.append(entry);out_vectors.append(vector)
        if not inserted: raise ValueError(f'Missing existing partition {tid}/{name}')
        setattr(memory,name+'_entries',out_entries)
        setattr(memory,name+'_embeddings',np.asarray(out_vectors,dtype=np.float32))
    (memory.workspace_dir/'trajectories'/tid/'trajectory.json').write_text(json.dumps(trajectory,ensure_ascii=False,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--revision-file',type=Path,required=True)
    args=p.parse_args()
    source=args.source.resolve();out=args.output.resolve()
    configure(ROOT)
    os.environ.update(LME_EMBEDDING_TOKENIZER_MODEL='/data/predator/ly/Mem/models/Qwen3-Embedding-8B',
                      HF_HOME='/data/predator/ly/Mem/.cache/huggingface',LME_REUSE_BUILD_EMBEDDING='1',LME_RECORD_FULL_REQUESTS='1')
    revision=json.loads(args.revision_file.read_text());tid=revision['trajectory_id']
    trajectory,work=changed_trajectory(source,'literal_revision',tid,revision['source_edits'][0]['state_index'],revision_spec=revision)
    out.mkdir(parents=True,exist_ok=False)
    setup=time.perf_counter()
    # Copy evidence, never symlink writable source state back into a baseline.
    shutil.copytree(source,out/'memory_state')
    memory=load_memory(out/'memory_state');memory.__class__=UpdateRag
    memory.controller_disable_thinking=True;memory.controller_max_retries=0
    memory.configure_runtime();seed(memory)
    before={name:(list(getattr(memory,name+'_entries')),getattr(memory,name+'_embeddings').copy())
            for name in ('raw_state','procedure_note','hint_note')}
    setup_s=time.perf_counter()-setup
    def save(name,value): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    save('update_input.json',{'trajectory':trajectory,'workload':work})
    previous=len(jsonl(memory.workspace_dir/'model_calls.jsonl'))
    start_epoch=time.time();start=time.perf_counter()
    bundle=memory._build_trajectory_artifact_bundle(trajectory_dir=memory.workspace_dir/'trajectories'/tid,simplified_trajectory=trajectory)
    build_s=time.perf_counter()-start;publication=time.perf_counter()
    replace_partition(memory,trajectory,bundle)
    save_memory(memory,memory.workspace_dir)
    np.savez(memory.workspace_dir/'embeddings/exact_input_memo.npz',**memory._construction_embedding_memo)
    loaded=load_memory(memory.workspace_dir)
    checks={'source_roundtrip':loaded._load_stored_trajectory(tid)==trajectory,
            'history_preserved':loaded.inserted_trajectory_ids==memory.inserted_trajectory_ids}
    for name,(old_entries,old_vectors) in before.items():
        entries=getattr(loaded,name+'_entries');vectors=getattr(loaded,name+'_embeddings')
        checks[name+'_roundtrip']=entries==getattr(memory,name+'_entries') and np.array_equal(vectors,getattr(memory,name+'_embeddings'))
        old_other=[(e,v) for e,v in zip(old_entries,old_vectors) if e['trajectory_id']!=tid]
        new_other=[(e,v) for e,v in zip(entries,vectors) if e['trajectory_id']!=tid]
        checks[name+'_untouched_preserved']=len(old_other)==len(new_other) and all(a==b and np.array_equal(av,bv) for (a,av),(b,bv) in zip(old_other,new_other))
    if not all(checks.values()): raise RuntimeError(f'RAG update invariant failed: {checks}')
    elapsed=time.perf_counter()-start;pub_s=time.perf_counter()-publication
    calls=jsonl(memory.workspace_dir/'model_calls.jsonl')[previous:]
    c=[r for r in calls if r['channel']=='controller'];e=[r for r in calls if r['channel']=='embedding']
    policy='rag_notes' if memory.enable_notes else 'raw_rag'
    save('update_calls.json',calls)
    save('derived_quality_review.json',{'workload':work,'old_events':[],'new_events':[],
        'old_notes':[x for name in ('procedure_note','hint_note') for x in before[name][0] if x['trajectory_id']==tid],
        'new_notes':[x for x in loaded.procedure_note_entries+loaded.hint_note_entries if x['trajectory_id']==tid],
        'checks':checks,'semantic_review':'pending; raw retrieval and retained notes checked separately'})
    metrics={'policy':policy,'case':'literal_revision','scope':'public_adapted_RAG_partition_update',
        'starting_snapshot':str(source),'starting_cache':'own initial memory; logged exact note requests and actual-input vectors only',
        'setup_load_and_seed_s_excluded':setup_s,'started_epoch':start_epoch,'completed_epoch':time.time(),
        'update_to_queryable_publish_s':elapsed,'artifact_build_s':build_s,'publication_and_reload_s':pub_s,
        'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'llm_calls':len(c),'llm_input_tokens_known':sum(r.get('prompt_tokens') or 0 for r in c),
        'llm_output_tokens_known':sum(r.get('completion_tokens') or 0 for r in c),
        'llm_input_tokens':usage(c,'prompt_tokens'),'llm_output_tokens':usage(c,'completion_tokens'),
        'embedding_calls':len(e),'embedding_vectors':sum(r['input_text_count'] for r in e),
        'embedding_tokens_known':sum(r.get('prompt_tokens') or 0 for r in e),
        'embedding_input_tokens':usage(e,'prompt_tokens'),
        'unknown_usage_calls':sum(r.get('prompt_tokens') is None for r in c+e),
        'api_failed_calls':sum(r['status']=='failed' for r in c+e),
        'reextracted_event_outputs':0,'regenerated_notes':memory.update_notes_regenerated,
        'exact_request_hits':sum(r['channel']=='update_request_cache' for r in calls),
        'embedding_hits':sum(r.get('cache_hits',0) for r in calls if r['channel']=='build_embedding_cache'),
        'trajectory_id':tid,'load_verified':True,'quality_checks':checks,'qa_status':'structural_pass_semantics_and_reader_pending',
        'raw_path':str(out)}
    save('update_metrics.json',metrics);print(json.dumps(metrics),flush=True)


if __name__=='__main__': main()
