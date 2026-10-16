# Generated-memory review: historical v13 date and quantity confirmation

Reviewed 2026-10-16 by the execution assistant from saved generated artifacts.
This is qualitative inspection, not a blinded human annotation or GPT Judge
score. No answers, generation settings or source edits were modified.

Sources: `derived_quality_review.json`, `update_input.json`, and the corrected
question responses under `runs/method-first-20261015/v13-confirm-{web-2a99f536-date,enterprise-12c22166-quantity}/literal_revision-{b3,source_coalesced}/`.
Eight affected event records and eight generated notes are inspected across
four branches. Generic notes are byte/content-equivalent to their own prior
versions in all four branches.

| Case/method | Corrected current evidence | Unmodified evidence | Narrative caveat |
|---|---|---|---|
| Date/B3 | State3 From=07/06/2021 appears in both affected events' explicit source blocks. | State4 From=07/05/2021 is distinguished; To=05/31/2023 remains in event3→4 prose. | Event2→3 prose incorrectly claims the post-state contains07/05/2021 and implies07/06 was prior. This is inconsistent with its own current block. |
| Date/Coalesced | State3 From=07/06/2021 is bound to event2→3 post-state and event3→4 pre-state. | State4 From=07/05/2021 is retained in its current block; To=05/31/2023 remains in valid retained prose. | Original From07/05 assertions persist as explicitly superseded prior-source interpretation. Reliability still depends on respecting state-specific precedence. |
| Quantity/B3 | State4 Quantity4, selected4/deselected6 and subtotal1399.96 are in both affected current blocks. | State3 Quantity1 and final state5 quantity6/total2099.94 are retained. | Event3→4 prose says the new quantity is6 and misattributes1399.96 to six items. Event4→5 overview also implies the preceding observed selection was6. These are genuine summary contradictions, despite6/6 total Reader success across both cases. |
| Quantity/Coalesced | Current evidence assigns Quantity4 and subtotal1399.96 only to state4, with option flags consistent. | Final state5 quantity6, total2099.94, requestREQ0010155 and confirmation outcome remain in retained event4→5 prose. | Historical state4 quantity6 claims remain marked as prior-source. No state5 current block is necessary merely to retain its unchanged facts; absence from that block is not evidence of loss. |

## Notes

Date notes describe navigating Reports→Products→Views, filling separate From/To
fields and submitting Show Report. They do not assert the revised state3 date.
Catalog notes describe selecting the desired Quantity, subtotal response and
Order Now. They do not assert a particular corrected state4 quantity/subtotal.
No new contradiction from these literal revisions was identified in the eight
notes. This does not validate arbitrary workflow-intent revisions or every
pre-existing note assertion.

## Decision and boundary

Both versions answered the six fixed confirmation questions correctly, but
complete/correct answers do not imply fully consistent generated prose. The
inspection distinguishes authoritative source blocks, prior-source narrative,
unmodified neighboring states and reusable notes. It supports retaining the
versioned confirmation evidence, with the B3 narrative errors and Coalesced
prior-prose limitation explicit. It does not create new held-out confirmation,
justify score relaxation, or replace the registered full-history quality work.
