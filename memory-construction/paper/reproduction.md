# Reproduction and execution record

Protocol: focused-maintenance-v4-20261015; revision: execution-recovery-20261016.
This is an in-progress evidence package. Old completion claims are superseded;
their documents and original results remain archived, not overwritten.

## Environment and fixed configuration

Run from `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction`
with `/data/predator/ly/Mem/.venv/bin/python`.
Controller/Reader: Qwen/Qwen3.5-9B at localhost:8023.
Embedding: Qwen3-Embedding-8B at localhost:8114.
Mounted tokenizer: `/data/predator/ly/Mem/models/Qwen3-Embedding-8B`.

`execution/experiment_contract.json` defines text-only mode, chunking, tokenizer
reuse, lexical backfill, query-embedding reuse, Reader2048/context12000,
thinking=false, temperature0.6/top-p0.95/top-k20. `tools/focused_runtime.py`
applies settings before importing the harness and overrides query-only loaded
settings without rewriting construction signatures. Actual `prompt_rows.jsonl`
messages, not `prompt_messages` image-path placeholders, determine image use.

New formal Reader entrypoints additionally use
`tools/focused_reader_transport.py`: SDK retries0 for all methods, recorded in
`effective_reader_transport.json`. This makes one recorded Reader attempt per
answer; failures remain failures and unknown usage must not be filled with zero.
Earlier repaired development runs used the legacy transport setting and retain
their provenance; no synthetic attempt counts are claimed for old hidden retries.

## Repaired development evidence

| Evidence | Location |
|---|---|
| Two-domain B3/Ours corrected diagnostic queries | `runs/focused-maintenance-v4/repair-20261016/pair-v1` |
| Corrected Source-only/Overlay/Delta diagnostic queries | `runs/focused-maintenance-v4/repair-20261016/remaining-v1` |
| Original fixed eight normal questions | `runs/focused-maintenance-v4/repair-20261016/normal-v1` |
| Raw RAG/Notes actual maintenance and queries | `runs/focused-maintenance-v4/public-repair-20261016` |
| Six-method shared-load development table | `reports/execution-recovery-20261016/public-v1/public_main.csv` |
| Generated event/notes inspection | `reports/execution-recovery-20261016/generated-memory-review-v1.md` |
| Five-method measured continuous development table/curve | `reports/execution-recovery-20261016/public-sequence-v2/` |
| Old noncompliant-query accounting repair | `reports/execution-recovery-20261016/legacy-accounting-v1` |
| Versioned historical confirmation with full query accounting | `reports/execution-recovery-20261016/confirmation-reuse-v1/` |

Development has ten trajectories/domain, not full Small. AgentRunbook update
snapshots are legally reused; only defective query stages were repeated. The
old screenshot-bearing `formal`/`repeat-20261016` quality outputs remain invalid
for text-only ranking, while their unaffected update costs remain usable.

The separate public sequential table uses the historical five-trajectory/domain
development libraries. It validates actual revised textual inputs and records
the inherited RAG+Notes first-round cache-provenance limitation; it is not pooled
with the ten-trajectory table or presented as full Small. Its zero-new-inference
entrypoint is `tools/report_public_development_sequence.py --output UNUSED_PATH`.

For a new query-only output, use the explicit source and question arguments:

```bash
/data/predator/ly/Mem/.venv/bin/python tools/run_focused_formal_reader.py \
  --domain web --policy source_coalesced \
  --memory-dir runs/focused-maintenance-v4/formal/web-update/literal_revision-source_coalesced/memory_state \
  --questions-path runs/focused-maintenance-v4/formal/query-data/web/questions.jsonl \
  --output-root runs/REPLACE_WITH_UNUSED_QUERY_DIRECTORY
```

Do not run this merely to seek a better score. Existing query runs should be
reused unless their configuration or a predeclared repeat requires new inference.

## Registered complete Small workload

Data manifest:
`manifests/focused-maintenance-v4/full-small-recovery-v1/data_manifest.json`.
It fixes official100 IDs/domain, per-trajectory content hashes, eight paired
state/workflow revisions on four trajectories,22 unique questions, core ablation
cases, three-round sequences and three total representative paired repetitions.
Exposure is explicit: these are not all new unseen questions or revision cases.

Registered commands and method-code/input hashes:
`execution/full-small-recovery-v1/experiment_plan.json`.
Actual full initial snapshots and configs are captured at the queued freeze
gate in `runs/focused-maintenance-v4/full-small-recovery-v1/runtime_manifest.json`.
That file must exist with validated actual histories before maintenance starts;
registration alone is not runtime freeze or experiment completion.

The queue uses three initial architectures per domain, reuses each architecture's
own existing10 partitions and adds missing official trajectories. Target
AgentRunbook partitions are prepared under matched construction settings;
unchanged B3 replay must make zero model calls. No stale event output is re-keyed.
Historical cost, incremental expansion and matched preparation are separate;
this is not a fresh cold-construction measurement.

The registered finite schedule contains32 main update units,4 core ablation
updates,24 additional paired repeat updates and24 later sequential updates,
with126 query batches. Main updates get case-specific and normal queries;
repeats/sequences use their fixed case-specific queries. Main round1 is reused
when source changes and query texts are identical. Initial normal QA is shared
among AgentRunbook branches, not counted as independent trials.

The offline final report writes the pooled four-method `public_main.csv`, its
eight-row `public_main_by_domain.csv`, and `maintenance_by_kind.csv` separating
literal-state revisions from workflow-intent revisions. These are views of the
same predeclared runs, not additional experiments or independent observations.
The per-kind rows keep actual Notes regeneration/fallback costs; literal zero-LLM
updates must not be generalized to workflow revisions. Case completeness checks
match declared IDs as well as counts. Missing measurements remain null/incomplete.

## Background execution and resumption

Inspect the actual existing jobs first:

```bash
bash execution/background_status.sh
```

Current registered job:
`execution/background/full-small-formal-queue-20261016-v1/`.
It waits for the actual `full-small-web-expansion-20261016-v1` process and terminal
receipt, then executes the finite queue sequentially. This waiting wrapper does
not call the models concurrently with the existing expansion. Both are detached
with the existing launcher; closing the interactive session does not end them.

For a new installation/output version, inspect the matrix before registration:

```bash
/data/predator/ly/Mem/.venv/bin/python tools/run_full_small_formal.py
# Only once for a previously unregistered output version:
/data/predator/ly/Mem/.venv/bin/python tools/run_full_small_formal.py --register
# Only if no current model-experiment runner is active:
bash execution/launch_detached.sh UNIQUE_JOB -- \
  /data/predator/ly/Mem/.venv/bin/python tools/run_full_small_formal.py --execute
```

Do not repeat registration or launch a competing runner in this existing
installation. Each unit has a command and terminal receipt under
`execution/full-small-recovery-v1/units/`. Failures/partial outputs are preserved;
dependent units are skipped, independent units continue, and the failure must
be diagnosed rather than blindly rerun. Snapshot/code/input changes require a
documented version and affected-stage resumption, not best-of score selection.

## Aggregation, checks and interpretation

The queue schedules `tools/report_full_small_formal.py`, which writes new
versioned main/ablation/repeat/sequence tables, per-question answers, quality
review inputs and `continuous_cost.svg` under
`reports/execution-recovery-20261016/full-small-v1/`. The curve uses measured
update+controller+Reader totals over successive rounds, excluding initial cost;
it is not a one-update stacked bar or an extrapolation.

```bash
/data/predator/ly/Mem/.venv/bin/python -m pytest -q \
  tests/test_agentrunbook_update_dependencies.py tests/test_rag_update_adapter.py \
  tests/test_execution_evidence.py tests/test_focused_evidence.py \
  tests/test_full_small_queue.py tests/test_full_small_report.py
```

These checks cover relevant cache/dependency, cross-state invalidation after
real save/reload, retrieval filtering, update partition, query configuration,
cost bookkeeping and schedule properties. They do not certify semantic quality.
Actual query checks use `execution/verify_evidence.py --reader-dir PATH`.
Its `--current` pointers intentionally still expose historical invalid scope
until complete replacement evidence exists; do not redirect them to a small
development table merely to get a green result.

Cost aggregation matches query invocation IDs to real controller/embedding
attempts and deduplicates copied record IDs without removing retries. Initial,
update and query costs are distinct; unknown usage remains null. Generated event
and Notes review is separate from source roundtrip and Reader accuracy. Normal
questions repeated across changed snapshots are not independent new questions.
The final paper and native Goal remain incomplete until the registered workload,
quality records, paired variation and traceable final writing are delivered.

Embedding transport has a separate observability limitation: the inherited
client permits up to3 SDK retries, while the operation ledger records one outer
call and returned usage. Reported embedding calls/vectors are logged operations
and returned vectors; individual transport attempts/retry compute are unknown,
not silently zero. Initial/maintenance LLM attempt accounting and publication
wall time remain separate. Do not relabel these embedding operation counts as
independently verified wire-request counts.

Publication wall time is the measured artifact-build through save/reload
verification interval, not the command's total lifetime. Both entrypoints
exclude initial cloning/loading from that interval. Their historical
`setup_load_and_seed_s_excluded` fields have different sub-boundaries:
AgentRunbook starts this timer after cloning/loading; RAG includes cloning,
loading and preservation-baseline copies. Keep the raw values with their scopes;
do not add them to publication and claim a comparable full-process wall time.
The offline formal reporter emits these scope labels, artifact/publication
components, exact-request hits and fallback-group counts without changing any
frozen inference input. Unmeasured full-process wall time remains null.

Initial-source reuse is also checked beyond trajectory IDs. The receipt
`reports/execution-recovery-20261016/initial-source-content-check-v1.json`
compares all six historical initial libraries (10 trajectories each) and the
then-saved47-trajectory web expansion with the frozen official contents. It
uses the existing trajectory-store preparation and logical fingerprint, which
include every text state, action, thought, URL, goal and outcome, excluding only
screenshot paths. All selected contents match; the47 web trajectories contain
700 states. The receipt includes IDs, content fingerprints and helper/manifest
hashes. This is partial expansion evidence, not verification of200 completed
initial trajectories; the final full snapshots still require the same
content-level check before research acceptance.
The scheduled `tools/report_full_small_formal.py` now writes
`initial_source_contents.json` for all six runtime-manifest initial snapshots,
including complete ID sets, per-library normalized-content digests and any
mismatched/unreadable trajectories. Its `initial_source_full_text_matches`
flag remains false before runtime freeze. This is an offline acceptance check,
not a claim that the running queue's earlier ID-only gate already checked
every saved source field or generated memory semantics.
