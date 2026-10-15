# 12-window batch2 development-scale audit (2026-10-13)

Run: `runs/fast-compare-v4-dev12-batch2-20261013`.

This is a read-only CPU audit of an already completed live GPU run. No model
was loaded, no experiment was rerun, and no source/runner/queue/STATUS file
was changed. The run is development-only: text-only construction through
real dense publication, excluding model load/warmup, Reader, Judge and
post-publication QA. It is not a Freshness or official Small/Medium result.

## Completion and headline result

The predeclared nested manifest contains 12 windows, 132 source events and
36 checkpoints per method. Both methods complete **36/36 checkpoints** and
**132/132 live extraction calls**, with no failed checkpoint/model call.
Each checkpoint has source coverage 1.0, a valid core snapshot and a dense
publication check. There are 264 extraction-call rows and 136 actual batch
rows (128 width-2, 8 width-1).

| Method | Total s | Initial builds s | Later checkpoints s | Live calls | Input / output tokens | Embedding calls / input tokens | Snapshot checks |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ours-dev | 293.223747490 | 101.513937753 | 191.709809737 | 132 | 267781 / 10913 | 68 / 59523 | 36/36 |
| B3-c2 | 292.721794441 | 101.064754485 | 191.657039956 | 132 | 267781 / 10913 | 68 / 59523 | 36/36 |

Ours-dev is **0.501953049 s slower** than B3-c2, a **0.17148% regression**;
the later-checkpoint difference is 0.052769781 s (0.02753%). Extraction
model wall is 266.829444500 s versus 266.438676347 s. This is a near tie,
not evidence of a strong-B3 advantage for either method. All 36 paired
checkpoint semantic hashes match. Official QA is `not_evaluated`.

## Reproducibility and provenance

- Source SHA256 is `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
- Run workload hash is `1a4bf4a56610caf0dd94a77940e56636217a9a7d2402c187a57084eb07624077`;
  independently recomputed from the manifest.
- Config hash is `7d74bd1f406642c0818f03690f4f7cbd7a17122b2f006387d9090cde68716dec`;
  independently recomputed from runtime/settings/model/embedding/code hashes.
- All seven frozen-code hashes listed in the run manifest match the copied
  bytes: prompt, construction, batched extraction, dense publication,
  local backend, strong baseline and runner.
- The scale manifest exactly reproduces `tools/freeze_dev_scale.py` from
  `fastloop_dev_v1.json`, including its base-manifest hash, balanced
  six-enterprise/six-web selection and official-exposure metadata. Its first
  four windows equal v1 byte-for-byte; the eight added windows are
  `297633cb`, `75c77677`, `7b5fd273`, `07d1d6f4`, `3ddd6f8b`, `07442c0d`,
  `26783e8b` and `3c27cae4`.
- The run's supervised stdout contains all 72 checkpoint records. The run
  manifest and source manifest were frozen before measurement; no window was
  selected from results.

The nested scale workload lists the allowed B0/Ours/B3 set, while the
top-level actual run contains only `Ours-dev` and `B3-c2`. The generic
`paired_successful_checkpoints=0` counts B0/Ours pairs only, not the 36
strong-B3 pairs recorded in `strong_paired_checkpoints.json`. Do not mistake
that zero for missing strong paired evidence, or invent a measured B0 row.

## Request, batch and token audit

All 264 call IDs are unique and each has one matching request-log row.
Independently recomputed request and response hashes, usage sums and
checkpoint aggregation have zero mismatches. Every call is
`completed/miss_live`, `finish_reason=stop`, text-only, temperature 0 and
max_tokens 256. Every actual generation group is width 2 except the eight
width-1 tail groups; both methods use the same ordered request-hash grouping
at every window/checkpoint. Their 132 corresponding events have identical
request hash, response hash, input tokens and output tokens.

The first four windows are unchanged relative to
`fast-compare-v4-e2e-batch2-20261013`: all 45 event request hashes and raw
response hashes match, and both methods' 12 checkpoint semantic fields
remain identical. Expansion adds 87 events and 24 checkpoints per method;
these are genuinely new live calls, not replayed old responses.

Input tokens range from 1284 to 2265 and output tokens from 43 to 112 over
the 132 unique events per method. Context lengths are 0 for 12 events, 1 for
12 and 2 for 108; all contexts are prefix-only, same-trajectory and contain
no future event. Every extracted source reference names only the current
event. Ours-dev has 161 facts in the eight new windows: 111 attempts,
42 observations, 6 intents and 2 explicit failures. Across all 12 windows
there are 248 facts: 160 attempts, 78 observations, 8 intents and 2
failures. These are model representations, not source-grounded quality
scores.

## Snapshot and semantic checks

All 72 persisted snapshot payloads pass `validate_snapshot`. Their event
lists exactly match the normalized source prefix (72/72 direct comparisons),
their recorded semantic hashes recompute, and source coverage is 1.0 for
every row. Direct Ours/B3 comparisons match `events`, `evidence`,
`state_view`, `workflow_view`, `relations`, `aliases`, `index` and `nodes`
for all 36 pairs. This is correctness and equivalence evidence, not Reader
accuracy.

The audit did not yet use the dense helper's full vector-by-vector numerical
inspection; the run's own `dense_checks_passed=36` is retained. A separate
read-only dense-artifact audit is requested for exact vector/hash/norm and
old-epoch checks before declaring the dense layer fully audited.

## New-window source risks

The eight added windows completed without runtime failures, but source-level
negative/terminal cases expose quality risks that are not fixed by equal
semantic hashes:

- `297633cb:8` has an explicit observed `failure` outcome. The model keeps
  an attempt plus a failure fact, which is appropriate; it must not be read
  as successful completion.
- `75c77677:11` has an explicit `failure` outcome while sending a travel
  summary. The model emits two `attempt` facts and does not preserve a
  failure-kind fact; a Reader must not infer that the reported duration was
  verified merely from the message action.
- `07442c0d:8` has a source-visible “blocked by network security” failure.
  The model emits a navigational attempt and a failure value; retain this
  negative case in quality evaluation.
- `07d1d6f4:8` has an explicit `success` outcome. The model stores two
  attempt/report-claim facts rather than a confirmation; report claims are
  not equivalent to verified UI state.
- `3c27cae4:0` and `3c27cae4:5` expose “Not Found”/404 states. One records
  only the filled search box, while the latter records an explicit 404
  observation. This illustrates inconsistent negative-state coverage.
- `3c27cae4:3` contains a visible “Pipeline: failed” link. The extracted
  fact says only that the branches page was opened; the failed pipeline
  signal is not preserved.

These examples are development quality leads, not an official answer score.
Reader input must use only the published memory/evidence budget; raw source
is reference gold for evaluation, not an unreported Reader workaround.

## Timing boundary and limitations

Extraction is 90.9986% of Ours total wall and 91.0211% of B3 total. Dense
publication boundary time is 24.7101/24.6110 s; deterministic kernel work
excluding extraction is only 1.6842/1.6721 s. The Ours/B3 difference is
therefore much smaller than normal model/runtime variation in this run.

The run has one repeat and 12 nested development windows. It demonstrates
scaling and paired reproducibility, not statistical significance, held-out
generalization or official benchmark accuracy. Do not present the 0.17%
near-tie as a win, and do not compare this e2e total to the earlier c1 run
without acknowledging different run scope/order/runtime conditions. B0 is
not present in this run; no B0 number is imputed. QA/Judge/Reader remain
separate required evidence.
