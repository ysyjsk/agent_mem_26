#!/usr/bin/env bash
# Pass1 is the existing v13 sequence round1; passes2/3 reset to common originals.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
py=/data/predator/ly/Mem/.venv/bin/python
for pass in 2 3; do
  for item in web:1ad1af4b:4:title enterprise:0ab99e0c:5:count; do
    IFS=: read -r domain tid state field <<< "$item"
    output="runs/method-first-20261015/v13-repeat${pass}-${domain}-${tid}-${field}"
    if test "$pass" = 2; then policies=(source_coalesced b3); else policies=(b3 source_coalesced); fi
    for policy in "${policies[@]}"; do
      if test -f "$output/literal_revision-$policy/update_metrics.json"; then continue; fi
      "$py" -u tools/run_agentrunbook_updates.py \
        --source "runs/method-first-20261015/matched-${domain}-v1/memory_state" \
        --output "$output" --trajectory-id "$tid" --state-index "$state" --cases literal_revision \
        --revision-file "configs/method_${domain}_${field}_replacement.json" \
        --current-state-evidence --policy-order "$policy"
    done
  done
done
