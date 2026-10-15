# PAPER02 cold-construction candidates

All rows are local text-only/adapted measurements with resident Qwen3.5-9B/Qwen3-Embedding-8B, the frozen 18,000-token preflight, 2,048 output tokens per event, zero controller retries, and save/reload publication checks. Construction, query, Reader and official Judge are separate. The first four rows are the matched four-cell 10-trajectory matrix; the final row is the fixed-10 enterprise expansion of common-preflight joint extraction.

| Candidate | Scope | Wall s | Controller calls (failed) | LLM input/output | Embedding calls/vectors/input | Joint parsed/split | Events | Quality | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| baseline | web+enterprise / 10 complete trajectories / 91 states | 830.00 | 93 (0) | 735023/18603 | 40/192/370342 | not recorded/0 | 81 | pass | reference |
| joint | web+enterprise / 10 complete trajectories / 91 states | 1025.77 | 78 (0) | 686954/19030 | 40/192/369525 | not recorded/21 | 81 | pass | negative wall-time candidate; retain as call/token ablation |
| embed | web+enterprise / 10 complete trajectories / 91 states | 882.95 | 97 (0) | 736591/19845 | 40/184/337503 | not recorded/0 | 81 | pass | low-risk vector-saving ablation; no wall-time gain |
| combined | web+enterprise / 10 complete trajectories / 91 states | 989.91 | 76 (0) | 666712/19254 | 40/184/337063 | not recorded/20 | 81 | pass | most measured input/call reduction; not selected because wall and one-question score regress |
| common-preflight joint (enterprise fixed-10) | enterprise / 5 complete trajectories / 54 states / 49 events | 1203.82 | 36 (0) | 355456/25824 | 20/108/208308 | 23/0 | 49 | pass | negative full-10 wall-time result; retain as required ablation, do not select |

## Measured trade-offs

In the matched 10-trajectory matrix, joint extraction lowers controller calls by 16.1% and input tokens by 6.5%, but increases wall time by 23.6%. Exact embedding reuse lowers vectors from 192 to 184 (8 exact hits) but raises wall time from 830.0015984240017s to 882.9542544959986s. The combined candidate gives the largest measured input/call reduction (666,712 input tokens; 76 calls) but reaches 6/8 rather than the baseline 7/8 and is slower than baseline.
The common-preflight fixed-10 enterprise expansion reduces calls from 59 to 36 (39.0%) and input tokens from 495,377 to 355,456 (28.2%), but wall time grows from 502.39s to 1,203.82s because output tokens grow to 25,824. All 49 events and source mappings pass structural/reload checks; the candidate is retained as a negative result and not selected as the final cold-build configuration.

The paper-supported conclusion is therefore conditional: joint/preflight grouping can reduce necessary request and input work, but serialized decoding and longer multi-event responses dominate end-to-end wall time on the fixed-10 enterprise workload. The selected update mechanism is evaluated separately against these cold-build ablations.

## Frozen configuration decision

For the remaining adapted construction/update experiments, use the existing bounded common-preflight path (`LME_EVENT_GROUP_SIZE=2`, shared bounded state preparation, split on the 18,000-token safety bound, 2,048 event-output tokens) with exact-input Embedding reuse enabled. This is selected as a cost-efficiency configuration, not as a universal wall-time win: the two-trajectory paired screen cuts controller calls by 37.5% and known LLM input by 20.7% at a 1.0% wall-time near-tie, while the fixed-10 expansion is explicitly retained as a negative wall-time result. Single-event extraction remains the latency reference and is used where a group exceeds the safe input bound. All downstream tables must report the variant and keep cold-build latency separate from incremental-update latency.
