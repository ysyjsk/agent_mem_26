# PAPER05 continuous-arrival Freshness and Goodput (adapted)

This is a real local-model text-only/adapted stream probe, not the official LongMemEval Small streaming protocol. Both methods start from independent clones of the same persisted enterprise snapshot. The target trajectory is deliberately absent from each clone; source states then arrive in three batches of 1, 2 and 3 transitions (cumulative prefixes 1, 3 and 6). Every batch performs real AgentRunbook-R extraction and Embedding, saves a queryable artifact, reloads it, and runs a retrieval probe. No replay responses are used.

Freshness is measured from batch arrival to queryable publication, including save/reload but excluding the separate retrieval probe. Goodput is newly arrived transitions divided by summed publication time. Batch members share the same publication timestamp; the per-transition P50/P95 therefore weights batch sizes. Stream wall time includes retrieval probes and is reported separately.

## Paired summary

| Method | Completed batches | Publish s total | Freshness P50 s | Freshness P95 s | Goodput transitions/s | Controller calls | LLM input tokens | Embedding calls/vectors | Quality + retrieval probes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| b3 | 3/3 | 187.30 | 74.46 | 98.12 | 0.0320 | 9 | 76918 | 9/16 | 3/3 + 3/3 |
| ours | 3/3 | 190.34 | 79.98 | 90.97 | 0.0315 | 10 | 77369 | 9/16 | 3/3 + 3/3 |

## Per-arrival measurements

| Batch | New transitions | Method | Publish s | Controller calls | Input tokens | Output tokens | Embedding vectors | Re-extracted events | Notes regenerated | Quality + reload/retrieval |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 1 | b3 | 38.38 | 2 | 10565 | 572 | 3 | 1 | 2 | True / True |
| 1 | 1 | ours | 30.37 | 2 | 10565 | 520 | 3 | 1 | 2 | True / True |
| 2 | 2 | b3 | 50.79 | 3 | 23678 | 817 | 5 | 3 | 2 | True / True |
| 2 | 2 | ours | 69.00 | 4 | 24129 | 1188 | 5 | 3 | 2 | True / True |
| 3 | 3 | b3 | 98.12 | 4 | 42675 | 1364 | 8 | 6 | 2 | True / True |
| 3 | 3 | ours | 90.97 | 4 | 42675 | 1309 | 8 | 6 | 2 | True / True |

On this continuous prefix-arrival protocol, Ours is not selected: compared with B3, publish-time total changes from 187.30s to 190.34s (+1.6%), controller calls from 9 to 10, and known LLM input from 76918 to 77369 (+0.6%). Freshness P95 is 98.12s for B3 versus 90.97s for Ours; all 6/6 source-grounded checks and 6/6 reload/retrieval probes pass.

The negative result is mechanistic rather than a quality failure. The current event-dependency key includes the complete action sequence and transition count. Each newly longer prefix therefore changes the request context for every event, so Ours receives no event-level reuse in this arrival protocol and may form one extra group. This confirms that the existing dependency key is appropriate for revisions with stable trajectory length, but is not yet a streaming-growth optimization. The result is retained; no global dependency was removed to manufacture cache hits.

Raw data: `results/tables/streaming_freshness_goodput.csv`; run manifest and per-arrival records: `runs/agentrunbook-stream-v1-enterprise-0ab99e0c`. Official Judge/native quality remains pending.
