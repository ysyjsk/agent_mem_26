# Full-Small recovery diagnostics (intermediate)

Generated from the registered receipts, failure JSON, `expansion_metrics.jsonl`,
and the per-memory `model_calls.jsonl` ledgers. This is an intermediate record,
not a completion claim. The active v9 recovery job remains the authoritative
producer for enterprise AgentRunbook.

## State at 2026-10-16 22:57 +08:00

| partition | published histories | expansion rows | known LLM tokens | LLM calls | vectors | unknown usage calls | status |
|---|---:|---:|---:|---:|---:|---:|---|
| web AgentRunbook | 100/100 | reused | historical/reference | — | — | — | complete and reusable |
| web Raw RAG | 100/100 | reused | 0 | 0 | historical | 0 | complete and reusable |
| web RAG+Notes | 100/100 | reused | historical/reference | — | — | — | complete and reusable |
| enterprise Raw RAG | 100/100 | 90 | 0 | 0 | 3,146 | 0 | complete and reusable |
| enterprise AgentRunbook | 54/100 | 44 | 12,119,038 | 1,157 | 3,328 | 313 | v9 still running; latest trajectory 45a55aa7: 316.25 s, 19 calls, 281,355 known tokens, 68 vectors, 0 unknown |
| enterprise RAG+Notes | 11/100 | 1 | 10,780 | 1 | 51 | 0 | failed at 02dad10c; recovery pending |

The AgentRunbook row includes the current partial output and therefore is not
eligible for runtime freeze until the official 100-trajectory marker validates.
The unknown-usage totals are not zero-filled; they include failed/retried
requests whose server usage was unavailable.

## Failure classification

### 02dad10c

- AgentRunbook has two preserved CUDA OOM failures: 815.46 s and 860.55 s.
- The later deterministic-fallback ledger row published 202 histories' worth
  of vectors for this trajectory with 248 calls and 248 unknown usages, but
  zero known tokens. It is retained as a recoverable artifact, not semantic
  equivalence to successful model-generated Notes.
- RAG+Notes has a separate OOM failure at 0.231 s and no completed expansion
  row. Its Notes partition remains incomplete and must be rerun once the GPU
  owner reaches a terminal boundary.

### 054c4ed2

- AgentRunbook has 38 ledger records: 30 event-extraction, 7 event-group and
  1 note-generation. The event-group and event-extraction attempts report
  `No module named 'workflow_memory'`; 15 retries and 15 fallbacks were
  recorded, followed by a deterministic note fallback.
- Its expansion row is 16.78 s, 38 calls, 32 vectors, zero known tokens and
  38 unknown usages. This is a service/import failure, not a normal semantic
  construction. It remains charged and requires a targeted repair or explicit
  fallback disclosure; it must not be counted as successful generated-memory
  quality.

## Recovery-entry verification

`execution/recover_full_small_after_failure.py` now: (i) discovers all failed
expansion roots by default, (ii) accepts repeated `--failed-unit`, (iii) reuses
validated original/recovery receipts or valid markers without another model
call, (iv) retries existing failed roots while preserving old receipts, (v)
continues independent eligible branches, and (vi) emits `partial` and exits
nonzero whenever any plan step remains failed or pending. `--dry-run` performs
the branch decision without invoking model services.

Targeted checks completed without model calls:

```text
python -m py_compile execution/recover_full_small_after_failure.py
python execution/recover_full_small_after_failure.py --dry-run \
  --failed-unit expand-enterprise-agentrunbook \
  --failed-unit expand-enterprise-rag_notes
/data/predator/ly/Mem/.venv/bin/python -m pytest -q \
  tests/test_full_small_queue.py tests/test_full_small_report.py \
  tests/test_execution_evidence.py
27 passed
```

The dry-run selected the two failed roots, reused five completed independent
units, and left all dependents pending; it did not start a model request.

## Next executable boundary

The healthy v9 job is preserved. After it reaches a terminal state, the
detached continuation will invoke this repaired entrypoint. It will reuse a
validated AgentRunbook marker if v9 finished it, retry the incomplete
enterprise RAG+Notes expansion, then run only newly unblocked preparation,
freeze, initial-query, maintenance, repeat/sequence and report units. B remains
frozen but must wait for all six initial libraries and the runtime-freeze gate.
