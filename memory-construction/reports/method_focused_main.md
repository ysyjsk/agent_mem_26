# Focused-method-v3 main results (adapted text-only development)

Current source-coalesced method versus strong B3. All methods use the same matched snapshots, Reader, retrieval, source evidence publisher, resource and budget. Raw RAG/RAG+Notes historical cold-build rows remain in method_external_dev.csv and are not mixed with these local maintenance rows. Initial construction is inherited and excluded from update totals.

| Scope | Case/aggregate | Method | Update LLM tokens/calls | Publish s | Embedding tokens/vectors | Correct/scored | Truncated | Additional cost |
|---|---|---|---:|---:|---:|---:|---:|---:|
| four current replacement cases | v12-enterprise-0ab99e0c-count-replacement | b3 | 14837/1 | 18.226 | 5183/3 | 2/2 | 0 |  |
| four current replacement cases | v12-enterprise-0ab99e0c-count-replacement | delta_guarded | 1245/1 | 6.530 | 5194/3 | 2/2 | 0 |  |
| four current replacement cases | v12-enterprise-0ab99e0c-count-replacement | source_overlay | 0/0 | 1.536 | 5205/3 | 2/2 | 0 |  |
| four current replacement cases | v12-enterprise-49f98e9e-sort-replacement | b3 | 13555/1 | 25.709 | 4539/3 | 2/2 | 0 |  |
| four current replacement cases | v12-enterprise-49f98e9e-sort-replacement | delta_guarded | 674/1 | 4.244 | 4556/3 | 2/2 | 0 |  |
| four current replacement cases | v12-enterprise-49f98e9e-sort-replacement | source_overlay | 0/0 | 1.728 | 4637/3 | 2/2 | 0 |  |
| four current replacement cases | v12-web-1ad1af4b-title-replacement | b3 | 8633/2 | 40.140 | 8399/7 | 2/2 | 0 |  |
| four current replacement cases | v12-web-1ad1af4b-title-replacement | delta_guarded | 1993/2 | 25.172 | 8215/5 | 2/2 | 0 |  |
| four current replacement cases | v12-web-1ad1af4b-title-replacement | source_overlay | 0/0 | 2.466 | 8290/5 | 2/2 | 0 |  |
| four current replacement cases | v12-web-2e8f6477-reply-replacement | b3 | 29451/2 | 27.975 | 4930/5 | 1/1 | 1 |  |
| four current replacement cases | v12-web-2e8f6477-reply-replacement | delta_guarded | 1861/2 | 8.422 | 4800/3 | 2/2 | 0 |  |
| four current replacement cases | v12-web-2e8f6477-reply-replacement | source_overlay | 0/0 | 1.394 | 4909/3 | 2/2 | 0 |  |
| two domains × three sequential rounds | aggregate | b3 | 70580/9 | 206.049 | 40666/30 | 11/12 | 0 | 214714 |
| two domains × three sequential rounds | aggregate | source_overlay | 0/0 | 13.788 | 44336/24 | 11/12 | 0 | 147865 |
| two domains × three sequential rounds | aggregate | source_coalesced | 0/0 | 12.841 | 39911/24 | 12/12 | 0 | 140111 |
| two held-out confirmation cases | v13-confirm-enterprise-12c22166-quantity | b3 | 16224/2 | 25.577 | 9085/5 | 3/3 | 0 | 29263 |
| two held-out confirmation cases | v13-confirm-enterprise-12c22166-quantity | source_coalesced | 0/0 | 2.209 | 8950/4 | 3/3 | 0 | 29135 |
| two held-out confirmation cases | v13-confirm-web-2a99f536-date | b3 | 7397/1 | 16.461 | 8857/4 | 3/3 | 0 | 31992 |
| two held-out confirmation cases | v13-confirm-web-2a99f536-date | source_coalesced | 0/0 | 2.160 | 8878/4 | 3/3 | 0 | 32563 |
| two held-out confirmation cases | v13-note-reuse-enterprise-selection | source_coalesced | 0/0 | 1.779 | 5798/3 | 3/3 | 0 | 32989 |

## Decision

Retain source_coalesced as the practical maintenance default for text-only source corrections. It consolidates one current source-evidence view per affected event, reuses unaffected event dependencies, and safely reuses generic notes only when complete old/current source lines are absent from those notes. It does not claim semantic validity for arbitrary changes; source-derived checks, Reader answers and limitations remain visible.

Across six sequential rounds (two domains × three corrections), B3 uses 70,580 update LLM tokens and 206.049 s publication; source_coalesced uses zero update LLM tokens and 12.841 s. Including query planning, Reader and retrieval-controller tokens, totals are 214,714 versus 140,111. The coalesced branch has 12/12 scored sequential answers, versus B3 11/12; this small adapted sample is not a statistical equivalence test. It also keeps current-evidence blocks at two and avoids overlay growth.

Two held-out trajectories (date fields and quantity/subtotal) are 3/3 for both methods with no truncation. The enterprise selection-mismatch case after note reuse is 3/3, zero update LLM tokens, 1.779 s, 5,798 embedding tokens. These confirm the direction but do not establish native Small quality.

Semantic-editing remains an ablation/comparator. It is not required for the measured cases and is not retained as an always-on step. The remaining paper evidence is a frozen two-domain ablation and formal write-up, not another baseline adapter.
