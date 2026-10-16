# Full-history fixed maintenance results

Full histories are 100 trajectories/domain. Eight fixed state/workflow cases on four exposed trajectories; repeats and sequential rounds are not independent cases. Initial construction is separate. All Reader, retrieval-controller, embedding, failure and unknown-usage costs are retained.

| Method | Cases | Update LLM tokens | Update+query LLM tokens | Revision QA | Normal QA observations |
|---|---:|---:|---:|---:|---:|
| raw_rag | 0/8 | None | None | None/None | None/None |
| rag_notes | 0/8 | None | None | None/None | None/None |
| b3 | 0/8 | None | None | None/None | None/None |
| source_coalesced | 0/8 | None | None | None/None | None/None |

Normal questions repeat across changed snapshots; report unique questions separately. Generated event/notes semantic review remains pending until annotated. A small QA difference is not proof of equivalence or systematic loss.

Missing update units: 84; missing query units: 126.
