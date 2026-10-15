# c1 → genuine batch2 request, semantic and accounting audit

Date: 2026-10-13. CPU-only audit; no weights loaded, GPU used, source changed,
experiment rerun or execution queue updated.

Runs compared:

- Reference: `runs/fast-compare-v4-e2e-c1-20261013` (Ours-dev/B3-c1).
- Candidate: `runs/fast-compare-v4-e2e-batch2-20261013` (Ours-dev/B3-c2).

The in-progress context0 experiment is not part of this audit. All code
interpretation below uses these completed runs' `frozen_code/`, not a
subsequently edited working-tree runner.

## Outcome

Batch2 is real and equally provided to both methods. Within the batch2
run, Ours and B3 have **45/45 identical requests, raw responses and token
counts**, and **12/12 equal structured snapshot pairs**. Across c1 and
batch2, all 45 requests remain identical, but 12 event responses change,
propagating to 10 checkpoint semantic hashes. Only the address window's
cp4/cp8 remain exact: **2/12**, not a result of only two events changing.

No prompt-token/padding, output-slicing, batch-wall double-counting or
observed output-truncation bug was found. The content changes are real
model outputs, not an accounting artifact. Their precise numerical/model
cause is not proved: generated token IDs, logits and runtime effective
generation configuration were not saved, and no GPU forward diagnostic
was run. Batch-shape-dependent numerical or model-internal attention/cache
behavior remains a hypothesis, not an established diagnosis.

## Same-run batching fairness and wall accounting

| Method | Total construction-e2e s | Extraction requests | Generate batches | Batch width distribution | Input / output tokens | Deduplicated extraction wall s |
|---|---:|---:|---:|---|---:|---:|
| Ours-dev | 100.288225884 | 45 | 23 | 22 × 2, 1 × 1 | 90640 / 3852 | 91.237324885 |
| B3-c2 | 100.270336674 | 45 | 23 | 22 × 2, 1 × 1 | 90640 / 3852 | 91.215696203 |

Both have 12/12 successful checkpoints, valid core snapshots, valid dense
publications and source-event coverage 1.0. All 90 requests are independent
live `completed/miss_live`, `finish_reason=stop`, temperature=0,
max_tokens=256, no images. No call reaches its output budget. The runner
prepares misses inside the measured checkpoint interval, then publishes
using only the same method's own prepared cache.

Grouping was compared as ordered tuples of request hashes at every
window/checkpoint/repeat, ignoring globally assigned batch IDs. Every
tuple and member order matches. Each 12-event window has pairs
(0,1)/(2,3) at cp4, (4,5)/(6,7) at cp8, and (8,9)/(10,11) at cp12.
The 9-event window ends with the identical width-one (8) batch at cp9.
Ours/B3 use separate construction stores and separate Embedding caches;
no method consumes another method's outputs. Preparation and publication
strategies differ as intended, but neither receives an inference budget
or grouping advantage.

All 46 batch records reconcile with their 90 member-call records: actual
batch width, membership, checkpoint context and elapsed interval match.
Each batch's wall interval is counted once in `model_total_s`. Incorrectly
summing member-call wall would yield 179.043590/178.997077 s instead;
the actual tables do **not** make this error. Per-checkpoint token counts,
request counts and deduplicated extraction wall reconcile with zero
mismatches. Request/response hash and usage checks also have zero failures.

Ours is 0.017889 s slower than B3-c2, approximately 0.01784%; this remains
a near tie, not a demonstrated strong-baseline win. The c1-to-batch2 timing
decrease is a measured development candidate, with changed outputs and
quality still pending, not proof of a semantics-preserving transformation.

## Exact response changes at the same request hash

All 45 input-token counts match c1 exactly (90640 total). Of 87 parsed
evidence items, **15 change `value`**, one of those also changes
`predicate` and `event_kind`. The same 12 events each retain two facts;
no fact-count, item-order, subject or source-reference change occurs.
Every source reference still names only its current event.

| Event | c1 → batch2 change | Interpretation to check |
|---|---|---|
| `0db80092:0` | "apply filters" → "apply asset filters"; intent adds explicit assignee/state labels | Surface specificity, same target values |
| `0db80092:2` | "filter list shows 'Show Related Fields' option" → "filter list updated with new condition" | Different observation; loses a named option and adds a coarse transition claim |
| `0db80092:5` | "clicked 'a1473'..." → "click('a1473')..." | Surface rephrasing |
| `0db80092:6` | observed `'Consumed'` option → observed `'Consumable (+)', 'Hardware (+)', 'Software License (+)'` | Chooses current pre-state categories instead of the State-field post-state detail |
| `0db80092:9` | goal/intent for Elisa Gracely/Consumed/empty serial → page-title observation | Only predicate/kind change: `goal/intent` → `observation/observation`; initial goal remains at event 0 |
| `0db80092:11` | action target "Serial number filter" → "third filter condition"; page-title observation → generic option categories | Loses specific action target and replaces observed fact |
| `170f5570:0` | "button 79" → "element 79" | Surface specificity |
| `170f5570:5` | page-title punctuation/quoting changes | Surface rephrasing |
| `4a5f0d7f:3` | "page title: Create submission" → "page remains on Create submission form" | Adds temporal wording; does not claim successful posting |
| `4a5f0d7f:6` | "searched forums for 'arlingtonva'" → "searched for arlingtonva forums" | Surface rephrasing; no-results observation unchanged |
| `4a5f0d7f:7` | earlier no-results observation → current `List of forums` title and `/forums` URL | Changes which visible state is retained; event 6 still records no results |
| `ec6c60c2:11` | displayed order-link wording normalized to Order #196; spacing changes in observed title | Same order identity, different exact text |

Aggregate kinds change from 49 attempts / 3 intents / 35 observations to
49 attempts / 2 intents / 36 observations. There are **zero
attempt→confirmation/success changes**, zero confirmations, and zero
failure-kind facts in either run. The explicit observed outcome at the
warranty terminal event is unchanged. Absence of kind promotion does not
prove absence of unsupported claims inside arbitrary natural-language
values, and it does not establish complete observation coverage.

Checkpoint accumulation explains the exact-hash result:

| Window | First changed event | Checkpoints with changed evidence |
|---|---:|---|
| `0db80092-prefix12` | 0 | 4, 8, 12 |
| `170f5570-prefix9` | 0 | 4, 8, 9 |
| `4a5f0d7f-prefix12` | 3 | 4, 8, 12 |
| `ec6c60c2-prefix12` | 11 | 12 only |

Across each method's 12 c1/c2 checkpoint pairs: events unchanged 12/12,
evidence changes 10/12, state_view 6/12, lexical index 6/12 and nodes
10/12. Workflow, relations and aliases remain exact 12/12. Workflow here
contains deterministic source-action sequences; its equality is not a
Reader quality guarantee. Exact equality is sensitive to surface wording,
so 2/12 exact matches is neither a 2/12 QA score nor proof that all ten
nonmatching checkpoint answers would be wrong.

## Source-grounded observation risks retained

These are concrete source checks, not official QA or a comprehensive
human-scored quality pass.

- `0db80092:6`: raw post-state contains State combobox value `-- None --`
  and option `Consumed` with `selected=False`. C1 mentions the option but
  omits the unselected state; batch2 replaces it with generic categories
  visible in the current pre-state. The projected post-state omits the
  central control detail. Neither memory should be read as confirmation
  that Consumed was selected at this event. The later select command is
  still an attempt, not by itself an observed result.
- `0db80092:11`: raw post-state shows Serial number with operator
  `starts with`, not an already-applied empty-string condition. Batch2
  loses the specific Serial number action label and records pre-state
  option categories. Neither version establishes that the intended final
  filter has been completed.
- `4a5f0d7f:3`: raw post-state explicitly says
  "You cannot post more. Wait a while before trying again." Both c1 and
  batch2 omit this important failure and retain only the submission-page
  fact. The 6000-character current-event projection removes the middle
  error message before either model call. This is a shared pre-existing
  projection-quality problem, not an omission newly caused by batching.
  Any source-grounded success/failure Reader check must retain this
  negative case; a page-title match cannot certify successful submission.
- `4a5f0d7f:7`: batch2 removes a duplicate pre-state no-results fact but
  retains the actual new page title/URL. The original search failure
  remains explicitly observed at event 6, so it is not globally lost.

Reference evidence is the runs' immutable final source events under
`snapshots/` (`pre_state_ref`/`post_state_ref`) and exact projected inputs
under `llm_calls.jsonl`. The evaluator can use raw source for gold; Reader
inputs must not receive evaluator gold or unrestricted raw source as an
unreported workaround for missing memory evidence.

## Padding, EOS and token-count diagnosis

The two runs' frozen `local_backends.py` are byte-for-byte identical
(SHA256 `74e052220edebd8a0bbc661f8d889d3c5f3b1df968058cfeaabef5564e7d1d99`).
Construction, prompt, strong-baseline and dense-publication files are also
unchanged. All 6 c1 and 7 batch2 frozen-file hashes match their manifests.
The only added execution path prepares Ours misses in batches; actual
request objects remain identical.

Using the frozen backend's `_render_inputs` with the real local tokenizer
on CPU reproduced all 23 Ours batches. For all **45/45 requests**:

- Removing padding by the attention mask yields exactly the same token-ID
  sequence as rendering that request alone.
- Attention masks are binary, have the correct lengths and left-padding
  shape, and end with 1. No token is truncated. Logged input counts match.
- Twenty-one rows have padding (2529 tokens total; maximum 571). Seven of
  the twelve changed events are padded and five are not; changes appear in
  both batch positions. This is not a change confined to short padded rows.
- No model weights were loaded; all rendered tensors stayed on CPU.

The frozen generation code slices outputs at the **padded input width**,
not each row's unpadded prompt length, and stops accounting at the first
configured generated EOS inclusive, excluding subsequent batch padding.
All responses are valid complete JSON and finish with `stop`. In both
c1 and batch2, every one of the 45 Ours calls has recorded output-token
count equal to re-encoded response-text length **plus 2**. The shared
offset is consistent across changed and unchanged responses; the total
3842→3852 increase is a real +10 in textual tokenization, not new per-row
padding counted as output.

The tokenizer defines pad ID 248044 (`<|endoftext|>`) and EOS ID 248046
(`<|im_end|>`); reconstructing generation settings from the local model
config yields EOS 248044. This can involve decoded-away special tokens,
but generated IDs and the effective runtime generation configuration are
not present in the run log. Therefore the exact +2 origin and first-EOS
sequence cannot be proved from saved text alone. There is no differential
EOS-accounting evidence explaining the c1/c2 semantic drift. Future
diagnosis should save effective EOS/pad configuration and generated IDs
for a bounded sample rather than retrospectively declaring a specific
floating-point mechanism.

Seven existing CPU generation/batch-accounting contracts pass: left
padding, unpadded usage, slicing after padded width, EOS before batch
padding, multiple EOS IDs, width-one leftovers, real bounded generate
calls, and deduplicated batch wall. They use fake generation outputs;
they validate wrapper behavior, not equivalence of actual Qwen forward
passes. In the CPU diagnostic process only, Torch's accelerator-detection
function was shimmed to return CPU to avoid a Transformers import failure
when CUDA visibility is empty. No persistent dependency or source change
was made.

## Acceptance boundary

The batch2 paired comparison is fair and its performance accounting is
valid. Retain it as a development performance result with changed outputs
and pending Reader/source-grounded quality, not a semantics-preserving
optimization by assertion. Official QA is still `not_evaluated`.
The observed missing state/failure facts must remain visible in subsequent
quality work. This audit requests no new GPU experiment and does not
change the root agent's active experimental schedule.
