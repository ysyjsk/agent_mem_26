#!/usr/bin/env bash
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
py=/data/predator/ly/Mem/.venv/bin/python
for item in web:1ad1af4b:5:description-rejection:description_rejection enterprise:0ab99e0c:6:selection-mismatch:selection_mismatch; do
  IFS=: read -r domain tid position label config_name <<< "$item"
  run="v12-new-${domain}-${tid}-${label}"
  output="runs/method-first-20261015/$run"
  test ! -e "$output"
  "$py" -u tools/run_agentrunbook_updates.py \
    --source "runs/method-first-20261015/matched-${domain}-v1/memory_state" \
    --output "$output" --trajectory-id "$tid" --state-index "$position" --cases literal_revision \
    --revision-file "configs/method_${domain}_${config_name}.json" \
    --current-state-evidence --policy-order delta_guarded source_overlay b3
  for policy in delta_guarded source_overlay b3; do
    root="$output/literal_revision-$policy"
    "$py" -u runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py \
      --data-root "runs/method-first-20261015/retrieval-probe-data/$run" --domain "$domain" \
      --method agentrunbook_r --output-dir "$root/revision_reader" --load-memory-dir "$root/memory_state" \
      --text-only --controller-disable-thinking --no-reader-enable-thinking \
      --max-completion-tokens 2048 --memory-context-max-tokens 12000 \
      --reader-max-concurrent-requests 1 --prompt-build-max-workers 1 \
      --event-concurrency 1 --event-group-size 2 --event-output-tokens 2048 \
      --event-max-input-tokens 18000 --controller-max-retries 0 --reuse-build-embedding \
      --chunk-memory-context --cache-context-tokenizer --lexical-backfill --reuse-query-embedding
  done
done
"$py" tools/report_method_external_dev.py
