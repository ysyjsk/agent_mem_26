# Normal-question disagreement: evidence is present, ordering is wrong

Read-only review, 2026-10-16; no new inference or rescoring. Repaired normal QA
uses the existing ten-trajectory/domain updated snapshots. B3 scores7/8 and
Coalesced6/8. Their differing result on question87711b62 is not evidence of
missing source facts, nor proof of random fluctuation.

The question asks for the second field containing the word "type" in the
alphabetically ordered Change Request filter-field list. Both actual Reader
requests contain all three relevant observations from trajectory16143664:

| Bound source location | Field |
|---|---|
| state7 line691 | Contact type |
| state7 line749 | Task type |
| state7 line753 | Type |

Both branches' persisted trajectory16143664 state7 contain the same three
options. The gold `task type` matches their order. B3 answers `Task type`.
Coalesced ultimately answers `Type` after reasoning only about `Task type` and
`Type`, ignoring `Contact type`. Its explanation initially claims only one
matching field is shown and later refers to state2, whereas the actual supplied
source excerpts are state7. This is a visible evidence-use/ordering error, not
just case normalization or a harmless shorter equivalent answer.

This inspection rules out absence of these three decisive source lines from
this particular Coalesced request. It does not isolate why the two Readers
differ: their complete memory contexts differ, and the configured Reader uses
sampling. One saved comparison cannot separate context interference from
sampling variability or establish statistical quality equivalence. Preserve
the original scores, do not change the evaluator, and do not select another
Reader setting based on this question.

Raw evidence:

- `runs/focused-maintenance-v4/repair-20261016/normal-v1/enterprise-b3/prompt_rows.jsonl`
- `runs/focused-maintenance-v4/repair-20261016/normal-v1/enterprise-source_coalesced/prompt_rows.jsonl`
- each adjacent `per_question.jsonl`, question_id87711b62, including `response_raw`
- `runs/focused-maintenance-v4/formal/enterprise-update/literal_revision-{b3,source_coalesced}/memory_state/trajectories/16143664/trajectory.json`

Only the relevant source lines are quoted above; the original complete requests
and memories remain unchanged. This is error attribution within exposed
development data, not an additional independent quality trial.
