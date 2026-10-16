# Coalesced generated-memory review across the saved three-round sequence

2026-10-16; existing development evidence only. No new model calls, score
changes or method tuning. Two target trajectories, five-history libraries per
domain, three dependent literal corrections per target. Twelve affected event
instances and twelve note instances are inspected; repeated versions are not
independent examples. The four distinct Notes are unchanged across rounds.

## Current-event evidence checks

Each generated event's current-observation block was decoded and compared with
the source text of its cited state. Changed lines must appear in each affected
event under the correct pre/post-state role. Superseded lines are checked only
in the corrected state's current block, not in unchanged neighboring states or
explicitly marked prior prose.

| Domain | Round | Current value at edited state | Affected event instances | Current blocks | Current evidence lines checked | Noncurrent lines / wrong roles / missing changed lines / superseded lines at edited state |
|---|---:|---|---:|---:|---:|---|
| web | 1 | state4 Title = Neon Harbor | 2 | 2 | 16 | 0 / 0 / 0 / 0 |
| web | 2 | state4 Title = Cedar Point | 2 | 2 | 16 | 0 / 0 / 0 / 0 |
| web | 3 | state4 Title = Silver Cove | 2 | 2 | 16 | 0 / 0 / 0 / 0 |
| enterprise | 1 | state5 count = 103 | 2 | 2 | 26 | 0 / 0 / 0 / 0 |
| enterprise | 2 | state5 count = 105 | 2 | 2 | 26 | 0 / 0 / 0 / 0 |
| enterprise | 3 | state5 count = 107 | 2 | 2 | 26 | 0 / 0 / 0 / 0 |

The126 checked lines include repeated evidence across adjacent events/rounds;
this is not126 unique facts. Legacy lexical failure flags remain in the raw
artifacts; they scan marked prior interpretations or restrict unchanged facts
to current blocks. The role-specific review does not overwrite those flags or
treat an automated pass as full semantic certification.

## Generated prose, unaffected facts and Notes

Web event3→4 retains the original action of filling Title with Cyberpunk, but
the post-state observation explicitly contains the replacement Title. Event4→5
places that replacement in its pre-state; the unchanged post-state5 still has
Title Cyberpunk, and the retained narrative preserves Description `Welcome to
the future`. Name Cyberpunk remains in neighboring evidence/narrative. The
original sentences asserting Title Cyberpunk at the corrected state remain in
the explicitly prior-source prose, not rewritten. Thus there is still a Reader
interpretation burden; the annotations are not equivalent to deleting every
contradictory old assertion from the entire context.

Enterprise event4→5 retains the failed-click/non-interactive result and Type
`-- None --`; event5→6 retains the later successful selection of Normal. The
revised count belongs to state5 only. Counts101 at unchanged states4 and6 remain
valid source observations, not evidence of failed correction or automatic
leakage. The original failed-click narrative still says101 unfiltered records,
with an explicit prior-source qualification. A current block does not prove
that every downstream Reader will respect that qualification.

The two web Notes describe generic form-field workflow/requirements; the two
enterprise Notes describe generic filter setup and click/select-option
pitfalls. They introduce no new correction-specific Title/count assertion.
Exact equality confirms Notes do not change between the three rounds, and the
event prose outside the current blocks is also identical across rounds. These
observations support preservation of the inspected unchanged facts; they do
not validate unrelated generalizations in the original generated Notes.

All12 saved Coalesced answers are complete and scored correct under the frozen
diagnostic rules. That supports this bounded workload, not statistical quality
equivalence, normal-QA generality or arbitrary semantic-edit safety.

## Size and interpretation

The target's query-eligible event characters remain6,474 for web and11,815 for
enterprise over all three rounds, with two current-evidence blocks each. B3
also keeps two current blocks because it regenerates affected events; its
target text size changes with generated prose (web6,515→5,715→5,660;
enterprise11,652→12,256→12,006). Source-only has fewer eligible event characters
(3,455/8,286) because affected events are retired. Smaller event size alone is
not a quality win. This development comparison lacks Overlay; it does not
isolate the incremental value of coalescing versus appending. The fixed formal
Overlay sequence remains queued, and old Overlay evidence stays versioned.

The figure is `public-sequence-v3/evidence_size.svg`, with source rows in
`public-sequence-v3/continuous_cost.csv`. It plots snapshot size after each
revision, not cumulative cost. B3 and Coalesced overlap at two blocks. Existing
cost/QA totals are byte-value-equivalent to v2; v3 adds offline size accounting.

## Raw provenance

- `runs/focused-maintenance-v4/dev/sequence-final/{web,enterprise}-r{1,2,3}/literal_revision-source_coalesced/derived_quality_review.json`
- adjacent `update_input.json`, `memory_state/pools/event_pool.jsonl` and `revision_reader/per_question.jsonl`
- generated source-role diagnostics: `public-sequence-v3/generated_memory_checks.json`
- size regeneration: `tools/report_public_development_sequence.py --output <new directory>`

The paper should cite this as a scoped agent-assisted review of saved generated
memory, not a blinded human study or independent Judge certification.
