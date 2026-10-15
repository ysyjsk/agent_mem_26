#!/usr/bin/env bash
# Fixed, finite METHOD02 cases. Sequential clients, unchanged shared snapshots.
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
  policies=(b3 ours delta_notes)
  if [ "$scenario" = workflow_revision ]; then policies=(delta_notes ours b3); fi
  /data/predator/ly/Mem/.venv/bin/python -u tools/run_agentrunbook_updates.py \
    --source "runs/method-first-20261015/matched-${domain}-v1/memory_state" \
    --output "runs/method-first-20261015/v5-${domain}-${tid}-${scenario}-state${position}" \
    --trajectory-id "$tid" --state-index "$position" --cases "$scenario" --policy-order "${policies[@]}"
  python tools/report_update_experiment.py --method-root runs/method-first-20261015
done
