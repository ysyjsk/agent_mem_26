#!/usr/bin/env bash
set -u -o pipefail
ROOT="/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction"
RUN="$ROOT/runs/agentrunbook-r-native-small-20261013/matched-qwenplus-v2"
PY="/data/predator/ly/Mem/.venv/bin/python"
mkdir -p "$RUN/web"
exec /usr/bin/time -f 'domain=web wall_seconds=%e' -o "$RUN/web/wall_time.txt" \
  "$PY" "$ROOT/third_party/LongMemEval-V2/evaluation/run_eval.py" \
  --method agentrunbook_r \
  --data-root "$ROOT/third_party/LongMemEval-V2/data/longmemeval-v2" \
  --domain web --tier small --output-dir "$RUN/web" \
  --reader-model /data/predator/ly/Mem/models/Qwen3.5-9B \
  --reader-base-url http://127.0.0.1:8023/v1 \
  --reader-temperature 0.6 --reader-top-p 0.95 --reader-top-k 20 \
  --reader-max-concurrent-requests 1 --reader-enable-thinking \
  --max-completion-tokens 20000 --memory-context-max-tokens 200000 \
  --controller-model /data/predator/ly/Mem/models/Qwen3.5-9B \
  --controller-base-url http://127.0.0.1:8023/v1 \
  --controller-temperature 0.6 --controller-top-p 0.95 --controller-top-k 20 \
  --embedding-model /data/predator/ly/Mem/models/Qwen3-Embedding-8B \
  --embedding-base-url http://127.0.0.1:8114/v1 \
  --evaluator-model qwen-plus \
  --evaluator-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --evaluator-api-key-env ALIYUN_API_KEY \
  --evaluator-reasoning-effort medium --prompt-build-max-workers 1
