#!/usr/bin/env python3
"""Extend one existing library to the frozen official history, saving per trajectory.

No cross-method outputs are reused. Historical costs are referenced separately;
the measured time here is expansion, not a fresh cold-build measurement.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runs/agentrunbook-r-native-small-20261014/local-text-only'))
sys.path.append(str(ROOT/'third_party/LongMemEval-V2'))
from memory_modules.memory import load_memory,save_memory
from focused_runtime import configure
from focused_evidence import jsonl
from run_rag_updates import UpdateRag,seed


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--domain',choices=['web','enterprise'],required=True)
    p.add_argument('--max-new-trajectories',type=int,default=None,help='Optional bounded first-stage verification; never claims full completion.')
    a=p.parse_args();manifest=json.loads(a.manifest.read_text());ids=manifest['data'][a.domain]['trajectory_ids']
    source=a.source.resolve();out=a.output.resolve();state=out/'memory_state'
    contract=configure(ROOT)
    os.environ.update(LME_EMBEDDING_TOKENIZER_MODEL='/data/predator/ly/Mem/models/Qwen3-Embedding-8B',
                      HF_HOME='/data/predator/ly/Mem/.cache/huggingface',LME_REUSE_BUILD_EMBEDDING='1',
                      LME_RECORD_FULL_REQUESTS='1',LME_EVENT_GROUP_SIZE='2',LME_EVENT_OUTPUT_TOKENS='1024',
                      LME_EVENT_MAX_INPUT_TOKENS='18000',LME_EVENT_CONCURRENCY='1')
    if not state.exists():
        out.mkdir(parents=True,exist_ok=False)
        shutil.copytree(source,state)
        (out/'expansion_origin.json').write_text(json.dumps({'source':str(source),'domain':a.domain,
            'manifest':str(a.manifest.resolve()),'manifest_sha256':hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
            'scope':'reuse own historical initial partitions; add missing official IDs; NOT cold build',
            'source_config':json.loads((source/'memory_config.json').read_text()),
            'reused_ids':json.loads((source/'index.json').read_text())['inserted_trajectory_ids']},indent=2)+'\n')
        # This clone's future extraction config is normalized. Keep the old
        # provenance for audit, but do not present it as current bound outputs.
        prior=state/'matched_update_cache.json'
        if prior.exists(): prior.rename(state/'historical_matched_update_cache.json')
    memory=load_memory(state)
    assert set(memory.inserted_trajectory_ids)<=set(ids)
    memory.controller_disable_thinking=True;memory.controller_max_retries=0
    if hasattr(memory,'query_generation_disable_thinking'):memory.query_generation_disable_thinking=True
    if memory.memory_type=='rag':
        memory.__class__=UpdateRag
        memory.configure_runtime();seed(memory)
    else: memory.configure_runtime()
    memory.trajectory_pool_root=None
    memory.trajectories_root_dir=ROOT/'third_party/LongMemEval-V2/data/longmemeval-v2'
    save_memory(memory,state)
    missing=[tid for tid in ids if tid not in memory.inserted_trajectory_ids]
    if a.max_new_trajectories is not None:missing=missing[:a.max_new_trajectories]
    wanted=set(missing);data={}
    for line in (memory.trajectories_root_dir/'trajectories.jsonl').open():
        tr=json.loads(line)
        if tr['id'] in wanted:data[tr['id']]=tr
    assert set(data)==wanted
    for tid in missing:
        trajectory_dir=state/'trajectories'/tid
        if trajectory_dir.exists():
            # Only an uncommitted directory for this known missing ID; retain
            # it rather than deleting evidence from an interrupted attempt.
            failed=out/'interrupted_trajectories'/f'{tid}-{time.time_ns()}'
            failed.parent.mkdir(exist_ok=True)
            trajectory_dir.rename(failed)
        offset=len(jsonl(state/'model_calls.jsonl'));started=time.perf_counter();epoch=time.time()
        try:
            memory.insert(data[tid]);save_memory(memory,state)
            if memory.memory_type=='rag':
                import numpy as np
                np.savez(state/'embeddings/exact_input_memo.npz',**memory._construction_embedding_memo)
            index=json.loads((state/'index.json').read_text())
            assert tid in index['inserted_trajectory_ids']
        except Exception as exc:
            (out/f'failure-{tid}-{time.time_ns()}.json').write_text(json.dumps({'trajectory_id':tid,'error':repr(exc),'started_epoch':epoch,'elapsed_s':time.perf_counter()-started})+'\n')
            raise
        calls=jsonl(state/'model_calls.jsonl')[offset:]
        row={'trajectory_id':tid,'started_epoch':epoch,'publish_wall_s':time.perf_counter()-started,
             'history_count':len(memory.inserted_trajectory_ids),'required_history_count':len(ids),
             'llm_calls':sum(c['channel']=='controller' for c in calls),
             'llm_tokens_known':sum((c.get('prompt_tokens') or 0)+(c.get('completion_tokens') or 0) for c in calls if c['channel']=='controller'),
             'embedding_vectors':sum(c.get('input_text_count',0) for c in calls if c['channel']=='embedding'),
             'unknown_usage_calls':sum(c.get('prompt_tokens') is None for c in calls if c['channel'] in ('controller','embedding'))}
        with (out/'expansion_metrics.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    complete=set(memory.inserted_trajectory_ids)==set(ids)
    if complete:
        reloaded=load_memory(state)
        assert set(reloaded.inserted_trajectory_ids)==set(ids)
        (out/'full_history_verified.json').write_text(json.dumps({'domain':a.domain,'actual_ids':reloaded.inserted_trajectory_ids,'official_id_set_matches':True,'manifest':str(a.manifest.resolve()),'initial_cost_scope':'historical reference + expansion, not fresh cold'},indent=2)+'\n')
    print(json.dumps({'history':len(memory.inserted_trajectory_ids),'full_history':complete}),flush=True)


if __name__=='__main__':main()
