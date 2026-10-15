# Accepted construction-kernel bottleneck audit (2026-10-13)

## Scope and provenance

Read-only audit of `runs/fast-compare-v4-corrected-20261013`: four fixed
development windows, 45 distinct source events, three checkpoints per window,
one repeat, independent live B0 and Ours-dev calls. This audit loaded no model
on a GPU and changed no implementation or execution state.

The accepted scope is `construction_kernel`: extraction, deterministic local
state/relation/workflow views, lexical index and SQLite publication. Cold
loading, warmup, dense Embedding/index, Reader, Judge and post-publication
checks are excluded. Kernel latency is **not** end-to-end Freshness; official
QA remains `not_evaluated`. B3 is not measured in this run.

- Config SHA256: `6cf2acec7960fc2dbe3a503883cddc78d728c1f5673b329223a338f4a9a75a92`.
- Workload SHA256: `d8a8ed49ddb813d487534108fb8e1529b26773cbe9fb561937d98596ddcce388`.
- Source SHA256: `0d839a1a9ab03b62c1862881de70f83140c83857dc0ebff6a99d4715b4129a3c`.
- Frozen prompt/code: `manifest.json` and `frozen_code/`; all four file hashes
  independently verified against the manifest.
- Shared model: local Qwen3.5-9B, bf16, GPU0, text-only, temperature 0,
  thinking disabled, c=1, 6000-character projection ceiling, prefix context=2,
  output-token ceiling=256. The strict concise prompt is frozen in the run.

## Measured wall time and tokens

Numbers are recomputed from `checkpoint_metrics.jsonl` and `llm_calls.jsonl`.
At c=1, summing call elapsed time is valid for this extraction component;
the same accounting must not be used blindly for future concurrent batches.

| Method | Live calls | Kernel s | Extraction s | Extraction share | Local remainder s | Input tokens | Output tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| B0 | 93 | 386.813572443 | 385.590823931 | 99.684% | 1.222748512 | 183591 | 7943 |
| Ours-dev | 45 | 193.688754320 | 192.703588448 | 99.491% | 0.985165872 | 90640 | 3842 |

Ours saves calls, not per-call time: mean extraction wall is 4.282302 s
versus B0's 4.146138 s. Mean input tokens are 2014.222 versus 1974.097;
mean output tokens are 85.378 versus 85.409. Per-call input range is
1311–2251 and output range is 48–106 in both methods. Every call stops
normally; none reaches the 256-token ceiling. Lowering the ceiling is not
shown to save work by this evidence.

The logs do not separate tokenization, prefill and decode wall time. Token
composition below is not a measured prefill/decode latency decomposition.
Exploratory, confounded Pearson input/output-token correlations with wall
are 0.136/0.466 for B0 and -0.032/0.538 for Ours; no causal speedup follows
from these observations.

| Window | Method | Calls | Kernel s | Extraction s | Input | Output |
|---|---|---:|---:|---:|---:|---:|
| 0db80092-prefix12 | B0 | 24 | 95.947509 | 95.620219 | 45640 | 2107 |
| 0db80092-prefix12 | Ours-dev | 12 | 51.768603 | 51.471485 | 23210 | 1034 |
| 170f5570-prefix9 | B0 | 21 | 86.427361 | 86.124412 | 39766 | 1770 |
| 170f5570-prefix9 | Ours-dev | 9 | 36.358917 | 36.142387 | 17400 | 765 |
| 4a5f0d7f-prefix12 | B0 | 24 | 105.155084 | 104.877066 | 48851 | 2112 |
| 4a5f0d7f-prefix12 | Ours-dev | 12 | 55.878552 | 55.691479 | 24872 | 1054 |
| ec6c60c2-prefix12 | B0 | 24 | 99.283618 | 98.969127 | 49334 | 1954 |
| ec6c60c2-prefix12 | Ours-dev | 12 | 49.682682 | 49.398237 | 25158 | 989 |

No one window dominates. Local deterministic optimization has at most
approximately 0.5% of Ours kernel wall available in this measurement.

## Request and semantic fairness

- 138 unique call IDs and 138 matching request-log rows; all are
  `completed/miss_live`. No failed call, truncation, replay or mixed config.
- Both methods cover the same 45 event IDs. B0 repeats 16 events three
  times, 16 twice and 13 once; Ours calls each event once. B0 therefore
  performs 48 additional, exactly repeated extraction requests.
- For all 45 events the cross-method request hash is identical. All 93
  B0-to-Ours same-event comparisons match input/output token counts and raw
  response hash. B0's repeated requests/responses are likewise identical.
  Request and response hashes were independently recomputed with zero
  mismatches; request-log/call-log contents also match.
- Shared resident backend fingerprint:
  `transformers-qwen:Qwen3.5-9B:061f4abd834f882d:cuda:0`.
- Context lengths over the 45 unique events: 0 for 4, 1 for 4, 2 for 37.
  No future or cross-trajectory context was observed. All 87 extracted facts
  cite only their current event.
- All 24 checkpoints validate, cover every source event and have readable
  snapshots. All 12 pairs match semantic hashes; direct comparisons of
  events/evidence/state/workflow/relations/aliases/index/nodes also match.
  Published lineage and metadata differ as expected for different methods.

Representative repeated request: event `0db80092:0` at B0 cp4/cp8/cp12
and Ours cp4 has hash
`ace2953db0ce08d2276820bdd106640d44ad642ae6e657d0d01faec874992993`,
1330 input / 89 output tokens and response hash
`ffa83f69645f55845f6406dfe285a5789db21a60d432cd8b66d5f58a05097800`.

This is append-only, repeat=1, greedy-decode evidence. It does not prove
revision/retraction correctness or quality. All 87 facts use subject
`agent`; the 35 observation facts use the generic predicate `observation`.
These representations still require Reader/reference-resolution checks;
semantic equality alone is not QA. The runner's semantic hash covers
evidence/state/workflow, not every snapshot field.

## CPU-only input-projection counterfactuals

The local tokenizer and accepted frozen construction module were used on
the 45 final Ours source events, with the manifest's frozen prompt and
`enable_thinking=False`. Full chat-template input counting reproduces
**45/45 recorded counts exactly**, totaling 90640 tokens. No LLM output or
GPU latency was measured in this analysis.

| Projection | Input tokens | Change from accepted |
|---|---:|---:|
| Accepted context=2 | 90640 | — |
| Existing unchanged projector with context=1 | 87315 | -3.668% |
| Diagnostic: retain only newest already-projected prior snippet | 78614 | -13.268% |

Simply changing the existing context window from 2 to 1 reallocates the
2000-character prior-context allocation from two approximately 1000-char
snippets to one approximately 2000-char snippet; this explains its modest
token saving. The second diagnostic instead takes `context[-1:]` from each
accepted request without expanding the surviving snippet. It keeps the
system prompt and current-event payload byte-for-byte, but drops prior
information. It is not an implemented or measured candidate.

Per-window accepted → ordinary context=1 → fixed-snippet diagnostic:
23210→22164→19959; 17400→16536→15106; 24872→24228→21668;
25158→24387→21881.

Standalone tokenizer counts are system prompt 16515 (367/call),
current-event JSON 46830 and context JSON 26432. These are approximate
composition indicators, not an additive split of the full chat prompt:
JSON/BPE boundaries and the chat template change the total.

## At most two matched next experiments

1. **Real ready-extraction batch2, equally offered to B3 and Ours.** Keep
   prompt, windows, checkpoints, projection and output ceiling unchanged;
   use independent method caches. Compare against each method's c=1 run.
   Verify actual backend generation batches and per-response `batch_size`,
   including width-one leftovers. Account for shared batch wall once,
   not once per response. Preserve ordering and do not publish a failed
   preparation. Check coverage, failed/truncated calls, all snapshot fields,
   attempt/observation semantics and readable publication. Even greedy
   batching can alter outputs; inspect differences instead of assuming
   semantic equality or predeclaring a speedup.
2. **One explicit fixed-snippet prefix-allocation variant, equally offered
   to B3 and Ours.** Reproduce the diagnostic deterministically: construct
   the original context=2 projection, then retain its newest prior snippet
   without expanding it. Preserve current-event projection, system prompt,
   6000-char ceiling and 256-token ceiling. Freeze this as a new projection
   policy/config hash, rather than claiming ordinary context=1 is identical.
   Compare tokens, actual latency, reference resolution, pre/post facts and
   Reader proxy quality on development data. The approximately 13.3% input
   cut is only a CPU counterfactual; neither wall saving nor quality is
   established. Retain any regressions and do not substitute proxy checks
   for official QA.

The dominant measured opportunity is model-call execution. Basic exact
request reuse must first be measured against legitimate B3; no B3 advantage
is inferred from this Fresh-relative table. The root agent owns subsequent
GPU experiments and mainline queue updates.
