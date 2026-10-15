# Fixed-10 enterprise expansion: common-preflight joint extraction

The two-trajectory screen was positive for wall time and LLM work, so the same code/configuration was expanded to the frozen five-trajectory enterprise workload (49 transitions). The existing V2 baseline is directly reusable: the candidate only changes joint-group preparation, while single-event preparation, model, output budget, retries, embedding reuse and persistence boundary remain matched.

| Variant | Wall s | Controller calls (failed) | LLM input/output | Embedding vectors/input | Joint parsed/split | Events | Quality |
|---|---:|---:|---:|---:|---:|---:|---|
| existing-v2-baseline | 502.39 | 59 (0) | 495377/11014 | 127/231324 | 0/0 | 49 | pass |
| v3-common-preflight-joint | 1203.82 | 36 (0) | 355456/25824 | 108/208308 | 23/0 | 49 | pass |

The candidate reduces controller calls by 39.0% and known LLM input tokens by 28.2%, but wall time increases 139.6% (502.39→1203.82s) because joint responses produce 25,824 output tokens versus 11,014 for baseline. All 49 transition events and source mappings are present and save/reload checks pass. This is retained as a negative wall-time result: the method reduces necessary request/input work but does not yet reduce end-to-end construction latency on the full enterprise workload.

Decision: do not expand this exact candidate to web or call it the final configuration. Return to update cost/quality and output-length control; any later output-budget change must preserve the required per-event evidence and be measured as a new candidate.
