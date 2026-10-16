#!/usr/bin/env bash
set -u -o pipefail
ROOT=/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
cd "$ROOT"
PY=/data/predator/ly/Mem/.venv/bin/python
QUEUE_ROOT="$ROOT/execution/main_queue/formal-ablation-20261016"
mkdir -p "$QUEUE_ROOT"
exec > >(tee -a "$QUEUE_ROOT/queue.log") 2>&1
failed=0
run_step() {
  local id="$1" marker="$2"; shift 2
  mkdir -p "$QUEUE_ROOT/$id"
  if [[ -f "$marker" ]]; then echo reused > "$QUEUE_ROOT/$id/status"; echo "$id reused"; return 0; fi
  date --iso-8601=seconds > "$QUEUE_ROOT/$id/started_at"
  "$@" > "$QUEUE_ROOT/$id/stdout.log" 2> "$QUEUE_ROOT/$id/stderr.log"
  local rc=$?
  printf '%s\n' "$rc" > "$QUEUE_ROOT/$id/exit_code"
  date --iso-8601=seconds > "$QUEUE_ROOT/$id/finished_at"
  if [[ $rc -eq 0 ]]; then echo completed > "$QUEUE_ROOT/$id/status"; echo "$id completed"; else echo failed > "$QUEUE_ROOT/$id/status"; echo "$id failed rc=$rc"; failed=1; fi
}
run_step web_update "$ROOT/runs/focused-maintenance-v4/formal/web-ablation-update/literal_revision-source_overlay/update_metrics.json" "$PY" tools/run_agentrunbook_updates.py --source runs/focused-maintenance-v4/formal/matched-web/memory_state --output runs/focused-maintenance-v4/formal/web-ablation-update --trajectory-id 1ad1af4b --state-index 4 --revision-file configs/method_web_title_replacement.json --current-state-evidence --cases literal_revision --policy-order source_overlay delta_guarded
run_step enterprise_update "$ROOT/runs/focused-maintenance-v4/formal/enterprise-ablation-update/literal_revision-source_overlay/update_metrics.json" "$PY" tools/run_agentrunbook_updates.py --source runs/focused-maintenance-v4/formal/matched-enterprise/memory_state --output runs/focused-maintenance-v4/formal/enterprise-ablation-update --trajectory-id 0ab99e0c --state-index 5 --revision-file configs/method_enterprise_count_replacement.json --current-state-evidence --cases literal_revision --policy-order source_overlay delta_guarded
for pair in "web source_overlay" "web delta_guarded" "enterprise source_overlay" "enterprise delta_guarded"; do
  set -- $pair
  domain=$1; policy=$2
  marker="$ROOT/runs/focused-maintenance-v4/formal/${domain}-ablation-update/literal_revision-${policy}/revision_reader/aggregated_metrics.json"
  run_step "${domain}_${policy}_reader" "$marker" "$PY" tools/run_focused_formal_reader.py --domain "$domain" --policy "$policy" --update-root "$ROOT/runs/focused-maintenance-v4/formal/${domain}-ablation-update"
done
run_step report "$ROOT/results/tables/focused-maintenance-v4/formal_ablation_extended.csv" "$PY" tools/report_focused_ablation_formal.py
if [[ $failed -eq 0 ]]; then echo completed > "$QUEUE_ROOT/status"; date --iso-8601=seconds > "$QUEUE_ROOT/finished_at"; exit 0; fi
echo failed > "$QUEUE_ROOT/status"; date --iso-8601=seconds > "$QUEUE_ROOT/finished_at"; exit 1
