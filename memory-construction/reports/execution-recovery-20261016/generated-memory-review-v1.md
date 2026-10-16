# Generated-memory review of the repaired development comparison

Date: 2026-10-16. Reviewer: execution assistant inspecting saved source edits,
generated event fields, current-evidence blocks and generated notes. This is
an explicit qualitative review, not a blinded human study or GPT Judge score.
No generation or scoring rule was changed by this review.

## Evidence and scope

For each domain, inspect `derived_quality_review.json` and `update_input.json`
under `runs/focused-maintenance-v4/formal/{domain}-update/literal_revision-{b3,source_coalesced,source_only}`
and `{domain}-ablation-update/literal_revision-source_overlay`. The two affected
events per branch give16 inspected event records:12 active,4 deliberately
invalidated Source-only records. Review both generated notes per branch.
Additionally inspect both notes in the two RAG+Notes public-update branches
under `runs/focused-maintenance-v4/public-repair-20261016/paired10/`.

This is the two-case development evidence. It does not certify unseen workflow
revisions or the registered full-history matrix, and does not relabel a stored
raw correction as successful generated-memory maintenance.

## State-specific findings

| Branch | Corrected observation and unchanged context | Generated-memory limitation |
|---|---|---|
| Web B3 | Event3→4 describes Title=Neon Harbor, Name=Cyberpunk. Event4→5 retains Description=Welcome to the future and the unchanged state5 Title=Cyberpunk. Current blocks bind the correction to state4 only. | Wording that the Title was corrected at the next step is an interpretation; source establishes the different observed value, not its causal reason. |
| Web Coalesced | Both affected events bind Neon Harbor to state4. Name=Cyberpunk and the description remain in source/current evidence or retained generated prose. State5 is explicitly independent. | Older Cyberpunk assertions remain in marked prior-source prose. Current evidence does not regenerate all prose or prove every Reader obeys precedence. |
| Web Overlay | Same state4/state5 coverage and retained description in this one-revision comparison. | A single update cannot establish cumulative disadvantage versus Coalesced. |
| Web Source-only | Both affected events are persisted as invalidated. Old strings remain stored for provenance, not eligible current-event retrieval. | No replacement event; updated Raw State supplies the new value. |
| Enterprise B3 | Current blocks assign count103 to state5 and count101 to untouched state4/state6; the later event retains successful Normal selection. | **Event4→5 prose incorrectly says count103 reverted to101 in the final state.** For this event the final state is state5=103. This is a generated-summary/state-attribution inconsistency despite correct explicit source blocks. |
| Enterprise Coalesced | Current blocks assign count103 to state5 only. Retained event4→5 prose preserves failed click and `-- None --`; event5→6 preserves later successful `select_option` to Normal. | Prior prose is not globally rewritten; source consistency is not an unconditional downstream-quality pass. |
| Enterprise Overlay | Same corrected count and failed-click/later-selection distinction for this revision. | Repeated patches require separate sequence inspection. |
| Enterprise Source-only | Both affected events remain invalidated; no new current event is claimed. | Absence of a replacement is a representation difference, not itself an implementation failure. |

## Generated Notes

All eight AgentRunbook branch comparisons preserve their two notes exactly.
Inspected web notes specify separate Name/Title fields and creation steps
without asserting corrected state4 Title must equal Cyberpunk. Enterprise notes
describe filter construction and fallback to select_option, without asserting
count101 at state5. The two RAG+Notes branches also retain generic form/filter
procedures and hints with no newly contradicted literal Title/count statement.

These particular literal corrections do not demonstrate a need to regenerate
Notes, and exact request reuse introduced no identified note contradiction here.
This does not establish that arbitrary source changes leave Notes valid. Four
registered workflow-intent revisions exercise that separate dependency and must
inspect newly generated notes.

## Decision

Keep the frozen method and proceed. Preserve the B3 state-attribution error,
retained-prior-prose limitation and small QA differences without tuning. Neither
source persistence nor an old lexical-check failure certifies semantic quality.
Full-history event/Notes review and fixed Reader results remain necessary.
