# Current method branches and early external development comparison

Text-only/adapted, not native Small, no external Judge. Frozen questions and full shared domain histories. Tables intentionally separate historical cold construction, new maintenance and query. Current Ours is v12 overlay/edit, NOT the old workflow-core Ours. Matched starting snapshots combine inherited history with refreshed selected partitions: their full cold cost is not newly measured here.

## Current branch comparison

| Case | Policy | Update LLM in/out | Calls | Publish s | Embedding tokens/vectors | Fixed QA | Full-retrieval revision QA | Derived lexical check |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 0ab99e0c | b3 | 14431/406 | 1 | 18.226 | 5183/3 | 4/4 | pending/? | False |
| 0ab99e0c | delta_guarded | 1083/162 | 1 | 6.530 | 5194/3 | 4/4 | pending/? | True |
| 0ab99e0c | source_overlay | 0/0 | 0 | 1.536 | 5205/3 | 4/4 | pending/? | False |
| 2e8f6477 | b3 | 28830/621 | 2 | 27.975 | 4930/5 | 3/4 | pending/? | False |
| 2e8f6477 | delta_guarded | 1634/227 | 2 | 8.422 | 4800/3 | 3/4 | pending/? | True |
| 2e8f6477 | source_overlay | 0/0 | 0 | 1.394 | 4909/3 | 3/4 | pending/? | True |

Regex failure remains visible; old strings in explicitly superseded interpretations need version-aware semantic review. Complete response is not correctness. Fixed QA does not by itself validate the corrected value. All independent snapshots/repeated questions are reported as such, not independent statistical samples.

## External development measurements

| Method / scope | Measurement | Cold publish s | Build LLM in/out | Calls (failed) | QA | Query / Reader s |
|---|---|---:|---:|---:|---:|---:|
| Raw RAG / 10 complete trajectories / 8 fixed questions | historical build and historical query; NOT rerun this round | 89.06 | 0/0 | 0 (0) | 7/8 | 2.491 / 37.9 |
| RAG+Notes / 10 complete trajectories / 8 fixed questions | historical build and historical query; NOT rerun this round | 243.53 | 19479/4672 | 11 (0) | 7/8 | 3.197 / 57.569 |
| AgentRunbook-R / 10 complete trajectories / 8 fixed questions | historical build and historical query; NOT rerun this round | 1170.71 | 761072/18450 | 124 (32) | 7/8 | 35.222 / 119.215 |

Raw paths, usage gaps and configuration caveats are in the companion CSV files. Raw RAG/RAG+Notes historical results already make low cold cost a relevant constraint; no claim of current-method cold-build superiority. MemForest is not removed if incomplete: inspect its model_calls/build_progress and finish the shared library.

## Decision (provisional)

Retain source_overlay as the cheap candidate and delta_guarded as the semantic-edit comparator. The first two normal-regression cases tie all three branches (7/8 each, 24/24 complete). Do not freeze from these: complete other two corrections, full-retrieval changed-value probes, preselected invalidated-conclusion cases, external shared-library quality and actual sequential maintenance before selecting. No query parameter sweep.
