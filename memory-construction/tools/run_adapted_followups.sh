#!/usr/bin/env bash
# Finite, explicit matched query-only followups; no service launches or rebuilds.
set -euo pipefail
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction

run_query() {
  local domain=$1 method=$2 build_suffix=$3 output_suffix=$4 data_variant=$5
  shift 5
  local output="runs/dev-adapted-text-v1/results/$domain-$output_suffix"
  if [ -e "$output" ]; then
    printf 'Refusing to overwrite %s\n' "$output" >&2
    return 1
  fi
  /data/predator/ly/Mem/.venv/bin/python \
    runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py \
    --data-root "runs/dev-adapted-text-v1/$data_variant/$domain" --domain "$domain" --tier small \
    --method "$method" --output-dir "$output" \
    --reader-max-concurrent-requests 1 --max-completion-tokens 2048 \
    --memory-context-max-tokens 12000 --no-reader-enable-thinking --text-only \
    --controller-disable-thinking --prompt-build-max-workers 1 \
    --load-memory-dir "runs/dev-adapted-text-v1/results/$domain-$build_suffix/memory_state" "$@"
}

# Single-factor source-backfill screening on the already built raw memory.
for domain in enterprise web; do
  run_query "$domain" rag_query_to_slice rag-raw-v1 rag-raw-optM-matched-v1 data \
    --chunk-memory-context --cache-context-tokenizer --lexical-backfill
done

# Only the winner is repeated; the baseline L score is already measured 6/8.
winner=$(/data/predator/ly/Mem/.venv/bin/python - <<'PY'
import json
from pathlib import Path
rows=[]
for d in ('enterprise','web'):
    rows += [json.loads(l) for l in Path(f'runs/dev-adapted-text-v1/results/{d}-rag-raw-optM-matched-v1/per_question.jsonl').read_text().splitlines()]
print('M' if len(rows)==8 and sum(r.get('score_bool') is True for r in rows)>6 else 'L')
PY
)
winner_flags=()
if [ "$winner" = M ]; then winner_flags=(--lexical-backfill); fi
printf 'Measured winner selected for repeats: %s\n' "$winner"
for repetition in 2 3; do
  for domain in enterprise web; do
    run_query "$domain" rag_query_to_slice rag-raw-v1 "rag-raw-opt$winner-r$repetition-matched-v1" data \
      --chunk-memory-context --cache-context-tokenizer "${winner_flags[@]}"
  done
done
for domain in enterprise web; do
  run_query "$domain" rag_query_to_slice rag-raw-v1 rag-raw-nochunks-cache-matched-v1 data \
    --cache-context-tokenizer
  run_query "$domain" rag_query_to_slice_notes rag-notes-v1 rag-notes-chunks-cache-matched-v1 data \
    --chunk-memory-context --cache-context-tokenizer
  run_query "$domain" agentrunbook_r agentrunbook-r-v1 agentrunbook-r-chunks-cache-matched-v1 data \
    --chunk-memory-context --cache-context-tokenizer
  run_query "$domain" rag_query_to_slice expanded20-rag-raw-optL-v1 expanded20-rag-raw-nochunks-v1 data-expanded20 \
    --cache-context-tokenizer
done
if [ "$winner" = M ]; then
  for domain in enterprise web; do
    run_query "$domain" rag_query_to_slice expanded20-rag-raw-optL-v1 expanded20-rag-raw-optM-v1 data-expanded20 \
      --chunk-memory-context --cache-context-tokenizer --lexical-backfill
    run_query "$domain" rag_query_to_slice rag-raw-v1 rag-raw-optM-nochunks-v1 data \
      --cache-context-tokenizer --lexical-backfill
    run_query "$domain" rag_query_to_slice_notes rag-notes-v1 rag-notes-backfill-matched-v1 data \
      --chunk-memory-context --cache-context-tokenizer --lexical-backfill
    run_query "$domain" agentrunbook_r agentrunbook-r-v1 agentrunbook-r-backfill-matched-v1 data \
      --chunk-memory-context --cache-context-tokenizer --lexical-backfill
    run_query "$domain" workflow_b3 workflow-b3-v2 workflow-b3-backfill-matched-v1 data \
      --chunk-memory-context --cache-context-tokenizer --lexical-backfill
    run_query "$domain" workflow_ours workflow-ours-v2 workflow-ours-backfill-matched-v1 data \
      --chunk-memory-context --cache-context-tokenizer --lexical-backfill
  done
fi
/data/predator/ly/Mem/.venv/bin/python tools/report_local_adapted.py
