#!/usr/bin/env bash
# Fixed Reader regression only. No search, no construction, no external Judge.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
for item in \
  web:1ad1af4b:state_revision:4 \
  web:1ad1af4b:workflow_revision:3 \
  enterprise:0ab99e0c:state_revision:5 \
  enterprise:0ab99e0c:workflow_revision:6 \
  web:2e8f6477:state_revision:3 \
  web:2e8f6477:workflow_revision:4 \
  enterprise:49f98e9e:state_revision:4 \
  enterprise:49f98e9e:workflow_revision:5; do
  IFS=: read -r domain tid scenario position <<< "$item"
  for policy in b3 delta_notes; do
    case_root="runs/method-first-20261015/v5-${domain}-${tid}-${scenario}-state${position}/${scenario}-${policy}"
    test -f "$case_root/update_metrics.json"
    test ! -e "$case_root/reader"
    /data/predator/ly/Mem/.venv/bin/python \
      runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py \
      --data-root "runs/dev-adapted-text-v1/data/$domain" --domain "$domain" \
      --method agentrunbook_r --output-dir "$case_root/reader" --load-memory-dir "$case_root/memory_state" \
      --text-only --controller-disable-thinking --no-reader-enable-thinking \
      --max-completion-tokens 2048 --memory-context-max-tokens 12000 \
      --reader-max-concurrent-requests 1 --prompt-build-max-workers 1 \
      --event-concurrency 1 --event-group-size 2 --event-output-tokens 2048 \
      --event-max-input-tokens 18000 --controller-max-retries 0 --reuse-build-embedding \
      --chunk-memory-context --cache-context-tokenizer --lexical-backfill --reuse-query-embedding
  done
done
