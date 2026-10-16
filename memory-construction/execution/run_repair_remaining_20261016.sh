#!/usr/bin/env bash
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
PY=/data/predator/ly/Mem/.venv/bin/python
BASE=runs/focused-maintenance-v4
for domain in web enterprise; do
  for policy in source_only source_overlay delta_guarded; do
    branch="$BASE/formal/$domain-update"
    [[ "$policy" == source_only ]] || branch="$BASE/formal/$domain-ablation-update"
    out="$BASE/repair-20261016/remaining-v1"
    if [[ ! -f "$out/$domain-$policy/aggregated_metrics.json" ]]; then
      "$PY" tools/run_focused_formal_reader.py --domain "$domain" --policy "$policy" --update-root "$branch" --output-root "$out"
    fi
    "$PY" execution/verify_evidence.py --reader-dir "$out/$domain-$policy"
  done
done
# The original eight normal development questions, without internal state IDs.
# All have already been fixed and exposed; no independent-confirmation claim.
for domain in web enterprise; do
  for policy in b3 source_coalesced source_only source_overlay; do
    branch="$BASE/formal/$domain-update"
    [[ "$policy" != source_overlay ]] || branch="$BASE/formal/$domain-ablation-update"
    out="$BASE/repair-20261016/normal-v1"
    if [[ ! -f "$out/$domain-$policy/aggregated_metrics.json" ]]; then
      "$PY" tools/run_focused_formal_reader.py --domain "$domain" --policy "$policy" --update-root "$branch" --output-root "$out" --questions-path "runs/dev-adapted-text-v1/data-expanded20/$domain/questions.jsonl"
    fi
    "$PY" execution/verify_evidence.py --reader-dir "$out/$domain-$policy"
  done
done
