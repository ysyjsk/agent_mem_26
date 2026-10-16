#!/usr/bin/env bash
# Bounded, sequential query repair. No construction or update work is repeated.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
PY=/data/predator/ly/Mem/.venv/bin/python
OUT=runs/focused-maintenance-v4/repair-20261016/pair-v1
for pair in 'web b3' 'web source_coalesced' 'enterprise source_coalesced' 'enterprise b3'; do
  read -r domain policy <<< "$pair"
  if [[ ! -f "$OUT/$domain-$policy/aggregated_metrics.json" ]]; then
    "$PY" tools/run_focused_formal_reader.py --domain "$domain" --policy "$policy" --output-root "$OUT"
  fi
  "$PY" execution/verify_evidence.py --reader-dir "$OUT/$domain-$policy"
done
