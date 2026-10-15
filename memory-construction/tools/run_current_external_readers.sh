#!/usr/bin/env bash
# Shared unmodified histories; all cold artifacts reused explicitly.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
py=/data/predator/ly/Mem/.venv/bin/python
for domain in web enterprise; do
  for label in current-common-start raw-rag rag-notes agentrunbook-r; do
    method=agentrunbook_r
    case "$label" in
      current-common-start) source="runs/method-first-20261015/matched-${domain}-v1/memory_state" ;;
      raw-rag) method=rag_query_to_slice; source="runs/dev-adapted-text-v1/results/${domain}-rag-raw-v1/memory_state" ;;
      rag-notes) method=rag_query_to_slice_notes; source="runs/dev-adapted-text-v1/results/${domain}-rag-notes-v1/memory_state" ;;
      agentrunbook-r) source="runs/dev-adapted-text-v1/results/${domain}-agentrunbook-r-v1/memory_state" ;;
    esac
    output="runs/method-first-20261015/external-readers/${domain}-${label}"
    test ! -e "$output"
    "$py" -u runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py \
      --data-root "runs/dev-adapted-text-v1/data/$domain" --domain "$domain" --method "$method" \
      --output-dir "$output" --load-memory-dir "$source" \
      --text-only --controller-disable-thinking --no-reader-enable-thinking \
      --max-completion-tokens 2048 --memory-context-max-tokens 12000 \
      --reader-max-concurrent-requests 1 --prompt-build-max-workers 1 \
      --event-concurrency 1 --event-group-size 2 --event-output-tokens 2048 \
      --event-max-input-tokens 18000 --controller-max-retries 0 --reuse-build-embedding \
      --chunk-memory-context --cache-context-tokenizer --lexical-backfill --reuse-query-embedding
  done
done
"$py" tools/report_method_external_dev.py
