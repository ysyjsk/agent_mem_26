#!/usr/bin/env bash
# Finite, predeclared two-trajectory confirmation; no new model/executor.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
py=/data/predator/ly/Mem/.venv/bin/python
for item in web:2a99f536:3:date enterprise:12c22166:4:quantity; do
  IFS=: read -r domain tid state field <<< "$item"
  prepared="runs/method-first-20261015/v13-confirmation-matched-${domain}"
  if ! test -f "$prepared/preparation_metrics.json"; then
    "$py" -u tools/run_agentrunbook_updates.py \
      --source "runs/method-first-20261015/matched-${domain}-v1/memory_state" \
      --output "$prepared" --prepare-trajectories "$tid"
  fi
  run="v13-confirm-${domain}-${tid}-${field}"
  output="runs/method-first-20261015/$run"
  if test "$domain" = web; then policies=(source_coalesced b3); else policies=(b3 source_coalesced); fi
  for policy in "${policies[@]}"; do
    root="$output/literal_revision-$policy"
    if ! test -f "$root/update_metrics.json"; then
      "$py" -u tools/run_agentrunbook_updates.py --source "$prepared/memory_state" --output "$output" \
        --trajectory-id "$tid" --state-index "$state" --cases literal_revision \
        --revision-file "configs/method_v13_confirm_${domain}_${field}.json" \
        --current-state-evidence --policy-order "$policy"
    fi
    if ! test -f "$root/revision_reader/aggregated_metrics.json"; then
      "$py" -u runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py \
        --data-root "runs/method-first-20261015/retrieval-probe-data/$run" --domain "$domain" \
        --method agentrunbook_r --output-dir "$root/revision_reader" --load-memory-dir "$root/memory_state" \
        --text-only --controller-disable-thinking --no-reader-enable-thinking \
        --max-completion-tokens 2048 --memory-context-max-tokens 12000 \
        --reader-max-concurrent-requests 1 --prompt-build-max-workers 1 \
        --event-concurrency 1 --event-group-size 2 --event-output-tokens 2048 \
        --event-max-input-tokens 18000 --controller-max-retries 0 --reuse-build-embedding \
        --chunk-memory-context --cache-context-tokenizer --lexical-backfill --reuse-query-embedding
    fi
  done
done
