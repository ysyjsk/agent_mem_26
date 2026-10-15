# First real construction comparison

Run: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-quality-v3-request-cache-e2e-20261013`

Derived development workload, text-only. Scope: construction_e2e. Model calls are independent; no replay. Cold model load, warmup, Reader and Judge are excluded equally. Dense embedding/index is included through readable publication. These are requested checkpoint construction latencies, not streaming arrival-rate Freshness. Resolve/state/workflow are deterministic local views; only extraction uses the LLM.

Checkpoint attempts: 24; failures: 0; jointly successful pairs: 0. QA: not_evaluated. P95 is descriptive for this small sample.

Workload: 4 fixed windows, 45 source events; source SHA256 `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
Configuration hash: `c957301df1f271943ffc87599b5701ff4d4fd14ec04225391fa453cc9c592214`. Prompt and source-code copies are frozen under `frozen_code/`.

- Ours-dev: 190.967 s total, 58.491 s cold-build checkpoints, 132.476 s later checkpoint service; 45 live calls; 96242 input / 5132 output tokens; 12/12 snapshot checks.
- B3-c2: 191.761 s total, 58.745 s cold-build checkpoints, 133.015 s later checkpoint service; 45 live calls; 96242 input / 5132 output tokens; 12/12 snapshot checks.
Ours-dev bottleneck: 120.793/190.967 s (63.25%) in live extraction calls; local graph/cache/view/publish remainder 70.174 s.
B3-c2 bottleneck: 121.205/191.761 s (63.21%) in live extraction calls; local graph/cache/view/publish remainder 70.556 s.
Ours-dev vs strong B3-c2, 12 joint-success pairs: 191.761 vs 190.967 s, 0.41% candidate reduction (negative is regression); exact semantic matches 12/12. No failed pairs are imputed.

Next: run the same real bounded batch2 opportunity for Ours-dev and strong B3, then compare a justified prefix-context candidate with retained quality risks. Select the next optimization from actual extraction/embedding/local publication costs; retain ties and regressions.

Raw checkpoint log: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-quality-v3-request-cache-e2e-20261013/checkpoint_metrics.jsonl`. Requests/responses: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-quality-v3-request-cache-e2e-20261013/llm_calls.jsonl`. Snapshots and paired checks are retained under the same run.
