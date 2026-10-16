# RAG+Notes: generated notes in the saved development sequence

Reviewed 2026-10-16 by the execution assistant, using saved actual requests,
published notes, source actions and state text. This is a scoped qualitative
inspection, not a blinded human evaluation, new model inference, or formal
full-history quality certification. No method, scoring rule or frozen input
was changed.

## Scope and cost provenance

Source directories are
`runs/focused-maintenance-v4/public-repair-20261016/sequence/{web,enterprise}-r{1,2,3}-rag_notes/`.
Each contains `derived_quality_review.json`, `update_input.json`,
`update_calls.json`, `update_metrics.json`, and the published `memory_state`.
The targets are web `1ad1af4b` and enterprise `0ab99e0c`.

There are four distinct generated notes: procedure and hint for each target.
They appear in twelve note instances across six published snapshots. Both notes
change from their inherited versions in round1; rounds2 and3 preserve the
round1 notes exactly. All saved structural preservation checks pass, but this
does not establish semantic correctness.

| Domain | Round1 generation/repair calls | Input tokens | Output tokens | Regenerated notes | Round2/3 new calls |
|---|---:|---:|---:|---:|---:|
| web | 2 | 1,946 | 770 | 2 | 0 / 0 |
| enterprise | 2 | 3,406 | 908 | 2 | 0 / 0 |

Total observed work is7,030 LLM tokens, including both JSON repairs. The initial
note requests and their repair requests all finish with `stop`. The malformed
initial drafts use arrays/broken quoting where bullet-list strings are required;
the subsequent request performs the recorded format repair. This is not an
unrecorded retry. The inherited requests lacked sufficient finish/thinking
metadata for lawful cache reuse; it is not evidence that changing a literal
Title/count intrinsically requires these note generations. Later exact requests
are reused without silently treating different inputs as equivalent.

## Generated-memory findings

Neither target's notes assert a revised Title/count value or a superseded value
as the corrected state's current value. Their content is generic workflow/hint
memory, so this absence is **not** proof that they answer the revision questions.
The published sequence's RAG+Notes Reader result remains5/12; no score is changed.

- **Web supported content:** separate Name/Title/Description/Sidebar fields,
  their required-field annotations, the forum creation action sequence, help
  identifiers, and the observed sidebar preview are grounded in the supplied
  annotated actions/thoughts. The final URL and success outcome support that
  this particular run created a forum.
- **Web overgeneralization:** the hint says Name and Title "must be filled
  before proceeding to other sections" and that Sidebar "expects a markdown
  bullet list format". The supplied run follows that order and uses that
  format; it does not demonstrate that other orders/formats are prohibited.
  These statements therefore overstate the evidence. They are not newly
  contradictory revision values, but a general semantic-quality pass would
  hide their unsupported necessity claims.
- **Enterprise supported content:** Type=Normal, Requested by entry, the Model
  `is empty string` operator, AND-condition construction, and the recovery from
  an unclickable option via `select_option` are supported. The note correctly
  states that State selection was not reached; it does not claim the failed
  task completed successfully.
- **Enterprise evidence gap:** both procedure/hint notes describe filling
  Short description as a text input. The16-state source ends after the action
  adding another AND condition for that intended next field. The action trace
  never selects or fills Short description. Its appearance in the goal, table
  column and list-search options does not establish the described filter-input
  interaction. That part is an unsupported procedural extrapolation, not an
  observed successful step. Similarly, categorical input/ordering requirements
  should not be inferred solely from one successful action sequence.

These limitations arise in the generated text despite successful source
roundtrip and valid JSON repair. They are neither a new maintenance regression
measurement nor proof of a relative Coalesced advantage: the runs use different
memory architectures and this review does not supply a new paired QA trial.

## Decision and traceability

Retain the frozen methods, actual costs and answers. Do not add prompts,
repair calls or scorer exceptions to remove these exposed errors. The registered
full-history workflow revisions still require inspection of their own generated
notes and actual Reader evidence; this development review does not satisfy that
remaining acceptance item.

SHA256 of each inspected `derived_quality_review.json`:

| Snapshot | SHA256 |
|---|---|
| web-r1 | `2fe0b693b3248fee8c44a678f71389f12f2315f7fcc37e3752a38e3ad2f8fc45` |
| web-r2 | `be1e6b34289ed013b1de51bf1a47a9769d74b22910aa51e9e7852e85a802b25c` |
| web-r3 | `5de6575dcd24bf7012873cab7da844651d9e34d914ccb43ea356d124505457fe` |
| enterprise-r1 | `6eb4cad266f93a691fd07958e93107b3b4db5dbdd6013cd62bfe1ecf408a3a81` |
| enterprise-r2 | `346f6b95d7354d56ee4129f6d7a8ec4315547c4aceb52e506d975659dc2f2272` |
| enterprise-r3 | `3d2d6384948d0462d722a4a79477b8e5909678af76147d4106258dd63c257548` |

