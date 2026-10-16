# Query configuration recovery: measured results

Development-scale histories only (10/domain). Update costs are reused from saved paired runs; only queries were newly executed. Initial cost is excluded. Questions are already exposed. No quality equivalence or full-Small completion is claimed.

| Domain | Policy | Update tokens | Controller tokens | Reader tokens | Total LLM tokens | Correct / fixed | Truncated |
|---|---|---:|---:|---:|---:|---:|---:|
| enterprise | b3 | 14849 | 5878 | 44041 | 64768 | 4/4 | 0 |
| enterprise | source_coalesced | 0 | 5836 | 43322 | 49158 | 3/4 | 0 |
| enterprise | source_only | 0 | 5893 | 46843 | 52736 | 4/4 | 0 |
| enterprise | source_overlay | 0 | 6075 | 42112 | 48187 | 4/4 | 0 |
| web | b3 | 8645 | 5753 | 44796 | 59194 | 3/4 | 0 |
| web | source_coalesced | 0 | 5775 | 45724 | 51499 | 3/4 | 0 |
| web | source_only | 0 | 5766 | 43167 | 48933 | 3/4 | 0 |
| web | source_overlay | 0 | 5765 | 42709 | 48474 | 3/4 | 0 |

Role-specific quality files preserve the previous checks. Changed evidence, unchanged full-event facts and stale source lines are separated; semantic attribution remains pending.
