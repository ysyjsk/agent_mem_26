# Cold construction candidate: common bounded input preparation before joint extraction

The candidate changes one mechanism only: when an event or adjacent pair exceeds the 18,000-token safety budget, both paths first apply the existing 12,000-character-per-state bounded preparation. A pair is sent jointly only if the prepared shared-state request fits; otherwise only that pair is split into single events. Models, output budgets, retries, embedding reuse, selected trajectories and persistence boundary are unchanged.

| Variant | Wall s | Controller calls (failed) | LLM input/output tokens | Embedding calls/vectors/input tokens | Joint parsed/split groups | Events | Quality |
|---|---:|---:|---:|---:|---:|---:|---|
| enterprise2-common-preflight-baseline | 741.94 | 35 (2) | 291019/13848 | 8/62/124319 | 0/0 | 29 | pass |
| enterprise2-common-preflight-joint | 412.44 | 19 (0) | 209996/11575 | 8/62/122949 | 14/0 | 29 | pass |

On the two long enterprise trajectories (`0ab99e0c`, `49f98e9e`), joint common-preflight reduced wall time by 44.4% (741.94s → 412.44s), controller calls from 35 to 19, and known LLM input tokens by 27.8% (291,019 → 209,996). It parsed 14 joint groups and split 0 oversized prepared groups; no API failures occurred in the joint run.

Both variants published all 29 expected transition events and passed save/reload plus source-coverage checks. This is a construction-quality check, not a claim of unchanged downstream QA; the fixed Reader regression remains reported separately. The candidate is retained for the next fixed-10 expansion because it reduces expensive model work without reducing required evidence or output budget.
