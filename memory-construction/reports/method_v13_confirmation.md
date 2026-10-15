# V13 independent confirmation

Two predeclared complete trajectories not used in the original four-case tuning: web report date fields and enterprise catalog quantity/subtotal. Both methods use the same matched source preparation, fixed retrieval and Reader configuration.

| Case | Policy | Update tokens/calls | Publish s | Embedding tokens/vectors | QA correct/scored | Complete/truncated | Reader tokens |
|---|---|---:|---:|---:|---:|---:|---:|
| v13-confirm-web-2a99f536-date | b3 | 7397/1 | 16.461 | 8857/4 | 3/3 | 3/0 | 31992 |
| v13-confirm-web-2a99f536-date | source_coalesced | 0/0 | 2.160 | 8878/4 | 3/3 | 3/0 | 32563 |
| v13-confirm-enterprise-12c22166-quantity | b3 | 16224/2 | 25.577 | 9085/5 | 3/3 | 3/0 | 29263 |
| v13-confirm-enterprise-12c22166-quantity | source_coalesced | 0/0 | 2.209 | 8950/4 | 3/3 | 3/0 | 29135 |

Both cases scored 3/3 for B3 and source_coalesced, with no truncation, service or parse failure. Source-derived checks passed before Reader. The confirmation is a small held-out adapted development sample, not native Small or statistical non-inferiority.
