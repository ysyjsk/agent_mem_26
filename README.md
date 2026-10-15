# Agent Memory Construction — code and research results

This repository contains the current implementation, experiment runners, plans and real measured results of the Agent Memory Construction project. It is an analysis snapshot of the active server project, exported on 2026-10-15T01:18:53+08:00.

The research objective is to reduce memory construction/update time, model calls and tokens while maintaining memory quality and downstream usability. The current route is **local text-only/adapted**. Native multimodal reproduction and official hosted judging have separate pending status.

## Start here

1. [Architecture and analysis guide](ANALYSIS_GUIDE.md)
2. [Current complete research goal](memory-construction/GOAL.md)
3. [Current execution status](memory-construction/STATUS.md) and [task queue](memory-construction/execution/queue.json)
4. [Construction results](memory-construction/results/tables/construction_pair_v2_full10.csv)
5. [B3/Ours update results](memory-construction/results/tables/agentrunbook_update_b3_ours.csv)
6. [Cost-focused paper draft](memory-construction/reports/construction_cost_paper_draft.md)

## Layout

- `memory-construction/src/workflow_memory/`: dependency tracking, incremental construction, scheduling, publication, model backends and evaluation.
- `memory-construction/tools/`, `scripts/`, `tests/`: experiment runners and regression checks.
- `memory-construction/runs/agentrunbook-r-native-small-20261014/local-text-only/`: actively used adapted AgentRunbook-R/RAG modules, Reader harness and evidence processing. This directory contains essential source code despite its location under `runs`.
- `memory-construction/results/` and `reports/`: result tables, figures, analysis reports and paper drafts.
- `memory-construction/runs/`: per-run metrics, final question answers, failure summaries, configuration/provenance, and frozen source versions.
- `memory-construction/third_party/`: required upstream source and licenses; third-party datasets and precomputed benchmark results are excluded.
- `EXPORT_MANIFEST.json`: source/export hashes, included files, upstream versions and export transformations.

Dataset files, screenshots, model weights, memory databases, vectors, request caches and full input prompt payloads are excluded. Per-question answers/scores and measured timing/token/call records are retained. API credentials, if found, are replaced with `REDACTED` in this copy. Configure credentials through environment variables.

The original directory structure is retained to preserve runner imports. Some commands/configs reference the original server paths; configure local model/data paths before reproducing. The repository supports analysis without downloading data, while live reproduction requires the separately obtained benchmark and model services.

Historical tables may include diagnostic runs, provisional quality checks or placeholder schemas. Check their `status`, `scope`, sample counts and linked reports before drawing conclusions. This snapshot does not assert that the complete paper experiment goal is finished.

Third-party code retains the licenses found in its respective directories. The repository does not assign a new license to the research code.
