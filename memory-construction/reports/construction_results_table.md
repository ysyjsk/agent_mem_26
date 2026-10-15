# Construction candidate table (fixed 10 trajectories)

Source: `results/tables/construction_pair_v2_full10.csv`; all cells use the same text-only/adapted data, model, output budgets, preflight, retries=0, persistence/reload boundary and frozen query stack. Each cell is one cold build per domain, summed for the table. Every cell retains 81 events,20 notes,91 states and passes structural source coverage.

| Candidate | Build publish s | LLM calls | LLM input tokens | Embedding vectors | Embedding input tokens | Complete/correct (8) | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| Baseline | 830.00 | 93 | 735,023 | 192 | 370,342 | 8/8, 7/8 | Reference |
| Joint extraction | 1,025.77 | 78 | 686,954 | 192 | 369,525 | 8/8, 7/8 | Keep as token/call ablation; not latency winner |
| Embedding exact reuse | 882.95 | 97 | 736,591 | 184 (8 hits) | 337,503 | 8/8, 7/8 | Keep as low-risk vector saving |
| Combined | 989.91 | 76 | 666,712 | 184 (8 hits) | 337,063 | 8/8, 6/8 | Most necessary-work reduction, but quality/wall trade-off |

The baseline/joint call totals include only successful calls; V2 preflight prevents known oversized single-event OOMs and all physical API failures are zero. Output and wall time remain stochastic on the serialized local service. Joint groups split locally when the 18k preflight cannot fit; 21 of 81 transitions were split in the combined aggregate.

The quality column is fixed development scoring, not official multimodal/Judge quality. Complete answers are tracked separately from correctness. Query-side exact embedding reuse is not counted in these construction numbers.
