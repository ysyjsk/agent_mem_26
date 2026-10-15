# Query-side experiments closed

The current priority is construction/update cost under a quality constraint. No further search of top-k, ordering or neighbor lines is queued.

Freeze: text-only/adapted; Qwen3.5-9B Reader, output2048, thinking=false, temperature0.6/top-p0.95/top-k20; context12000; chunked context, cached tokenizer, lexical source backfill, neighbor-lines0, exact query-local embedding reuse. Use these equally for all construction variants.

Completed query-only O vs Notes+M on the same saved ten-trajectory memory:

| Metric | Notes+M | +query embedding reuse |
|---|---:|---:|
| Embedding API calls | 24 | 8 |
| Embedding input tokens | 1788 | 596 |
| Exact cache hits | 0 | 16 |
| Internal retrieval duration sum (s; not build wall) | 1.654 | 0.520 |
| Reader input tokens | 82430 | 82430 |
| Complete answers | 8/8 | 8/8 |
| Development correct | 8/8 | 7/8 |

All eight Reader prompts are exactly equal, so the score difference cannot be attributed to changed evidence/prompt inputs. Prior three Notes+M samples were8/8,7/8,7/8. This is retained as sampling variability, not used to launch another query search. Query O on the expanded20 corpus is6/8, using a historical build; no construction saving claimed.

Sources: `results/tables/dev_adapted_first_compare.csv`, `runs/dev-adapted-text-v1/results/{web,enterprise}-rag-notes-{backfill-matched,optO}-v1/`. Original answers/evaluator criteria remain in per_question.jsonl.
