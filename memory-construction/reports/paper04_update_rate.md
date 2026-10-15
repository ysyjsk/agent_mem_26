# Controlled update-rate screen (adapted)

One enterprise trajectory (`0ab99e0c`), one shared starting snapshot, independent B3/Ours cache clones; state revisions are applied at indices 4..(4+n-1). This is a controlled single-trajectory screen, not a population estimate. Setup/seed load is excluded; wall time covers update through queryable publication. Quality is source-grounded/persisted-state checks, not official QA.

| Revised states | Method | Publish s | LLM calls | Input tokens | Output tokens | Event outputs | Embedding vectors | Quality |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | b3 | 156.38 | 7 | 97322 | 2307 | 14 | 14 | True |
| 1 | ours | 23.02 | 1 | 14325 | 340 | 2 | 2 | True |
| 3 | b3 | 174.15 | 7 | 97238 | 2352 | 14 | 14 | True |
| 3 | ours | 45.77 | 2 | 28639 | 691 | 4 | 4 | True |
| 6 | b3 | 176.29 | 7 | 97214 | 2502 | 14 | 14 | True |
| 6 | ours | 87.87 | 4 | 52394 | 1148 | 7 | 7 | True |

Paired deltas (Ours relative to B3)

| Revised states | Publish latency reduction | LLM input-token reduction | Re-extracted event-output reduction |
|---:|---:|---:|---:|
| 1 | 85.3% | 85.3% | 85.7% |
| 3 | 73.7% | 70.5% | 71.4% |
| 6 | 50.2% | 46.1% | 50.0% |

Paper-ready summary: On this fixed snapshot, event-level dependency reuse reduces update work across the 1/3/6-state screen: mean publish-latency reduction 69.7%, mean LLM-input reduction 67.3%, and mean re-extracted-event-output reduction 69.0%. These are paired measurements on one enterprise trajectory, not a domain-level average.

## Fixed Reader regression on the 6-revision pair

Same four fixed enterprise questions, text-only/adapted Qwen Reader, 2,048-token output ceiling, thinking disabled; this is a local development proxy, not official Judge QA. Reader checks are a separate quality constraint from the source-grounded publication checks above.

| Method | Correct / 4 | Complete / 4 | Truncated | Service failures | Parse failures | Reader wall s |
|---|---:|---:|---:|---:|---:|---:|
| b3 | 3/4 | 4/4 | 0 | 0 | 0 | 12.86 |
| ours | 2/4 | 4/4 | 0 | 0 | 0 | 156.11 |

Both update snapshots pass source-grounded persistence checks, but this small Reader slice scores B3 3/4 vs Ours 2/4. This matches the previously observed enterprise state-revision direction (3/4 vs 2/4), while the broader eight-case fixed Reader regression ties at 21/32 per method; it does not establish per-slice quality equivalence. All answers in this new pair were complete/parseable with zero truncation, service or parse failures.
