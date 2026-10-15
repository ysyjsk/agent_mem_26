#!/usr/bin/env bash
# Run ONLY after run_method_v11_confirmation.sh exits. Fixed configs throughout.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
for item in web:2e8f6477:8:reply enterprise:49f98e9e:5:sort; do
  IFS=: read -r domain tid position field <<< "$item"
  policies=(b3 delta_guarded)
  if [ "$domain" = enterprise ]; then policies=(delta_guarded b3); fi
  /data/predator/ly/Mem/.venv/bin/python -u tools/run_agentrunbook_updates.py \
    --source "runs/method-first-20261015/matched-${domain}-v1/memory_state" \
    --output "runs/method-first-20261015/v11-new-${domain}-${tid}-${field}-replacement" \
    --trajectory-id "$tid" --state-index "$position" --cases literal_revision \
    --revision-file "configs/method_${domain}_${field}_confirmation.json" \
    --policy-order "${policies[@]}"
done
run_reader() {
  local domain="$1" case_root="$2" reader_name="${3:-reader}"
  test -f "$case_root/update_metrics.json"
  test ! -e "$case_root/$reader_name"
  /data/predator/ly/Mem/.venv/bin/python \
    runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py \
    --data-root "runs/dev-adapted-text-v1/data/$domain" --domain "$domain" \
    --method agentrunbook_r --output-dir "$case_root/$reader_name" --load-memory-dir "$case_root/memory_state" \
    --text-only --controller-disable-thinking --no-reader-enable-thinking \
    --max-completion-tokens 2048 --memory-context-max-tokens 12000 \
    --reader-max-concurrent-requests 1 --prompt-build-max-workers 1 \
    --event-concurrency 1 --event-group-size 2 --event-output-tokens 2048 \
    --event-max-input-tokens 18000 --controller-max-retries 0 --reuse-build-embedding \
    --chunk-memory-context --cache-context-tokenizer --lexical-backfill --reuse-query-embedding
}
# Exactly one resampling check for the two v5 differences; no parameter sweep.
for item in web:1ad1af4b:3 enterprise:49f98e9e:5; do
  IFS=: read -r domain tid position <<< "$item"
  for policy in delta_notes b3; do
    run_reader "$domain" "runs/method-first-20261015/v5-${domain}-${tid}-workflow_revision-state${position}/workflow_revision-${policy}" reader_repeat1
  done
done
# Paired Reader on first repetition, not cherry-picked best generated outputs.
for item in web:1ad1af4b:title enterprise:0ab99e0c:count; do
  IFS=: read -r domain tid field <<< "$item"
  for policy in b3 delta_guarded; do
    run_reader "$domain" "runs/method-first-20261015/v11-r1-${domain}-${tid}-${field}-replacement/literal_revision-${policy}"
  done
done
for item in web:2e8f6477:reply enterprise:49f98e9e:sort; do
  IFS=: read -r domain tid field <<< "$item"
  for policy in b3 delta_guarded; do
    run_reader "$domain" "runs/method-first-20261015/v11-new-${domain}-${tid}-${field}-replacement/literal_revision-${policy}"
  done
done
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
  run_reader "$domain" "runs/method-first-20261015/v11-${domain}-${tid}-${scenario}-state${position}/${scenario}-delta_guarded"
done
/data/predator/ly/Mem/.venv/bin/python tools/report_update_experiment.py --method-root runs/method-first-20261015
