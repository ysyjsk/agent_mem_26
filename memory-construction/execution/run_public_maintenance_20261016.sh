#!/usr/bin/env bash
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
PY=/data/predator/ly/Mem/.venv/bin/python
OUT=runs/focused-maintenance-v4/public-repair-20261016
for domain in web enterprise; do
  field=title; [[ "$domain" != enterprise ]] || field=count
  for method in raw_rag rag_notes; do
    suffix=rag-raw-optL; [[ "$method" != rag_notes ]] || suffix=rag-notes
    branch="$OUT/paired10/$domain-$method"
    if [[ ! -f "$branch/update_metrics.json" ]]; then
      "$PY" tools/run_rag_updates.py --source "runs/dev-adapted-text-v1/results/$domain-expanded20-$suffix-v1/memory_state" --output "$branch" --revision-file "configs/method_${domain}_${field}_replacement.json"
    fi
    for query_set in diagnostic normal; do
      questions="runs/focused-maintenance-v4/formal/query-data/$domain/questions.jsonl"
      [[ "$query_set" != normal ]] || questions="runs/dev-adapted-text-v1/data-expanded20/$domain/questions.jsonl"
      if [[ ! -f "$branch/$query_set-reader/aggregated_metrics.json" ]]; then
        "$PY" tools/run_rag_maintenance_reader.py --domain "$domain" --memory-dir "$branch/memory_state" --questions-path "$questions" --output "$branch/$query_set-reader"
      fi
      "$PY" execution/verify_evidence.py --reader-dir "$branch/$query_set-reader"
    done
  done
done
# Six existing predeclared sequence revisions, same five-trajectory/domain
# development histories as B3/Ours v4. Each method carries its own history.
for domain in web enterprise; do
  for round in 1 2 3; do
    for method in raw_rag rag_notes; do
      suffix=rag-raw; [[ "$method" != rag_notes ]] || suffix=rag-notes
      source="runs/dev-adapted-text-v1/results/$domain-$suffix-v1/memory_state"
      [[ "$round" == 1 ]] || source="$OUT/sequence/$domain-r$((round-1))-$method/memory_state"
      branch="$OUT/sequence/$domain-r$round-$method"
      data="runs/focused-maintenance-v4/dev/sequence-final/$domain-r$round"
      if [[ ! -f "$branch/update_metrics.json" ]]; then
        "$PY" tools/run_rag_updates.py --source "$source" --output "$branch" --revision-file "$data/revision.json"
      fi
      if [[ ! -f "$branch/revision_reader/aggregated_metrics.json" ]]; then
        "$PY" tools/run_rag_maintenance_reader.py --domain "$domain" --memory-dir "$branch/memory_state" --questions-path "$data/data/questions.jsonl" --output "$branch/revision_reader"
      fi
      "$PY" execution/verify_evidence.py --reader-dir "$branch/revision_reader"
    done
  done
done
