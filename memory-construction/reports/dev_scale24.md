# First real construction comparison

Run: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-dev24-batch2-20261013`

Derived development workload, text-only. Scope: construction_e2e. Model calls are independent; no replay. Cold model load, warmup, Reader and Judge are excluded equally. Dense embedding/index is included through readable publication. These are requested checkpoint construction latencies, not streaming arrival-rate Freshness. Resolve/state/workflow are deterministic local views; only extraction uses the LLM.

Checkpoint attempts: 180; failures: 0; jointly successful pairs: 60. QA: not_evaluated. P95 is descriptive for this small sample.

Workload: 24 fixed windows, 205 source events; source SHA256 `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
Configuration hash: `7d74bd1f406642c0818f03690f4f7cbd7a17122b2f006387d9090cde68716dec`. Prompt and source-code copies are frozen under `frozen_code/`.

- B0: 1268.666 s total, 257.371 s cold-build checkpoints, 1011.295 s later checkpoint service; 413 live calls; 819130 input / 34553 output tokens; 60/60 snapshot checks.
- Ours-dev: 476.220 s total, 188.934 s cold-build checkpoints, 287.286 s later checkpoint service; 205 live calls; 412723 input / 17120 output tokens; 60/60 snapshot checks.
- B3-c2: 473.990 s total, 187.269 s cold-build checkpoints, 286.721 s later checkpoint service; 205 live calls; 412723 input / 17120 output tokens; 60/60 snapshot checks.

Joint-success pairs only (60): total latency 1268.666 vs 476.220 s, 62.46% reduction. Exact structured semantic matches: 12/60. This is relative to repeated Fresh, not strong B3.
Joint-success input-token reduction: 49.61% (819130 vs 412723); all failed checkpoints remain in the table and raw log.
B0 bottleneck: 1198.745/1268.666 s (94.49%) in live extraction calls; local graph/cache/view/publish remainder 69.921 s.
Ours-dev bottleneck: 433.735/476.220 s (91.08%) in live extraction calls; local graph/cache/view/publish remainder 42.485 s.
B3-c2 bottleneck: 431.117/473.990 s (90.95%) in live extraction calls; local graph/cache/view/publish remainder 42.873 s.
Ours-dev vs strong B3-c2, 60 joint-success pairs: 473.990 vs 476.220 s, -0.47% candidate reduction (negative is regression); exact semantic matches 60/60. No failed pairs are imputed.

Next: run the same real bounded batch2 opportunity for Ours-dev and strong B3, then compare a justified prefix-context candidate with retained quality risks. Select the next optimization from actual extraction/embedding/local publication costs; retain ties and regressions.

Raw checkpoint log: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-dev24-batch2-20261013/checkpoint_metrics.jsonl`. Requests/responses: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-dev24-batch2-20261013/llm_calls.jsonl`. Snapshots and paired checks are retained under the same run.
