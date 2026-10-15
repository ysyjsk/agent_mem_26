# Development Reader quality audit

Run: `runs/dev-reader-v4-first-20261013`  
Aggregated table: `results/tables/dev_quality.csv`  
Question-level records: `runs/dev-reader-v4-first-20261013/qa_per_question.jsonl`

## Scope and status

This is a text-only development proxy, not an official benchmark evaluation. The
fixed question manifest contains 12 source-field questions (four observed URLs,
four attempted actions, and four ordered action pairs). It was run against
three construction checkpoints/configurations: c1 (`B0`, `Ours-dev`, `B3-c1`),
batch2 (`Ours-dev`, `B3-c2`), and batch2/context0 (`Ours-dev`, `B3-c2`). Thus
the initial aggregate has 7 method/configuration rows and 84 real Reader calls.
H4a (`runs/dev-reader-v4-temporal-c1-20261013`) adds the same c1 three methods
with a public-step temporal retrieval view, so `results/tables/dev_quality.csv`
now has 10 rows and 120 real Reader calls in total. H4b
(`runs/dev-reader-v4-quality-v3-20261013`) adds a further three rows with
source-literal/salient-v3 construction and bounded Reader views. The aggregate
now keeps those 13 live rows and appends 10 non-overlapping QA2 type-partition
rows (`exact_field` and `semantic`) from an evaluator-only rescore. The
underlying runs contain 156 original Reader calls plus 90 QA2 source-run calls
(246 completed calls total); the 10 appended rows must not be summed as extra
calls. All source-run calls completed, with zero Reader/runtime failures, and
the rescore made no new model or embedding calls. `official_qa_status` is
`not_evaluated`; `quality_scope` is
`auto_source_development_proxy`. References are deterministic projections of
source fields for auditing, not human gold labels.

## Aggregate results

| Construction run | Method | Exact | Token F1 | Source recall | Unknown | Reader s | Input / output tokens |
|---|---|---:|---:|---:|---:|---:|---:|
| e2e-c1 | B0 | 0/12 | 0.16760 | 0.6667 | 7 | 4.781 | 5004 / 118 |
| e2e-c1 | Ours-dev | 0/12 | 0.16760 | 0.6667 | 7 | 4.878 | 5004 / 118 |
| e2e-c1 | B3-c1 | 0/12 | 0.16760 | 0.6667 | 7 | 4.799 | 5004 / 118 |
| e2e-batch2 | Ours-dev | 0/12 | 0.15248 | 0.6250 | 7 | 4.772 | 5004 / 117 |
| e2e-batch2 | B3-c2 | 0/12 | 0.15248 | 0.6250 | 7 | 4.832 | 5004 / 117 |
| e2e-batch2-context0 | Ours-dev | 1/12 | 0.16506 | 0.5417 | 8 | 4.340 | 4987 / 102 |
| e2e-batch2-context0 | B3-c2 | 1/12 | 0.16506 | 0.5417 | 8 | 4.352 | 4987 / 102 |
| e2e-c1 + public-step-lexical-v2 | B0 | 0/12 | 0.23892 | 1.0000 | 4 | 5.914 | 2576 / 191 |
| e2e-c1 + public-step-lexical-v2 | Ours-dev | 0/12 | 0.23892 | 1.0000 | 4 | 5.928 | 2576 / 191 |
| e2e-c1 + public-step-lexical-v2 | B3-c1 | 0/12 | 0.23892 | 1.0000 | 4 | 5.974 | 2576 / 191 |
| quality-v3 + source-literals/salient-v3 | B0 | 12/12 | 1.00000 | 1.0000 | 0 | 12.930 | 14515 / 319 |
| quality-v3 + source-literals/salient-v3 | Ours-dev | 12/12 | 1.00000 | 1.0000 | 0 | 12.883 | 14543 / 319 |
| quality-v3 + source-literals/salient-v3 | B3-c2 | 12/12 | 1.00000 | 1.0000 | 0 | 12.875 | 14543 / 319 |

The original c1 and batch2 rows are exactly tied within each construction run
because the corresponding published memories and Reader settings are shared.
H4a's three rows are likewise tied because they use the same c1 memories and
only change retrieval. H4a improves source recall to 1.0 and token F1 to
0.23892, but exact remains 0/12, so it is not a sufficient quality result.
H4b adds source-literal/salient-v3 evidence and bounded views; all three
methods reach 12/12 exact with source recall 1.0. This is a positive
development result, but remains an auto-source proxy and is not official QA.
The context0 row gains one exact answer but loses source recall and retains
eight unknown answers; it is therefore a performance/quality diagnostic, not a
selected formal configuration. No row supports an Ours-versus-B3 quality win.

## QA2 rescore: exact fields versus semantic answers

Source run: `runs/dev-reader-v4-quality-v3-qa2-20261013` (18 questions per
method/configuration, 90 original Reader calls). Rescore output:
`runs/dev-reader-v4-quality-v3-qa2-rescored-20261013`. The rescore is
evaluator-only: it reused every answer, reference, token count and latency,
made zero new model/embedding calls, and corrected only five
`shipping_checkbox_state` rows where the old evaluator parsed the answer text
`"false"` as boolean `False` while the reference was the string `"false"`.

| Configuration | Method(s) | Type | Exact | Token F1 | Source recall | Unknown | Reader s | Input / output tokens |
|---|---|---|---:|---:|---:|---:|---:|---:|
| H2 negative control | Ours-dev, B3-c2 | exact_field | 0/14 | 0.21449 | 1.0000 | 6 | 7.081 / 7.108 | 6773 / 189 |
| H2 negative control | Ours-dev, B3-c2 | semantic | 1/4 | 0.25000 | 1.0000 | 0 | 1.359 / 1.293 | 1543 / 30 |
| H4b quality-v3 | B0 | exact_field | 14/14 | 1.00000 | 1.0000 | 0 | 14.886 | 17049 / 370 |
| H4b quality-v3 | Ours-dev, B3-c2 | exact_field | 14/14 | 1.00000 | 1.0000 | 0 | 15.014 / 14.975 | 17077 / 370 |
| H4b quality-v3 | B0 | semantic | 4/4 | 1.00000 | 1.0000 | 0 | 1.864 | 4849 / 17 |
| H4b quality-v3 | Ours-dev, B3-c2 | semantic | 4/4 | 1.00000 | 1.0000 | 0 | 1.861 / 1.927 | 4849 / 17 |

The mixed QA2 summaries are 1/18 exact (F1 0.22238, six unknowns) for both
H2 negative-control methods and 18/18 exact (F1 1.0, zero unknowns) for B0,
Ours-dev and B3-c2 under H4b. The table stores the two disjoint type
partitions, while those mixed summaries remain in the rescore run files; this
avoids double-counting the same 90 calls. QA2 is still
`auto_source_development_proxy`, not an official or held-out benchmark.

## Category audit

- `observed_url`: exact 0/4 for every row and token F1 0, despite source recall
  1.0. Retrieved evidence often describes navigation but does not retain the
  exact URL scalar, so this is a representation/serialization loss rather than
  only a nearest-neighbour miss.
- `attempt_action`: exact 0/4. c1 and batch2 source recall is 0.25 with a small
  token-F1 signal; context0 recall is 0.0. The retriever favors earlier,
  semantically similar actions and misses the requested final action.
- `workflow_order`: c1 exact 0/4 (F1 0.4750, recall 0.75), batch2 exact 0/4
  (F1 0.4297, recall 0.625), and context0 exact 1/4 (F1 0.4952, recall
  0.625). Retrieved final-step evidence can contain multiple actions from the
  same source position, so ordering and exact command identity remain
  ambiguous.
- H4a (`public-step-lexical-v2`) raises all three category recalls to 1.0,
  but exact remains 0/4 for each category (URL F1 0; action F1 0.18993;
  workflow F1 0.52682). This separates retrieval location from missing exact
  fields in the published evidence.
- H4b (`source-literals/salient-v3` with bounded views) reaches exact 4/4 in
  each category for B0, Ours-dev and B3-c2, with category source recall 1.0.
  The improvement comes from explicitly preserved, source-grounded literals;
  it does not establish an official benchmark score.

## Error evidence retained for the next repair

The question-level log shows four actionable failure modes without changing
the answer standard:

1. Exact URLs are often paraphrased or omitted even when the target source
   step is retrieved.
2. Lexical core retrieval spends its eight-item budget on older, overlapping
   actions; the target source step is absent for several action questions.
3. A source step can have multiple extracted facts (for example
   `0db80092:10`), and the Reader can select the wrong action from that step.
4. Compact extraction can drop high-value state/failure fields. Examples in
   the fixed source include the explicit post failure at `4a5f0d7f:3`, the
   `-- None --`/`selected=False` state at `0db80092:6`, and the `starts with`
   operator at `0db80092:11`.

These are retained as negative results. They are not repaired by changing the
gold or by reading raw source at query time.

## Audit conclusion and next experiment

The completed source runs are valid, fully logged quality checkpoints: 246/246
Reader calls finished when the 90-call QA2 source run is included. H4a proves
that step-aware retrieval fixes source location (`recall=1.0`) but exact
recovery is still 0/12. H4b then supplies bounded, source-literal evidence and
reaches 12/12 exact for all three methods on the original fixed proxy; QA2
also reaches 14/14 exact-field and 4/4 semantic for each H4b method. The QA2
rescore is a measurement correction, not a second experiment, and the five
boolean/string fixes must not be interpreted as a model gain. These are
meaningful development repairs, but not official QA or held-out paper results;
independent data must remain frozen and separate. The context0 setting remains
unselected. H4a/H4b/QA2 details are recorded in
`reports/quality_repair_log.md` and `reports/h4b_audit.md`.

Raw provenance for the original 12-question proxy is unchanged: question
manifest hash
`21a1daf384f9d6fba8843d67a37b9a0e41dc62d461f9fd4680f1562fd363c709`; source
hash and construction manifests are recorded in the Reader manifest and the
aggregated CSV. QA2 uses question manifest hash
`05c50115f55605236da34873c035045e4729a4fef43510d1e8139407b73a6a5b`;
rescore output SHA-256 is
`5c67933aa68868d4a3509c277ff20d137766b5aea39597e31a1931410521ed1d`, source
QA SHA-256 is
`3f5f20a64805879de7a5b438449a5846a96975cf5018202e3f2506f9c51413a6`, and the
score-function SHA-256 is
`aff8407c3865e87bc443840b54f6352b7a726763692d9e752dbc21b4281bd49a`.

## H6b — compact source-reference Embedding

Construction run: `runs/fast-compare-v4-quality-v3-compact-emb-20261013`.
Reader run: `runs/dev-reader-v4-quality-v3-compact-emb-qa2-20261013`.
The workload, four windows, checkpoint prefixes, source hash and QA2 v2
question manifest are fixed to the H4b protocol. H6b changes only the dense
Embedding render to `source-ref-v1`; it is not a new answer standard and is
not an official QA evaluation.

### Live construction and Embedding cost

Both methods completed 12/12 checkpoints with 0 failures, 12/12 snapshot and
dense checks, source coverage 1.0, 45 live extraction calls and
96,242/5,132 extraction input/output tokens. The measured construction-e2e
totals are:

| Method | Total s | Embedding calls | Embedding input tokens | Embedding s | New / reused vectors |
|---|---:|---:|---:|---:|---:|
| Ours-dev | 185.418812 | 304 | 32,172 | 14.102546 | 601 / 632 |
| B3-c2 | 183.646227 | 304 | 32,172 | 14.059886 | 601 / 632 |

The same-run strong-B3 comparison is a negative result: Ours-dev is
`-0.9652168080277806%` slower. Relative to the H4b full-render runs, compact
source-ref rendering reduces per-method Embedding input tokens from 172,266 to
32,172 and total time from 218.883346392 to 185.418811636 s for Ours-dev
(`15.28875325949563%` cross-run reduction), and from 215.861274510 to
183.646227382 s for B3-c2 (`14.923958547510388%`). These cross-run changes are
development descriptions, not repeated measurements or a frozen speed claim.

The construction audit found 24/24 completed checkpoints, 90/90 extraction
request-call hash matches, 608/608 completed live Embedding calls, all calls
marked `miss_live`, 24/24 valid snapshots and dense indexes, and 8/8 frozen
construction code hashes. The construction run made no replay substitution.

### Fixed QA2 v2 Reader result

H6b made 36 fresh Reader calls (18 per method), all completed with 36/36
request-call hash matches and valid public-step retrieval plans. The question
manifest hash is
`05c50115f55605236da34873c035045e4729a4fef43510d1e8139407b73a6a5b`, the
Reader settings hash is
`a7ca0d6ade765b619c6c8e8e9a5e40696b03236e392c27c6f16e5d8aefe33e48`, and the
H6b questions are byte-identical to QA2 v2. The disjoint quality rows appended
to `results/tables/dev_quality.csv` are:

| Method | Type | Exact | Token F1 | Source recall | Unknown | Input / output tokens | Reader s |
|---|---|---:|---:|---:|---:|---:|---:|
| Ours-dev | exact_field | 14/14 | 1.00000 | 1.0000 | 0 | 17,077 / 370 | 14.864483 |
| B3-c2 | exact_field | 14/14 | 1.00000 | 1.0000 | 0 | 17,077 / 370 | 14.901581 |
| Ours-dev | semantic | 4/4 | 1.00000 | 1.0000 | 0 | 4,849 / 17 | 1.849830 |
| B3-c2 | semantic | 4/4 | 1.00000 | 1.0000 | 0 | 4,849 / 17 | 1.870926 |

The mixed 18-question summaries are 18/18 exact, F1 1.0 and zero unknowns for
both methods, but the aggregate table stores only the two disjoint type
partitions so the same 36 calls are not counted twice. Compared with the
rescored H4b QA2 v2 rows, all 36 compared answers, references, score fields,
token counts and timings match; this is a fixed-protocol repeat, not a
different QA standard. Official QA remains `not_evaluated`.

### Independent dense retrieval audit and selection decision

The Reader result above does not certify the dense retriever. The independent
audit `runs/dense-retrieval-audit-v4-h6b-20261013` used 72 retrieval-only
queries, 72 query Embedding calls, 3,008 Embedding input tokens, zero failures
and zero Reader calls. For both methods, source recall stayed 0.888889, but
`literal_field_coverage` fell from 0.75 with H4b `full-v1` to 0.50 with H6b
`source-ref-v1`. The `workflow_order` slice fell from recall 1.0 to 0.5 and
literal coverage from 0.875 to 0.25. This is a real compact-render quality
regression, not a scoring artifact, and is not included as extra Reader rows.

Therefore H6b is retained as a cost/quality diagnostic and a candidate for
further repair, but is **not selected or frozen**. The next change must recover
the lost dense literal/workflow fields while preserving the measured Embedding
token reduction; no official QA conclusion is inferred.
