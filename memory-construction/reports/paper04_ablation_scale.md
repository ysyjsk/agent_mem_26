# PAPER04 adapted ablations, scale and update intensity

This report uses measured text-only/adapted runs only. The four-cell cold matrix is the component ablation (joint extraction × exact embedding reuse); the scale rows reuse frozen 12- and 24-window construction runs; update-intensity rows are descriptive strata from the eight fixed revision cases, computed as re-extracted event outputs divided by the trajectory's original event count. They are not a post-hoc claim of a separately randomized update-rate sweep.

## Cold construction component ablation

| Variant | Scope | Wall s | Controller calls | Input tokens | Output tokens | Embedding vectors | Quality |
|---|---|---:|---:|---:|---:|---:|---|
| baseline | web+enterprise / 10 complete trajectories / 91 states | 830.00 | 93 | 735023 | 18603 | 192 | True |
| joint | web+enterprise / 10 complete trajectories / 91 states | 1025.77 | 78 | 686954 | 19030 | 192 | True |
| embed | web+enterprise / 10 complete trajectories / 91 states | 882.95 | 97 | 736591 | 19845 | 184 | True |
| combined | web+enterprise / 10 complete trajectories / 91 states | 989.91 | 76 | 666712 | 19254 | 184 | True |
| common-preflight joint (enterprise fixed-10) | enterprise / 5 complete trajectories / 54 states / 49 events | 1203.82 | 36 | 355456 | 25824 | 108 | True |

The fixed-10 combined variant reduces measured controller calls and input tokens but increases wall time relative to baseline; embedding reuse saves vectors without a wall-time gain. Common-preflight joint is retained as a negative fixed-10 result in PAPER02 rather than selected as the default.

## Frozen scale evidence

| Run scope | Method | Total s | Checkpoints | Calls | Input tokens | Reused nodes | Invalidated nodes | Snapshot checks |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 12 windows / 36 checkpoints | B3-c2 | 292.72 | 36 | 132 | 267781 | 144 | 1416 | 36 |
| 12 windows / 36 checkpoints | Ours-dev | 293.22 | 36 | 132 | 267781 | 744 | 444 | 36 |
| 24 windows / 60 checkpoints | B0 | 1268.67 | 60 | 413 | 819130 | 0 | 0 | 60 |
| 24 windows / 60 checkpoints | B3-c2 | 473.99 | 60 | 205 | 412723 | 208 | 2125 | 60 |
| 24 windows / 60 checkpoints | Ours-dev | 476.22 | 60 | 205 | 412723 | 1076 | 641 | 60 |

The 12/24-window rows are construction_e2e development measurements, not Freshness or official QA. B0 remains serial full-prefix rebuilding; Ours-dev and B3-c2 use the same frozen workload and actual bounded concurrency 2.

## Update-intensity strata

| Method/band | Cases | Mean ratio | Mean publish s | Mean calls | Mean input tokens | Quality rows |
|---|---:|---:|---:|---:|---:|---:|
| b3:high | 3 | 0.386 | 33.64 | 2.33 | 13198 | 3/3 |
| b3:low | 4 | 0.138 | 28.30 | 2.50 | 20853 | 4/4 |
| b3:medium | 1 | 0.200 | 13.77 | 1.00 | 9981 | 1/1 |
| ours:high | 2 | 0.286 | 20.86 | 1.50 | 4596 | 2/2 |
| ours:low | 4 | 0.138 | 28.95 | 2.50 | 20853 | 4/4 |
| ours:medium | 2 | 0.200 | 24.64 | 1.50 | 13523 | 2/2 |

Low/medium/high are observed event-recomputation strata, not a new controlled rate sweep. All primary revision rows pass source-grounded persistence checks; downstream Reader quality remains a separate constraint, with the enterprise state-revision regression showing B3 3/4 versus Ours 2/4.

A separate controlled update-rate screen is reported in `paper04_update_rate.md`; it varies 1/3/6 revised states on one fixed enterprise snapshot and is not conflated with these post-hoc strata.
Raw combined table: `results/tables/paper04_ablation_scale.csv`. Existing raw runs remain the source of truth.
