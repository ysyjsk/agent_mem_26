# Archived pre-repair manuscript — quality/configuration claims superseded

## Abstract

Agent memories become expensive to maintain when a small source correction triggers full event re-extraction and note regeneration. We study a text-only/adapted AgentRunbook-R maintenance path in which source changes invalidate only dependent events, preserve unaffected entries, and publish one state-scoped current-evidence view for affected events. On a frozen formal workload of ten complete trajectories per domain (web and enterprise), one literal source revision and two fixed dynamic questions per domain, the proposed `source_coalesced` branch used zero update LLM calls and reduced update publication from 23.28 to 2.39 seconds on web and from 19.58 to 1.85 seconds on enterprise relative to matched B3. The savings are real, but the downstream Reader constraint is not uniformly preserved: B3/source_coalesced score 2/2 versus 1/2 on web and 1/2 versus 1/2 on enterprise. All formal responses are complete and parseable, with no truncation, service, or parsing failures. We therefore report a cost reduction with an explicit quality limitation rather than claiming equivalence.

## 1. Problem and scope

The experiment targets maintenance, not cold construction or arbitrary semantic editing. A published memory contains raw state slices, generated transition events, procedure notes, hint notes, embeddings, and retrieval indices. A correction to one observed source state should not force every trajectory or every event to be regenerated. The formal scope is text-only/adapted Small history libraries; it is not the native multimodal benchmark.

## 2. Method

The fixed implementation uses three steps. First, a source diff identifies the changed state and derives the affected transition IDs from their pre/post state positions. Exact dependency keys bind event outputs to the construction semantics and request configuration, so unrelated cached outputs remain legal while changed dependencies are not silently re-keyed. Second, the `source_coalesced` policy retains unaffected events and notes, then publishes a single current-evidence block per affected event. The block is formed from exact current source lines and local unchanged evidence; obsolete observations are removed from the current view rather than appended indefinitely. Third, the updated raw state, event entries, notes, embeddings, and index are persisted and reloaded before the snapshot is considered queryable. Source-only is an ablation that updates raw state and invalidates dependent events without generating replacement events. B3 is the matched AgentRunbook-R update path with the same starting snapshot, model, budgets, caches, and query workload.

The method is deliberately conservative: non-literal or unsupported changes fall back to ordinary extraction, and source-grounded checks are not treated as semantic certification. The formal coalesced runs failed a predeclared lexical rule requiring all neighboring facts to remain in the generated event text; this failure is retained.

## 3. Experimental setup

We freeze ten complete trajectories for each domain, a web Title correction on trajectory `1ad1af4b`, an enterprise count correction on `0ab99e0c`, and two dynamic questions per domain. All branches use Qwen3.5-9B for the controller/Reader, Qwen3-Embedding-8B for embeddings, thinking disabled, a 2,048-token Reader ceiling, a 12,000-token memory context, event groups of two, and the same retrieval configuration. Update time includes artifact generation, embeddings, save/reload, and queryable publication. Reader prompt construction, retrieval, and generation are reported separately. The enterprise initial snapshot is a legally reused ten-trajectory build; its historical preparation is not presented as a new cold-build measurement.

## 4. Formal results

| Domain | Method | Update LLM tokens | Update publish (s) | Embedding tokens | Reader correct / scored | Complete / scored | Source checks |
|---|---:|---:|---:|---:|---:|---:|---|
| Web | B3 | 8,645 | 23.283 | 8,410 | 2/2 | 2/2 | pending semantic review |
| Web | Source-only | 0 | 2.157 | 7,503 | 0/2 | 2/2 | passed lexical gate |
| Web | Source-coalesced | 0 | 2.388 | 8,194 | 1/2 | 2/2 | lexical limitation retained |
| Enterprise | B3 | 14,849 | 19.575 | 5,207 | 1/2 | 2/2 | lexical limitation retained |
| Enterprise | Source-only | 0 | 1.588 | 4,096 | 1/2 | 2/2 | passed lexical gate |
| Enterprise | Source-coalesced | 0 | 1.853 | 5,134 | 1/2 | 2/2 | lexical limitation retained |

Across both domains, Source-only and source-coalesced eliminate the measured update LLM calls for the fixed literal revisions. Relative to B3, source-coalesced reduces publication wall time by 89.7% on web and 90.5% on enterprise. The cost result is not a quality-equivalence result: Source-only loses both web questions, and source-coalesced loses one. The aggregate fixed Reader workload has 12/12 complete/parseable answers and zero truncation, service, or parse failures; correctness is 6/12 across the six formal branches.

The cumulative figure [`focused-maintenance-v4-formal-cumulative.svg`](../results/figures/focused-maintenance-v4/focused-maintenance-v4-formal-cumulative.svg) separates update LLM tokens from fixed query/Reader tokens. The raw table, ablation, and per-question records are under `results/tables/focused-maintenance-v4/`.

### 4.1 Mechanism ablations

We then ran the predeclared `source_overlay` and `delta_guarded` branches on the same frozen snapshots and questions. Overlay required zero update LLM tokens in both domains, with publication times of 2.485 s (web) and 1.686 s (enterprise); its Reader scores were 1/2 and 2/2. Delta-guarded used 1,877 update LLM tokens and 10.961 s on web, scoring 0/2, while the enterprise case used no update LLM tokens and 1.662 s but produced only one scorable, non-truncated answer. The enterprise overlay and delta-guarded branches both failed the predeclared event-coverage check for the count correction. These rows are retained as mechanism evidence and negative quality results, not folded into the source-coalesced main claim. The complete table is `results/tables/focused-maintenance-v4/formal_ablation_extended.csv`; the enterprise delta-guarded truncation remains explicitly recorded in its raw Reader output.

## 5. Discussion and limitations

The results support a narrow systems claim: source-bound dependency invalidation and current-evidence coalescing can remove repeated model work for literal source corrections while preserving a queryable snapshot. They do not support a general claim that the method preserves downstream answer quality, dominates Source-only, or accelerates cold construction. The ablations reinforce the boundary: overlay is as cheap as coalescing on these literal cases, while guarded editing can reintroduce model work without restoring quality. The formal quality gap is especially important because it shows that retaining raw source and invalidating events is not enough for normal retrieval. Future work would need a fixed, independently selected quality workload and a stronger semantic validation of event coverage; such work is outside this frozen experiment and no formal result was tuned after inspection.

## 6. Reproducibility

Exact commands, model endpoints, frozen Manifest, raw run paths, and known environmental failures are listed in [`reproduction.md`](reproduction.md). The original no-space and snapshot-order failures are preserved as renamed directories and are not counted as successful measurements.
