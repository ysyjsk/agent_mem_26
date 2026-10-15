# Draft: reducing repeated work in event-based agent memory construction

## Setting

We evaluate a text-only adaptation of AgentRunbook-R on a frozen development workload: eight official-source questions, ten complete trajectories,91 observed states,81 transitions, and20 trajectory-level notes. Each domain has one shared memory containing the evidence trajectories and fixed distractors. Queries reuse that memory rather than rebuilding question-conditioned corpora. This is not a native multimodal Small result or an official Judge score.

All variants retain the complete raw trajectories, one generated event per transition, both procedure and hint notes, their embeddings, and source mappings. The original text-only note path uses URLs, thoughts and actions; it does not reconstruct screenshot content. Controller and Reader use the same resident local Qwen3.5-9B service, with thinking disabled and fixed sampling. The embedding model is Qwen3-Embedding-8B. Single/paired event ceilings are2048/4096 tokens, while the Reader ceiling is2048. Original note requests ask for8192, but the resident service actually caps output at4096. No additional generation steps are introduced to create artificial acceleration opportunities.

## Mechanisms

Adjacent joint extraction submits two consecutive transitions in one model request. Task context and the annotated action trace are shared, and the intermediate state is included once. The model returns two separately identified events with the original overview and state-transition fields. Invalid or oversized groups split locally; successful groups are not regenerated. A singleton arrival is processed immediately, without waiting for future events.

Exact construction embedding reuse operates on the actual token-bounded text sent to the embedding model. Keys include the model, endpoint, relevant input configuration, and exact prepared text. Identical inputs share a computed vector; all original event/window source mappings remain separate. No averaging or similarity-based substitution is used.

The update comparison retains a strong B3-style exact-request cache and exact vector cache in both methods. The additional mechanism validates each output event against its own source/context dependencies, allowing a changed subset of adjacent events to be regrouped without regenerating unaffected group siblings. Both methods begin from independent copies of the same already-built snapshot. This is explicitly an AgentRunbook-R adapted mechanism comparison, not a relabeling of the historical workflow-core B3/Ours experiments.

## Measurement

Cold construction begins with empty method memory and ends after persistence and reload verification; GPU model loading is excluded because weights are resident for all variants. Two domain build wall times are summed, not summed request durations. Construction, retrieval, Reader, and subsequent update costs remain separate. Historical reused artifacts are marked and never reported as a newly measured cold build.

Client telemetry is reconciled with the resident server log: SDK automatic retries can hide multiple physical HTTP requests. Failed usage is unknown, not zero. V1 exposed128 OOM attempts arising from32 failed SDK calls. V2 therefore freezes a shared18000-token preflight rule and disables automatic controller retries; oversized single requests enter the existing12000-character/state fallback before sending. Full raw source remains queryable. This common failure handling is not attributed to either candidate.

## Preliminary results

On the first complete eight-state trajectory, joint extraction reduces event requests7→4, total controller calls8→5, and reported input tokens38824→29581 (−23.8%). Both sides preserve all seven events and both notes and pass the same five source-backed fact probes. Publication time61.20→61.51s does not demonstrate speedup: output tokens increase1528→1608, and decoding cost remains substantial.

On all five web trajectories, the matched V1 joint run reduces publication time558.09→520.17s (−6.8%) and reported successful-call input tokens252945→211444 (−16.4%). Both produce complete answers on4/4 questions with development correctness3/4. The joint run introduces two failed SDK calls/eight physical OOM attempts; their usage is unknown and excluded from the reported token totals. Thus the token result is a reduction in measured successful work, not a claim about unobserved failed compute.

The V1 ten-trajectory baseline completes in1339.04s with8/8 complete responses and6/8 development correctness. The controlled V2 four-cell matrix is in progress; do not fill unmeasured cells, claim an established best combination, or generalize the screening result to a held-out benchmark.

## Limits and next evidence

Eight development questions cannot establish statistical quality equivalence. Structural source/event checks and literal probes are complementary but not full semantic evaluation. Samples are stochastic, so a one-question difference is interpreted alongside existing matched-repeat variation. Larger-corpus repetitions, component ablations, and local-update measurements must precede a broad efficiency claim. No DAG speedup is claimed unless expensive extraction or embedding work actually decreases against valid B3 caches.

Raw results: `results/tables/construction_pair_runs.csv`, `results/tables/construction_pair_full10.csv`, `runs/construction-pair-v1/`, and the separately frozen `runs/construction-pair-v2/`.
