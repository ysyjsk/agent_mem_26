# Source-Grounded Local Maintenance of Agent Memory

Working draft, execution-recovery-20261016. Development evidence is measured;
registered full-history results are pending. This document does not claim
completion, statistical quality equivalence or an established unique advantage.
The superseded draft is preserved in the execution-recovery report directory.

## Abstract

Small corrections to an agent's recorded environment can trigger repeated
event extraction even when most memory remains valid. We study maintenance
of an adapted AgentRunbook-R memory containing source slices, transition events
and procedure/hint notes. A source-grounded update retains unaffected artifacts
and publishes a state-scoped current-evidence view for affected events. Legal
exact request and vector caches are also available to strong reconstruction
baseline B3. On two exposed development revisions, this removes23,494 update
LLM tokens and reduces summed publication time from42.86 to4.24 seconds.
Including retrieval controllers and12 fixed post-update questions, LLM tokens
fall from171,529 to148,689 (13.3%). Diagnostic accuracy is4/4 versus3/4, whereas
normal-question accuracy is6/8 versus7/8. These small samples establish neither
equivalence nor systematic degradation. Simpler maintenance methods also use
zero update LLM calls, and Overlay is cheaper in this development run. We treat
the results as a local-maintenance cost finding, not evidence of dominance.
Registered full-history state/workflow updates, cumulative costs, paired repeats
and generated-memory checks will determine the final contribution scope.

## 1. Problem and scope

We maintain a published memory after a controlled correction to an existing
trajectory. We do not claim faster cold construction, arbitrary semantic
editing, optimized natural trajectory growth or a native multimodal benchmark
reproduction. An update must publish usable source and derived memory, preserve
unaffected information and expose its model and query costs. Strong B3 retains
legal exact model requests and embeddings; public Raw RAG/RAG+Notes retain their
own efficient retrieval paths and receive partition-local maintenance adapters.

### 1.1 Related work and attribution

LongMemEval-V2 [1] supplies the environment-history benchmark and AgentRunbook-R
architecture: raw slices, adjacent-state events, and procedure/hint Notes.
Its slice and slice-plus-Notes RAG methods underlie our public comparisons.
We retain these representations and study controlled correction after
construction; we do not claim their memory pools or controller as new.
The original Small tier uses a shared100-trajectory history per domain. Our
adapted maintenance workload uses those histories but is not the original
multimodal full-question leaderboard evaluation.

Dependency-based reuse is established build-system machinery. Mokhov et al.
[2] distinguish scheduling from rebuild decisions and describe dependency
hashes and cached results. Our use of exact request/vector caches is therefore
shared infrastructure, not a novel general incremental-computation framework.
The empirical question is whether state-scoped source maintenance avoids
expensive regeneration without transferring unacceptable cost or errors to QA.

Mem0 [3] extracts conversational facts and uses retrieved existing memories
plus an LLM to choose ADD, UPDATE, DELETE or NOOP. Our fixed literal-revision
path instead receives an explicit source correction and preserves its state
role without a model decision for each supported update. This narrower input
contract is a limitation as well as a computational opportunity. Mem0 is
related work, not a measured baseline here; we claim no superiority over it.
Source-only and Overlay determine whether the additional event-evidence
organization and merging are useful within our actual matched workload.

## 2. Method

Source differences identify affected transitions by their pre-state/post-state
positions. Construction-bound dependency keys preserve unaffected event outputs
without re-keying stale outputs under changed inputs. For supported literal
corrections, Coalesced marks retained generated prose as prior-source and
maintains one current-evidence block per affected event. Observations are bound
to a state and transition role: one state's value does not assert persistence
into the next state. Subsequent revisions remove obsolete observations from
this current view instead of accumulating separate authoritative patches.
This is not a full semantic rewrite of prior narrative. Unsupported changes
use the existing regeneration fallback; its complete cost is recorded.
The implementation gate recognizes local text changes with unchanged global
trajectory dependencies; it is not a semantic classifier proving that an edit
is merely literal. The evaluated supported cases are the fixed literal
corrections. Changes to workflow thoughts take regeneration fallback. Claims do
not extend to arbitrary text edits that invalidate broader narrative conclusions.

Notes follow the common original generation path. Only an identical actual
request may reuse a successful cached response. Absence of a source sentence
from a note is not a semantic-independence rule. Embedding keys bind actual
input text to model and relevant configuration. Changed inputs are recomputed;
different vectors are not averaged or substituted by similarity. Publication
includes artifact/index replacement, persistence and reload.

Source-only updates Raw State and invalidates affected events without replacing
them. Invalid events must remain invalid across later different-state changes
and reloads. Overlay retains appended versioned evidence rather than coalescing.
Only their matched comparison isolates merging; Source-only versus Coalesced
changes current-event availability and organization jointly. B3 and AgentRunbook-R
denote the same public maintenance row, not two independent baselines.

### 2.1 Affected events and lawful reuse

Let a trajectory contain ordered source states \(S_0,\ldots,S_T\), actions
\(a_0,\ldots,a_{T-1}\), and derived events
\(E_t=(S_t,a_t,S_{t+1})\). A correction at state \(S_j\) can affect both
\(E_{j-1}\) and \(E_j\); the roles are post-state and pre-state respectively.
The implementation preserves task goal, outcome, the full action trace,
workflow position and prepared source evidence as event dependencies. A change
to those global dependencies is not silently ignored for a cache hit. Adjacent
events may share an extraction request, but event-level dependency reuse avoids
recomputing a valid partner solely because another output in its request group
became dirty. Strong B3 has the same lawful exact-request and vector caches;
it is not forced to regenerate identical requests or untouched partitions.

Notes use their original generation dependency/request. The same actual input,
model and relevant generation settings may reuse a recorded successful result;
otherwise generation and any formatting repair are charged. Event reuse and
note reuse are separate decisions. This is a maintenance adapter to existing
memory construction, not a claim that the underlying public implementations
natively support arbitrary historical correction.

### 2.2 Coalesced state-scoped evidence

For each affected event and source-state role, denote the prior current-view
lines by \(V_{e,s}\), removed source lines by \(O_s\), added source lines by
\(A_s\), and the selected neighboring-state evidence by \(N_{e,s}\). The
published view retains old lines only when they remain in that state's actual
source; it then adds the corrected observations and neighbor evidence:

\[
V'_{e,s}=\operatorname{source\_ordered\_unique}
\left(((V_{e,s}\setminus O_s)\cap\operatorname{lines}(S'_s))
\cup A_s\cup N_{e,s}\right).
\]

Matching and deduplication use stripped exact source lines, not semantic
similarity. Neighbor evidence uses the existing node-ID/label-prefix rule.
The event retains its original action and marked prior interpretation; the
current evidence explicitly names its state and pre/post role. A value changed
at one state is not propagated into a later state without source support.
Subsequent updates replace the current view rather than append another
authoritative block. The tested mechanism therefore limits accumulation in
that view, but does not guarantee that retained prose is contradiction-free.

### 2.3 Publication, fallback and cost boundary

Unsupported dependency changes or an invalid local update use the existing
event-generation path. Workflow-thought revisions exercise this fallback and
the ordinary Notes dependencies. Updated raw slices, event descriptions, Notes
and their required embeddings are published through the original partition
replacement, indexing and persistence path; reload verification finishes the
measured publication interval. No necessary event/Note is omitted to claim
zero model cost. A Source-only ablation deliberately retires affected events
instead and is reported as a different available-memory representation.

For a fixed sequence of revisions and queries, the reported maintenance work is
\(\sum_r(C_{\mathrm{update},r}+C_{\mathrm{controller},r}
+C_{\mathrm{Reader},r})\), with embedding work and wall time alongside it.
Initial construction is separate, and lifecycle totals require its compatible
measured cost. Source diffing, dependency checking and publication can still
inspect existing trajectory/index data; the implementation makes no sublinear
runtime guarantee. In particular, retaining full action-trace dependencies
does not establish an optimized continuously growing same-trajectory workload.

## 3. Experimental protocol

Methods receive the same complete histories, revisions and questions. Controller
and Reader use local Qwen3.5-9B, with Qwen3-Embedding-8B embeddings. The shared
text-only Reader has2,048 output tokens,12,000 memory-context tokens, thinking
disabled, temperature0.6, top-p0.95 and top-k20. AgentRunbook retrieval settings
are identical across its branches; public RAG methods retain their original
retrieval structures. Chunking, tokenizer reuse and source-line backfill are
shared where applicable and not counted as construction gains.

Maintenance preserves the source construction settings: adjacent event groups
of two,1,024 output tokens per event, bounded input preparation and safe group
splitting. Every branch has independent inherited caches. Formal Reader SDK
retries are disabled uniformly to prevent invisible attempts; failed usage is
unknown even when the legacy harness emits zero placeholders.

Primary costs are update LLM input/output and update-plus-fixed-query LLM
tokens. Calls, embeddings, publication/query wall time, failures and unknown
usage are separate. Query cost includes retrieval controllers and Reader;
nested retrieval time is not added twice. Setup/cloning is reported separately
from publication. Historical initial memory is neither free nor newly measured
construction; full lifecycle totals require compatible initial cost evidence.
Publication timings start at artifact construction after initial loading/cache
setup and end after persistence/reload verification. The existing AgentRunbook
setup submetric excludes earlier cloning/loading, whereas the RAG setup submetric
includes them; these setup values are not comparable end-to-end startup times.
Whole-process wall time is not inferred by adding these incomplete submetrics.
Embedding counts are logged operations and returned vectors: the inherited
embedding SDK permits transport retries without an individual-attempt ledger,
so total wire attempts/retry work remain unknown rather than assumed zero.

Quality separates normal questions, corrected facts/neighbor states, workflow
intent, completeness, truncation, service/parse failures and semantic review.
Fixed questions are not changed after seeing answers. Generated events and notes
are inspected, not just persisted source. Small score differences do not trigger
tuning or establish statistical equivalence.

## 4. Repaired development results

Each domain has ten complete trajectories and one literal correction. Four
diagnostic and eight original normal questions reuse each updated snapshot.

| Method | Update tokens | Publication sum, s | Update + all12 queries tokens | Diagnostic | Normal |
|---|---:|---:|---:|---:|---:|
| Raw RAG | 0 | 3.589 | 129,006 | 1/4 | 7/8 |
| RAG+Notes | 0 | 3.371 | 125,072 | 1/4 | 7/8 |
| AgentRunbook-R/B3 | 23,494 | 42.859 | 171,529 | 3/4 | 7/8 |
| Coalesced | 0 | 4.241 | 148,689 | 4/4 | 6/8 |
| Source-only | 0 | 3.745 | 152,412 | 3/4 | 7/8 |
| Overlay | 0 | 4.171 | 141,492 | 4/4 | 7/8 |

Source: `reports/execution-recovery-20261016/public-v1/public_main.csv`, including
per-branch raw paths. Legal AgentRunbook updates are reused; corrected queries
and public maintenance measurements are new. All12 answers/method are complete
and parseable. B3/Coalesced disagree on one normal field-ordering question;
this alone neither attributes the difference to memory loss nor proves chance.
Both actual requests contain the three decisive options, Contact type, Task
type and Type, with identical source-state citations. Coalesced's answer ignores
Contact type and incorrectly chooses Type as the second match. Thus this saved
error concerns evidence use/order reasoning, not absence of those source lines;
the role of other context differences versus sampling is unresolved. See
`reports/execution-recovery-20261016/normal-question-disagreement-review.md`.

Coalesced reduces update publication by90.1% and eliminates three reconstruction
requests. Embedding input drops only2.1%; savings principally avoid event
generation. No branch regenerates Notes on these literal cases, so this table
supports no workflow-note revision-cost claim. Overlay uses fewer total tokens
and answers one more normal question than Coalesced in this run. Raw RAG and
RAG+Notes are cheaper but miss more diagnostic facts. Unique superiority of
Coalesced is therefore not established.

### 4.1 Generated-memory evidence

The explicit qualitative review is recorded in
`reports/execution-recovery-20261016/generated-memory-review-v1.md`.
Coalesced/Overlay bind the corrected Title/count to the intended state and retain
neighboring values and action results. Generic notes are unchanged and contain
no identified contradictory literal assertion in these inspected cases. Prior
prose can retain superseded interpretations; a correct current block is not
unconditional downstream semantic reliability. B3's enterprise event4→5 prose
incorrectly describes a return to101 within the event while its post-state
block correctly shows103. This generated-summary inconsistency is retained.
Source-only's retired events are not evaluated as replacement current events.

### 4.2 Historical evidence and evaluation corrections

Old `formal` Reader runs/repeats contained stale screenshots and cannot establish
text-only quality rankings. Valid updates are preserved; only affected query
stages are replaced. Old totals omitted retrieval-controller tokens, and a
lexical checker incorrectly restricted unchanged facts to current blocks. These
were evaluation/accounting problems, not evidence of a method win or failure.
Original artifacts remain available as noncompliant history.

Historical cold construction reduced calls93→78 but increased wall time830→1,026
seconds. The combined candidate likewise failed to accelerate construction.
These negative findings remain. Earlier v13 continuous/confirmation results are
versioned auxiliary evidence, not pooled current formal scores. They motivate
testing cumulative evidence size but do not replace full-history evaluation.

The saved v13 date/quantity confirmation pair has also been reaggregated from
actual query IDs: B3/Coalesced each answer6/6, with update+query tokens93,398
versus70,175 and update publication42.04 versus4.37 seconds. Same-snapshot
construction signatures, text-only requests and Reader/controller settings are
verified in `reports/execution-recovery-20261016/confirmation-reuse-v1/`.
This remains the original a04 version's confirmation, now exposed to the project;
it is not a new held-out v4 test or an additional formal denominator.
Generated-memory inspection of these same artifacts identifies B3 narratives
that contradict their explicit corrected date/quantity evidence, despite correct
Reader answers. Coalesced retains marked superseded prose while binding current
facts to the changed state; unchanged final-state facts remain in retained prose.
The separate review is `confirmation-reuse-v1/generated-memory-review.md`.

### 4.3 Public continuous-maintenance development comparison

The compatible five-trajectory/domain v4 development sequence now includes
Raw RAG and RAG+Notes. All methods use the same two target histories and revised
text, three dependent revisions/target, and two diagnostic questions/update.
Actual query messages and controller flags were checked. This analysis reuses
existing runs; it is not another independent experiment or full Small result.

| Method | Six-update LLM tokens | Publication sum, s | Update+query tokens | Correct /12 |
|---|---:|---:|---:|---:|
| Raw RAG | 0 | 9.772 | 133,302 | 5/12 |
| RAG+Notes | 7,030 | 56.637 | 128,682 | 5/12 |
| AgentRunbook-R/B3 | 70,612 | 133.736 | 213,021 | 12/12 |
| Source-only | 0 | 9.988 | 149,499 | 8/12 |
| Coalesced | 0 | 12.239 | 142,508 | 12/12 |

All60 answers are complete/parseable. Coalesced reduces total measured LLM
tokens33.1% versus B3 in this workload and uses fewer tokens than Source-only,
but public RAG methods remain cheaper with lower diagnostic scores. These
repeated questions do not establish statistical equivalence or generality.
The actual cumulative curves, not a one-step stacked bar, are in
`reports/execution-recovery-20261016/public-sequence-v2/continuous_cost.svg`;
all per-round costs and answers are in the adjacent tables.

![Development cumulative update and query cost](figures/development-continuous-cost.svg)

Figure 1. The same measured development series, rendered with distinct line
styles and explicit revision rounds. Initial construction is excluded; the
horizontal axis counts dependent updates, not independent evaluation samples.

The corresponding event-size figure is
`reports/execution-recovery-20261016/public-sequence-v3/evidence_size.svg`.
This offline reaggregation changes no scores or cost totals. Coalesced's target
event text remains6,474 web/11,815 enterprise characters and two current blocks
through all three revisions. B3 also maintains two blocks by regeneration;
Source-only has fewer query-eligible events because it retires affected ones.
These observations do not isolate merging versus Overlay, which is absent
from this development comparison. The formal paired Overlay sequence remains
required. Scoped review of12 affected event instances and12 note instances
finds no noncurrent source line or incorrect state role among126 current-block
line instances. Marked prior prose still contains superseded assertions; the
review does not claim complete narrative rewriting or general semantic safety.
Details are in `coalesced-sequence-memory-review.md` under the recovery reports.

![Development published event size](figures/development-evidence-size.svg)

Figure 2. Published event size after each revision, not cumulative work. The
two-block B3 and Coalesced curves coincide; dashed rendering exposes both
without jittering values. This development series contains no Overlay branch.
Figure sources and zero-inference rendering commands are in `figures/README.md`.

RAG+Notes has a provenance-dependent cache-start cost: the historical initial
logs lack finish_reason/thinking metadata. Two first-round note generations
and two JSON repairs therefore ran instead of re-keying those old responses.
Later rounds legally reuse the newly recorded requests and use zero update LLM.
The full measured cost is retained, with rounds2–3 separately tabulated;
the7,030 tokens must not be presented as an inherent requirement of literal
source revision. Earlier Reader transport retries were not individually logged;
displayed usage is recorded returned usage, with that observability limitation.

Scoped inspection of the four distinct RAG+Notes outputs (twelve instances
across six snapshots) identifies no asserted current revised Title/count,
but does identify unsupported generalization. The web hint treats an observed
field-entry order/markdown format as a necessary requirement. Enterprise notes
describe filling Short description although the failed run ends before selecting
that filter field. Successful format repair and source preservation therefore
do not certify generated-note semantics. The actual notes and5/12 score remain
unchanged; this is qualitative development evidence, not another paired trial
or a maintenance-specific causal attribution. See
`reports/execution-recovery-20261016/rag-notes-sequence-memory-review.md`.

The two public RAG methods' equal5/12 sequence scores have distinct error
components. Each has six `UNKNOWN` responses on the unchanged Name/Type
questions: the correct fields remain in published raw slices, but their
state-specific evidence is absent from the actual Reader input. Generic target
Notes do not establish the requested state value. These are repetitions of two
question templates, not twelve independent errors. Each method also has one
count error despite an explicitly supplied corrected state5 observation (Raw
RAG round1; RAG+Notes round3). The saved contexts are post-budget, so they cannot
separate initial retrieval ranking from subsequent pruning. This diagnosis
supports neither a storage-loss claim nor a sampling-noise explanation. Costs
and scores remain unchanged. See `public-rag-sequence-error-review.md` and its
request-hashed evidence JSON under the recovery reports.

Inspection of Source-only's four incorrect sequence answers distinguishes
storage, retrieval and interpretation. All six saved snapshots preserve the
corrected source, unaffected events/Notes and their vectors; none of twelve
queries retrieves an invalidated event. Nevertheless, two count answers select
101 despite an explicitly state5-bound updated count in the actual Reader
input. One explanation incorrectly equates state5 with earlier states. Two
unchanged-field answers abstain with no target-state field evidence retrieved;
earlier-state/generic Notes do not establish that value at the requested state.
These observed failure modes do not prove a universal representation advantage
and do not justify post-hoc scoring or retrieval changes. The per-question
evidence and manual interpretation are in
`reports/execution-recovery-20261016/source-only-saved-sequence-v2/error-review.md`.

## 5. Registered full-history evaluation — pending

The data manifest fixes the official100 trajectories/domain (200 total), eight
state/workflow cases on four preselected trajectories and22 unique questions.
The workload includes exposed development cases; full distractor histories do
not create independent unseen revision samples. Every main update receives its
case-specific questions plus four normal questions/domain. Normal questions
repeated across snapshots are observations, not additional independent questions.

Four public/main methods run all eight cases. Source-only/Overlay use two fixed
core state revisions. Those cases receive three total paired timing runs with
reversed method order on repetition2, plus three sequential revisions per
independent branch. Compatible main round1 is reused, not counted as a second
independent trial. The finite queue has84 update units and126 query batches,
alongside history expansion, matched preparation and aggregation. Workflow
changes exercise Notes dependencies and existing fallback without new tuning.

The four workflow cases use a deliberately narrow synthetic intervention: append
the same sentence, "Workflow clarification: verify the required field before
proceeding to the next form field," to the recorded thoughts at one state.
They do not change observed actions, state text or the original outcome. Their
four task-specific questions share the same expected phrase, "required field."
Thus they exercise changed Notes inputs and regeneration fallback across four
contexts, but are one clarification template, not four distinct reasoning skills
or a benchmark of arbitrary workflow revision. The frozen phrase score checks
recall of the clarification only; it cannot certify preservation of ordering,
original workflow facts, or the distinction between recorded intent and an
executed action. Those properties require separate review of generated notes.
The original enterprise filter task remains a failed run after the clarification;
the added intent must not be interpreted as evidence that it succeeded.

Data: `manifests/focused-maintenance-v4/full-small-recovery-v1/data_manifest.json`.
Commands/input/code hashes: `execution/full-small-recovery-v1/experiment_plan.json`.
Complete initial snapshots must pass the queued runtime-freeze gate before
maintenance. Tables, paired variation, quality records and actual cumulative
cost curves are scheduled under `reports/execution-recovery-20261016/full-small-v1/`.
Pending measurements are not replaced by projections or the old20-trajectory table.

The first completed initial library is the web AgentRunbook history. Its saved
expanded and matched snapshots each contain all100 official trajectories,
1,737 states,1,637 adjacent-state events and100 procedure/100 hint notes.
Full normalized source text/actions/thoughts match the frozen official inputs;
event coverage has no missing or duplicated transition. These are structural
checks, not generated-text semantic certification. Reusing10 historical partitions
and adding90 trajectories incurred892 recorded LLM calls (11,594,733 input and
322,555 output tokens),3,088 returned embedding vectors (5,961,015 input tokens),
and14,284.80 seconds summed sequential publication time. Startup/cloning and
historical construction are excluded; this is not fresh cold-build or complete
lifecycle cost. No logged request failures or missing usage were found in this
new expansion ledger. This is not a no-fallback claim:727 joint requests yielded
723 parsed groups, while four returned outputs required single-event fallback;
six other groups split at the input-budget preflight without a joint request.
The60 single-event requests include these fallbacks and unpaired transitions.
All1,506 new transitions are covered by723 parsed pairs plus60 single events.
The90 note-generation requests additionally required15 JSON-format repairs.
Four unsuccessful joint outputs consume61,497 tokens and the note repairs
15,147 tokens, already included in the totals rather than treated as free work.
All892 recorded requests are text-only, thinking-disabled and finish with
`stop`; valid termination does not establish semantic correctness. Details:
`reports/execution-recovery-20261016/web100-agentrunbook-request-verification.json`.
Embedding transport attempts remain subject to the stated observability
limitation. Matched preparation and unchanged B3 verification required no new
model calls. Evidence: `reports/execution-recovery-20261016/web100-source-and-cost-verification.json`.

The completed web Raw RAG expansion also preserves all100 official trajectories
and1,737 raw slices. Reconstructed slice text, action context, state positions
and URLs match every saved slice; all1,737 embedding rows are finite. Starting
from its own10 historical partitions, the90 added trajectories incurred no LLM
calls,88 logged embedding operations,1,402 newly calculated vectors and5,711,320
embedding input tokens. Exact-input reuse accounts for194 of1,596 logical vector
requests; the original slice entries are retained. Sequential publication stages
sum to1,344.56 seconds, excluding startup/cloning and inherited construction.
These are architecture-specific expansion costs, not a new cold-build comparison
or a maintenance speedup. Full source storage does not imply that embeddings
consume unlimited context: their frozen input bound remains4,096 tokens.
Structural acceptance does not certify retrieval or answer quality. Evidence:
`reports/execution-recovery-20261016/web100-raw-rag-source-and-cost-verification.json`.
Web RAG+Notes also completes100 trajectories and1,737 matching raw slices,
with100 procedure and100 hint Notes and aligned finite embedding rows. Its own
ten inherited Notes partitions and vectors are unchanged. Adding90 trajectories
requires104 LLM calls (270,408 input and46,025 output tokens), including14
format-repair requests. Logged embedding work is1,582 vectors and5,743,700 input
tokens, with194 exact-input hits among1,776 logical vector requests. Sequential
publication stages sum to2,708.55 seconds on the same expansion-only boundary.
All104 actual requests disable thinking, contain no images and finish with
`stop`. Nevertheless, one trajectory (`d0bcf4db`) still produces invalid JSON
after repair and receives the baseline's original deterministic fallback Notes.
Their3,691 generation/repair tokens remain charged. The fallback procedure
lists the first8 of11 actions and therefore omits later order navigation and the
final size-answer action; its hint preserves the recorded failure outcome.
Full source evidence remains stored, but this is not successful semantic note
extraction. The final table must preserve this fallback limitation, not certify
quality from nonempty fields. Evidence:
`reports/execution-recovery-20261016/web100-rag-notes-source-and-cost-verification.json`.
Enterprise initial libraries and all formal maintenance outcomes remain pending.

The recovery ledger is kept separate from semantic success. At the current
checkpoint (2026-10-16 22:57 +08:00), the enterprise AgentRunbook expansion is
still active at 54/100 histories; the latest completed trajectory records 19
LLM calls, 281,355 known tokens, 68 vectors and no unknown usage. The
enterprise RAG+Notes branch remains incomplete after an independent CUDA-OOM
at trajectory `02dad10c`. AgentRunbook trajectory `02dad10c` also has preserved
OOM attempts and a deterministic Notes fallback, while `054c4ed2` contains
`workflow_memory` import failures followed by fallback output. These rows are
charged as observed recovery costs but are not certified as model-generated
semantic Notes. The recovery diagnosis and the versioned receipts are in
`reports/execution-recovery-20261016/full-small-v1/recovery_diagnostics.md` and
`execution/recovery/enterprise-agentrunbook-notes-fallback-20261016-v2.json`.

### 5.1 Independent confirmation freeze

Before any confirmation-model call, we froze `manifests/focused-maintenance-v4/independent-confirmation-v1/manifest.json`. It selects eight official Small trajectories (four per domain) by source completeness, trajectory length and page-family spread, not by a result. B3 and Coalesced receive one fixed literal source revision on all eight cases; Source-only and Overlay are additionally run on two preselected cases per domain. Each case has one changed-fact and one unchanged-neighbor check. A separate fixed normal-QA set contains twelve official text-only questions per domain, with three questions from each of dynamic, procedure, static and negative/dynamic-absence categories. The 24 questions are evaluated on one preselected revised snapshot per domain for four methods, yielding 96 responses but 24 independent question identities.

The selected trajectories were not used in this maintenance method-tuning set, but their histories were present in earlier native evaluation artifacts; all selected normal questions were likewise historically evaluated. We therefore report this batch as same-dataset independent maintenance confirmation relative to the present method-selection workload, not as a held-out benchmark or cross-dataset generalization result. The exact source edits, question text, gold answers, scoring rules, exposure labels and selection reasons are hashed in the manifest. Runtime and snapshot hashes are bound after the registered full-history expansion and before the first confirmation call; results cannot trigger sample replacement or method changes.

## 6. Conclusions and limitations

Evidence currently supports narrow local-maintenance savings over matched
regeneration, not cold-build acceleration, quality equivalence, dominance over
simpler methods or arbitrary-growth benefits. Registered work measures this
boundary rather than guarantees a positive conclusion. Completion requires the
full evidence and generated-memory quality records, not merely finished scripts.
See `paper/reproduction.md` for the actual execution and provenance entrypoints.

## References

The accompanying `paper/references.bib` supplies bibliographic records; numeric
labels below identify the primary works used above. Related-work inspection
did not change the frozen implementation or experiment selection.

1. Di Wu et al. 2026. *LongMemEval-V2: Evaluating Long-Term Agent Memory Toward
   Experienced Colleagues*. arXiv:2605.12493v1. Architecture and baselines:
   Sections4.1/C.1--C.2; shared Small histories: AppendixA.3.
2. Andrey Mokhov, Neil Mitchell, and Simon Peyton Jones. 2018. *Build Systems
   à la Carte*. Proceedings of the ACM on Programming Languages2(ICFP),79.
   DOI:10.1145/3236774. Scheduling and dependency/cached-result traces: Section4.
3. Prateek Chhikara et al. 2025. *Mem0: Building Production-Ready AI Agents with
   Scalable Long-Term Memory*. arXiv:2504.19413v1. Extraction/update: Section2.1.
