#!/usr/bin/env bash
# Start after the current MemForest domain stage, not concurrently with it.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
py=/data/predator/ly/Mem/.venv/bin/python
for item in web:1ad1af4b:4:title:replacement enterprise:49f98e9e:5:sort:confirmation; do
  IFS=: read -r domain tid position field config_suffix <<< "$item"
  output="runs/method-first-20261015/v12-${domain}-${tid}-${field}-replacement"
  test ! -e "$output"
  "$py" -u tools/run_agentrunbook_updates.py \
    --source "runs/method-first-20261015/matched-${domain}-v1/memory_state" \
    --output "$output" --trajectory-id "$tid" --state-index "$position" --cases literal_revision \
    --revision-file "configs/method_${domain}_${field}_${config_suffix}.json" \
    --current-state-evidence --policy-order source_overlay b3 delta_guarded
done
"$py" tools/prepare_method_retrieval_probes.py
run_reader() {
  local domain="$1" root="$2" data="$3" name="$4"
  if test -f "$root/$name/aggregated_metrics.json"; then return; fi
  test ! -e "$root/$name"
  "$py" -u runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py \
    --data-root "$data" --domain "$domain" --method agentrunbook_r \
    --output-dir "$root/$name" --load-memory-dir "$root/memory_state" \
    --text-only --controller-disable-thinking --no-reader-enable-thinking \
    --max-completion-tokens 2048 --memory-context-max-tokens 12000 \
    --reader-max-concurrent-requests 1 --prompt-build-max-workers 1 \
    --event-concurrency 1 --event-group-size 2 --event-output-tokens 2048 \
    --event-max-input-tokens 18000 --controller-max-retries 0 --reuse-build-embedding \
    --chunk-memory-context --cache-context-tokenizer --lexical-backfill --reuse-query-embedding
}
for item in web:1ad1af4b:title enterprise:49f98e9e:sort web:2e8f6477:reply enterprise:0ab99e0c:count; do
  IFS=: read -r domain tid field <<< "$item"
  run="v12-${domain}-${tid}-${field}-replacement"
  for policy in source_overlay b3 delta_guarded; do
    root="runs/method-first-20261015/$run/literal_revision-$policy"
    run_reader "$domain" "$root" "runs/dev-adapted-text-v1/data/$domain" reader
    run_reader "$domain" "$root" "runs/method-first-20261015/retrieval-probe-data/$run" revision_reader
  done
done
"$py" tools/report_method_external_dev.py
