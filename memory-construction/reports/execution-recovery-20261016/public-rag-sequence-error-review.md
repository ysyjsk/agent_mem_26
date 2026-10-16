# Raw RAG / RAG+Notes: saved sequence error attribution

Reviewed 2026-10-16 by the execution assistant from the twelve saved update
snapshots and twenty-four actual Reader requests/answers. This is qualitative
inspection of development evidence, not a new QA experiment, blinded human
evaluation or full-history acceptance. No scores, parameters or methods changed;
the review makes zero model calls.

The five-history/domain sequence uses the same two target trajectories over
three dependent revisions. Each method retains its original5/12 score. All24
answers are complete and all24 actual requests are text-only. Image filenames
still occur in logging-only context items; they are absent from the serialized
`messages` actually sent to the Reader.

## Published facts versus supplied evidence

All twelve snapshots match their intended revised textual trajectory, and all
target-center raw slices retain the four tested fields: corrected Title or
record count, and unchanged Name or Type selection. Thus these answer errors
are not evidence that the raw maintenance interface lost the tested facts.
This limited source check does not certify generated Notes; their separate
semantic review is `rag-notes-sequence-memory-review.md`.

| Method | Complete /12 | Correct /12 | Incorrect: target-state field evidence absent | Incorrect despite supplied current count |
|---|---:|---:|---:|---:|
| Raw RAG | 12 | 5 | 6 | 1 |
| RAG+Notes | 12 | 5 | 6 | 1 |

The twelve evidence-absent answers are repetitions of only two question
templates, not twelve independent failures:

- **Name at web state4:** all six answers are `UNKNOWN`. The actual Reader
  payload contains raw results from other trajectories, but no target raw
  section or state4 Name evidence. RAG+Notes includes the target's generic
  forum-creation procedure, which describes filling Name without stating its
  observed value. The saved target slice still contains Name=`Cyberpunk`.
- **Type immediately after the failed click at enterprise state5:** all six
  answers are `UNKNOWN`. Other trajectories' raw slices and generic Notes do
  not establish that exact state. In particular, the target's Notes describe
  the later `select_option` recovery and Type=Normal workflow, not the
  pre-recovery state5 selection. The saved target slice still contains the
  Type combobox value `-- None --` and its selected option.

Every saved context reports budget pruning. However, `build_prompt_row` saves
`memory_context` **after** pruning. These artifacts establish absence in the
supplied context, not whether the target originally missed retrieval ranking
or was subsequently removed by the context budget. A copied target ID in
`Source raw query` is also not evidence that a target slice was retrieved.
No stronger ranking-versus-budget causal claim is made.

## Current evidence supplied but not used

Raw RAG enterprise round1 answers101 instead of103; RAG+Notes enterprise round3
answers101 instead of107. Both actual Reader inputs explicitly contain the
corrected line bound to `[0ab99e0c state 5 line 42]`. The responses are complete
boxed answers, not truncations or parse failures. Other context includes101,
but the brief responses do not reveal the reason it was preferred. These are
evidence-use failures despite the supplied current fact, not proven storage
failure, stale-vector leakage, or isolated sampling noise.

## Decision and reproducibility

Keep the frozen methods and all measured costs/scores; finish the registered
full-history comparison. Do not improve these exposed questions by changing
retrieval, budget, prompts or scoring. Equal aggregate scores conceal different
count-error rounds, while the unchanged-field failures recur across both
methods. Neither a small score gap nor source roundtrip alone establishes
quality equivalence.

Per-snapshot checks, per-question field evidence, context tokens, actual request
paths and SHA256 records are in `public-rag-sequence-error-evidence.json`.
Raw directories are
`runs/focused-maintenance-v4/public-repair-20261016/sequence/{web,enterprise}-r{1,2,3}-{raw_rag,rag_notes}/`.
