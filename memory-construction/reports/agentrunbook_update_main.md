# AgentRunbook-R adapted local multi-trajectory updates

All cases start from independent copies of the same combined web/enterprise starting snapshot; ‘combined’ identifies the source artifact, not a claim that it is the quality-optimal configuration. B3 and Ours preserve the same legal request/vector caches, while Fresh/B0 clears the cloned touched-partition build caches and reconstructs that trajectory partition. Model load/cache seeding is excluded from update-to-queryable wall time, while save/reload publication is included. The eight revision cases and two same-trajectory growth cases remain distinct workloads.

The four trajectories were selected by domain, length and page family: web `1ad1af4b` (8 states, forum form) and `2e8f6477` (11 states, forum thread); enterprise `0ab99e0c` (16 states, ServiceNow change-request flow) and `49f98e9e` (15 states, ServiceNow asset flow). State/workflow patches cover interior and pair-boundary positions.

| Domain | Trajectory | Case | Policy | Pass | Publish s | LLM calls / input/output tokens | Events | Notes | Embedding vectors | Exact reused events | Quality |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| enterprise | `0ab99e0c` | state_revision | b3 | primary | 17.51 | 2 / 20178/369 | 2 | 0 | 2 |  | pass |
| enterprise | `0ab99e0c` | state_revision | fresh | primary | 245.13 | 9 / 110171/3375 | 15 | 2 | 32 |  | pass |
| enterprise | `0ab99e0c` | state_revision | ours | primary | 17.22 | 2 / 20178/381 | 2 | 0 | 2 | 13 | pass |
| enterprise | `0ab99e0c` | trajectory_growth | b3 | primary | 168.99 | 9 / 114484/3366 | 16 | 2 | 19 |  | pass |
| enterprise | `0ab99e0c` | trajectory_growth | ours | primary | 129.85 | 9 / 114484/3232 | 16 | 2 | 19 | 0 | pass |
| enterprise | `0ab99e0c` | workflow_revision | b3 | primary | 34.34 | 3 / 23125/953 | 2 | 2 | 4 |  | pass |
| enterprise | `0ab99e0c` | workflow_revision | fresh | primary | 237.30 | 9 / 110242/3219 | 15 | 2 | 32 |  | pass |
| enterprise | `0ab99e0c` | workflow_revision | ours | primary | 34.38 | 3 / 23125/971 | 2 | 2 | 4 | 13 | pass |
| enterprise | `49f98e9e` | state_revision | b3 | primary | 14.63 | 2 / 18835/284 | 2 | 0 | 2 |  | pass |
| enterprise | `49f98e9e` | state_revision | fresh | primary | 166.73 | 8 / 93407/2564 | 14 | 2 | 30 |  | pass |
| enterprise | `49f98e9e` | state_revision | ours | primary | 14.64 | 2 / 18835/242 | 2 | 0 | 2 | 12 | pass |
| enterprise | `49f98e9e` | workflow_revision | b3 | primary | 46.73 | 3 / 21274/709 | 2 | 2 | 4 |  | pass |
| enterprise | `49f98e9e` | workflow_revision | fresh | primary | 192.20 | 8 / 93457/2524 | 14 | 2 | 30 |  | pass |
| enterprise | `49f98e9e` | workflow_revision | ours | primary | 49.56 | 3 / 21274/723 | 2 | 2 | 4 | 12 | pass |
| web | `1ad1af4b` | state_revision | b3 | primary | 44.93 | 2 / 8016/764 | 4 | 0 | 7 |  | pass |
| web | `1ad1af4b` | state_revision | fresh | primary | 58.96 | 5 / 29611/1555 | 7 | 2 | 16 |  | pass |
| web | `1ad1af4b` | state_revision | ours | primary | 19.80 | 1 / 3928/376 | 2 | 0 | 5 | 5 | pass |
| web | `1ad1af4b` | trajectory_growth | b3 | primary | 149.11 | 6 / 31600/2338 | 8 | 2 | 12 |  | pass |
| web | `1ad1af4b` | trajectory_growth | ours | primary | 109.92 | 5 / 30996/1743 | 8 | 2 | 12 | 0 | pass |
| web | `1ad1af4b` | workflow_revision | b3 | primary | 20.75 | 2 / 5264/691 | 2 | 2 | 4 |  | pass |
| web | `1ad1af4b` | workflow_revision | fresh | primary | 61.15 | 5 / 29597/1637 | 7 | 2 | 16 |  | pass |
| web | `1ad1af4b` | workflow_revision | ours | primary | 21.92 | 2 / 5264/733 | 2 | 2 | 4 | 5 | pass |
| web | `2e8f6477` | state_revision | b3 | primary | 13.77 | 1 / 9981/334 | 2 | 0 | 3 |  | pass |
| web | `2e8f6477` | state_revision | fresh | primary | 130.32 | 6 / 61307/2186 | 10 | 2 | 23 |  | pass |
| web | `2e8f6477` | state_revision | ours | primary | 19.10 | 1 / 9981/526 | 2 | 0 | 3 | 8 | pass |
| web | `2e8f6477` | workflow_revision | b3 | primary | 35.23 | 3 / 26314/966 | 3 | 2 | 5 |  | pass |
| web | `2e8f6477` | workflow_revision | fresh | primary | 157.41 | 6 / 61329/2233 | 10 | 2 | 23 |  | pass |
| web | `2e8f6477` | workflow_revision | ours | primary | 30.18 | 2 / 17065/878 | 2 | 2 | 4 | 8 | pass |
| enterprise | `0ab99e0c` | state_revision | b3 | r1 | 19.55 | 2 / 20178/435 | 2 | 0 | 2 |  | pass |
| enterprise | `0ab99e0c` | state_revision | ours | r1 | 16.18 | 2 / 20178/334 | 2 | 0 | 2 | 13 | pass |
| enterprise | `0ab99e0c` | trajectory_growth | b3 | r1 | 132.15 | 9 / 114484/3109 | 16 | 2 | 19 |  | pass |
| enterprise | `0ab99e0c` | trajectory_growth | ours | r1 | 133.84 | 9 / 114484/3449 | 16 | 2 | 19 | 0 | pass |
| enterprise | `0ab99e0c` | workflow_revision | b3 | r1 | 34.97 | 3 / 23125/967 | 2 | 2 | 4 |  | pass |
| enterprise | `0ab99e0c` | workflow_revision | ours | r1 | 39.22 | 3 / 23125/1144 | 2 | 2 | 4 | 13 | pass |
| enterprise | `49f98e9e` | state_revision | b3 | r1 | 15.13 | 2 / 18835/305 | 2 | 0 | 2 |  | pass |
| enterprise | `49f98e9e` | state_revision | ours | r1 | 14.27 | 2 / 18835/283 | 2 | 0 | 2 | 12 | pass |
| enterprise | `49f98e9e` | workflow_revision | b3 | r1 | 37.41 | 3 / 21274/685 | 2 | 2 | 4 |  | pass |
| enterprise | `49f98e9e` | workflow_revision | ours | r1 | 27.28 | 3 / 21274/727 | 2 | 2 | 4 | 12 | pass |
| web | `1ad1af4b` | state_revision | b3 | r1 | 23.52 | 2 / 8016/691 | 4 | 0 | 7 |  | pass |
| web | `1ad1af4b` | state_revision | ours | r1 | 14.05 | 1 / 3928/385 | 2 | 0 | 5 | 5 | pass |
| web | `1ad1af4b` | trajectory_growth | b3 | r1 | 61.01 | 5 / 30996/1793 | 8 | 2 | 12 |  | pass |
| web | `1ad1af4b` | trajectory_growth | ours | r1 | 57.74 | 5 / 30996/1673 | 8 | 2 | 12 | 0 | pass |
| web | `1ad1af4b` | workflow_revision | b3 | r1 | 20.96 | 2 / 5264/697 | 2 | 2 | 4 |  | pass |
| web | `1ad1af4b` | workflow_revision | ours | r1 | 22.12 | 2 / 5264/733 | 2 | 2 | 4 | 5 | pass |
| web | `2e8f6477` | state_revision | b3 | r1 | 18.40 | 1 / 9981/492 | 2 | 0 | 3 |  | pass |
| web | `2e8f6477` | state_revision | ours | r1 | 14.84 | 1 / 9981/372 | 2 | 0 | 3 | 8 | pass |
| web | `2e8f6477` | workflow_revision | b3 | r1 | 38.88 | 3 / 26314/1094 | 3 | 2 | 5 |  | pass |
| web | `2e8f6477` | workflow_revision | ours | r1 | 27.07 | 2 / 17065/764 | 2 | 2 | 4 | 8 | pass |
| enterprise | `0ab99e0c` | state_revision | b3 | r2 | 105.87 | 7 / 97352/2622 | 14 | 0 | 14 |  | pass |
| enterprise | `0ab99e0c` | state_revision | ours | r2 | 14.99 | 1 / 14409/343 | 2 | 0 | 2 | 13 | pass |
| enterprise | `0ab99e0c` | workflow_revision | b3 | r2 | 173.97 | 8 / 100237/2857 | 14 | 2 | 14 |  | pass |
| enterprise | `0ab99e0c` | workflow_revision | ours | r2 | 28.22 | 2 / 17240/791 | 2 | 2 | 4 | 13 | pass |
| enterprise | `49f98e9e` | state_revision | b3 | r2 | 107.17 | 5 / 65689/1510 | 10 | 0 | 10 |  | pass |
| enterprise | `49f98e9e` | state_revision | ours | r2 | 22.83 | 1 / 13407/279 | 2 | 0 | 2 | 12 | pass |
| enterprise | `49f98e9e` | workflow_revision | b3 | r2 | 129.00 | 6 / 68282/1961 | 10 | 2 | 12 |  | pass |
| enterprise | `49f98e9e` | workflow_revision | ours | r2 | 35.93 | 2 / 15839/733 | 2 | 2 | 4 | 12 | pass |
| web | `1ad1af4b` | state_revision | b3 | r2 | 24.02 | 2 / 8012/703 | 4 | 0 | 7 |  | pass |
| web | `1ad1af4b` | state_revision | ours | r2 | 13.73 | 1 / 3926/372 | 2 | 0 | 5 | 5 | pass |
| web | `1ad1af4b` | workflow_revision | b3 | r2 | 23.95 | 2 / 5278/801 | 2 | 2 | 4 |  | pass |
| web | `1ad1af4b` | workflow_revision | ours | r2 | 22.22 | 2 / 5278/732 | 2 | 2 | 4 | 5 | pass |
| web | `2e8f6477` | state_revision | b3 | r2 | 44.71 | 3 / 39698/1093 | 6 | 0 | 7 |  | pass |
| web | `2e8f6477` | state_revision | ours | r2 | 18.69 | 1 / 9980/506 | 2 | 0 | 3 | 8 | pass |
| web | `2e8f6477` | workflow_revision | b3 | r2 | 53.80 | 4 / 41655/1442 | 6 | 2 | 8 |  | pass |
| web | `2e8f6477` | workflow_revision | ours | r2 | 29.80 | 2 / 17071/855 | 2 | 2 | 4 | 8 | pass |
| enterprise | `0ab99e0c` | state_revision | b3 | r3 | 102.04 | 7 / 97352/2420 | 14 | 0 | 14 |  | pass |
| enterprise | `0ab99e0c` | state_revision | ours | r3 | 14.34 | 1 / 14409/325 | 2 | 0 | 2 | 13 | pass |
| enterprise | `0ab99e0c` | workflow_revision | b3 | r3 | 114.37 | 8 / 100237/2926 | 14 | 2 | 16 |  | pass |
| enterprise | `0ab99e0c` | workflow_revision | ours | r3 | 34.98 | 2 / 17240/1047 | 2 | 2 | 4 | 13 | pass |
| enterprise | `49f98e9e` | state_revision | b3 | r3 | 62.74 | 5 / 65689/1477 | 10 | 0 | 10 |  | pass |
| enterprise | `49f98e9e` | state_revision | ours | r3 | 12.75 | 1 / 13407/282 | 2 | 0 | 2 | 12 | pass |
| enterprise | `49f98e9e` | workflow_revision | b3 | r3 | 85.28 | 7 / 68797/2266 | 10 | 2 | 12 |  | pass |
| enterprise | `49f98e9e` | workflow_revision | ours | r3 | 22.44 | 2 / 15839/617 | 2 | 2 | 4 | 12 | pass |
| web | `1ad1af4b` | state_revision | b3 | r3 | 47.15 | 2 / 8012/681 | 4 | 0 | 7 |  | pass |
| web | `1ad1af4b` | state_revision | ours | r3 | 23.67 | 1 / 3926/349 | 2 | 0 | 5 | 5 | pass |
| web | `1ad1af4b` | workflow_revision | b3 | r3 | 46.84 | 2 / 5290/727 | 2 | 2 | 4 |  | pass |
| web | `1ad1af4b` | workflow_revision | ours | r3 | 45.49 | 2 / 5290/705 | 2 | 2 | 4 | 5 | pass |
| web | `2e8f6477` | state_revision | b3 | r3 | 90.51 | 3 / 39698/1244 | 6 | 0 | 7 |  | pass |
| web | `2e8f6477` | state_revision | ours | r3 | 28.80 | 1 / 9980/392 | 2 | 0 | 3 | 8 | pass |
| web | `2e8f6477` | workflow_revision | b3 | r3 | 61.70 | 4 / 41655/1617 | 6 | 2 | 8 |  | pass |
| web | `2e8f6477` | workflow_revision | ours | r3 | 36.89 | 3 / 17538/1116 | 2 | 2 | 4 | 8 | pass |

## Fresh/B0 touched-partition rebuild comparison

Fresh/B0 starts from the same persisted source memory but clears the cloned controller-response, event-output, and construction-embedding caches before rebuilding the touched trajectory partition. It is a no-build-cache partition-rebuild reference, not a full rebuild of every trajectory in the domain. B3/Ours values below are matched primary rows; their separate order-reversed repetitions are retained in the full table.

Matched fixed revisions: 8. Aggregate update-to-publication totals (not a per-request latency sum):
- fresh: 1249.20s; 56 controller calls; 589121/19293 input/output tokens; 202 embedding vectors.
- b3: 227.90s; 18 controller calls; 132987/5070 input/output tokens; 31 embedding vectors.
- ours: 206.79s; 16 controller calls; 119650/4830 input/output tokens; 28 embedding vectors.
All displayed Fresh/B0, B3 and Ours update-quality checks are retained per row; fixed Reader regression remains a separate downstream check.

## Same-trajectory growth (separate from new-trajectory append)

One real follow-up state was appended to an existing trajectory while preserving its identity and prior snapshot. The current global action/step dependency key changes, so the Ours implementation may conservatively regenerate old event outputs; no global dependency was removed. This workload is not pooled into the eight revision cases or the cross-trajectory append result.

- web: B3 149.11s / 6 calls / 31600 input and 2338 output tokens; Ours 109.92s / 5 calls / 30996 input and 1743 output tokens. Ours regenerated 8 event outputs and exactly reused 0 prior event outputs; embedding work was 12 vectors. Source-grounded content/event coverage: pass. One paired run is descriptive, not a stable latency estimate.
- enterprise: B3 168.99s / 9 calls / 114484 input and 3366 output tokens; Ours 129.85s / 9 calls / 114484 input and 3232 output tokens. Ours regenerated 16 event outputs and exactly reused 0 prior event outputs; embedding work was 19 vectors. Source-grounded content/event coverage: pass. One paired run is descriptive, not a stable latency estimate.
- Reverse-order repeat: web Ours 57.74s vs B3 61.01s, both with 5 / 5 calls and zero exact event reuse; enterprise Ours 133.84s vs B3 132.15s, both with 9 / 9 calls and zero exact event reuse. The order-reversed repeats confirm large wall variance and do not establish a growth speedup.

## Matched update repeats: eight fixed revisions

Each row aggregates the same eight revision cases from a fresh independent copy of the same combined starting snapshot. The runs are sequential on the resident model service; setup/cache seeding is excluded and publish includes save/reload verification. Actual policy order: primary B3→Ours, repeat-1 Ours→B3, repeat-2 Ours→B3 (order mistake retained), repeat-3 B3→Ours. Repeat-3 balances the order; the r2 run is not silently discarded.

| Pass | B3 wall s | Ours wall s | Ours vs B3 | Calls B3/Ours | Input tokens B3/Ours | Events B3/Ours | Quality checks B3/Ours |
|---|---:|---:|---:|---:|---:|---:|---:|
| primary | 227.90 | 206.79 | -9.3% | 18/16 | 132987/119650 | 19/16 | 8/8 |
| repeat-1 | 208.82 | 175.02 | -16.2% | 18/16 | 132987/119650 | 19/16 | 8/8 |
| repeat-2 | 662.50 | 186.42 | -71.9% | 37/12 | 426203/97150 | 66/16 | 8/8 |
| repeat-3 | 610.64 | 219.36 | -64.1% | 38/13 | 426730/97629 | 66/16 | 8/8 |

Structured per-pass totals: `results/tables/agentrunbook_update_repeat_summary.csv`. These totals show whether the observed update-work savings survive order changes; the r2 B3 recomputation/cost spike remains included.

## Reader regression across eight fixed revision cases

This is a text-only/adapted fixed-question regression on persisted update snapshots. It covers both state and workflow revisions for two web and two enterprise trajectories, with B3 and Ours using the same local Qwen Reader, 2,048-token ceiling, thinking disabled and four questions per case. Fresh/B0 is not included in the full eight-case table because only a subset of Fresh workflow snapshots was re-read; its state-revision results remain in the separate Fresh/B3/Ours report.

| Domain | Trajectory | Case | Method | Correct / 4 | Complete / 4 | Trunc | Service | Parse | Reader input/output tokens | Reader wall s |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| web | `1ad1af4b` | state_revision | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 41813/138 | 15.99 |
| web | `1ad1af4b` | state_revision | ours | 3/4 | 4/4 | 0 | 0 | 0 | 40505/1133 | 43.80 |
| web | `1ad1af4b` | workflow_revision | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 40777/158 | 18.40 |
| web | `1ad1af4b` | workflow_revision | ours | 3/4 | 4/4 | 0 | 0 | 0 | 34348/47 | 11.35 |
| web | `2e8f6477` | state_revision | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 32020/137 | 13.26 |
| web | `2e8f6477` | state_revision | ours | 3/4 | 4/4 | 0 | 0 | 0 | 32110/138 | 13.21 |
| web | `2e8f6477` | workflow_revision | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 34225/43 | 11.32 |
| web | `2e8f6477` | workflow_revision | ours | 4/4 | 4/4 | 0 | 0 | 0 | 36405/226 | 16.87 |
| enterprise | `0ab99e0c` | state_revision | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 21199/693 | 25.05 |
| enterprise | `0ab99e0c` | state_revision | ours | 2/4 | 4/4 | 0 | 0 | 0 | 17291/256 | 12.07 |
| enterprise | `0ab99e0c` | workflow_revision | b3 | 2/4 | 4/4 | 0 | 0 | 0 | 19186/78 | 7.78 |
| enterprise | `0ab99e0c` | workflow_revision | ours | 2/4 | 4/4 | 0 | 0 | 0 | 16281/1692 | 51.17 |
| enterprise | `49f98e9e` | state_revision | b3 | 2/4 | 4/4 | 0 | 0 | 0 | 16807/240 | 11.55 |
| enterprise | `49f98e9e` | state_revision | ours | 2/4 | 4/4 | 0 | 0 | 0 | 15025/95 | 7.14 |
| enterprise | `49f98e9e` | workflow_revision | b3 | 2/4 | 4/4 | 0 | 0 | 0 | 19371/330 | 14.67 |
| enterprise | `49f98e9e` | workflow_revision | ours | 2/4 | 4/4 | 0 | 0 | 0 | 16751/145 | 8.88 |

Across B3/Ours, 42/64 fixed responses are correct and 64/64 are complete/parseable. Truncation, service failures and parse failures are all zero. This is a downstream development constraint, not an official Judge score; the construction source-grounded checks remain 48/48.

Per-case results and raw paths are in `results/tables/agentrunbook_revision_case_reader.csv`.


## Reader regression on state-revision update snapshots

This is a text-only/adapted downstream quality check using the fixed four questions per domain after a controlled state revision. It reuses persisted update snapshots and does not add construction work. All answers use a 2,048-token Reader ceiling, thinking disabled, and the same local Qwen service.

| Domain | Method | Repeat | Correct / 4 | Complete / 4 | Trunc | Service | Parse | Reader input/output tokens | Prompt / Reader wall s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| web | fresh | r1 | 3/4 | 4/4 | 0 | 0 | 0 | 31334/47 | 15.98 / 10.39 |
| web | b3 | r1 | 3/4 | 4/4 | 0 | 0 | 0 | 41813/138 | 14.00 / 15.99 |
| web | ours | r1 | 3/4 | 4/4 | 0 | 0 | 0 | 40505/1133 | 16.10 / 43.80 |
| enterprise | fresh | r1 | 2/4 | 4/4 | 0 | 0 | 0 | 17064/34 | 16.10 / 5.85 |
| enterprise | fresh | r2 | 2/4 | 4/4 | 0 | 0 | 0 | 16777/459 | 15.89 / 17.65 |
| enterprise | b3 | r1 | 3/4 | 4/4 | 0 | 0 | 0 | 18334/36 | 16.92 / 6.32 |
| enterprise | b3 | r2 | 3/4 | 4/4 | 0 | 0 | 0 | 21199/693 | 16.86 / 25.05 |
| enterprise | ours | r1 | 2/4 | 4/4 | 0 | 0 | 0 | 19607/305 | 16.27 / 14.10 |
| enterprise | ours | r2 | 2/4 | 4/4 | 0 | 0 | 0 | 17291/256 | 15.53 / 12.07 |

All 36 scored responses (9 rows × 4 questions) were complete, boxed and service-successful, with zero truncation, service failure or parse failure. Web is 3/4 for all three methods. Enterprise is 2/4 for Fresh in both repeats, 3/4 for B3 in both repeats, and 2/4 for Ours in both repeats. The stable enterprise gap is therefore a quality constraint on this representative state-revision snapshot, not evidence of quality preservation for Ours.

The misses are concentrated in dynamic/procedure questions and vary in answer wording; source-grounded construction checks still pass. We retain the negative result and do not select Ours as a quality-equivalent update method until a broader Reader/QA evaluation is completed.

Raw aggregate: `results/tables/agentrunbook_revision_reader_regression.csv`. Per-question answers: `results/tables/agentrunbook_revision_reader_per_question.csv`.


## Reader regression on same-trajectory growth snapshots

This is a text-only/adapted quality check over the fixed eight development questions (four web + four enterprise), reusing the already published growth snapshots. It does not change construction/update timing and is not native Small or official Judge scoring.

| Domain | Method | Correct / 4 | Complete / 4 | Trunc | Service failures | Parse failures | Reader input/output tokens | Prompt/query build wall s | Reader generation wall s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| web | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 41526/47 | 88.04 | 14.93 |
| web | ours | 3/4 | 4/4 | 0 | 0 | 0 | 40964/47 | 532.52 | 14.79 |
| enterprise | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 46730/438 | 283.61 | 26.26 |
| enterprise | ours | 3/4 | 4/4 | 0 | 0 | 0 | 44347/175 | 137.53 | 18.00 |

All four cells produced complete, boxed, service-successful answers with zero truncation or parse failure. Web B3/Ours both score 3/4; enterprise B3/Ours both score 3/4. The only web miss is the same dynamic question answered UNKNOWN by both; the enterprise miss is the task-type question, with B3 returning “Type of Change” and Ours returning “type, type”.

Query/prompt build wall time is reported separately because it is not part of the construction/update cost claim. It varied widely across paired runs (for example, web 88.04 s vs 532.52 s), so only the complete/parseable status and paired question scores are used as the quality constraint here.

Raw aggregate rows: `results/tables/agentrunbook_growth_reader_regression.csv`. Per-question rows: `results/tables/agentrunbook_growth_reader_per_question.csv`.


## Paired interpretation

- `web/1ad1af4b/state_revision` primary Ours vs B3 wall -25.13s; input-token delta -4088. r3 Ours vs B3 wall -23.48s.
- `web/2e8f6477/state_revision` primary Ours vs B3 wall +5.32s; input-token delta +0. r3 Ours vs B3 wall -61.71s.
- `web/1ad1af4b/workflow_revision` primary Ours vs B3 wall +1.16s; input-token delta +0. r3 Ours vs B3 wall -1.35s.
- `web/2e8f6477/workflow_revision` primary Ours vs B3 wall -5.05s; input-token delta -9249. r3 Ours vs B3 wall -24.81s.
- `enterprise/0ab99e0c/state_revision` primary Ours vs B3 wall -0.29s; input-token delta +0. r3 Ours vs B3 wall -87.70s.
- `enterprise/49f98e9e/state_revision` primary Ours vs B3 wall +0.01s; input-token delta +0. r3 Ours vs B3 wall -50.00s.
- `enterprise/0ab99e0c/workflow_revision` primary Ours vs B3 wall +0.04s; input-token delta +0. r3 Ours vs B3 wall -79.39s.
- `enterprise/49f98e9e/workflow_revision` primary Ours vs B3 wall +2.83s; input-token delta +0. r3 Ours vs B3 wall -62.84s.

Source-grounded checks pass in 80/80 persisted rows (new fact, old fact handling, untouched facts, complete event coverage; Ours additionally checks only actually reused joint events). The historical pre-fix checker rows remain under runs/agentrunbook-updates-main but are excluded from this table; the corrected paired rerun is included. These checks do not establish Reader quality. The fixed B3/Ours Reader regression covers eight revision cases (64/64 complete parseable answers, 42/64 correct, zero truncation/service/parse failures); both methods score 21/32 overall, with web 12/16 vs 13/16 and enterprise 9/16 vs 8/16. Fresh/B0 Reader coverage is partial and is not pooled into this matched table. The append result remains an arrival-of-a-new-trajectory case, distinct from same-trajectory growth. Growth quality rechecks are written beside raw run metrics; raw measurements and original checker output are preserved.
