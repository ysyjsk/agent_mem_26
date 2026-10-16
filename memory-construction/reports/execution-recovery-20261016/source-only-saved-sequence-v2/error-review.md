# Source-only saved-sequence error review

Read-only follow-up, 2026-10-16. No model requests, scoring changes or method
changes. These are the existing five-trajectory/domain development histories,
three sequential corrections per target and twelve saved answers, not new
independent samples or full Small results.

## Evidence and findings

`queries.csv` records each saved question, unchanged score, exact edited source
lines present/missing in actual Reader messages, target-state source excerpts,
context-budget pruning and output-completeness flags. `snapshots.csv` checks
source roundtrip, event invalidation, unaffected descriptions/vectors and Notes.
The six snapshot checks pass and no invalidated event is retrieved in twelve
queries. Nine queries contain at least one changed line; only six contain every
changed line. The all-lines boolean is not a necessary condition for answering
an unchanged-field question and is not a semantic quality metric.

All four scored errors occur in enterprise; all six web questions are correct.
All twelve Reader outputs are complete and parseable. Context-budget pruning
is not output truncation.

| Round/question | Observed answer / gold | Evidence in actual messages | Supported diagnosis |
|---|---|---|---|
| enterprise r1 count_current | 101 / 103 | `[0ab99e0c state 5 line 42]` explicitly says 103 records; only this one of four edited lines is present | Correct current count reached Reader; not a total evidence-recall failure. Short answer gives no basis to identify the precise internal cause. |
| enterprise r2 selection_preserved | UNKNOWN / None | No target-state source excerpt or exact `Choose option for field: Type` observation; raw results refer to trajectory276f9dff | Missing state-specific field evidence in this query context. Unrelated occurrences of `None` do not establish the target value. |
| enterprise r3 count_current | 101 / 107 | Target-state line42 explicitly says 107; Reader explanation instead equates state5 with earlier state0/3 and quotes 101 | Visible state-attribution/conflicting-context error despite supplied corrected evidence. It does not demonstrate that an invalidated event was retrieved. |
| enterprise r3 selection_preserved | UNKNOWN / None | No target-state field source line; retained event3→4 and generic Notes mention the earlier/default `-- None --`, raw results again concern another trajectory | Earlier-state/generic evidence is available but lacks direct state5 support. The answer abstains; do not label this a proven source-storage loss. |

For comparison, enterprise r1 `selection_preserved` answers `-- None --`
correctly while also lacking the target-state field source line, and r2
`count_current` answers105 with just the same single edited count-line pattern.
Therefore the above are observable failure modes, not a deterministic causal
model or proof that one representation will always win.

The saved state5 text itself contains both the updated record count and
`combobox 'Choose option for field: Type' value='-- None --'` in every round.
Persistence checks and absence of invalidated retrieval do not by themselves
guarantee state-specific query coverage or correct interpretation. No scoring
rule is relaxed, and no Reader/retrieval tuning follows this review; the frozen
full-history matrix tests the existing method and baselines.

## Raw provenance and reproduction

Each row's actual requests and answers are respectively:

- `runs/focused-maintenance-v4/dev/sequence-final/enterprise-r{1,2,3}/literal_revision-source_only/revision_reader/prompt_rows.jsonl`
- the adjacent `per_question.jsonl` (`response_raw`, `response_parsed_boxed`, `score`)
- the parent `update_input.json`, `derived_quality_review.json`, and `memory_state/`

Reproduce the line/invalidation checks without inference, using a new output
directory (existing evidence is not overwritten):

```bash
/data/predator/ly/Mem/.venv/bin/python tools/check_saved_source_only_sequence.py \
  --output reports/execution-recovery-20261016/source-only-saved-sequence-v2-rerun
```

The generated CSV reports literal evidence presence; the error descriptions in
this document additionally inspect saved source roles, retrieved event headers
and Reader explanations. They are not automatic semantic certification.
