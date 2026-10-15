#!/usr/bin/env bash
# Frozen normal retrieval/Reader. Never overwrite an existing run.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
for item in web:2e8f6477:reply enterprise:0ab99e0c:count; do
  IFS=: read -r domain tid field <<< "$item"
  for policy in b3 delta_guarded source_overlay; do
    root="runs/method-first-20261015/v12-${domain}-${tid}-${field}-replacement/literal_revision-${policy}"
    test -f "$root/update_metrics.json"
    if test -f "$root/reader/aggregated_metrics.json"; then continue; fi
    test ! -e "$root/reader"
    /data/predator/ly/Mem/.venv/bin/python -u \
      runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py \
      --data-root "runs/dev-adapted-text-v1/data/$domain" --domain "$domain" \
      --method agentrunbook_r --output-dir "$root/reader" --load-memory-dir "$root/memory_state" \
      --text-only --controller-disable-thinking --no-reader-enable-thinking \
      --max-completion-tokens 2048 --memory-context-max-tokens 12000 \
      --reader-max-concurrent-requests 1 --prompt-build-max-workers 1 \
      --event-concurrency 1 --event-group-size 2 --event-output-tokens 2048 \
      --event-max-input-tokens 18000 --controller-max-retries 0 --reuse-build-embedding \
      --chunk-memory-context --cache-context-tokenizer --lexical-backfill --reuse-query-embedding
  done
done
