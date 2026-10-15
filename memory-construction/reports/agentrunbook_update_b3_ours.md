# AgentRunbook-R adapted local updates: B3 vs Ours

All six runs start from independent clones of the same persisted `screen-web-g2` snapshot. Model weights are resident; cache seeding/load is excluded from update-to-queryable wall time. Both methods retain exact valid request/vector caches; Ours additionally validates per-event dependencies and only regroups dirty adjacent outputs.

| Case | Policy | Update→queryable s | Event outputs recomputed | Notes regenerated | LLM calls/in tokens | Embedding calls/vectors | Cache hits |
|---|---|---:|---:|---:|---:|---:|---:|
| state_revision | b3 | 22.11 | 4 | 0 | 2/8012 | 2/7 | req 4, emb 10 |
| state_revision | ours | 12.62 | 2 | 0 | 1/3926 | 2/5 | req 2, emb 12 |
| workflow_revision | b3 | 33.81 | 4 | 2 | 3/9458 | 3/6 | req 2, emb 11 |
| workflow_revision | ours | 21.36 | 2 | 2 | 2/5370 | 3/4 | req 0, emb 13 |
| state_revision | b3 | 23.47 | 4 | 0 | 2/8012 | 2/7 | req 3, emb 10 |
| state_revision | ours | 11.96 | 2 | 0 | 1/3926 | 2/5 | req 1, emb 12 |
| workflow_revision | b3 | 32.19 | 4 | 2 | 3/9458 | 3/6 | req 2, emb 11 |
| workflow_revision | ours | 32.95 | 2 | 2 | 3/5891 | 3/4 | req 0, emb 13 |
| append | b3 | 18.48 | 2 | 2 | 2/1761 | 4/7 | req 0, emb 0 |
| append | ours | 18.13 | 2 | 2 | 2/1761 | 4/7 | req 0, emb 0 |

Append uses a real additional official-source trajectory prefix (3 arrived states, no future state/outcome) and does not wait for later events. State revision appends one source-backed visible status. Workflow revision changes one recorded thought/workflow fragment while preserving actions, values and source evidence.

State revision: Ours recomputes 2 event outputs vs B3 4 and publishes in11.96s vs23.47s. Workflow revision: both recompute2 events +2 notes; Ours uses less known LLM input (5891 vs9458), but wall time is roughly tied (32.95 vs32.19s). Append costs are nearly tied (18.13 vs18.48s) because both must generate the new trajectory notes/events.

This is an adapted text-only mechanism experiment, not native Small, official Judge, or a claim that prior workflow-core B3/Ours numbers are interchangeable.

## Best combined snapshot

The state/workflow revisions were repeated from `runs/construction-pair-v2/full10-web-combined` (the selected necessary-work configuration). The append case is retained from the independent screen snapshot because the full five-trajectory web corpus already contains every web trajectory; inserting a sixth web trajectory would change the frozen workload.
