#!/usr/bin/env python3
"""Fixed common Reader and original RAG retrieval, on an updated shared library."""
import argparse
import json
import os
from pathlib import Path
import sys
from focused_runtime import configure, reader_arguments, record_observed_runtime
from focused_reader_transport import configure_reader_transport

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--domain',required=True,choices=['web','enterprise'])
    p.add_argument('--memory-dir',type=Path,required=True)
    p.add_argument('--questions-path',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    contract=configure(ROOT)
    os.environ.update(LME_EMBEDDING_TOKENIZER_MODEL='/data/predator/ly/Mem/models/Qwen3-Embedding-8B',
                      HF_HOME='/data/predator/ly/Mem/.cache/huggingface')
    sys.path.insert(0,str(ROOT/'runs/agentrunbook-r-native-small-20261014/local-text-only'))
    sys.path.append(str(ROOT/'third_party/LongMemEval-V2'))
    from evaluation import harness
    memory=a.memory_dir.resolve();out=a.output.resolve()
    if out.exists(): raise FileExistsError(out)
    runtime=out/'runtime_inputs';runtime.mkdir(parents=True)
    configure_reader_transport(harness,out)
    questions=[json.loads(l) for l in a.questions_path.open() if l.strip()]
    ids=json.loads((memory/'index.json').read_text())['inserted_trajectory_ids']
    (runtime/'questions.json').write_text(json.dumps(questions,ensure_ascii=False,indent=2)+'\n')
    (runtime/'haystack.json').write_text(json.dumps({q['id']:ids for q in questions})+'\n')
    argv=['evaluation.harness','--domain',a.domain,'--questions-path',str(runtime/'questions.json'),
          '--haystack-path',str(runtime/'haystack.json'),'--trajectories-path',str(ROOT/'third_party/LongMemEval-V2/data/longmemeval-v2/trajectories.jsonl'),
          '--memory-config-path',str(memory/'memory_config.json'),'--load-memory-dir',str(memory),
          '--output-dir',str(out),'--base-url','http://localhost:8023/v1','--api-key-env','OPENAI_API_KEY',
          '--prompt-build-max-workers','1','--reader-max-concurrent-requests','1',
          '--evaluator-model','','--evaluator-base-url','']+reader_arguments(contract)
    record_observed_runtime(ROOT,out,contract,argv)
    old=sys.argv
    try: sys.argv=argv;harness.main()
    finally: sys.argv=old


if __name__=='__main__': main()
