# Agent Memory Construction: adapted cost/quality results

## Scope and status

This report consolidates the current paper-facing local text-only/adapted evidence. It uses fixed LongMemEval-V2-derived trajectories and questions, resident local Qwen3.5-9B for controller/Reader, Qwen3-Embedding-8B for vectors, and independent method-owned caches. Screenshots are not sent in this route. The numbers below are not native multimodal Small results and do not replace the pending official GPT/Judge evaluation.

The frozen shared development corpus contains ten complete trajectories, 91 states, 81 transitions and eight fixed questions (four web, four enterprise). Each domain uses one shared memory with distractor trajectories; questions are not removed after an error. Reader output is capped at 2,048 tokens with thinking disabled.

## Main adapted comparison

| Method | Build→publish (s) | Build calls | LLM input tokens | Complete | Correct |
|---|---:|---:|---:|---:|---:|
| AgentRunbook-R | 1170.71 | 124 (32 failed) | 761,072 | 8/8 | 6/8 |
| RAG+Notes | 243.53 | 11 | 19,479 | 8/8 | 4/8 |
| Raw RAG | 89.06 | 0 | 0 | 8/8 | 5/8 |
| RAG+Notes + backfill | 243.53 | 11 | 19,479 | 8/8 | 8/8 |
| Strong B3 (matched representation) | 537.68 | 91 | 181,191 | 8/8 | 6/8 |
| Ours (matched representation) | 690.42 | 91 | 181,191 | 8/8 | 6/8 |

The matched B3/Ours cold-build rows do not support a cold-build model-work reduction claim: controller calls and input tokens are equal. They are retained as the mechanism baseline for incremental updates. The full per-row table is `results/tables/paper03_local_adapted_main.csv`.

## Construction candidate decision

Adjacent joint extraction with bounded common preflight is frozen for remaining adapted runs as a cost-efficiency candidate. On two long enterprise trajectories, single-event extraction required 32 calls and 283,175 known input tokens in 277.40 s; the joint candidate required 20 calls and 224,445 input tokens in 274.71 s. All 29 transition IDs, source actions, state pairs/order and save/reload checks passed. The 1.0% wall-time difference is a near-tie, not a material end-to-end speedup. The fixed-10 expansion remains a negative wall-time result and is not selected. Exact-input construction Embedding reuse is enabled; identical prepared inputs share vectors without averaging or approximate substitution. Details: `reports/paper02_cold_construction.md`.

## Incremental update result

Across eight fixed state/workflow revisions (four web/enterprise trajectories, interior and group-boundary positions), all persisted source-grounded checks pass. Fresh/B0 touched-partition rebuild totals 1,249.20 s, 56 calls and 589,121 known input tokens. Strong B3 totals 227.90 s, 18 calls and 132,987 input tokens. Ours totals 206.79 s, 16 calls and 119,650 input tokens. The four-pass repeat summary shows the largest Ours gains when conservative B3 rebuilding expands after cache mismatch; low-cost rounds are near ties. The fixed Reader regression over 64 matched answers is 21/32 for each method, with 64/64 complete/parseable and zero truncation/service/parse failures. These are adapted local proxy checks, not official QA.

## Scale and ablations

The four-cell cold matrix shows the cost/latency trade-off: baseline 830.00 s / 93 calls / 735,023 input tokens; joint 1,025.77 s / 78 calls / 686,954 input tokens; exact Embedding reuse 882.95 s / 97 calls / 736,591 input tokens; combined 989.91 s / 76 calls / 666,712 input tokens. All structural checks pass, but no cell improves wall time. At 24 windows and 60 checkpoints, B0 totals 1,268.67 s, Ours 476.22 s and strong B3 473.99 s, with 60/60 snapshot checks in each incremental method. The complete table and figure are `results/tables/paper04_ablation_scale.csv` and `reports/paper04_ablation_scale.svg`.

## Continuous-arrival Freshness/Goodput

The real adapted stream probe removes target trajectory `0ab99e0c` from independent B3/Ours clones, then exposes source prefixes in batches of 1, 2 and 3 transitions. Each batch invokes the real local controller and Embedding, saves/reloads a queryable snapshot, and runs a retrieval probe. All six arrival quality checks and six reload/retrieval probes pass.

| Method | Publish total (s) | Freshness P50/P95 (s) | Goodput (new transitions/s) | Calls | Input tokens |
|---|---:|---:|---:|---:|---:|
| B3 | 187.30 | 74.46 / 98.12 | 0.0320 | 9 | 76,918 |
| Ours | 190.34 | 79.98 / 90.97 | 0.0315 | 10 | 77,369 |

Ours is not selected for this growth protocol. The current dependency key includes the full action sequence and transition count, so every longer prefix changes the event request context and yields no event-level reuse. This is a mechanistic negative result; no global dependency was removed to manufacture hits. Raw rows and figure: `results/tables/streaming_freshness_goodput.csv` and `reports/streaming_freshness_goodput.svg`.

## Paper-ready method description

We represent each trajectory as source-linked raw state slices, transition events and reusable procedure/hint notes. A transition event preserves its pre/post state references, annotated action, state change and source identifiers. For adjacent transitions, a bounded common-preflight stage prepares shared context once and emits two independently keyed event records; if the safe input bound is exceeded, the group splits to singleton extraction. Construction Embedding is content-addressed over the exact bounded input and model/configuration.

For updates, B3 conservatively invalidates the touched trajectory while preserving legal exact-request/vector caches. Ours additionally validates each event against its own dependency key and reuses unaffected event outputs when the trajectory context remains stable. Both methods publish through the same save/reload boundary and use the same representation, model, budgets and query settings.

## Limitations

The current quality evidence is a fixed adapted development proxy with eight questions, stochastic local Reader outputs and no verified official Judge. The continuous stream is a controlled source-prefix protocol rather than externally timestamped production traffic. Native multimodal Small and official Judge remain pending/blocked by external service availability. The strongest supported claim is conditional: event-level dependency reuse reduces necessary update work for localized revisions, while the current full-prefix dependency context prevents a streaming-growth speedup; joint cold extraction reduces measured calls/input in some workloads but does not guarantee wall-time improvement.

## Reproduction entry points

- Update matrix: `tools/run_agentrunbook_updates.py`
- Continuous stream: `tools/run_agentrunbook_stream.py`
- Stream report: `tools/report_streaming_freshness.py`
- Cold decision: `reports/paper02_cold_construction.md`
- Update table/figure: `results/tables/agentrunbook_update_main.csv`, `reports/agentrunbook_update_cumulative.svg`
- Scale/ablation table/figure: `results/tables/paper04_ablation_scale.csv`, `reports/paper04_ablation_scale.svg`
