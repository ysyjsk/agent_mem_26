# First real construction comparison

Run: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-quality-v3-request-cache-kernel-20261013`

Derived development workload, text-only. Scope: construction_kernel. Model calls are independent; no replay. Cold model load, warmup, Reader and Judge are excluded equally. Dense embedding/index is excluded equally. These are requested checkpoint construction latencies, not streaming arrival-rate Freshness. Resolve/state/workflow are deterministic local views; only extraction uses the LLM.

Checkpoint attempts: 24; failures: 0; jointly successful pairs: 0. QA: not_evaluated. P95 is descriptive for this small sample.

Workload: 4 fixed windows, 45 source events; source SHA256 `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
Configuration hash: `cfe6d98ea14a1451fff0445fa9f92c57cf663e85f2cec4f716cbaa345b7396dc`. Prompt and source-code copies are frozen under `frozen_code/`.

- Ours-dev: 128.073 s total, 40.951 s cold-build checkpoints, 87.122 s later checkpoint service; 45 live calls; 96242 input / 5132 output tokens; 12/12 snapshot checks.
- B3-c2: 128.014 s total, 40.822 s cold-build checkpoints, 87.192 s later checkpoint service; 45 live calls; 96242 input / 5132 output tokens; 12/12 snapshot checks.
Ours-dev bottleneck: 121.128/128.073 s (94.58%) in live extraction calls; local graph/cache/view/publish remainder 6.945 s.
B3-c2 bottleneck: 121.171/128.014 s (94.65%) in live extraction calls; local graph/cache/view/publish remainder 6.843 s.
Ours-dev vs strong B3-c2, 12 joint-success pairs: 128.014 vs 128.073 s, -0.05% candidate reduction (negative is regression); exact semantic matches 12/12. No failed pairs are imputed.

Next: add the same dense embedding/index publication boundary and a legitimate conservative-partition cached strong B3. Select the next optimization from actual extraction/embedding/local publication costs; retain ties and regressions.

Raw checkpoint log: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-quality-v3-request-cache-kernel-20261013/checkpoint_metrics.jsonl`. Requests/responses: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-quality-v3-request-cache-kernel-20261013/llm_calls.jsonl`. Snapshots and paired checks are retained under the same run.
