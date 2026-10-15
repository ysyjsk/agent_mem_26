# v4 measured development loop

## 2026-10-14 fixed full-trajectory text-only/adapted continuation

The current user override prioritizes the local eight-question comparison, not blocked native Small.
Measured A/B/C use different hypotheses (smaller repeated model inputs, lower client concurrency,
and evidence packing) and retain negative results: A 1181.419s/6 correct, B 1041.207s/4 correct,
C reused build/5 correct, versus AgentRunbook 1170.713s/6 correct. No true-batching claim for B.
After shared chunk packing, matched AgentRunbook and raw-RAG J both reach 6/8. Raw memory build
cost is 89.065s. L caches the unchanged tokenizer instance: 34.321s -> 6.091s prompt wall,
same 86186 Reader input tokens, all eight prompt messages exactly equal, still 6/8. This is
a common engineering fix, offered equally to all subsequent methods. All runs retain eight
questions including errors. Expanded L uses 20 complete trajectories/293 states, retains the
same eight questions, costs 283.056s to queryable publication, and reaches 6/8.

Integrity corrections: E-K historical query metadata requested 100 trajectories while loading
five per domain; preserve and flag them, use corrected frozen roots for new runs, and reject
future saved-memory ID/order mismatches. H/I interleave counts are raw items, not hits. I had a
different embedding alias. The invalid answer-substring-selected four-question expansion is
retained but excluded; expanded20 instead adds predetermined distractors without selecting answers.

Current existing-core integration: independent strong B3 and Ours stores, same salient-v3
extraction/source literals, compact fact embeddings with complete raw-state backreferences,
same Reader and common chunk/tokenizer fixes. No historical scores are copied into this QA table.
The first B3 attempt (`enterprise-workflow-b3-v1`) failed after 136.508s and 16 successful API
calls because two otherwise complete final JSONs had partial preambles before `</think>`.
Keep that failed run. The adapter now parses the final post-marker segment without modifying
the retained raw response; v2 starts from independent empty stores. Live request logs now also
record the nested actual thinking setting and finish_reason. Both methods receive the repair.
M (not yet measured here) adds bounded, stable-line-deduplicated lexical source backfill from
the top retrieved trajectories; it never consults gold answers or incurs new generation calls.

## Initial comparison — hypothesis H0 (2026-10-13)

On the fixed `fastloop_dev_v1.json` workload, retained prefix-local extraction
should reduce repeated inference when serving the same three checkpoints as
Fresh. This is a baseline-relative measurement, not a claim against strong B3.

- Fixed source SHA256 verified: `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
- Four fixed windows; 45 source events, 12 requested checkpoints per method.
- Both methods: local Qwen3.5-9B, bf16, temperature=0, 256 output tokens,
  6000-character deterministic input projection, prefix context=2, c=1.
- B0: empty independent cache/store at each checkpoint. Ours-dev: only its
  own previous window snapshot/cache. Real requests in both; no replay.
- Necessary repair before measurement: strict structured evidence parsing;
  no silent heuristic fallback; ensure the compact request retains pre/post
  observation text. These repairs apply identically to both methods.
- Scope: `construction_kernel`, including deterministic local views, lexical
  index and SQLite publish; dense embedding, Reader/Judge, cold load excluded.
- Next actual experiment: one fixed-window live validation, then unchanged
  four-window comparison `runs/fast-compare-v4-initial-20261013`.
- After first table: add dense index/readable publication and legitimate
  cached conservative-partition B3 on the same four windows.

## Core correction before acceptance — H0b (2026-10-13)

- Retained runs: `fast-compare-v4-initial-20261013` (empty extraction),
  `fast-compare-v4-retry1-window1` (single-window diagnosis),
  `fast-compare-v4-full-20261013` (B0 420.244 s/93 calls/182214 input tokens;
  Ours-dev 235.649 s/45 calls/90067 input tokens; each 9/12 successes).
  Initial run actually made 138 calls, not the earlier commentary's 284.
- Root causes: no goal lexical match was wrongly treated as unreadability;
  long terminal action copied repeatedly exhausted 256 output tokens;
  generic model IDs (`e1`) collided and silently removed older event evidence.
  The runner queried a disk Snapshot object, so a global locator conflict was
  not the cause of those read-check failures. A separate explicitly pinned
  store/old-epoch payload fix prevents future version/index ambiguity.
- Repairs apply to both methods: concise structured prompt at unchanged
  256 output-token budget; builder-owned per-event IDs; prompt frozen per run;
  cache keys include actual prompt, input projection and decoding budgets;
  source-event evidence coverage is checked at every checkpoint; unfiltered
  persisted read checks separated from goal-retrieval hits. No heuristics.
- Prediction: all fixed checkpoints parse/read correctly, no dropped event
  evidence; incremental extraction remains 45 live calls versus Fresh 93.
- Necessary CPU contracts: ID collisions, context revision invalidation,
  cache budget/prompt changes, pinned old epoch; selected 24 tests passed.
- Next: `runs/fast-compare-v4-corrected-20261013`, then same-window real dense
  Embedding/index publication and legitimate cached B3. Negative/failed runs
  above are not erased or relabeled as valid performance wins.

## Accepted H0b result and next H1

- Run `fast-compare-v4-corrected-20261013`: B0 **386.814 s**, 93 calls,
  183591 input / 7943 output tokens; Ours-dev **193.689 s**, 45 calls,
  90640 input / 3842 output tokens. Same 12 checkpoints per method, zero
  failures, all source-event coverage 1.0, 12/12 exact paired structured
  matches. Model cold load/warmup/Embedding/Reader/Judge excluded equally.
- Reductions versus repeated Fresh: latency 49.927%, input tokens 50.629%,
  live extraction calls 51.613%. No claim versus strong B3 yet; official QA
  remains `not_evaluated`.
- Actual bottleneck: live extraction 99.68% B0 / 99.49% Ours-dev time.
  Tightening local deterministic DAG costs alone has limited headroom here.
- H1: Adding the same true dense Embedding/index/readable publication will
  retain the Fresh-relative inference reduction; legal-cached B3-c1 should
  also reach 45 real extraction calls, exposing whether Ours has any benefit
  beyond basic exact request reuse. Preserve ties and regressions.
- Immediate run: B0/Ours-dev/B3-c1, same 4 windows, construction_e2e;
  Qwen3.5-9B GPU0 + Qwen3-Embedding-8B GPU1. Then actual c2 batch, not a
  concurrency flag, followed by at most 1–3 paired candidates per iteration.

## H1 observed and H2 next (2026-10-13)

- Completed `fast-compare-v4-e2e-c1-20261013`: B0 286.444 s/93 live calls,
  Ours-dev 139.112 s/45, B3-c1 138.512 s/45. Each has 12/12 completed
  checkpoints, 0 failures and 12 dense publication checks. Independent
  raw-token/dense/frozen-code audit is being retained separately.
- Ours-dev and B3-c1 both consume 90640 input/3842 output extraction tokens;
  the 0.43% Ours regression is retained, not treated as an improvement.
  Repeated Fresh-relative reduction is 51.43%, not evidence of novelty.
- True extraction remains ~93.4% of incremental end-to-end construction time.
  H2: bounded batch2 should reduce generation wall time, with no reduction
  in logical extraction count or information budget. Both Ours and strong B3
  receive exactly the same real batch2 opportunity and independent caches.
- Necessary Ours helper prepares complete arrived-prefix exact misses only;
  all requests and strict provenance parsing occur inside measured time,
  before build/apply can publish. Actual c is response-reported batch width,
  not a configured concurrency parameter; batch wall time counted once.
- Next actual run: `fast-compare-v4-e2e-batch2-20261013` on unchanged 4-window
  workload, followed by a justified context projection candidate and real
  Reader quality diagnostics. QA still `not_evaluated`.

## H2 observed and H3 next (2026-10-13)

- `fast-compare-v4-e2e-batch2-20261013`: Ours 100.288225884 s vs B3-c2
  100.270336674 s. Both 12/12 successful, zero failures, 45 true calls,
  90640 input/3852 output tokens, 12 dense/coverage checks; 12/12 exact
  within-run structured matches. Total 46 real model batches: 44 width2,
  2 width1. Frozen code and raw/checkpoint token sums verified.
- Versus each method's c1: Ours -27.908% latency, B3 -27.609%. Against
  strong B3, Ours -0.01784% reduction (tiny regression/tie), not a win.
- Batch size changes numerical execution: c1→c2 has only 2/12 exact
  structured checkpoint matches, with unchanged requests/input tokens and
  +10 output tokens per method. No claim of byte-identical live outputs;
  source coverage is not QA. Reader checks must precede final selection.
- H3: remove prior-event raw context (2→0), keeping current pre/action/post
  inputs, output budget, real batch2 and dense publication identical in
  both methods. Prediction: input reduction may reduce prefill time, but
  stronger current-event projection could increase output length or lose
  reference/context resolution. It is an algorithm/input variant and not
  assumed semantically equivalent. Preserve any slowdown or quality loss.
- 12/24 expansion manifests fixed before new answers: respectively
  132 events/36 checkpoints and 205 events/60 checkpoints; all v1 windows
  retained. The 24-window source includes eight short trajectories. Official
  Small overlap 2/12 and 4/24, Medium 9/12 and 19/24; no held-out claim.
- Next actual run: `fast-compare-v4-e2e-batch2-context0-20261013`, same
  four windows; then fixed development-proxy Reader and scale experiments.

## H3 observed; expand conservative H2 while Reader is prepared

- `fast-compare-v4-e2e-batch2-context0-20261013`: Ours89.008189939 s,
  strong B3-c2 88.650322447 s. Both12/12 successful, zero failures,
  45 calls/64335 input/3810 output tokens, all coverage/dense checks pass.
  All frozen hashes and raw/checkpoint token sums verified. Ours is 0.404%
  slower than strong B3, so no strong-baseline gain is established.
- Context2→0: Ours latency -11.248%, B3 -11.589%, inputs -29.021%.
  Within-run semantic equality12/12, cross-configuration equality0/12;
  output semantics and reference resolution cannot be assumed unchanged.
  Retain as performance candidate only until source-grounded Reader checks.
- H2 and H3 each have paired method curves/negative results in
  `dev_iterations.csv`, satisfying the two-iteration development artifact,
  not final parameter selection or official quality acceptance.
- Next 12-window run expands the conservative context2 batch2 configuration,
  not an unvalidated context0 winner. Ours/B3 are measured first while the
  independent fixed Reader entry is completed on CPU; expanded Fresh is
  still necessary and is not imputed from the four-window baseline.

## H4a 12-window scale observed; fixed Reader running

- `fast-compare-v4-dev12-batch2-20261013`: Ours293.22374749 s,
  B3-c2 292.721794441 s, each36/36 completed, zero failures,132 live calls,
  267781 input/10913 output tokens,68 true Embedding calls/59523 input.
  All36 dense/snapshot checks per method pass. Ours still0.1715% slower.
- This expands the original conservative context2 batch2 configuration;
  no context0 quality equivalence or Fresh-expanded improvement is assumed.
  Independent CPU audit checks raw aggregation and unchanged original windows.
- Fixed Reader questions manifest hash
  `21a1daf384f9d6fba8843d67a37b9a0e41dc62d461f9fd4680f1562fd363c709`:
  12 auto-source questions, observation URL, attempted command and ordered
  two-action workflow. Exact-command diagnostic can penalize compression;
  it is not an official quality score. Source references/gold are evaluator
  only; Reader sees question+budget8 actually retrieved memory+ordinals.
- Current `dev-reader-v4-first-20261013` evaluates all7 valid method/config
  groups across c1/H2/H3,84 real Reader calls without answer replay/cache.
  Source recall and exact/token-F1 are separate; missing evidence/unknown
  remain in denominators. Next full24-window Fresh/Ours/strong B3 run.

## H4b source-literal/salient-v3 observed — quality gain with a real cost

- Construction run `fast-compare-v4-quality-v3-20261013` reused the fixed four
  windows and 12 checkpoints with source-literal evidence, salient-v3 input
  projection and bounded two-event views. B0/Ours-dev/B3-c2 completed 12/12
  each with zero failures and 12/12 snapshot checks. Reader run
  `dev-reader-v4-quality-v3-20261013` made 36 fresh calls with the fixed
  question manifest: all three methods reached 12/12 exact, token-F1 1.0 and
  source recall 1.0. This is an `auto_source_development_proxy`; official QA
  remains `not_evaluated`, and the old first-run/H4a negative rows are retained.
- Compared with the same-method H2 batch2 run on the same 4-window workload,
  H4b latency regresses substantially: Ours-dev **100.288225884 ->
  218.883346392 s** (reduction **-118.2543%**), B3-c2 **100.270336674 ->
  215.861274510 s** (reduction **-115.2793%**). Both retain 45 live extraction
  calls, but input/output tokens rise from 90640/3852 to 96242/5132.
- The major new cost is dense/source-literal publication: each H2 method used
  23 real Embedding calls, 87 new vectors and 20945 embedding input tokens;
  H4b uses **304 Embedding calls, 601 new vectors and 172266 embedding input
  tokens** per incremental method. Source-literal publication/Embedding is
  therefore the new bottleneck, not extraction-call count.
- Same-run H4b strong comparison remains a tie in quality and a speed negative:
  B3-c2 **215.861274510 s** versus Ours-dev **218.883346392 s**, reduction
  **-1.4000%**, with equal 96242 input/5132 output tokens, 45 calls each and
  12/12 paired structured semantic matches. No Ours-versus-B3 speed advantage
  is claimed.
- H4b is retained as a quality-positive but cost-negative development
  candidate. The next optimization should isolate/reduce the 601-vector/304-
  Embedding-call overhead while preserving exact source literals and bounded
  Reader views; it must be measured with the same quality proxy before any
  configuration is frozen.

## 2026-10-14 construction priority: adjacent joint extraction

Latest user request freezes query optimization and ranks construction/update candidates by necessary model work under a quality constraint. Query O is archived in `reports/query_freeze_20261014.md` (24→8 embedding requests, identical8 prompts; no build claim).

New complete-trajectory screen: `runs/construction-pair-v1/screen-web-g{1,2}`.7→4 event requests; total8→5 LLM calls; input38824→29581; output1528→1608; publish61.20→61.51s. No speedup in this small pair; all7 events/both notes/source mappings,5 literal change probes retained; no failures/truncation. Keep joint extraction for expanded input-cost evaluation, not as an established latency win.

Five complete web trajectories: `full10-web-{baseline,joint}`. Publish558.09→520.17s; known-success input252945→211444; output8216→8870. Both4 complete/3 correct. Joint introduced2 failed SDK calls (8 physical OOM attempts); failed usage unknown. Necessary successful event calls decrease, while output growth and note repair remain bottlenecks.

Full10 baseline:1339.04s,81 events/20 notes,8 complete/6 correct,124 SDK calls including32 failures. Server-log alignment reveals220 HTTP requests, including128 OOM attempts. These are separately counted, not disguised as necessary work. The scheduled V1 tail was canceled only after the web-joint child finished, preserving all results.

V2 common fix: input preflight18000 tokens, existing12000-char/state fallback before known oversized single requests, controller SDK retries0. All four cold-build cells get the same policy. New matrix `bash tools/run_construction_matrix_v2.sh`, independent empty memories, frozen full10/QA8. V1 is not silently relabeled or merged into the V2 comparison.

Actual prepared construction embedding inputs in V1 baseline: web79 vectors/76 unique, enterprise113/108 unique, total8 duplicate positions of192 (4.17%). Exact reuse remains a small bounded candidate; do not expect a large overall wall gain or expand a general cache platform. All mappings remain intact.

Next mechanism experiment: `tools/run_agentrunbook_updates.py`, same starting snapshot copied independently; B3 retains exact group request/vector caches; Ours validates per-event output dependencies and regroups only arrived adjacent dirty events. State/workflow correction contracts pass offline source-based checks. Live update costs remain unmeasured until the cold queue finishes.
