#!/usr/bin/env bash
set -euo pipefail

ROOT="/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction"
PY="/data/predator/ly/Mem/.venv/bin/python"
DATA_ROOT="$ROOT/third_party/LongMemEval-V2/data/longmemeval-v2"
RUN_ROOT="$ROOT/runs/agentrunbook-r-native-small-20261014/adapted-aliyun-vl"
DOMAIN="${1:-}"

if [[ "$DOMAIN" != web && "$DOMAIN" != enterprise ]]; then
  echo "usage: ALIYUN_API_KEY=<runtime-only> $0 {web|enterprise}" >&2
  exit 2
fi
: "${ALIYUN_API_KEY:?ALIYUN_API_KEY must be supplied in the process environment}"

OUT="$RUN_ROOT/$DOMAIN"
if [[ -e "$OUT/run_args.json" || -e "$OUT/memory_workspace" ]]; then
  echo "Refusing to reuse a non-empty run output: $OUT" >&2
  exit 3
fi

umask 077
mkdir -p "$OUT"
export PYTHONNOUSERSITE=1
export PYTHONPATH="$ROOT/third_party/LongMemEval-V2${PYTHONPATH:+:$PYTHONPATH}"
export LME_EMBEDDING_TOKENIZER_MODEL="/data/predator/ly/Mem/models/Qwen3-Embedding-8B"
exec > >(tee -a "$OUT/run.log") 2>&1

echo "run_kind=adapted-matched"
echo "method=agentrunbook_r domain=$DOMAIN tier=small"
echo "reader_controller=qwen3-vl-plus evaluator=qwen-plus evaluator_scope=evaluator-only"
echo "embedding=local-Qwen3-Embedding-8B reader_concurrency=1 prompt_build_workers=1"
echo "output_dir=$OUT"

/usr/bin/time -f "domain=$DOMAIN wall_seconds=%e" -o "$OUT/wall_time.txt" \
  "$PY" "$ROOT/third_party/LongMemEval-V2/evaluation/run_eval.py" \
  --method agentrunbook_r \
  --data-root "$DATA_ROOT" \
  --domain "$DOMAIN" \
  --tier small \
  --output-dir "$OUT" \
  --reader-model qwen3-vl-plus \
  --reader-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --reader-api-key-env ALIYUN_API_KEY \
  --reader-temperature 0.6 \
  --reader-top-p 0.95 \
  --reader-top-k 20 \
  --reader-max-concurrent-requests 1 \
  --reader-enable-thinking \
  --max-completion-tokens 20000 \
  --memory-context-max-tokens 200000 \
  --controller-model qwen3-vl-plus \
  --controller-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --controller-api-key-env ALIYUN_API_KEY \
  --controller-temperature 0.6 \
  --controller-top-p 0.95 \
  --controller-top-k 20 \
  --no-controller-disable-thinking \
  --embedding-model Qwen3-Embedding-8B \
  --embedding-base-url http://127.0.0.1:8114/v1 \
  --embedding-api-key-env LME_LOCAL_EMBEDDING_API_KEY \
  --evaluator-model qwen-plus \
  --evaluator-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --evaluator-api-key-env ALIYUN_API_KEY \
  --evaluator-reasoning-effort medium \
  --evaluator-max-completion-tokens 4096 \
  --prompt-build-max-workers 1
