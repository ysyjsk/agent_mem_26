# v5 generated-memory review (partial, 2026-10-15)

This is manual inspection of actual generated fields and deterministic preservation checks. It is not official Judge evaluation, and fixed Reader results are still pending. All source modifications in this screen are additive.

| Case | Generated change and propagation | Existing memory | Decision |
|---|---|---|---|
| web 1ad1af4b state4 | "The status label 'Title validation: saved' is visible." Attached to post-state of event3→4 and pre-state of event4→5 | Original overview/state_transition retained; two notes unchanged | Derived memory pass; Reader pending |
| web 1ad1af4b workflow3 | "Workflow clarification: verify the required field before proceeding to the next form field." Attached to the two affected events and procedure as recorded intent | Old event fields and note content preserved; hint unchanged | Derived memory pass; Reader pending |
| enterprise 0ab99e0c state5 | "[correction] status 'Title validation: saved', visible" attached to the two affected events with correct state role | Old event fields and both notes retained | Derived memory pass; Reader pending; synthetic status deliberately not treated as task success |
| enterprise 0ab99e0c workflow6 | Same explicit verification-before-next-field clarification, generated once then propagated to both affected events and procedure | Old event and note content retained; hint unchanged | Derived memory pass; Reader pending |
| web 2e8f6477 state3 | Model returned state_index4 instead of3. Validation rejected it; full-extraction fallback omitted the added status in both generated events | Original evidence remains, but that is not quality success | Failed propagation; retain cost and repair source-reference output contract |
| web 2e8f6477 workflow4 | Exact verification-before-next-field clarification generated once, attached to event3→4 and4→5 as intent, and appended to procedure | Existing event fields and procedure prefixes retained; hint unchanged | Derived memory pass; Reader pending |
| enterprise 49f98e9e state4 | Literal visible status attached to correct pre/post roles of event3→4 and4→5 | Both existing event fields retained, notes unchanged | Derived memory pass; Reader pending |
| enterprise 49f98e9e workflow5 | Exact verification-before-next-field clarification in both affected events and procedure | Existing event/note content retained; hint unchanged | Derived memory pass; Reader pending |

The event-only v5 ablation for web1ad1af4b workflow3 saved model input but regenerated notes omitted the new check. The previous loose lexical check was a false positive from a validation heading and required-field bullets; the current check requires verification and ordering within one sentence. The combined delta_notes output explicitly preserves the clarification. No accuracy improvement is inferred from these necessary checks.

Scope limitation: appending an explicit sentence is easier than replacing or revoking an existing assertion. A deterministic source-append baseline and actual replacement cases are necessary before claiming that an expensive model is essential for this update mechanism. The method remains exploratory.
