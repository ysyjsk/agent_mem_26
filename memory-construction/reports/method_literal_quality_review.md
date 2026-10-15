# Literal correction review (development, not official Judge)

All reviews inspect generated overview/state_transition and notes, with raw evidence used only as the reference. Rules in the manifests are predeclared necessary checks, not semantic pass labels. Original metrics remain immutable; invalid attempts and semantic decisions are recorded separately here.

| Version | Web Title | Enterprise count | Decision |
|---|---|---|---|
| v6a | Missing event output, fallback drops Neon Harbor | Missing event output, fallback drops103 | Reject pair contract |
| v7 | Contradictory pre-state Title statements remain | No-op leaves101 active | Reject |
| v8 | Corrected Title and unchanged Name/description preserved; causal phrasing imprecise | New103 wrongly described in post-state6 instead of pre-state5 | Reject combination |
| v9 | Validation exception leaked rejected partial result | Same validation defect | Invalid implementation evidence, not successful retraction |
| v10 | Deletes unrelated Name/action-result information, retains stale Title | One fallback; generated checks alone insufficient | Reject deletion-only contract |
| v11 discovery | Neon Harbor at state4; Name Cyberpunk retained; description action and post-state result preserved. No surviving explicit pre-state Title=Cyberpunk | State5 count103 replaces stale count in event4->5; event5->6 retains old valid content and gains explicitly pre-state5-scoped observation | Pass factual/source-scope checks for these two runs; Reader and repeats pending |

For v11 discovery, exact task/action metadata and all other event source mappings are retained. Original notes remain byte-identical: their source prompt depends on unchanged thoughts/actions, and their generic field-filling/filtering instructions make no assertions about the replaced Title value or list count. This is an explicit generated-note check, not raw persistence certification. The phrase “action updates” in the web summary still compresses an observed post-action outcome; it does not change the stored attempted action (Cyberpunk). No success beyond the observed form state is introduced. Broader causal fidelity remains a limitation of the inherited representation.

The deterministic source-append comparator's two additive cases preserve every old generated field and note as a prefix, insert only the provided current fact with pre/post attribution, and preserve event coverage. It is adequate for these explicit annotations and eliminates the observation-model call. Do not infer arbitrary replacement validity from this result.

V11 has not been frozen: same-version paired repeats, unchanged fixed-query regression and two preselected new replacement cases are next. Do not count a source phrase appearing in a copied raw state as a generated-memory pass.

## Three fresh paired repetitions (v11)

All six candidate published outputs have been inspected. Enterprise: all3 preserve unchanged failure/selection facts, replace stale count in event4->5 and use a deterministic pre-state5-scoped observation in event5->6; no post-state6=103 assertion. Web: all3 preserve Name/description and current Title at state4. Repeat2 triggers the predeclared forbidden regex because its first clause repeats the attempted Cyberpunk value, but the same sentence explicitly contrasts it with “observed post-state ... Neon Harbor”. Manual judgment accepts the observed-value distinction; the automatic failure remains in the raw result and table. The ambiguous inherited causal wording is a limitation, not silently counted as exact textual equivalence. Notes do not contain the replaced facts and remain unchanged.

Per-run review_decision.json files record these judgments independently of automated checks. They do not assert downstream regression has passed. New cases (reply textbox/preview and sort status, on the other two frozen trajectories) were specified before execution; their outcome will decide whether this limited mechanism generalizes or needs further changes.

## Two preselected new replacements

Reply (`2e8f6477`,state8): candidate explicitly records stay calm in textbox/preview, retains the intended action text don't panic, and retains don't panic in the unchanged post-state9. User identity, Post button, comment-count change16→17 and new-comment indicator remain. The inherited phrase “page content remains visually identical” is now overly broad, and the overview's “required text” refers to intent rather than the revised observed text. These narrative qualifications are recorded, not erased by the lexical pass; the generated-only Reader probes check whether they cause a value/state error. No universal semantic-equivalence claim is made.

Sort (`49f98e9e`,state5): one malformed JSON edit was rejected and the existing single-event extractor reran. The resulting event states2of2 in the post-state, with the sort setup and same-page context retained. The following event preserves dropdown/field options and adds the revised status explicitly as pre-state5; no false propagation to state6. Both existing procedure and hint notes are unchanged and contain none of the revoked count status. Fallback cost remains part of the result (10245LLMtokens,9.843s vsB313574,14.696s).

The fixed Reader on the new enterprise snapshot misses87711b62 despite “Task type” appearing in both final contexts; it answers“Type”. This is the same sampling-sensitive question as the prior v5 mismatch, on an unchanged answer trajectory. Do not search retrieval or claim statistical equivalence from the small test. The original answers remain in method_reader_regression.csv.
