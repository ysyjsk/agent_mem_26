# Repaired public development maintenance comparison

Two shared 10-trajectory histories; one revision/domain; four exposed diagnostic and eight fixed normal questions. Original retrieval designs retained; common text-only Reader/chunk/backfill settings. Update measured once per branch and reused for both question sets. Not full Small or independent confirmation.

| Method | Update publish sum (s) | Update LLM tokens | Update + all fixed queries tokens | Diagnostic | Normal |
|---|---:|---:|---:|---:|---:|
| raw_rag | 3.589 | 0 | 129006 | 1/4 | 7/8 |
| rag_notes | 3.371 | 0 | 125072 | 1/4 | 7/8 |
| b3 | 42.859 | 23494 | 171529 | 3/4 | 7/8 |
| source_coalesced | 4.241 | 0 | 148689 | 4/4 | 6/8 |
| source_only | 3.745 | 0 | 152412 | 3/4 | 7/8 |
| source_overlay | 4.171 | 0 | 141492 | 4/4 | 7/8 |

No equivalence claim on this small exposed set. Literal source revisions do not change the existing note-generation request; exact request reuse is legal. Workflow-intent updates are separately predeclared for the formal matrix.
