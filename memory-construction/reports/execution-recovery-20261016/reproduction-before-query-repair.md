# Archived pre-repair reproduction record — use current paper/reproduction.md

Protocol: `focused-maintenance-v4-20261015`, revision `execution-ready-r2-freeze`.

## Environment

- Project: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction`
- Python: `/data/predator/ly/Mem/.venv/bin/python`
- Controller/Reader: `Qwen/Qwen3.5-9B`, `http://localhost:8023/v1`
- Embedding: `Qwen3-Embedding-8B`, `http://localhost:8114/v1`
- Reader: thinking disabled, 2,048 max completion tokens, 12,000 memory-context tokens, temperature 0.6, top-p 0.95, top-k 20, concurrency 1
- Embedding tokenizer: `/data/predator/ly/Mem/models/Qwen3-Embedding-8B`

## Frozen data and snapshots

- Manifest: `results/tables/focused-maintenance-v4-manifest.json`
- Web initial ten-trajectory build: `runs/focused-maintenance-v4/formal/web-initial`
- Matched web snapshot: `runs/focused-maintenance-v4/formal/matched-web`
- Matched enterprise snapshot: `runs/focused-maintenance-v4/formal/matched-enterprise`
- Formal revision configs: `configs/method_web_title_replacement.json` and `configs/method_enterprise_count_replacement.json`
- Fixed questions: `runs/focused-maintenance-v4/formal/query-data/{web,enterprise}/questions.jsonl`

## Commands

Prepare/reuse matched snapshots (already completed):

```bash
/data/predator/ly/Mem/.venv/bin/python tools/run_agentrunbook_updates.py \
  --source runs/focused-maintenance-v4/formal/matched-enterprise/memory_state \
  --output runs/focused-maintenance-v4/formal/enterprise-update \
  --trajectory-id 0ab99e0c --state-index 5 \
  --revision-file configs/method_enterprise_count_replacement.json \
  --current-state-evidence --cases literal_revision \
  --policy-order b3 source_only source_coalesced
```

The web command is identical with `matched-web`, output `web-update`, trajectory `1ad1af4b`, state index `4`, and `configs/method_web_title_replacement.json`. Existing B3 outputs were reused; only missing policies were executed in the final session.

Run the fixed two-question Reader for one branch:

```bash
/data/predator/ly/Mem/.venv/bin/python tools/run_focused_formal_reader.py \
  --domain web --policy source_coalesced
```

Use `--domain enterprise` and `--policy b3|source_only|source_coalesced` for the other branches. The helper loads the persisted memory, uses the actual `index.json` insertion order, and writes `revision_reader/` under the branch. It sets `LME_EMBEDDING_TOKENIZER_MODEL` and `HF_HOME` to mounted local paths so the run does not attempt to fill the quota-limited `/home/ly` cache.

Aggregate tables and figure:

```bash
/data/predator/ly/Mem/.venv/bin/python tools/report_focused_maintenance_formal.py
```

Outputs: `results/tables/focused-maintenance-v4/{public_main,source_only_compare,ablation,formal_reader_answers}.csv`, `results/figures/focused-maintenance-v4/focused-maintenance-v4-formal-cumulative.svg`, and `reports/focused-maintenance-v4-formal.md`.

The frozen mechanism-ablation queue (Overlay and Delta-guarded, followed by their fixed Reader runs and aggregation) is reproducible with:

```bash
./execution/run_formal_ablation_queue.sh
```

Its detached completed run is recorded as `execution/background/formal-main-queue-20261016/`; outputs are under `runs/focused-maintenance-v4/formal/{web,enterprise}-ablation-update/` and `results/tables/focused-maintenance-v4/formal_ablation_extended.csv`.

## Detached execution

Long runs can be detached from the Codex shell with the repository wrapper; it records a PID, command, status, stdout/stderr, start/finish timestamps, and exit code.

```bash
./execution/launch_detached.sh JOB_NAME -- bash -lc 'cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction && ...'
./execution/background_status.sh
tail -f execution/background/JOB_NAME/stdout.log
```

The launcher uses `setsid` and `nohup`; the detached process is reparented to PID 1. Do not launch a second GPU runner while one is active. The 2026-10-16 formal Reader repeat is recorded under `runs/focused-maintenance-v4/repeat-20261016/` with job metadata in `execution/background/formal-reader-repeat-20261016/`.

## Counting and known boundaries

Update wall time includes save/reload and queryable publication; setup/cache seeding is excluded and reported in the raw metrics. LLM tokens exclude Embedding tokens, which are a separate column. Complete/parseable answers are distinct from correct answers. Judge scoring was unavailable, so the fixed short-answer scorer is reported and semantic quality remains a limitation. The formal scope is adapted text-only maintenance, not native multimodal Small and not a cold-construction benchmark.
