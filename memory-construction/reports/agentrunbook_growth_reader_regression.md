# Reader regression on same-trajectory growth snapshots

This is a text-only/adapted quality check over the fixed eight development questions (four web + four enterprise), reusing the already published growth snapshots. It does not change construction/update timing and is not native Small or official Judge scoring.

| Domain | Method | Correct / 4 | Complete / 4 | Trunc | Service failures | Parse failures | Reader input/output tokens | Prompt/query build wall s | Reader generation wall s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| web | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 41526/47 | 88.04 | 14.93 |
| web | ours | 3/4 | 4/4 | 0 | 0 | 0 | 40964/47 | 532.52 | 14.79 |
| enterprise | b3 | 3/4 | 4/4 | 0 | 0 | 0 | 46730/438 | 283.61 | 26.26 |
| enterprise | ours | 3/4 | 4/4 | 0 | 0 | 0 | 44347/175 | 137.53 | 18.00 |

All four cells produced complete, boxed, service-successful answers with zero truncation or parse failure. Web B3/Ours both score 3/4; enterprise B3/Ours both score 3/4. The only web miss is the same dynamic question answered UNKNOWN by both; the enterprise miss is the task-type question, with B3 returning “Type of Change” and Ours returning “type, type”.

Query/prompt build wall time is reported separately because it is not part of the construction/update cost claim. It varied widely across paired runs (for example, web 88.04 s vs 532.52 s), so only the complete/parseable status and paired question scores are used as the quality constraint here.

Raw aggregate rows: `results/tables/agentrunbook_growth_reader_regression.csv`. Per-question rows: `results/tables/agentrunbook_growth_reader_per_question.csv`.
