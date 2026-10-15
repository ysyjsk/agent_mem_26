# Reader regression on state-revision update snapshots

This is a text-only/adapted downstream quality check using the fixed four questions per domain after a controlled state revision. It reuses persisted update snapshots and does not add construction work. All answers use a 2,048-token Reader ceiling, thinking disabled, and the same local Qwen service.

| Domain | Method | Repeat | Correct / 4 | Complete / 4 | Trunc | Service | Parse | Reader input/output tokens | Prompt / Reader wall s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| web | fresh | r1 | 3/4 | 4/4 | 0 | 0 | 0 | 31334/47 | 15.98 / 10.39 |
| web | b3 | r1 | 3/4 | 4/4 | 0 | 0 | 0 | 41813/138 | 14.00 / 15.99 |
| web | ours | r1 | 3/4 | 4/4 | 0 | 0 | 0 | 40505/1133 | 16.10 / 43.80 |
| enterprise | fresh | r1 | 2/4 | 4/4 | 0 | 0 | 0 | 17064/34 | 16.10 / 5.85 |
| enterprise | fresh | r2 | 2/4 | 4/4 | 0 | 0 | 0 | 16777/459 | 15.89 / 17.65 |
| enterprise | b3 | r1 | 3/4 | 4/4 | 0 | 0 | 0 | 18334/36 | 16.92 / 6.32 |
| enterprise | b3 | r2 | 3/4 | 4/4 | 0 | 0 | 0 | 21199/693 | 16.86 / 25.05 |
| enterprise | ours | r1 | 2/4 | 4/4 | 0 | 0 | 0 | 19607/305 | 16.27 / 14.10 |
| enterprise | ours | r2 | 2/4 | 4/4 | 0 | 0 | 0 | 17291/256 | 15.53 / 12.07 |

All 36 scored responses (9 rows × 4 questions) were complete, boxed and service-successful, with zero truncation, service failure or parse failure. Web is 3/4 for all three methods. Enterprise is 2/4 for Fresh in both repeats, 3/4 for B3 in both repeats, and 2/4 for Ours in both repeats. The stable enterprise gap is therefore a quality constraint on this representative state-revision snapshot, not evidence of quality preservation for Ours.

The misses are concentrated in dynamic/procedure questions and vary in answer wording; source-grounded construction checks still pass. We retain the negative result and do not select Ours as a quality-equivalent update method until a broader Reader/QA evaluation is completed.

Raw aggregate: `results/tables/agentrunbook_revision_reader_regression.csv`. Per-question answers: `results/tables/agentrunbook_revision_reader_per_question.csv`.
