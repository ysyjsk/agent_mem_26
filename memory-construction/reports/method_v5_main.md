# Matched eight-case method screen (v5)

Completed paired cases: 8/8. Necessary generated-memory checks: 7/8. Manual review is in method_v5_quality_review.md. Includes the failed candidate/fallback, not successful-only sampling.

| Method | Total LLM tokens | Update publication sum (s) | LLM calls | Actual Embedding vectors |
|---|---:|---:|---:|---:|
| Strong B3 | 143740 | 325.426 | 16 | 36 |
| Event dependency only | 101838 | 248.620 | see raw table | see raw table |
| Source observation + local note update | 22477 | 58.059 | 9 | 24 |

One development pass, not repeat/stability evidence. All cases start independently from the same matched snapshots; load/cache seeding is reported separately and excluded. Publication includes artifact generation, actual Embedding, merge, save and reload checks. A wall sum across cases is not a sequential evolving-memory stream or a sum of concurrent request times.

A source-ID output mistake causes the v5 failure. The v6 repair is a separate run and does not replace this row. Do not freeze or claim overall quality preservation. All eight source edits are additive controlled annotations; replacement/revocation correctness and a deterministic source-append comparator remain necessary. Native/official Judge quality is not claimed.

Per-case data: results/tables/method_v5_paired.csv; full input/output, calls, vectors/tokens, failures, publication and paths: results/tables/method_update_costs.csv. Fixed Reader results are in results/tables/method_v5_reader.csv as they finish.
