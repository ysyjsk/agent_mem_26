# Reader regression across eight fixed revision cases

This is a text-only/adapted fixed-question regression on persisted update snapshots. It covers both state and workflow revisions for two web and two enterprise trajectories, with B3 and Ours using the same local Qwen Reader, 2,048-token ceiling, thinking disabled and four questions per case. Fresh/B0 is not included in the full eight-case table because only a subset of Fresh workflow snapshots was re-read; its state-revision results remain in the separate Fresh/B3/Ours report.

| Domain | Trajectory | Case | Method | Correct / 4 | Complete / 4 | Trunc | Service | Parse | Reader input/output tokens | Reader wall s |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| web | `1ad1af4b` | state_revision | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 41813/138 | 15.99 |
| web | `1ad1af4b` | state_revision | ours | 3/4 | 4/4 | 0 | 0 | 0 | 40505/1133 | 43.80 |
| web | `1ad1af4b` | workflow_revision | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 40777/158 | 18.40 |
| web | `1ad1af4b` | workflow_revision | ours | 3/4 | 4/4 | 0 | 0 | 0 | 34348/47 | 11.35 |
| web | `2e8f6477` | state_revision | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 32020/137 | 13.26 |
| web | `2e8f6477` | state_revision | ours | 3/4 | 4/4 | 0 | 0 | 0 | 32110/138 | 13.21 |
| web | `2e8f6477` | workflow_revision | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 34225/43 | 11.32 |
| web | `2e8f6477` | workflow_revision | ours | 4/4 | 4/4 | 0 | 0 | 0 | 36405/226 | 16.87 |
| enterprise | `0ab99e0c` | state_revision | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 21199/693 | 25.05 |
| enterprise | `0ab99e0c` | state_revision | ours | 2/4 | 4/4 | 0 | 0 | 0 | 17291/256 | 12.07 |
| enterprise | `0ab99e0c` | workflow_revision | b3 | 2/4 | 4/4 | 0 | 0 | 0 | 19186/78 | 7.78 |
| enterprise | `0ab99e0c` | workflow_revision | ours | 2/4 | 4/4 | 0 | 0 | 0 | 16281/1692 | 51.17 |
| enterprise | `49f98e9e` | state_revision | b3 | 2/4 | 4/4 | 0 | 0 | 0 | 16807/240 | 11.55 |
| enterprise | `49f98e9e` | state_revision | ours | 2/4 | 4/4 | 0 | 0 | 0 | 15025/95 | 7.14 |
| enterprise | `49f98e9e` | workflow_revision | b3 | 2/4 | 4/4 | 0 | 0 | 0 | 19371/330 | 14.67 |
| enterprise | `49f98e9e` | workflow_revision | ours | 2/4 | 4/4 | 0 | 0 | 0 | 16751/145 | 8.88 |

Across B3/Ours, 42/64 fixed responses are correct and 64/64 are complete/parseable. Truncation, service failures and parse failures are all zero. This is a downstream development constraint, not an official Judge score; the construction source-grounded checks remain 48/48.

Per-case results and raw paths are in `results/tables/agentrunbook_revision_case_reader.csv`.
