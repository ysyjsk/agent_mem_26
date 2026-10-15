# Independent construction-e2e c1 audit (2026-10-13)

Run: `runs/fast-compare-v4-e2e-c1-20261013`.

This is a CPU-only, read-only audit of completed live experiment artifacts.
No c1 experiment was rerun; no GPU, source edit or queue update was made.
The sole audit artifacts are this report and the preceding kernel audit.

## Accepted scope and result

The same four development windows contain 45 unique source events and 12
requested prefix checkpoints per method. All **36/36 checkpoints** and
**183/183 extraction calls** complete successfully. Each method has 12/12
valid core snapshots and 12/12 valid dense publications, with complete
source-event coverage. This is text-only construction through dense-index
publication, excluding cold model loading, warmup, Reader/Judge and
post-publication checks. It is not streaming Freshness or official QA.

| Method | Total s | Initial-build s | Later-checkpoint s | Extraction calls | Input / output tokens | Embedding calls | Embedding input tokens | New / reused vectors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 | 286.443673525 | 49.129737260 | 237.313936265 | 93 | 183591 / 7943 | 47 | 43483 | 181 / 0 |
| Ours-dev | 139.111877041 | 48.855205712 | 90.256671329 | 45 | 90640 / 3842 | 23 | 20929 | 87 / 94 |
| B3-c1 | 138.511807269 | 48.695270825 | 89.816536444 | 45 | 90640 / 3842 | 23 | 20929 | 87 / 94 |

Ours-dev reduces total measured wall time **51.4348% versus repeated Fresh**.
Against legitimate cached B3-c1 it is **0.4332% slower**, or 0.600070 s
across all 12 checkpoints. Later-checkpoint service is 0.4900% slower.
This repeat=1 small sample supports a near tie/negative development result,
not an Ours advantage over strong B3 and not a statistical significance
claim. Both methods perform identical inference and semantic-vector work.

## Independent table and request reconciliation

The auditor recomputed totals from `checkpoint_metrics.jsonl` and
`llm_calls.jsonl`, then compared every field in:

- Run-local `summary.csv` (three rows).
- `results/tables/first_compare_e2e.csv` (B0/Ours-dev, two rows).
- `results/tables/dev_strong_compare.csv` (three rows).
- Run-local `metrics.json` summaries.

There are zero field mismatches. All checkpoint request counts, input/output
tokens and summed serial extraction wall times reconcile exactly within
floating-point tolerance. All extraction calls have actual batch size 1,
`finish_reason=stop`, no images, temperature=0, max_tokens=256 and strict
JSON. Usage totals add correctly. All 183 IDs are unique and each has an
identical request-log record; independently recomputed request and response
hashes have zero mismatches.

All 45 unique event requests match across **all three methods**, including
input tokens, output tokens and raw response hashes. B0 has 16 events
computed three times, 16 twice and 13 once; Ours and B3 compute each once.
The 183 requests/responses also match the same-event accepted kernel run
`fast-compare-v4-corrected-20261013`, with zero differences. This establishes
request matching, not comparability of wall time across those two separate
runs: their scopes and observed execution speeds differ.

Context lengths are 0 for four unique events, 1 for four, and 2 for 37.
No future or cross-trajectory context is present. All 87 unique facts cite
only their current event. They contain 49 attempts, 3 intents and 35
observations, with no unsupported success promotion by event kind. All
subjects are `agent`; predicates are `action`, `goal` and `observation`.
The compact/generic representations still require source-grounded Reader
quality checks. Matching output does not establish that important visible
state is adequately represented.

## Wall-time decomposition

The following stages are measured at their existing instrumentation
boundaries; at c1 no batch-wall deduplication is needed.

| Method | Extraction s | Other kernel s | Embedding s | Dense index s | Dense descriptor publish s | Remaining boundary overhead s |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 270.821480747 | 0.644294320 | 12.154861975 | 2.808089893 | 0.010582977 | 0.004338671 |
| Ours-dev | 129.987658085 | 0.487572879 | 5.843478729 | 2.780269016 | 0.010132317 | 0.002741749 |
| B3-c1 | 129.409718123 | 0.614699735 | 5.845312276 | 2.629359884 | 0.010415238 | 0.002279875 |

Extraction remains 94.5462%/93.4411%/93.4287% of B0/Ours/B3 total wall;
Embedding is approximately 4.2% for all three. Other deterministic kernel
work is only 0.35% of Ours wall. Mean extraction calls are
2.912059/2.888615/2.875772 s respectively. Ours saves 0.127127 s in local
kernel work versus B3, but that is outweighed by a 0.577940 s extraction
timing difference and approximately 0.150909 s dense-index difference.
These small component differences are observational, not causal proof.

`embedding_total_s` is the dense publisher's Embedding-stage boundary;
`dense_stats.index_s` and `publish_s` are separate. The report generator's
phrase "local graph/cache/view/publish remainder" for total minus
extraction also contains real Embedding time and must not be interpreted as
pure deterministic overhead.

## Core snapshots and B3 behavior

All 12 B0/Ours and 12 B3/Ours pairs have equal semantic hashes. Direct full
field comparisons additionally show exact equality of
`events/evidence/state_view/workflow_view/relations/aliases/index/nodes` in
all 12 triplets. Differences are method-owned store paths, metadata and
publication history; B0 also has different snapshot IDs at its eight later
fresh rebuilds. Ours and B3 snapshot IDs match at every checkpoint.

B3 revalidates 93 arrived-prefix extraction requests, obtains 48 valid
method-owned cache hits, prepares 45 real misses, and reports zero invalid
cache entries or failed preparations. Its four trajectory/environment
partitions are conservatively recomposed at every checkpoint. All 477
reported invalidated nodes are recomposed, including initial builds.
Independent method/window caches are created by the frozen runner;
Fresh resets both construction and semantic Embedding cache per checkpoint.

Do not interpret Ours `reused_nodes=248` versus B3 `reused_nodes=48` as the
same measurement. Ours counts reused construction-node IDs; B3 labels its
48 exact-request extraction cache hits as reused nodes. Likewise B3's
invalidation count includes its initial full partition recomposition.
`strong_stats.actual_batch_size=0` is the serial-path sentinel in all 12
B3 rows, not evidence of zero inference: call logs and outer checkpoint
`actual_concurrency=1` correctly establish 45 serial live calls.

## Independent dense-artifact and persisted-epoch checks

A second read-only auditor reconciled all 93 Embedding calls, including
actual request hashes, usage and response vector hashes against persisted
vectors. Every call is `completed/miss_live`. Per-checkpoint call counts,
input tokens and new/reused vectors match the checkpoint log with zero
mismatches. Raw Embedding wrapper call time is 11.466594/5.514898/5.526075 s
for B0/Ours/B3. These figures differ legitimately from the publisher's
12.154862/5.843479/5.845312 s Embedding-stage boundary: raw call time stops
before vector hashing and JSONL logging, while the publisher boundary
includes that recording overhead. Do not add both measurements together.

All 36 Dense files match their content hashes, descriptors, evidence IDs,
rendered-content hashes, pinned snapshot core and model-settings hashes.
Per-window checkpoint vector counts are 8/16/23, 8/15/17, 8/16/24 and
8/15/23. Across these publications 543 vectors (2,224,128 float coordinates)
were inspected: all are 4096-dimensional, finite, nonzero, and unit-norm
within 0.9999999036441699–1.0000001062379547. This is not a quantized index:
the model runs bfloat16, pools/normalizes in float32 and saves JSON floats.

Read-only SQLite reopen of all 36 pinned snapshots matches Dense core
hashes after conversion through `Snapshot.to_dict()`. The persisted graph
is an additional payload field, not a mismatch; graph dependency contents
also match in all 12 triplets after ignoring set-list ordering. All 12
`dense/published.json` descriptors point to the proper final checkpoint.
Sixteen earlier epochs remain readable after subsequent publication;
the other 20 are each store's current epoch. These old-epoch reads were
performed by the audit after the run, not by a concurrent-reader test.

**Dense equality is not bitwise equality across all three methods.**
Ours/B3 vectors match bit-for-bit at every checkpoint. Of the 181 paired
B0 checkpoint vectors, 23 differ from the corresponding Ours/B3 vector:
five at `170f5570-prefix9/cp9`, six at `4a5f0d7f-prefix12/cp12`, and 12 at
`ec6c60c2-prefix12/cp12`. Maximum coordinate difference is 0.0041279569;
maximum L2 difference is 0.0177162140; minimum paired cosine is
0.9998430679. Inputs are identical but fresh/incremental Embedding batch
groupings differ; numerical batch effects are a plausible explanation,
not a proven diagnosis. Retrieval-ranking and Reader impact are unmeasured.

The publisher's `index_s` includes core pinning, cache preparation,
file writing and its pre-publication read-back, not only serialization.
End-to-end timing includes `publish_dense`'s internal read-back and
descriptor publication, while the separate `read_dense` call and core
checks after it are outside the measured boundary. Per-checkpoint
`e2e-minus-kernel` and Dense elapsed agree within 1 ms.

## Provenance and interpretation cautions

- Config SHA256:
  `e9c695de3ca9bc147dc7797335793fad30f01e4fe898d17826ad1bb1866a0b20`.
- Workload SHA256:
  `d8a8ed49ddb813d487534108fb8e1529b26773cbe9fb561937d98596ddcce388`.
- Source SHA256:
  `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
- Construction resident backend:
  `transformers-qwen:Qwen3.5-9B:061f4abd834f882d:cuda:0`.
- Embedding resident backend:
  `transformers-embedding:Qwen3-Embedding-8B:c84150183c0dee2b:cuda:1`.
- Frozen prompt/implementation copies live under `frozen_code/`.

All six frozen-code file SHA256 values match the manifest; actual source
bytes match the recorded source SHA256. All 36 checkpoint records also
match the supervised process's progress stdout. Construction uses GPU0,
Embedding GPU1; Embedding settings are batch_size=4, max_length=1024,
bfloat16. Backend fingerprints are not hashes of every weight shard, and
six frozen files do not imply that the entire environment is frozen.
The current runner has subsequently changed: use the run-local frozen
runner when interpreting this completed run.

The top-level manifest correctly records three methods and
`construction_e2e`; its nested `workload` retains the original selection
manifest's two-method/kernel labels. Use the top-level actual-run scope and
tables when describing this run. The generated report's concluding
"Next: add dense...and B3" line is stale because both are now measured.
These metadata/prose caveats do not change raw run measurements.

Official QA remains `not_evaluated`. The current run is append-only,
single-repeat, four-window development evidence; neither revision/retraction
robustness nor a formal Small/Medium benchmark is established. The next
performance test should offer genuine batch2 to both strong B3 and Ours at
identical prompts/budgets and independently owned stores. Retain this tie
and every batching regression instead of relabeling the Fresh-relative win
as a strong-baseline win.
