# Common-preflight paired construction screen (adapted)

Two long enterprise trajectories (`0ab99e0c`, `49f98e9e`), complete trajectories (31 states / 29 transitions), same local Qwen3.5-9B controller and Qwen3-Embedding-8B backend, 18,000-token input safety bound, 2,048 output tokens per event, no retries, text-only requests. The paired group candidate reuses the existing 12,000-character/state fallback before deciding whether each adjacent pair fits; over-budget groups split locally. Wall time runs through save/load publication validation.

| Variant | Publish s | Controller calls (failed) | LLM input/output tokens | Embedding calls/vectors/input tokens | Parsed/split joint groups | Events | Structural/source checks |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline | 277.40 | 32 (0) | 283175/5868 | 8/64/132324 | 0/0 | 29 | pass |
| joint | 274.71 | 20 (0) | 224445/6282 | 8/64/131269 | 13/1 | 29 | pass |

Paired deltas: the joint candidate reduces controller calls 37.5% and LLM input tokens 20.7%, raises LLM output tokens 7.1%, and changes build-to-publish wall time -1.0% (277.40s → 274.71s). Embedding work is unchanged in vector count (64 each); embedding input tokens are 132324 vs 131269.

The joint run parsed 13 groups and split 1 oversized groups; all 29 transition IDs, source action mappings, state pairs and order were present. Save/reload validation passed for both variants. This is structural/source evidence, not downstream Reader or official QA.

Decision: retain as a small call/token efficiency candidate with near-tie wall time; do not call it a material cold-build speedup or a quality-equivalent selected default. The fixed-10 common-preflight expansion already recorded in PAPER02 remains negative on wall time, so it is not rerun as a duplicate scale point.

Raw table: `results/tables/construction_pair_v4_common_preflight.csv`. Per-run source checks are stored beside each snapshot in `construction_quality_checks.json`.
