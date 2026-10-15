# H5 mechanism stress results

Runs:

- `runs/mechanism-revision-v4-20261013` (`revision_stress`)
- `runs/mechanism-scope-v4-20261013` (`scope_isolation`)
- Aggregate: `results/tables/dev_mechanisms.csv`
- Iteration ledger rows: `results/tables/dev_iterations.csv` (`H5-mechanism-revision`, `H5-mechanism-scope`)

Both experiments use the same fixed workload hash
`d8a8ed49ddb813d487534108fb8e1529b26773cbe9fb561937d98596ddcce388` and
source hash
`0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
They are construction-kernel measurements only: real extraction/preparation,
method-owned cache, graph/state/workflow/index construction and SQLite
publication are included; model loading, common warmup, Embedding/dense
publication, Reader, Judge, post-publication checks and snapshot file export
are excluded. Therefore these numbers are not end-to-end Freshness latency.
Embedding has no calls in either runner and is recorded as
`excluded_from_construction_kernel`, not as zero cost. Official QA is
`not_evaluated`.

## Integrity checks

- Revision: 48/48 checkpoints completed, 0 failures, 48/48 valid snapshots and
  48/48 storage files; source coverage minimum 1.0.
- Scope: 8/8 checkpoints completed, 0 failures, 8/8 valid snapshots and 8/8
  storage files; source coverage minimum 1.0.
- Revision has 334/334 model request rows matched to 334/334 completed calls
  by request hash; scope has 94/94 matched calls. All 178 revision and 50
  scope model batches completed.
- Frozen code contains 12 files in each run and all manifest hashes verify.
- Revision-update source archives are valid for 12/12 checkpoints per method.
  Initial builds have no revision archive by protocol. The scope experiment
  has no source revision archive because its append is a scope change, so
  archive status is `not_applicable`, not a failed check.

## Revision update

The initial build is intentionally reported because it verifies identical
starting work. Both methods used 135 live calls and 288,726/15,396 input/output
tokens. Ours-dev was 422.379 s versus 423.061 s for B3-c2 (a small 0.161%
initial-build difference). The mechanism comparison is the paired
`revision_update` phase:

| Method | Time (s) | Calls | Input / output tokens | Logical hits / misses | Affected / recomputed nodes |
|---|---:|---:|---:|---:|---:|
| B3-c2 | 143.690862281 | 32 | 69,206 / 3,796 | 103 / 32 | 687 / 687 |
| Ours-dev | 144.012886148 | 32 | 69,206 / 3,796 | 103 / 32 | 687 / 251 |

Ours-dev recreated 251 nodes rather than B3-c2's 687, but was 0.322024 s
slower, corresponding to `latency_reduction_pct = -0.22410879988336846`.
This is a real negative construction-kernel result: the smaller recomputation
set did not translate into lower wall time under this workload. It is retained
as evidence for profiling and is not reported as an Ours speedup.

## Scope append

The scope experiment has only two append checkpoints per method, so its timing
is a mechanism diagnostic rather than a stable estimate:

| Method | Time (s) | Calls | Input / output tokens | Logical hits / misses | Affected / recomputed nodes |
|---|---:|---:|---:|---:|---:|
| B3-c2 | 19.825467937 | 2 | 3,535 / 193 | 45 / 2 | 132 / 237 |
| Ours-dev | 19.591558244 | 2 | 3,535 / 193 | 45 / 2 | 12 / 12 |

Ours-dev is 0.233909693 s faster (`+1.1798444997278228%`) while reducing
recomputation from 237 nodes to 12. Because this is only two paired
checkpoints, the ledger keeps the positive result but explicitly does not
claim a stable advantage.

## Next experiment decision

H5 isolates a concrete mechanism bottleneck: Ours-dev's smaller invalidation
and recomputation set is visible in the node counts, but revision-update wall
time remains tied/slightly worse because extraction and local publication still
dominate the construction-kernel path. The next candidate should therefore be
one bounded optimization of local publication or model-call scheduling, paired
against the same strong B3 workload and the existing quality-v3 Reader proxy.
No Embedding cost, Reader score, or end-to-end Freshness conclusion is inferred
from these runs.
