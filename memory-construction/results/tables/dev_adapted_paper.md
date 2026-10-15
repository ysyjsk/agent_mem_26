| Method | Traj./states | Build→publish s | Build gen calls (failed) | Complete | Correct | Pending | Prompt / Reader wall s |
|---|---:|---:|---:|---:|---:|---:|---:|
| AgentRunbook-R (original packing) | 10/91 | 1170.71 | 124 (32) | 8/8 | 6/8 | 0 | not recorded |
| RAG+Notes (original packing) | 10/91 | 243.53 | 11 (0) | 8/8 | 4/8 | 0 | not recorded |
| Raw RAG (original packing) | 10/91 | 89.06 | 0 (0) | 8/8 | 5/8 | 0 | not recorded |
| AgentRunbook-R + chunks | 10/91 | 1170.71 | 124 (32) | 8/8 | 6/8 | 0 | 70.589 / 42.943 |
| Raw RAG + chunks (J) | 10/91 | 89.06 | 0 (0) | 8/8 | 6/8 | 0 | 34.321 / 60.092 |
| Raw RAG + chunks + tokenizer reuse (L) | 10/91 | 89.06 | 0 (0) | 8/8 | 6/8 | 0 | 6.091 / 49.795 |
| L + lexical source backfill (M) | 10/91 | 89.06 | 0 (0) | 8/8 | 7, 7, 6/8 (repeats) | 0 | 2.491 / 37.9 |
| M + adjacent source lines (N) | 10/91 | 89.06 | 0 (0) | 8/8 | 6/8 | 0 | 2.84 / 35.259 |
| M minus chunk packing | 10/91 | 89.06 | 0 (0) | 8/8 | 5/8 | 0 | 5.708 / 139.768 |
| M, expanded corpus | 20/293 | 283.06 | 0 (0) | 8/8 | 7/8 | 0 | 5.147 / 71.102 |
| RAG+Notes + common fixes + backfill | 10/91 | 243.53 | 11 (0) | 8/8 | 8, 7, 7/8 (repeats) | 0 | 7.208 / 76.035 |
| Notes+M + exact query embedding reuse (O) | 10/91 | 243.53 | 11 (0) | 8/8 | 7/8 | 0 | 3.197 / 57.569 |
| Notes+M minus chunks | 10/91 | 243.53 | 11 (0) | 8/8 | 5/8 | 0 | 3.756 / 41.541 |
| O, expanded corpus | 20/293 | 772.47 | 22 (0) | 8/8 | 6/8 | 0 | 3.499 / 44.65 |
| AgentRunbook-R + common fixes + backfill | 10/91 | 1170.71 | 124 (32) | 8/8 | 7/8 | 0 | 35.222 / 119.215 |
| Strong B3-c1 + backfill | 10/91 | 537.68 | 91 (0) | 8/8 | 6/8 | 0 | 7.065 / 85.535 |
| Ours-dev + backfill | 10/91 | 690.42 | 91 (0) | 8/8 | 6/8 | 0 | 6.789 / 88.985 |
| RAG+Notes + common fixes | 10/91 | 243.53 | 11 (0) | 8/8 | 6/8 | 0 | 3.099 / 31.295 |
| L minus chunk packing | 10/91 | 89.06 | 0 (0) | 8/8 | 5/8 | 0 | 2.229 / 14.217 |
| AgentRunbook-R + common fixes | 10/91 | 1170.71 | 124 (32) | 8/8 | 6/8 | 0 | 20.123 / 40.087 |
| Strong B3-c1 / structured-source adapted | 10/91 | 537.68 | 91 (0) | 8/8 | 4/8 | 0 | 5.44 / 78.729 |
| Ours-dev / structured-source adapted | 10/91 | 690.42 | 91 (0) | 8/8 | 5/8 | 0 | 4.797 / 87.59 |
| L, expanded corpus | 20/293 | 283.06 | 0 (0) | 8/8 | 6/8 | 0 | 6.577 / 37.393 |
| L minus chunks, expanded corpus | 20/293 | 283.06 | 0 (0) | 8/8 | 5/8 | 0 | 2.369 / 18.655 |
| RAG+Notes + backfill, expanded corpus | 20/293 | 772.47 | 22 (0) | 8/8 | 6/8 | 0 | 6.575 / 39.867 |
