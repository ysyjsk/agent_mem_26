# Focused method ablation and paper-ready result text

## Component interpretation

All rows use the same matched source snapshots, text-only AgentRunbook-R adapter, Qwen3.5-9B controller/Reader, Qwen3-Embedding-8B, 2,048-token Reader output, fixed 12,000-token memory context, chunk/tokenizer reuse, lexical backfill and query-embedding reuse. The initial construction is inherited and excluded from update totals.

| Variant | Event dependency reuse | Current-source representation | Safe note reuse | Sequential update LLM tokens | Sequential update publish s | Sequential update+query LLM tokens | Current evidence blocks after rounds 1/2/3 | QA |
|---|---|---|---|---:|---:|---:|---|---|
| Strong B3 | no | ordinary regenerated event | no | 70,580 | 206.049 | 214,714 | 2/2/2 | 11/12 |
| source_overlay | yes | append versioned CURRENT blocks | no | 0 | 13.788 | 147,865 | 2/4/6 | 11/12 |
| source_coalesced | yes | one state-scoped current view | yes when exact source lines absent from notes | 0 | 12.841 | 140,111 | 2/2/2 | 12/12 |
| delta_guarded (four-case comparator) | localized semantic edit | generated literal edit/append | no | 5,773 | 44.369 | not rerun in sequence | n/a | modified-fact 8/8 |

The B3-to-overlay comparison includes event-level dependency reuse and is therefore not an orthogonal one-factor estimate. Overlay-to-coalesced is the direct representation ablation: it keeps the same zero-update-LLM event reuse and changes only the treatment of accumulated current evidence and safe text-only note reuse. The coalesced branch removes overlay growth and lowers the measured sequential update+query total by 7,754 tokens (5.2%) relative to overlay, while retaining complete answers in all 12 scored sequence cells. Semantic editing is retained as a cost/quality comparator, not as a required final component.

## Paper-ready methods paragraph

For a local source correction, we preserve the original event interpretation as historical and publish exact source observations with explicit state and pre/post roles. The update path recomputes only events whose source/dependency key changed; unaffected event outputs and exact vectors remain legal cache entries. The current-evidence publisher then coalesces all prior correction blocks for an event into one state-scoped view, retaining only exact lines present in the latest source and adding the latest changed/neighbor lines. It does not infer validity from similarity, average vectors, or a learned compression model. Procedure and hint notes are reused only for text-only corrections where complete obsolete and current source lines are absent from the existing notes; otherwise the original note-generation path remains available. Save/reload verification and source mappings are applied before publication is counted.

## Paper-ready results paragraph

On two shared-domain histories with three sequential controlled corrections per domain, strong B3 required 70,580 update LLM tokens and 206.049 seconds to publish six updates. The source-coalesced method required no update LLM calls and 12.841 seconds. Counting retrieval planning, Reader generation and retrieval-controller tokens in the same six-round sequence, totals were 214,714 for B3 and 140,111 for source-coalesced. The append-only overlay ablation also used zero update LLM tokens but grew its current-evidence blocks from 2 to 4 to 6 and consumed 147,865 total tokens; coalescing kept two blocks and retained 12/12 scored answers versus 11/12 for B3. Two predeclared held-out trajectories (date fields and quantity/subtotal) were 3/3 for both methods with no truncation. A separate rejected-fill and selection-mismatch confirmation also scored 3/3; safe note reuse reduced the latter to zero update LLM tokens and 1.779 seconds. These are adapted text-only development results, not native Small or official Judge statistics.

## Limitations and claim boundary

The sequence and confirmation questions are controlled source-correction probes, not independent benchmark samples. The primary quality evidence is exact source-role checking plus fixed Reader answers; one small B3 Reader miss is retained rather than tuned away. The method claim is limited to localized maintenance and correction, not cold-construction speedup, arbitrary semantic editing, same-trajectory growth, or native multimodal Small quality.
