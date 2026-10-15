# Current method branches and early external development comparison

Text-only/adapted, not native Small, no external Judge. Frozen questions and full shared domain histories. Tables intentionally separate historical cold construction, new maintenance and query. Current Ours is v12 overlay/edit, NOT the old workflow-core Ours. Matched starting snapshots combine inherited history with refreshed selected partitions: their full cold cost is not newly measured here.

## Current branch comparison

| Case | Policy | Update LLM in/out | Calls | Publish s | Embedding tokens/vectors | Fixed correct/all | Revision correct/all (truncated) | Derived lexical check |
|---|---|---:|---:|---:|---:|---:|---|---|
| 0ab99e0c | b3 | 14431/406 | 1 | 18.226 | 5183/3 | 4/4 | 2/2 (0) | False |
| 0ab99e0c | delta_guarded | 1083/162 | 1 | 6.530 | 5194/3 | 4/4 | 2/2 (0) | True |
| 0ab99e0c | source_overlay | 0/0 | 0 | 1.536 | 5205/3 | 4/4 | 2/2 (0) | False |
| 49f98e9e | b3 | 13268/287 | 1 | 25.709 | 4539/3 | 4/4 | 2/2 (0) | True |
| 49f98e9e | delta_guarded | 633/41 | 1 | 4.244 | 4556/3 | 3/4 | 2/2 (0) | True |
| 49f98e9e | source_overlay | 0/0 | 0 | 1.728 | 4637/3 | 4/4 | 2/2 (0) | False |
| 1ad1af4b | b3 | 7986/647 | 2 | 40.140 | 8399/7 | 3/4 | 2/2 (0) | True |
| 1ad1af4b | delta_guarded | 1633/360 | 2 | 25.172 | 8215/5 | 3/4 | 2/2 (0) | True |
| 1ad1af4b | source_overlay | 0/0 | 0 | 2.466 | 8290/5 | 3/4 | 2/2 (0) | False |
| 2e8f6477 | b3 | 28830/621 | 2 | 27.975 | 4930/5 | 3/4 | 1/2 (1) | False |
| 2e8f6477 | delta_guarded | 1634/227 | 2 | 8.422 | 4800/3 | 3/4 | 2/2 (0) | True |
| 2e8f6477 | source_overlay | 0/0 | 0 | 1.394 | 4909/3 | 3/4 | 2/2 (0) | True |

Regex failure remains visible; old strings in explicitly superseded interpretations need version-aware semantic review. Complete response is not correctness. Fixed QA does not by itself validate the corrected value. All independent snapshots/repeated questions are reported as such, not independent statistical samples.

## External development measurements

| Method / scope | Measurement | Cold publish s | Build LLM in/out | Calls (failed) | QA | Query / Reader s |
|---|---|---:|---:|---:|---:|---:|
| Raw RAG / 10 complete trajectories / 8 fixed questions | historical build and historical query; NOT rerun this round | 89.06 | 0/0 | 0 (0) | 7/8 | 2.491 / 37.9 |
| RAG+Notes / 10 complete trajectories / 8 fixed questions | historical build and historical query; NOT rerun this round | 243.53 | 19479/4672 | 11 (0) | 7/8 | 3.197 / 57.569 |
| AgentRunbook-R / 10 complete trajectories / 8 fixed questions | historical build and historical query; NOT rerun this round | 1170.71 | 761072/18450 | 124 (32) | 7/8 | 35.222 / 119.215 |

Raw paths, usage gaps and configuration caveats are in the companion CSV files. Raw RAG/RAG+Notes historical results already make low cold cost a relevant constraint; no claim of current-method cold-build superiority. MemForest partial artifacts are preserved but its adaptation/expansion is deferred by focused-method-v3, not a selection or freezing prerequisite.

## Decision (provisional)

Source_overlay is the provisional cheap default for four measured literal-correction cases; delta_guarded remains only the semantic-edit comparator, not a mandatory default step. Completed normal regression: B3/overlay14/16, edit13/16. Modified-fact QA: overlay/edit8/8; B3 seven correct and one truncated/unscored, not full-scored accuracy. Four updates: B366476tokens/112.050s, edit5773/44.369s, overlay0/7.124s. Do not freeze from these: v13 actual sequential maintenance tests current-evidence coalescing, followed by preselected invalidated-conclusion cases. No new external adapters and no query parameter sweep.
