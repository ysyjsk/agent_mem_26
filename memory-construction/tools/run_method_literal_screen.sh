#!/usr/bin/env bash
# Finite mechanism screen, single resident-model client. No Reader search.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
for item in web:1ad1af4b:4:title enterprise:0ab99e0c:5:count; do
  IFS=: read -r domain tid position field <<< "$item"
  policies=(b3 delta_notes)
  if [ "$domain" = enterprise ]; then policies=(delta_notes b3); fi
  /data/predator/ly/Mem/.venv/bin/python -u tools/run_agentrunbook_updates.py \
    --source "runs/method-first-20261015/matched-${domain}-v1/memory_state" \
    --output "runs/method-first-20261015/v6a-${domain}-${tid}-${field}-replacement" \
    --trajectory-id "$tid" --state-index "$position" --cases literal_revision \
    --revision-file "configs/method_${domain}_${field}_replacement.json" \
    --policy-order "${policies[@]}"
done
for item in web:1ad1af4b:state_revision:4 enterprise:0ab99e0c:workflow_revision:6; do
  IFS=: read -r domain tid scenario position <<< "$item"
  /data/predator/ly/Mem/.venv/bin/python -u tools/run_agentrunbook_updates.py \
    --source "runs/method-first-20261015/matched-${domain}-v1/memory_state" \
    --output "runs/method-first-20261015/v6-${domain}-${tid}-${scenario}-source-append" \
    --trajectory-id "$tid" --state-index "$position" --cases "$scenario" \
    --policy-order source_append
done
/data/predator/ly/Mem/.venv/bin/python tools/report_update_experiment.py --method-root runs/method-first-20261015
