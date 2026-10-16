# Query configuration recovery: measured results

Development-scale histories only (10/domain). Update costs are reused from saved paired runs; only queries were newly executed. Initial cost is excluded. Questions are already exposed. No quality equivalence or full-Small completion is claimed.

| Domain | Policy | Update tokens | Controller tokens | Reader tokens | Total LLM tokens | Correct / fixed | Truncated |
|---|---|---:|---:|---:|---:|---:|---:|
| enterprise | delta_guarded | 0 | 3594 | 21818 | 25412 | 0/2 | 1 |
| enterprise | source_overlay | 0 | 3577 | 19299 | 22876 | 2/2 | 0 |
| enterprise | b3 | 14849 | 8194 | 18769 | 41812 | 1/2 | 0 |
| enterprise | source_coalesced | 0 | 3427 | 21672 | 25099 | 1/2 | 0 |
| enterprise | source_only | 0 | 3480 | 21493 | 24973 | 1/2 | 0 |
| web | delta_guarded | 1877 | 2899 | 21299 | 26075 | 0/2 | 0 |
| web | source_overlay | 0 | 2908 | 23144 | 26052 | 1/2 | 0 |
| web | b3 | 8645 | 2910 | 15807 | 27362 | 2/2 | 0 |
| web | source_coalesced | 0 | 2896 | 12904 | 15800 | 1/2 | 0 |
| web | source_only | 0 | 2907 | 20533 | 23440 | 0/2 | 0 |

Role-specific quality files preserve the previous checks. Changed evidence, unchanged full-event facts and stale source lines are separated; semantic attribution remains pending.
