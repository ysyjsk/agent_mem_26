# Current repository location

As of 2026-10-15, this repository is managed directly in the live source project, not in a separate export directory. Use GIT_USAGE.md for server commits. The earlier snapshot/export descriptions below explain the initial upload; current revisions are ordinary Git commits.

# Guide for AI analysis

## Research question

Can joint memory construction reduce repeated input processing while event-level dependency/reuse avoids update amplification, preserving the memory views and downstream answer quality?

The main optimization targets are construction/update publication latency, model calls, input/output tokens and embedding work. Answer quality is a constraint. Generic representation/input/cache improvements should be available to the strong B3 comparison too.

## Read the implementation in this order

1. `memory-construction/tools/run_agentrunbook_updates.py`: current adapted B3/Ours update policies, dependency keys, cache seeding, update variants and measured publication boundary.
2. `memory-construction/runs/agentrunbook-r-native-small-20261014/local-text-only/memory_modules/agentrunbook_r.py`: single/joint event extraction, note generation, input budgets and embedding reuse.
3. The same adapter directory's `evaluation/harness.py`, `run_eval_local_text.py`, `memory_modules/source_backfill.py`, and `memory_modules/workflow_adapted.py`: Reader/context handling and the connection to the core pipeline.
4. `memory-construction/src/workflow_memory/`: `construction.py`, `dependency.py`, `cache.py`, `strong_baseline.py`, `scheduler.py`, `commit.py`, `dense_publication.py`, and `local_backends.py`.
5. `memory-construction/tools/run_construction_matrix_v2.sh`, `run_fast_compare.py`, `report_construction_pair.py`, and the relevant tests.

The adapted AgentRunbook-R update path and older core B0/B3/Ours experiments are related but distinct experiments. Do not combine their numbers as if they were one matched run.

## Read the evidence in this order

- `memory-construction/results/tables/construction_pair_v2_full10.csv` and `reports/construction_pair_v2.md`: fixed ten-trajectory cold-construction matrix. Call/token savings do not imply wall-clock gains.
- `memory-construction/results/tables/agentrunbook_update_b3_ours.csv` and `reports/agentrunbook_update_b3_ours.md`: local update comparisons. Check post-update quality status and the number/type of distinct cases before generalizing.
- `memory-construction/results/tables/dev_adapted_first_compare.csv` and `dev_adapted_per_question.csv`: adapted development baseline/Reader evidence.
- `memory-construction/reports/optimization_log.md`, `quality_repair_log.md`, `construction_cost_paper_draft.md`: previous positive/negative experiments and the emerging paper argument.
- `memory-construction/runs/`: corresponding per-run metrics, final answers, failures and provenance. Full source inputs/caches are intentionally absent.

## Useful review output

Identify concrete code changes that can reduce expensive model/embedding work while preserving quality, rank them by expected practical benefit and implementation effort, and propose a small paired experiment for each. Distinguish completed measured evidence from pending formal-scale/quality experiments. Follow the current `memory-construction/GOAL.md`; old native-first priorities lower in historical documents are superseded.

The local generation service currently serializes model generation. Client concurrency should not be described as real GPU batching without an implemented batching backend.
