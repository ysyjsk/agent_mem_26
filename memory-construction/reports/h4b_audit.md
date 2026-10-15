# H4b audit — source-literal/salient-v3 with bounded views

Date: 2026-10-13  
Construction run: `runs/fast-compare-v4-quality-v3-20261013`  
Reader run: `runs/dev-reader-v4-quality-v3-20261013`

## Completion and measured result

The fixed text-only workload has 4 windows and 12 checkpoints per method. The
construction run completed 36/36 checkpoints and 183 live extraction calls
(B0 93, Ours-dev 45, B3-c2 45), with zero failed checkpoints/model calls and
12/12 snapshot checks for each method. Construction totals were B0 475.425 s,
Ours-dev 218.883 s, and B3-c2 215.861 s; these are `construction_e2e`
measurements, not Reader latency or official Freshness.

The Reader run completed 36/36 questions with zero failures. All three methods
have the same development-proxy result: **12/12 exact, token F1 1.0, source
recall 1.0, and zero unknown answers**. `official_qa_status` remains
`not_evaluated`; this is an `auto_source_development_proxy`, not a human or
official benchmark score. The rows are appended to
`results/tables/dev_quality.csv`; H4a and the original low-score rows remain.

## Controlled variant and bounded information

H4b is explicitly `H4b_source_literals_salient_v3`. Construction uses
`source-literals-v1`, salient-v3 input projection, a two-event prefix context,
6000-character model-input budget, strict JSON output and at most two compact
model facts per current event. The prompt instructs the model to preserve exact
source literals, but does not provide evaluator references or answer labels.

Reader uses `public-step-lexical-v2`, retrieval budget 8, `include_views=true`
and bounded snapshot evidence. Every retrieval plan records
`information_scope=public_question+derived_evidence_provenance+snapshot_ordinals_only`,
`step_filter_respected=true`, `selected_from_snapshot_evidence=true`, and no
out-of-prefix source positions. Reader response cache is false; all 36 Reader
rows are `cache=miss_live`. Construction calls likewise report `cache=miss_live`.

An audit over all 183 construction requests and 36 Reader requests found no
`reference`, `expected`, `gold`, `answer_key`, `reference_hash`, or `raw_source`
markers in request payloads. The deterministic question manifest and source
field hashes are evaluator-side records, not sent as answer keys to the model.

## Provenance hashes

- Source SHA256: `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`
- Question manifest: `21a1daf384f9d6fba8843d67a37b9a0e41dc62d461f9fd4680f1562fd363c709`
- Construction config: `ffb53b936e95eacfebcfc1feadb480af3e99b6158aee2eecb8e273d77eb12da9`
- Reader config: `6c4cb0cef1de4d23f5d460f9a738369140b2425acb2784d05dbebe50a70579a3`
- Reader settings: `a7ca0d6ade765b619c6c8e8e9a5e40696b03236e392c27c6f16e5d8aefe33e48`

The construction manifest records eight code SHA-256 entries and frozen copies
under `runs/fast-compare-v4-quality-v3-20261013/frozen_code/`; all eight
copies were independently re-hashed and matched. The Reader manifest records
five code SHA-256 entries (construction, local backend, source literals,
temporal retrieval and Reader runner); its run-level manifest retains those
hashes and the settings hash above.

H4b is therefore a valid positive development checkpoint for source-field
fidelity under this fixed proxy, but it is not yet an official QA or held-out
paper result. Independent evaluation must remain frozen and separate from
these development questions.
