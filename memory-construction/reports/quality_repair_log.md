# Reader quality repair log

## H4a — public-step temporal retrieval

Run: `runs/dev-reader-v4-temporal-c1-20261013`  
Baseline: `runs/dev-reader-v4-first-20261013` c1 rows  
Aggregated table: `results/tables/dev_quality.csv`

### Hypothesis and controlled change

The first Reader run used `core_lexical_query_v1` with a budget of eight
evidence items. Its action questions frequently retrieved older, lexically
similar steps. H4a changed only the retrieval view to
`public-step-lexical-v2`: the question's public source-step number is mapped to
the corresponding published evidence position, with lexical retrieval as the
fallback. The 12 questions, construction run, Qwen Reader, output budget,
temperature and scoring references were unchanged. H4a made 36 fresh Reader
calls (12 each for B0, Ours-dev and B3-c1); all completed and none read the raw
source or gold answer at query time.

### Measured result

| c1 method | Exact | Token F1 | Source recall | Unknown | Reader s | Input / output tokens |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 0/12 | 0.23892 | 1.0000 | 4 | 5.914 | 2576 / 191 |
| Ours-dev | 0/12 | 0.23892 | 1.0000 | 4 | 5.928 | 2576 / 191 |
| B3-c1 | 0/12 | 0.23892 | 1.0000 | 4 | 5.974 | 2576 / 191 |

Relative to the original c1 rows, source recall increases from 0.6667 to
1.0000, unknown answers fall from 7 to 4, and token F1 rises from 0.16760 to
0.23892 (+0.07131). Exact recovery remains **0/12 for all three methods**.
Reader wall time increases from roughly 4.78–4.88 s to 5.91–5.97 s per
12-question batch; this is a quality diagnostic, not a construction latency
claim. The three methods remain tied because they read the same c1 published
memories; no Ours-versus-B3 quality advantage is established.

### Interpretation

H4a fixes the primary retrieval-location failure: every target source position
is now present in the retrieved evidence. It does **not** fix loss of exact
content during construction/serialization. The category rows remain exact
0/4 for observed URLs, attempt commands and workflow-order arrays. In
particular, URL values are still absent/paraphrased, and action facts can be
semantic descriptions rather than the exact command string. Therefore this
run cannot be reported as sufficient quality or as a solved Reader pipeline.

The result is retained as a positive retrieval / negative exact-field
checkpoint. The next candidate is an explicit, versioned source-field view
alongside semantic facts (exact URL, action command, control value and
selection/disabled state, and failure or warning span), followed by the same
frozen 12-question paired Reader run. The old c1/batch2/context0 rows remain
in `dev_quality.csv`; no low score was overwritten and no answer standard was
changed.

Provenance: question manifest hash
`21a1daf384f9d6fba8843d67a37b9a0e41dc62d461f9fd4680f1562fd363c709`; H4a
retrieval mode `public-step-lexical-v2`; Reader settings hash
`62b388b5cde1801975e0a11c9d3c2140407dcab1ff62b6412a31f30525e3ebf2`.
Official QA remains `not_evaluated`.

## H4b — source-literal/salient-v3 with bounded views

Runs: `runs/fast-compare-v4-quality-v3-20261013` and
`runs/dev-reader-v4-quality-v3-20261013`. H4b keeps the same 4-window/12-
checkpoint workload and the same 12-question manifest. It adds a versioned
`source-literals-v1` evidence view and salient-v3 construction projection,
then feeds the Reader bounded public-step views (`public-step-lexical-v2`,
budget 8, `include_views=true`). Extraction is limited to a two-event prefix,
6000-character input, strict JSON and two compact facts per current event.
Reader response caching is disabled.

All 36 construction checkpoints and 36 Reader questions completed without
failure. The Reader result is **12/12 exact, token F1 1.0 and source recall
1.0** for B0, Ours-dev and B3-c2, with zero unknown answers. Category rows are
also 4/4 exact for observed URLs, attempted actions and workflow-order arrays.
This is the first positive exact-field result after the H4a retrieval-only
repair; H4b retains the old first-run and H4a negative rows in
`results/tables/dev_quality.csv` rather than replacing them.

The quality gain is attributable to explicitly preserved, source-grounded
literals and bounded views, not to changing references: the question manifest,
answer format and scoring stayed fixed. An audit of all 183 construction and
36 Reader request payloads found no `reference`, `expected`, `gold`,
`answer_key`, `reference_hash` or `raw_source` markers; all construction and
Reader calls were live cache misses. The run manifests record construction
config `ffb53b936e95eacfebcfc1feadb480af3e99b6158aee2eecb8e273d77eb12da9`,
Reader config `6c4cb0cef1de4d23f5d460f9a738369140b2425acb2784d05dbebe50a70579a3`,
and Reader settings hash
`a7ca0d6ade765b619c6c8e8e9a5e40696b03236e392c27c6f16e5d8aefe33e48`.
All eight construction frozen-code copies match their manifest SHA-256 values;
the Reader manifest records five code hashes. Official QA remains
`not_evaluated`, so H4b is a positive `auto_source_development_proxy`
checkpoint, not a final paper-quality claim.

## QA2 — evaluator-only rescore with exact/semantic split

Source run: runs/dev-reader-v4-quality-v3-qa2-20261013  
Rescore run: runs/dev-reader-v4-quality-v3-qa2-rescored-20261013  
Aggregated type rows: results/tables/dev_quality.csv

QA2 is an 18-question extension of the fixed development Reader proxy: the
original 12 questions are retained and six questions cover outcome/failure and
control-state fields. The split is 14 exact_field questions and 4 semantic
questions. It contains 90 original Reader calls (H2 Ours-dev/B3 negative
control plus H4b B0/Ours-dev/B3-c2). The rescore is evaluator-only: it reused
the original answers, references, token usage and latency, made zero model or
embedding calls, and is explicitly not a new experiment.

The old evaluator treated the answer text "false" as JSON boolean False,
which did not exactly match the reference string. The unified scorer corrected
only five shipping_checkbox_state rows (old exact 0 → new exact 1); their
token F1, answer text, references, inputs/outputs and timings are unchanged.
No question, reference, construction result or answer standard was modified.

| Configuration | Method(s) | Type | Exact | Token F1 | Recall | Unknown |
|---|---|---|---:|---:|---:|---:|
| H2 negative control | Ours-dev, B3-c2 | exact_field | 0/14 | 0.21449 | 1.0000 | 6 |
| H2 negative control | Ours-dev, B3-c2 | semantic | 1/4 | 0.25000 | 1.0000 | 0 |
| H4b quality-v3 | B0, Ours-dev, B3-c2 | exact_field | 14/14 | 1.00000 | 1.0000 | 0 |
| H4b quality-v3 | B0, Ours-dev, B3-c2 | semantic | 4/4 | 1.00000 | 1.0000 | 0 |

The mixed summaries are 1/18 exact with F1 0.22238 and six unknowns for both
H2 negative-control methods, versus 18/18 exact with F1 1.0 and zero unknowns
for each H4b method. Ours-dev and B3 remain tied on quality; B0 also reaches
the same H4b score. The aggregate table stores the two disjoint type
partitions rather than duplicating the mixed rows, so the same 90 calls are
not counted twice. official_qa_status remains not_evaluated and
quality_scope remains auto_source_development_proxy.

Rescore provenance: QA2 question-manifest hash
05c50115f55605236da34873c035045e4729a4fef43510d1e8139407b73a6a5b;
source QA JSONL SHA-256
3f5f20a64805879de7a5b438449a5846a96975cf5018202e3f2506f9c51413a6;
rescore output SHA-256
5c67933aa68868d4a3509c277ff20d137766b5aea39597e31a1931410521ed1d;
score-function SHA-256
aff8407c3865e87bc443840b54f6352b7a726763692d9e752dbc21b4281bd49a.
The manifest records rescored_rows=90, score_corrections=5,
new_model_calls=0, new_embedding_calls=0, and latency_tokens_reused=true.

## H6b — source-ref Embedding cost candidate and dense regression

Construction run: `runs/fast-compare-v4-quality-v3-compact-emb-20261013`.
Reader run: `runs/dev-reader-v4-quality-v3-compact-emb-qa2-20261013`.
Fixed QA2 v2 questions and Reader settings are unchanged from H4b; the
construction workload is the same four windows and 12 checkpoints per method.
H6b replaces full dense Embedding rendering with compact `source-ref-v1`.

Both Ours-dev and B3-c2 completed 12/12 construction checkpoints, snapshot and
dense checks with no failure and source coverage 1.0. Each used 45 live
extraction calls (96,242/5,132 input/output tokens), 304 live Embedding calls,
32,172 Embedding input tokens, 601 new vectors and 632 reused vectors.
Construction-e2e totals are 185.418811636 s for Ours-dev and 183.646227382 s
for B3-c2; Embedding times are 14.102545678 and 14.059885565 s. Ours-dev is
0.9652% slower than strong B3 in the same run. H4b full-render totals were
218.883346392 and 215.861274510 s with 172,266 Embedding input tokens each.
The resulting cross-run time reductions (15.2888% Ours-dev, 14.9240% B3-c2)
are unreplicated development descriptions, not stable performance claims.

H6b made 36 fresh Reader calls. Both methods retained exact_field 14/14 and
semantic 4/4 exact, F1 1.0, source recall 1.0 and zero unknowns. Each method
used 17,077/370 Reader tokens for exact_field and 4,849/17 for semantic. The
aggregate stores only these four disjoint type rows, not mixed duplicates.
All 90 extraction and 36 Reader request-call hashes match; all 608 Embedding
calls completed live; all 24 construction snapshot/storage/dense index paths
exist and eight frozen construction code hashes verify. The QA2 v2 manifest
hash remains
`05c50115f55605236da34873c035045e4729a4fef43510d1e8139407b73a6a5b`.

The independent dense audit
`runs/dense-retrieval-audit-v4-h6b-20261013` is a real negative result:
72/72 queries completed, with 72 query Embedding calls, 3,008 input tokens,
zero failures and no Reader calls. Both methods kept source recall 0.888889,
but literal field coverage fell from 0.75 (`full-v1`) to 0.50
(`source-ref-v1`). The workflow-order slice fell from source recall 1.0 to
0.5 and literal coverage 0.875 to 0.25. The fixed lexical/public-step Reader
18/18 result remains independently valid; it cannot override this dense
retrieval loss or certify the compact render as quality-preserving.

Decision: retain H6b cost savings and the dense negative result, but do not
select or freeze H6b. Official QA remains `not_evaluated`. Further H6
iterations are paused while the user-prioritized AgentRunbook-R Small main
line proceeds; no H6a aggregate rows are added by this pause.
