# PAPER03 local text-only/adapted main comparison

This table freezes measured rows from the existing 10-trajectory, 91-state, eight-question development corpus. It is not native multimodal Small and has no verified external Judge. Build wall time ends at persisted/reload-verified memory publication; prompt/retrieval and Reader time are reported separately.

| Method | Build→publish s | Build LLM calls (failed) | Build input/output tokens | Embedding calls/input tokens | Complete | Correct | Pending | Prompt / Reader wall s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AgentRunbook-R | 1170.71 | 124 (32) | 761072/18450 | 40/370732 | 8/8 | 6/8 | 0 | n/a / n/a |
| RAG+Notes | 243.53 | 11 (0) | 19479/4672 | 30/357467 | 8/8 | 4/8 | 0 | n/a / n/a |
| Raw RAG | 89.06 | 0 (0) | 0/0 | 10/354007 | 8/8 | 5/8 | 0 | n/a / n/a |
| RAG+Notes + backfill | 243.53 | 11 (0) | 19479/4672 | 30/357467 | 8/8 | 8/8 | 0 | 7.208 / 76.035 |
| Strong B3 | 537.68 | 91 (0) | 181191/9984 | 10/139245 | 8/8 | 6/8 | 0 | 7.065 / 85.535 |
| Ours | 690.42 | 91 (0) | 181191/10730 | 10/140053 | 8/8 | 6/8 | 0 | 6.789 / 88.985 |

## Interpretation

The table keeps AgentRunbook-R/RAG baselines separate from the matched structured-source Strong B3/Ours mechanism pair. Strong B3 and Ours use the same adapted representation, Reader, model service, budgets and common lexical backfill; they differ only in their construction/update mechanism and independent caches. The existing measurements show both at 6/8 correct with 8/8 complete answers, while B3 has lower cold-build wall time (537.68s vs 690.42s) and identical build-controller call/input-token counts (91 / 181,191), so this table does not support a claim that Ours reduces expensive cold-build model work.

RAG+Notes + backfill reaches 8/8 in the recorded stochastic Reader run at 243.53s construction, but it is a query/retrieval baseline rather than a matched mechanism comparison. All rows are adapted text-only development evidence; failures and the unavailable native/Judge route remain outside this table.
