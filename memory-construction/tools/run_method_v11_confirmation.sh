#!/usr/bin/env bash
# Finite METHOD03 development confirmation, not a frozen full-scale job.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
for repeat in 1 2 3; do
  for item in web:1ad1af4b:4:title enterprise:0ab99e0c:5:count; do
    IFS=: read -r domain tid position field <<< "$item"
    policies=(b3 delta_guarded)
    if [ "$repeat" = 2 ]; then policies=(delta_guarded b3 ours); fi
    /data/predator/ly/Mem/.venv/bin/python -u tools/run_agentrunbook_updates.py \
      --source "runs/method-first-20261015/matched-${domain}-v1/memory_state" \
      --output "runs/method-first-20261015/v11-r${repeat}-${domain}-${tid}-${field}-replacement" \
      --trajectory-id "$tid" --state-index "$position" --cases literal_revision \
      --revision-file "configs/method_${domain}_${field}_replacement.json" \
      --policy-order "${policies[@]}"
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
  /data/predator/ly/Mem/.venv/bin/python -u tools/run_agentrunbook_updates.py \
    --source "runs/method-first-20261015/matched-${domain}-v1/memory_state" \
    --output "runs/method-first-20261015/v11-${domain}-${tid}-${scenario}-state${position}" \
    --trajectory-id "$tid" --state-index "$position" --cases "$scenario" \
    --policy-order delta_guarded
done
/data/predator/ly/Mem/.venv/bin/python tools/report_update_experiment.py --method-root runs/method-first-20261015
