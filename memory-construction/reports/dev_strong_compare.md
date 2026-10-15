# First real construction comparison

Run: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-e2e-c1-20261013`

Derived development workload, text-only. Scope: construction_e2e. Model calls are independent; no replay. Cold model load, warmup, Reader and Judge are excluded equally. Dense embedding/index is included through readable publication. These are requested checkpoint construction latencies, not streaming arrival-rate Freshness. Resolve/state/workflow are deterministic local views; only extraction uses the LLM.

Checkpoint attempts: 36; failures: 0; jointly successful pairs: 12. QA: not_evaluated. P95 is descriptive for this small sample.

Workload: 4 fixed windows, 45 source events; source SHA256 `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
Configuration hash: `e9c695de3ca9bc147dc7797335793fad30f01e4fe898d17826ad1bb1866a0b20`. Prompt and source-code copies are frozen under `frozen_code/`.

- B0: 286.444 s total, 49.130 s cold-build checkpoints, 237.314 s later checkpoint service; 93 live calls; 183591 input / 7943 output tokens; 12/12 snapshot checks.
- Ours-dev: 139.112 s total, 48.855 s cold-build checkpoints, 90.257 s later checkpoint service; 45 live calls; 90640 input / 3842 output tokens; 12/12 snapshot checks.
- B3-c1: 138.512 s total, 48.695 s cold-build checkpoints, 89.817 s later checkpoint service; 45 live calls; 90640 input / 3842 output tokens; 12/12 snapshot checks.

Joint-success pairs only (12): total latency 286.444 vs 139.112 s, 51.43% reduction. Exact structured semantic matches: 12/12. This is relative to repeated Fresh, not strong B3.
Joint-success input-token reduction: 50.63% (183591 vs 90640); all failed checkpoints remain in the table and raw log.
B0 bottleneck: 270.821/286.444 s (94.55%) in live extraction calls; local graph/cache/view/publish remainder 15.622 s.
Ours-dev bottleneck: 129.988/139.112 s (93.44%) in live extraction calls; local graph/cache/view/publish remainder 9.124 s.
B3-c1 bottleneck: 129.410/138.512 s (93.43%) in live extraction calls; local graph/cache/view/publish remainder 9.102 s.
Ours-dev vs strong B3-c1, 12 joint-success pairs: 138.512 vs 139.112 s, -0.43% candidate reduction (negative is regression); exact semantic matches 12/12. No failed pairs are imputed.

Next: add the same dense embedding/index publication boundary for both methods, and a legitimate conservative-partition cached B3. The largest expected component here is model extraction; inspect per-call and checkpoint model_elapsed_s before selecting the next optimization.

Raw checkpoint log: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-e2e-c1-20261013/checkpoint_metrics.jsonl`. Requests/responses: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-e2e-c1-20261013/llm_calls.jsonl`. Snapshots and paired checks are retained under the same run.
