#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
JOB="$ROOT/execution/background/full-small-recovery-20261016-v9"
while [[ "$(cat "$JOB/status" 2>/dev/null || echo unknown)" == running ]]; do
  sleep 30
done
# The preceding recovery used the original GPU-only KV cache.  Restart the
# shared chat service exactly once at this safe persistence boundary, before
# the first retry request, so long missing Event/Notes entries use the
# offloaded-cache backend.  Never touch a live model runner or an unmatching
# process.
CHAT_PID_FILE="$ROOT/execution/background/chat-server-recovery-20261016.pid"
CHAT_LOG="$ROOT/execution/background/chat-server-paper-delivery-20261016-v1.log"
CHAT_PID="$(cat "$CHAT_PID_FILE" 2>/dev/null || true)"
if [[ "$CHAT_PID" =~ ^[0-9]+$ ]] && kill -0 "$CHAT_PID" 2>/dev/null; then
  CHAT_CMD="$(tr '\0' ' ' < "/proc/$CHAT_PID/cmdline" 2>/dev/null || true)"
  if [[ "$CHAT_CMD" == *"tools/local_openai_server.py --mode chat"* && "$CHAT_CMD" == *"--port 8023"* ]]; then
    kill -TERM "$CHAT_PID"
    for _ in $(seq 1 60); do
      kill -0 "$CHAT_PID" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$CHAT_PID" 2>/dev/null; then
      echo "chat service did not stop at safe boundary: $CHAT_PID" >&2
      exit 1
    fi
  else
    echo "refusing to replace non-matching chat PID $CHAT_PID" >&2
    exit 1
  fi
fi
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export LME_OFFLOAD_CACHE_PROMPT_TOKENS=12000
export PYTHONPATH="$ROOT/src:$ROOT/third_party/LongMemEval-V2"
nohup /data/predator/ly/Mem/.venv/bin/python "$ROOT/tools/local_openai_server.py" \
  --mode chat --model-path /data/predator/ly/Mem/models/Qwen3.5-9B \
  --model-id Qwen3.5-9B --device cuda:0 --dtype bfloat16 --host 127.0.0.1 \
  --port 8023 --max-input-tokens 32768 --max-new-tokens-cap 4096 \
  --enable-thinking --log-requests >"$CHAT_LOG" 2>&1 &
NEW_CHAT_PID=$!
echo "$NEW_CHAT_PID" >"$CHAT_PID_FILE"
for _ in $(seq 1 120); do
  if curl -fsS http://127.0.0.1:8023/health >/dev/null 2>&1; then break; fi
  sleep 1
done
if ! curl -fsS http://127.0.0.1:8023/health >/dev/null 2>&1; then
  echo "restarted chat service failed health check: $NEW_CHAT_PID" >&2
  exit 1
fi
exec /data/predator/ly/Mem/.venv/bin/python "$ROOT/execution/recover_full_small_after_failure.py" --execute
