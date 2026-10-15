# First real construction comparison

Run: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-corrected-20261013`

Derived development workload, text-only. Model calls are independent; no replay. Cold model load, warmup, dense embeddings, Reader and Judge are excluded equally. These are checkpoint construction latencies, not end-to-end Freshness. Resolve/state/workflow are deterministic local views in this current Ours-dev implementation; only extraction uses the LLM.

Checkpoint attempts: 24; failures: 0; jointly successful pairs: 12. QA: not_evaluated. P95 is descriptive for this small sample.

Workload: 4 fixed windows, 45 source events; source SHA256 `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
Configuration hash: `6cf2acec7960fc2dbe3a503883cddc78d728c1f5673b329223a338f4a9a75a92`. Prompt and source-code copies are frozen under `frozen_code/`.

- B0: 386.814 s total, 60.856 s cold-build checkpoints, 325.957 s later checkpoint service; 93 live calls; 183591 input / 7943 output tokens; 12/12 snapshot checks.
- Ours-dev: 193.689 s total, 70.927 s cold-build checkpoints, 122.762 s later checkpoint service; 45 live calls; 90640 input / 3842 output tokens; 12/12 snapshot checks.

Joint-success pairs only (12): total latency 386.814 vs 193.689 s, 49.93% reduction. Exact structured semantic matches: 12/12. This is relative to repeated Fresh, not strong B3.
Joint-success input-token reduction: 50.63% (183591 vs 90640); all failed checkpoints remain in the table and raw log.
B0 bottleneck: 385.591/386.814 s (99.68%) in live extraction calls; local graph/cache/view/publish remainder 1.223 s.
Ours-dev bottleneck: 192.704/193.689 s (99.49%) in live extraction calls; local graph/cache/view/publish remainder 0.985 s.

Next: add the same dense embedding/index publication boundary for both methods, and a legitimate conservative-partition cached B3. The largest expected component here is model extraction; inspect per-call and checkpoint model_elapsed_s before selecting the next optimization.

Raw checkpoint log: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-corrected-20261013/checkpoint_metrics.jsonl`. Requests/responses: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/runs/fast-compare-v4-corrected-20261013/llm_calls.jsonl`. Snapshots and paired checks are retained under the same run.
