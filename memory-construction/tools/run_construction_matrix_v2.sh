#!/usr/bin/env bash
# Finite sequential live matrix. No service changes and no parallel GPU clients.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
for variant in baseline joint embed combined; do
  group=1
  extra=()
  if [ "$variant" = joint ] || [ "$variant" = combined ]; then group=2; fi
  if [ "$variant" = embed ] || [ "$variant" = combined ]; then extra+=(--reuse-build-embedding); fi
  for domain in web enterprise; do
    output="runs/construction-pair-v2/full10-${domain}-${variant}"
    test ! -e "$output" || { printf 'Refusing overwrite: %s\n' "$output" >&2; exit 2; }
    /data/predator/ly/Mem/.venv/bin/python \
      runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py \
      --data-root "runs/dev-adapted-text-v1/data/$domain" --domain "$domain" \
      --method agentrunbook_r --output-dir "$output" \
      --text-only --controller-disable-thinking --no-reader-enable-thinking \
      --max-completion-tokens 2048 --memory-context-max-tokens 12000 \
      --reader-max-concurrent-requests 1 --prompt-build-max-workers 1 \
      --event-concurrency 1 --event-group-size "$group" --event-output-tokens 2048 \
      --event-max-input-tokens 18000 --controller-max-retries 0 \
      --record-full-requests --save-memory --chunk-memory-context \
      --cache-context-tokenizer --lexical-backfill --reuse-query-embedding "${extra[@]}"
  done
  /data/predator/ly/Mem/.venv/bin/python tools/report_construction_pair.py --run-root runs/construction-pair-v2
done
