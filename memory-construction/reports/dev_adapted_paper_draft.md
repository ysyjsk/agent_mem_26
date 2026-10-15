# Text-only adapted development: experimental draft

## Experimental setup

We evaluate eight fixed questions from LongMemEval-V2 (four each from enterprise and web) against a shared memory per domain. Each base memory contains five **complete** trajectories, including one fixed distractor: ten trajectories and 91 recorded states in total. The questions cover static environment, dynamic environment, and procedure types. Questions are not removed after incorrect responses. The source IDs, answer-bearing trajectories and file hashes are in the frozen manifests. Selection is evidence-accessible development sampling, not held-out evaluation.

The controller and Reader use the resident Qwen3.5-9B service, and embedding uses Qwen3-Embedding-8B. The Reader has a 2048-token output ceiling, thinking disabled, temperature 0.6, top-p 0.95, top-k 20, concurrency one, and a common 12000-token memory-context budget. Earlier 1024-token Reader runs truncated; 2048 is used throughout this comparison. We retain full recorded text and omit screenshots explicitly. Controller operations retain method-specific prompts/budgets (AgentRunbook/RAG notes: 8192 ceiling; adapted core extraction: 1024 ceiling with the existing compact extraction prompt), so only B3 versus Ours is a matched construction-mechanism comparison. Controller output budgets are not Reader budgets.

We reuse the official question-specific deterministic evaluators for these selected questions. Correctness is measured over all eight fixed questions and is separate from complete boxed-answer parsing. These are text-only adapted development scores, not native multimodal Small, not an official Judge result, and not independent test accuracy. No unavailable Judge is replaced implicitly.

Construction wall time runs from insertion of the first trajectory through indexing, per-trajectory persistence and final reload validation. Resident model serving and pre-insertion client/tokenizer initialization are outside this boundary. Cold means an empty method memory/cache, not cold GPU model loading. Query-only modifications reuse compatible persisted memory: their construction number is the cost of the source build, not a new measurement. Prompt-stage and Reader-stage wall times are recorded separately; inclusive per-question queue sums must not be read as wall time. Model totals include reported usage, with unknown usage counts retained separately. Failed requests with unknown tokens are not free.

## Current results

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

## Method and ablation interpretation

The first practical candidate L combines raw-state RAG, line-boundary chunk/interleave packing of oversized retrieved items, and reuse of the identical tokenizer instance during repeated context-budget checks. Full raw trajectories remain on disk. Chunking changes evidence allocation under the common budget; it does not add gold answers or new model calls. Continuation chunks currently do not repeat source headers, a provenance/readability limitation. Tokenizer reuse is a common engineering optimization, not a new retrieval method.

Candidate M adds query-time lexical source backfill from at most two top retrieved trajectories. It normalizes leading UI node IDs only for repeated-line deduplication, scores literal source lines by query-term inverse document frequency, weights explicitly quoted query words threefold, and retains up to 64 anchors under a 12000-character excerpt cap. Source trajectory/state/line coordinates accompany each retained line. It adds no generation or embedding requests. These heuristics were developed on this development set, not frozen before seeing its errors. N changes one factor: add immediate neighboring source lines into unused space under the same excerpt cap. The ordinary 12000-token Reader memory budget still applies to all variants.

Candidate A bounded the event extractor's initial AXTree request. It removed 32 failed build calls but did not reduce construction wall time (1181.42s versus 1170.71s), with 6/8 correct. Candidate B reduced client event concurrency from 16 to 4; its 1041.21s run reached only 4/8 and retained 32 failed build calls. The service serializes model execution, so this is **not** evidence of real batching. Candidate C prioritized raw evidence and reached 5/8, not an improvement over the 6/8 reference. Removing event generation (D) cost 398.18s and reached 4/8. The full candidate table retains further unsuccessful ordering/top-k attempts. These negative results motivated changing the amount of generated memory and the evidence packing, rather than optimizing cheap dependency bookkeeping.

With common chunk packing, AgentRunbook-R and raw RAG J both reached 6/8 on a correctly matched rerun. Raw RAG's recorded construction cost is 89.07s versus 1170.71s (92.39% lower), but this is a single historical cold-build comparison, not a repeated speedup estimate or a general claim of equal accuracy. The matched tokenizer ablation reduced prompt-stage wall time from 34.32s (J) to 6.09s (L) on the first paired runs, with identical 86186 total Reader input tokens and 6/8 correct in both. Reader generation is stochastic; only the deterministic input equality and measured stage times support the tokenizer claim.

Strong B3 and Ours use their existing conservative-partition and dependency-incremental cores respectively, independent stores/caches, the same salient-v3/source-literal representation, and the same live extractor. Generated facts drive state-slice embeddings and are returned with full raw source backreferences. Methods run serially against the same resident service, with order reversed between domains. The historical eager batch2 backend is not reloaded alongside this service. Full-trajectory insertions are measured as cold construction with per-trajectory publications; they do not establish state-revision Freshness/Goodput. If calls and tokens remain equal, the appropriate conclusion is no demonstrated expensive-work reduction, not a DAG speedup.

## Repeats

- L: J + tokenizer reuse: 6/8 correct, 8/8 complete; prompt 6.091s, Reader 49.795s.
- M: L + lexical source backfill: 7/8 correct, 8/8 complete; prompt 2.491s, Reader 37.9s.
- M repeat 2: 7/8 correct, 8/8 complete; prompt 2.477s, Reader 41.923s.
- M repeat 3: 6/8 correct, 8/8 complete; prompt 2.468s, Reader 66.392s.
- N: M + adjacent source lines: 6/8 correct, 8/8 complete; prompt 2.84s, Reader 35.259s.
- RAG+Notes + backfill: 8/8 correct, 8/8 complete; prompt 7.208s, Reader 76.035s.
- Notes+M repeat 2: 7/8 correct, 8/8 complete; prompt 7.28s, Reader 61.509s.
- Notes+M repeat 3: 7/8 correct, 8/8 complete; prompt 7.007s, Reader 89.335s.

These are repeated stochastic Reader runs on one memory, not independent cold-build repetitions or additional questions.

## Corpus scaling

The expanded corpus keeps the same eight questions and all original evidence trajectories. Five distractors per domain are selected from the common official haystack by SHA256(expanded20-v1:trajectory_id), without consulting answers or outputs. This gives twenty complete trajectories and 293 states. The configuration is frozen before the expansion run. This tests distractor/load robustness, not generalization to independent questions.

## Integrity and limitations

Historical E–K query commands requested official 100-trajectory haystack metadata while loading the actual five-trajectory/domain cache. Their answers were generated from those five cached trajectories, but the metadata mismatch is retained and flagged; they are excluded from the clean paper table until matched reruns exist. A new ID/order guard rejects such loads. Historical I additionally used a different embedding-model alias. H/I's interleave counts refer to raw memory items, including images, not ranked hits. The four-question expansion attempt chosen by answer substring was invalid and is excluded, with its files retained. Larger-corpus expansion above avoids that selection error.

Eight development questions, active tuning on their errors, single-run cold builds, sampling variance, missing vision, and no independent test set limit publication claims. Current supported contribution is a measured cost/quality trade-off and diagnosis of evidence-budget waste; there is no supported general SOTA, native Small, or strong-B3 speedup claim.

## Updated measured findings (generated from the current table)

- M repeated QA: 7/8, 7/8, 6/8; 24/24 complete outputs. Repeated answers are not distinct questions or independent cold builds.
- N repeated QA: 6/8; 8/8 complete outputs. Repeated answers are not distinct questions or independent cold builds.
- Notes+M repeated QA: 8/8, 7/8, 7/8; 24/24 complete outputs. Repeated answers are not distinct questions or independent cold builds.
- M minus chunks: 5/8 correct, 8/8 complete, source build 89.065s; prompt + Reader wall 145.476s.
- M expanded20: 7/8 correct, 8/8 complete, source build 283.056s; prompt + Reader wall 76.248s.
- Expanded20 RAG+Notes + backfill: 6/8 correct, 8/8 complete, source build 772.465s; prompt + Reader wall 46.442s.
- O: Notes+M + query embedding reuse: 7/8 correct, 8/8 complete, source build 243.530s; prompt + Reader wall 60.766s.
- O expanded20: 6/8 correct, 8/8 complete, source build 772.465s; prompt + Reader wall 48.149s.
- Notes+M minus chunks: 5/8 correct, 8/8 complete, source build 243.530s; prompt + Reader wall 45.297s.
- RAG+Notes + backfill: 8/8 correct, 8/8 complete, source build 243.530s; prompt + Reader wall 83.243s.
- AgentRunbook-R + backfill: 7/8 correct, 8/8 complete, source build 1170.713s; prompt + Reader wall 154.437s.
- Strong B3-c1 + backfill: 6/8 correct, 8/8 complete, source build 537.681s; prompt + Reader wall 92.599s.
- Ours-dev + backfill: 6/8 correct, 8/8 complete, source build 690.423s; prompt + Reader wall 95.774s.
- Existing-core pair: B3 537.681s / 4/8, Ours 690.423s / 5/8. Construction generation calls 91 vs 91; input tokens 181191 vs 181191; output tokens 9984 vs 10730. Sampling differed, so observed runtime/QA differences do not isolate dependency scheduling; no demonstrated reduction of expensive model work.
