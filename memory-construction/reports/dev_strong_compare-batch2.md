# First real construction comparison

Run: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-e2e-batch2-20261013`

Derived development workload, text-only. Scope: construction_e2e. Model calls are independent; no replay. Cold model load, warmup, Reader and Judge are excluded equally. Dense embedding/index is included through readable publication. These are requested checkpoint construction latencies, not streaming arrival-rate Freshness. Resolve/state/workflow are deterministic local views; only extraction uses the LLM.

Checkpoint attempts: 24; failures: 0; jointly successful pairs: 0. QA: not_evaluated. P95 is descriptive for this small sample.

Workload: 4 fixed windows, 45 source events; source SHA256 `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
Configuration hash: `7d74bd1f406642c0818f03690f4f7cbd7a17122b2f006387d9090cde68716dec`. Prompt and source-code copies are frozen under `frozen_code/`.

- Ours-dev: 100.288 s total, 33.989 s cold-build checkpoints, 66.299 s later checkpoint service; 45 live calls; 90640 input / 3852 output tokens; 12/12 snapshot checks.
- B3-c2: 100.270 s total, 34.041 s cold-build checkpoints, 66.229 s later checkpoint service; 45 live calls; 90640 input / 3852 output tokens; 12/12 snapshot checks.
Ours-dev bottleneck: 91.237/100.288 s (90.98%) in live extraction calls; local graph/cache/view/publish remainder 9.051 s.
B3-c2 bottleneck: 91.216/100.270 s (90.97%) in live extraction calls; local graph/cache/view/publish remainder 9.055 s.
Ours-dev vs strong B3-c2, 12 joint-success pairs: 100.270 vs 100.288 s, -0.02% candidate reduction (negative is regression); exact semantic matches 12/12. No failed pairs are imputed.

Next: run the same real bounded batch2 opportunity for Ours-dev and strong B3, then compare a justified prefix-context candidate with retained quality risks. Select the next optimization from actual extraction/embedding/local publication costs; retain ties and regressions.

Raw checkpoint log: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-e2e-batch2-20261013/checkpoint_metrics.jsonl`. Requests/responses: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-e2e-batch2-20261013/llm_calls.jsonl`. Snapshots and paired checks are retained under the same run.
