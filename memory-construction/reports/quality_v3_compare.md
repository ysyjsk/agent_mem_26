# First real construction comparison

Run: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-quality-v3-20261013`

Derived development workload, text-only. Scope: construction_e2e. Model calls are independent; no replay. Cold model load, warmup, Reader and Judge are excluded equally. Dense embedding/index is included through readable publication. These are requested checkpoint construction latencies, not streaming arrival-rate Freshness. Resolve/state/workflow are deterministic local views; only extraction uses the LLM.

Checkpoint attempts: 36; failures: 0; jointly successful pairs: 12. QA: not_evaluated. P95 is descriptive for this small sample.

Workload: 4 fixed windows, 45 source events; source SHA256 `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
Configuration hash: `ffb53b936e95eacfebcfc1feadb480af3e99b6158aee2eecb8e273d77eb12da9`. Prompt and source-code copies are frozen under `frozen_code/`.

- B0: 475.425 s total, 74.950 s cold-build checkpoints, 400.475 s later checkpoint service; 93 live calls; 196372 input / 10189 output tokens; 12/12 snapshot checks.
- Ours-dev: 218.883 s total, 61.462 s cold-build checkpoints, 157.421 s later checkpoint service; 45 live calls; 96242 input / 5132 output tokens; 12/12 snapshot checks.
- B3-c2: 215.861 s total, 60.560 s cold-build checkpoints, 155.301 s later checkpoint service; 45 live calls; 96242 input / 5132 output tokens; 12/12 snapshot checks.

Joint-success pairs only (12): total latency 475.425 vs 218.883 s, 53.96% reduction. Exact structured semantic matches: 4/12. This is relative to repeated Fresh, not strong B3.
Joint-success input-token reduction: 50.99% (196372 vs 96242); all failed checkpoints remain in the table and raw log.
B0 bottleneck: 336.348/475.425 s (70.75%) in live extraction calls; local graph/cache/view/publish remainder 139.077 s.
Ours-dev bottleneck: 123.295/218.883 s (56.33%) in live extraction calls; local graph/cache/view/publish remainder 95.588 s.
B3-c2 bottleneck: 122.650/215.861 s (56.82%) in live extraction calls; local graph/cache/view/publish remainder 93.212 s.
Ours-dev vs strong B3-c2, 12 joint-success pairs: 215.861 vs 218.883 s, -1.40% candidate reduction (negative is regression); exact semantic matches 12/12. No failed pairs are imputed.

Next: run the same real bounded batch2 opportunity for Ours-dev and strong B3, then compare a justified prefix-context candidate with retained quality risks. Select the next optimization from actual extraction/embedding/local publication costs; retain ties and regressions.

Raw checkpoint log: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-quality-v3-20261013/checkpoint_metrics.jsonl`. Requests/responses: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-quality-v3-20261013/llm_calls.jsonl`. Snapshots and paired checks are retained under the same run.
