# Query configuration recovery: measured results

Development-scale histories only (10/domain). Update costs are reused from saved paired runs; only queries were newly executed. Initial cost is excluded. Questions are already exposed. No quality equivalence or full-Small completion is claimed.

| Domain | Policy | Update tokens | Controller tokens | Reader tokens | Total LLM tokens | Correct / fixed | Truncated |
|---|---|---:|---:|---:|---:|---:|---:|
| enterprise | b3 | 14849 | 2939 | 19190 | 36978 | 1/2 | 0 |
| enterprise | source_coalesced | 0 | 2928 | 19389 | 22317 | 2/2 | 0 |
| web | b3 | 8645 | 2897 | 22541 | 34083 | 2/2 | 0 |
| web | source_coalesced | 0 | 2922 | 22793 | 25715 | 2/2 | 0 |

Role-specific quality files preserve the previous checks. Changed evidence, unchanged full-event facts and stale source lines are separated; semantic attribution remains pending.
