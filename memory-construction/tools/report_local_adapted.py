#!/usr/bin/env python3
"""Aggregate persisted text-only development runs, including loaded-memory queries."""
import csv
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs/dev-adapted-text-v1/results"
VARIANTS = (
    ("AgentRunbook-R", "agentrunbook-r-v1", "agentrunbook-r-reader2048-v1"),
    ("RAG+Notes", "rag-notes-v1", "rag-notes-v1"),
    ("RAG raw", "rag-raw-v1", "rag-raw-v1"),
    ("A: bounded event AXTree", "agentrunbook-r-optA-v1", "agentrunbook-r-optA-v1"),
    ("B: event concurrency=4", "agentrunbook-r-optB-v1", "agentrunbook-r-optB-v1"),
    ("C: evidence-first packing", "agentrunbook-r-v1", "agentrunbook-r-optC-v1"),
    ("A+C", "agentrunbook-r-optA-v1", "agentrunbook-r-optAC-v1"),
    ("D: raw-state index + notes (no generated events)", "agentrunbook-r-optD-v1", "agentrunbook-r-optD-v1"),
    ("E: D + evidence-first query", "agentrunbook-r-optD-v1", "agentrunbook-r-optE-v1"),
    ("F: E + interleaved evidence chunks", "agentrunbook-r-optD-v1", "agentrunbook-r-optF-v1"),
    ("G: E + raw retrieval top-k10/merge8", "agentrunbook-r-optD-v1", "agentrunbook-r-optG-v1"),
    ("H: E + notes after 3 raw items", "agentrunbook-r-optD-v1", "agentrunbook-r-optH-v1"),
    ("I: E + notes after 1 raw item", "agentrunbook-r-optD-v1", "agentrunbook-r-optI-v1"),
    ("J: RAG raw + interleaved evidence chunks", "rag-raw-v1", "rag-raw-optJ-v1"),
    ("K ablation: RAG+Notes + interleaved evidence chunks", "rag-notes-v1", "rag-notes-optK-v1"),
    ("AgentRunbook-R + chunks (matched)", "agentrunbook-r-v1", "agentrunbook-r-chunks-matched-v1"),
    ("J matched repeat", "rag-raw-v1", "rag-raw-optJ-r3-matched-v1"),
    ("L: J + tokenizer reuse", "rag-raw-v1", "rag-raw-optL-matched-v1"),
    ("L repeat 2", "rag-raw-v1", "rag-raw-optL-r2-matched-v1"),
    ("L repeat 3", "rag-raw-v1", "rag-raw-optL-r3-matched-v1"),
    ("M: L + lexical source backfill", "rag-raw-v1", "rag-raw-optM-matched-v1"),
    ("M repeat 2", "rag-raw-v1", "rag-raw-optM-r2-matched-v1"),
    ("M repeat 3", "rag-raw-v1", "rag-raw-optM-r3-matched-v1"),
    ("N: M + adjacent source lines", "rag-raw-v1", "rag-raw-optN-matched-v1"),
    ("N repeat 2", "rag-raw-v1", "rag-raw-optN-r2-matched-v1"),
    ("N repeat 3", "rag-raw-v1", "rag-raw-optN-r3-matched-v1"),
    ("N expanded20", "expanded20-rag-raw-optL-v1", "expanded20-rag-raw-optN-v1"),
    ("M minus chunks", "rag-raw-v1", "rag-raw-optM-nochunks-v1"),
    ("M expanded20", "expanded20-rag-raw-optL-v1", "expanded20-rag-raw-optM-v1"),
    ("RAG+Notes + backfill", "rag-notes-v1", "rag-notes-backfill-matched-v1"),
    ("Notes+M repeat 2", "rag-notes-v1", "rag-notes-best-r2-v1"),
    ("Notes+M repeat 3", "rag-notes-v1", "rag-notes-best-r3-v1"),
    ("O: Notes+M + query embedding reuse", "rag-notes-v1", "rag-notes-optO-v1"),
    ("Notes+M minus chunks", "rag-notes-v1", "rag-notes-best-nochunks-v1"),
    ("O expanded20", "expanded20-rag-notes-v1", "expanded20-rag-notes-optO-v1"),
    ("AgentRunbook-R + backfill", "agentrunbook-r-v1", "agentrunbook-r-backfill-matched-v1"),
    ("Strong B3-c1 + backfill", "workflow-b3-v2", "workflow-b3-backfill-matched-v1"),
    ("Ours-dev + backfill", "workflow-ours-v2", "workflow-ours-backfill-matched-v1"),
    ("K matched + tokenizer reuse", "rag-notes-v1", "rag-notes-chunks-cache-matched-v1"),
    ("No chunks + tokenizer reuse", "rag-raw-v1", "rag-raw-nochunks-cache-matched-v1"),
    ("AgentRunbook-R + chunks + tokenizer reuse", "agentrunbook-r-v1", "agentrunbook-r-chunks-cache-matched-v1"),
    ("Strong B3-c1 adapted", "workflow-b3-v2", "workflow-b3-v2"),
    ("Ours-dev adapted", "workflow-ours-v2", "workflow-ours-v2"),
    ("L expanded20", "expanded20-rag-raw-optL-v1", "expanded20-rag-raw-optL-v1"),
    ("Expanded20 no chunks", "expanded20-rag-raw-optL-v1", "expanded20-rag-raw-nochunks-v1"),
    ("Expanded20 RAG+Notes + backfill", "expanded20-rag-notes-v1", "expanded20-rag-notes-v1"),
)


def jsonl(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.is_file() else []


def tally(calls, stage):
    result = {}
    for channel in ("controller", "embedding"):
        subset = [c for c in calls if c.get("channel") == channel]
        prefix = stage + "_" + channel + "_"
        result.update({
            prefix + "calls": len(subset),
            prefix + "failed": sum(c.get("status") != "success" for c in subset),
            prefix + "input_tokens": sum(c.get("prompt_tokens") or 0 for c in subset),
            prefix + "output_tokens": sum(c.get("completion_tokens") or 0 for c in subset) if channel == 'controller' else '',
            prefix + "unknown_input_usage_calls": sum(c.get("prompt_tokens") is None for c in subset),
            prefix + "unknown_output_usage_calls": sum(c.get("completion_tokens") is None for c in subset) if channel == 'controller' else 0,
        })
    return result


def paper_outputs(summaries):
    """Refresh only this experiment's paper artifacts from persisted numbers."""
    names = {
        'AgentRunbook-R': 'AgentRunbook-R (original packing)',
        'AgentRunbook-R + chunks (matched)': 'AgentRunbook-R + chunks',
        'AgentRunbook-R + chunks + tokenizer reuse': 'AgentRunbook-R + common fixes',
        'RAG+Notes': 'RAG+Notes (original packing)',
        'RAG raw': 'Raw RAG (original packing)',
        'J matched repeat': 'Raw RAG + chunks (J)',
        'L: J + tokenizer reuse': 'Raw RAG + chunks + tokenizer reuse (L)',
        'M: L + lexical source backfill': 'L + lexical source backfill (M)',
        'N: M + adjacent source lines': 'M + adjacent source lines (N)',
        'N expanded20': 'N, expanded corpus',
        'M minus chunks': 'M minus chunk packing',
        'M expanded20': 'M, expanded corpus',
        'RAG+Notes + backfill': 'RAG+Notes + common fixes + backfill',
        'O: Notes+M + query embedding reuse': 'Notes+M + exact query embedding reuse (O)',
        'Notes+M minus chunks': 'Notes+M minus chunks',
        'O expanded20': 'O, expanded corpus',
        'AgentRunbook-R + backfill': 'AgentRunbook-R + common fixes + backfill',
        'Strong B3-c1 + backfill': 'Strong B3-c1 + backfill',
        'Ours-dev + backfill': 'Ours-dev + backfill',
        'K matched + tokenizer reuse': 'RAG+Notes + common fixes',
        'No chunks + tokenizer reuse': 'L minus chunk packing',
        'Strong B3-c1 adapted': 'Strong B3-c1 / structured-source adapted',
        'Ours-dev adapted': 'Ours-dev / structured-source adapted',
        'L expanded20': 'L, expanded corpus',
        'Expanded20 no chunks': 'L minus chunks, expanded corpus',
        'Expanded20 RAG+Notes + backfill': 'RAG+Notes + backfill, expanded corpus',
    }
    selected = [r for r in summaries if r['method'] in names and r['haystack_metadata'] == 'matched']
    repeat_families = {'M: L + lexical source backfill': ['M repeat 2', 'M repeat 3'],
                       'RAG+Notes + backfill': ['Notes+M repeat 2', 'Notes+M repeat 3']}
    by_name = {r['method']: r for r in summaries}
    def quality_label(row):
        scores = [row['correct']] + [by_name[n]['correct'] for n in repeat_families.get(row['method'], []) if n in by_name]
        return ', '.join(map(str, scores)) + '/8' + (' (repeats)' if len(scores) > 1 else '')
    table = ['| Method | Traj./states | Build→publish s | Build gen calls (failed) | Complete | Correct | Pending | Prompt / Reader wall s |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in selected:
        timing = f"{r['prompt_wall_s']} / {r['reader_wall_s']}" if r['prompt_wall_s'] != '' else 'not recorded'
        table.append(f"| {names[r['method']]} | {r['trajectories']}/{r['states']} | {r['build_publish_s']:.2f} | {r['build_controller_calls']} ({r['build_controller_failed']}) | {r['complete']}/{r['questions']} | {quality_label(r)} | {r['pending']} | {timing} |")
    (ROOT / 'results/tables/dev_adapted_paper.md').write_text('\n'.join(table) + '\n')
    latex = ['% Text-only adapted development; query-only rows reuse the recorded cold construction.',
             r'\begin{tabular}{lrrrr}', r'\hline', r'Method & Trajectories & Build (s) & Complete & Correct \\', r'\hline']
    for r in selected:
        label = names[r['method']].replace('&', r'\&').replace('_', r'\_')
        latex.append(f"{label} & {r['trajectories']} & {r['build_publish_s']:.2f} & {r['complete']}/8 & {quality_label(r)} " + r'\\')
    latex += [r'\hline', r'\end{tabular}']
    (ROOT / 'results/tables/dev_adapted_paper.tex').write_text('\n'.join(latex) + '\n')
    figure_names = {
        'AgentRunbook-R + chunks (matched)': 'AgentRunbook-R + chunks',
        'RAG raw': 'Raw RAG, original packing',
        'J matched repeat': 'J: raw + chunks',
        'L: J + tokenizer reuse': 'L: J + tokenizer reuse',
        'M: L + lexical source backfill': 'M: L + source backfill',
        'N: M + adjacent source lines': 'N: M + local source context',
        'RAG+Notes + backfill': 'RAG+Notes + M (quality candidate)',
        'O: Notes+M + query embedding reuse': 'O: Notes+M + query reuse',
        'Strong B3-c1 adapted': 'Strong B3-c1 adapted',
        'Ours-dev adapted': 'Ours-dev adapted',
    }
    plotted = [r for r in selected if r['method'] in figure_names]
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{110+45*len(plotted)}">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<g font-family="sans-serif" font-size="13" fill="#222">',
           '<text x="15" y="24">Text-only adapted development (8 fixed questions; 10 complete trajectories)</text>',
           '<text x="295" y="52">Recorded cold build to publication (seconds)</text>',
           '<text x="800" y="52">Correct / 8 (repeat range)</text>']
    largest = max((r['build_publish_s'] for r in plotted), default=1)
    for i, r in enumerate(plotted):
        y = 70 + 45*i
        bar = 370 * r['build_publish_s']/largest
        svg += [f'<text x="15" y="{y+17}">{escape(figure_names[r["method"]])}</text>',
                f'<rect x="295" y="{y}" width="{bar:.1f}" height="24" fill="#397ca8"/>',
                f'<text x="{305+bar:.1f}" y="{y+17}">{r["build_publish_s"]:.1f}</text>']
        scores = [r['correct']] + [by_name[n]['correct'] for n in repeat_families.get(r['method'], []) if n in by_name]
        for j in range(8):
            color = '#228866' if j < min(scores) else ('#e2ae43' if j < max(scores) else '#dddddd')
            svg.append(f'<circle cx="{808+j*19}" cy="{y+12}" r="6" fill="{color}"/>')
    svg += [f'<text x="15" y="{100+45*len(plotted)}">Amber = variation across repeats. Query variants reuse cold builds. No native/Judge or superiority claim.</text>', '</g></svg>']
    (ROOT / 'reports/dev_adapted_paper.svg').write_text('\n'.join(svg) + '\n')
    repeated = [r for r in summaries if r['method'] in {'L: J + tokenizer reuse', 'L repeat 2', 'L repeat 3', 'M: L + lexical source backfill', 'M repeat 2', 'M repeat 3', 'N: M + adjacent source lines', 'N repeat 2', 'N repeat 3', 'RAG+Notes + backfill', 'Notes+M repeat 2', 'Notes+M repeat 3'}]
    repeat_text = '\n'.join(f"- {r['method']}: {r['correct']}/8 correct, {r['complete']}/8 complete; prompt {r['prompt_wall_s']}s, Reader {r['reader_wall_s']}s." for r in repeated)
    draft = '''# Text-only adapted development: experimental draft

## Experimental setup

We evaluate eight fixed questions from LongMemEval-V2 (four each from enterprise and web) against a shared memory per domain. Each base memory contains five **complete** trajectories, including one fixed distractor: ten trajectories and 91 recorded states in total. The questions cover static environment, dynamic environment, and procedure types. Questions are not removed after incorrect responses. The source IDs, answer-bearing trajectories and file hashes are in the frozen manifests. Selection is evidence-accessible development sampling, not held-out evaluation.

The controller and Reader use the resident Qwen3.5-9B service, and embedding uses Qwen3-Embedding-8B. The Reader has a 2048-token output ceiling, thinking disabled, temperature 0.6, top-p 0.95, top-k 20, concurrency one, and a common 12000-token memory-context budget. Earlier 1024-token Reader runs truncated; 2048 is used throughout this comparison. We retain full recorded text and omit screenshots explicitly. Controller operations retain method-specific prompts/budgets (AgentRunbook/RAG notes: 8192 ceiling; adapted core extraction: 1024 ceiling with the existing compact extraction prompt), so only B3 versus Ours is a matched construction-mechanism comparison. Controller output budgets are not Reader budgets.

We reuse the official question-specific deterministic evaluators for these selected questions. Correctness is measured over all eight fixed questions and is separate from complete boxed-answer parsing. These are text-only adapted development scores, not native multimodal Small, not an official Judge result, and not independent test accuracy. No unavailable Judge is replaced implicitly.

Construction wall time runs from insertion of the first trajectory through indexing, per-trajectory persistence and final reload validation. Resident model serving and pre-insertion client/tokenizer initialization are outside this boundary. Cold means an empty method memory/cache, not cold GPU model loading. Query-only modifications reuse compatible persisted memory: their construction number is the cost of the source build, not a new measurement. Prompt-stage and Reader-stage wall times are recorded separately; inclusive per-question queue sums must not be read as wall time. Model totals include reported usage, with unknown usage counts retained separately. Failed requests with unknown tokens are not free.

## Current results

TABLE

## Method and ablation interpretation

The first practical candidate L combines raw-state RAG, line-boundary chunk/interleave packing of oversized retrieved items, and reuse of the identical tokenizer instance during repeated context-budget checks. Full raw trajectories remain on disk. Chunking changes evidence allocation under the common budget; it does not add gold answers or new model calls. Continuation chunks currently do not repeat source headers, a provenance/readability limitation. Tokenizer reuse is a common engineering optimization, not a new retrieval method.

Candidate M adds query-time lexical source backfill from at most two top retrieved trajectories. It normalizes leading UI node IDs only for repeated-line deduplication, scores literal source lines by query-term inverse document frequency, weights explicitly quoted query words threefold, and retains up to 64 anchors under a 12000-character excerpt cap. Source trajectory/state/line coordinates accompany each retained line. It adds no generation or embedding requests. These heuristics were developed on this development set, not frozen before seeing its errors. N changes one factor: add immediate neighboring source lines into unused space under the same excerpt cap. The ordinary 12000-token Reader memory budget still applies to all variants.

Candidate A bounded the event extractor's initial AXTree request. It removed 32 failed build calls but did not reduce construction wall time (1181.42s versus 1170.71s), with 6/8 correct. Candidate B reduced client event concurrency from 16 to 4; its 1041.21s run reached only 4/8 and retained 32 failed build calls. The service serializes model execution, so this is **not** evidence of real batching. Candidate C prioritized raw evidence and reached 5/8, not an improvement over the 6/8 reference. Removing event generation (D) cost 398.18s and reached 4/8. The full candidate table retains further unsuccessful ordering/top-k attempts. These negative results motivated changing the amount of generated memory and the evidence packing, rather than optimizing cheap dependency bookkeeping.

With common chunk packing, AgentRunbook-R and raw RAG J both reached 6/8 on a correctly matched rerun. Raw RAG's recorded construction cost is 89.07s versus 1170.71s (92.39% lower), but this is a single historical cold-build comparison, not a repeated speedup estimate or a general claim of equal accuracy. The matched tokenizer ablation reduced prompt-stage wall time from 34.32s (J) to 6.09s (L) on the first paired runs, with identical 86186 total Reader input tokens and 6/8 correct in both. Reader generation is stochastic; only the deterministic input equality and measured stage times support the tokenizer claim.

Strong B3 and Ours use their existing conservative-partition and dependency-incremental cores respectively, independent stores/caches, the same salient-v3/source-literal representation, and the same live extractor. Generated facts drive state-slice embeddings and are returned with full raw source backreferences. Methods run serially against the same resident service, with order reversed between domains. The historical eager batch2 backend is not reloaded alongside this service. Full-trajectory insertions are measured as cold construction with per-trajectory publications; they do not establish state-revision Freshness/Goodput. If calls and tokens remain equal, the appropriate conclusion is no demonstrated expensive-work reduction, not a DAG speedup.

## Repeats

REPEATS

These are repeated stochastic Reader runs on one memory, not independent cold-build repetitions or additional questions.

## Corpus scaling

The expanded corpus keeps the same eight questions and all original evidence trajectories. Five distractors per domain are selected from the common official haystack by SHA256(expanded20-v1:trajectory_id), without consulting answers or outputs. This gives twenty complete trajectories and 293 states. The configuration is frozen before the expansion run. This tests distractor/load robustness, not generalization to independent questions.

## Integrity and limitations

Historical E–K query commands requested official 100-trajectory haystack metadata while loading the actual five-trajectory/domain cache. Their answers were generated from those five cached trajectories, but the metadata mismatch is retained and flagged; they are excluded from the clean paper table until matched reruns exist. A new ID/order guard rejects such loads. Historical I additionally used a different embedding-model alias. H/I's interleave counts refer to raw memory items, including images, not ranked hits. The four-question expansion attempt chosen by answer substring was invalid and is excluded, with its files retained. Larger-corpus expansion above avoids that selection error.

Eight development questions, active tuning on their errors, single-run cold builds, sampling variance, missing vision, and no independent test set limit publication claims. Current supported contribution is a measured cost/quality trade-off and diagnosis of evidence-budget waste; there is no supported general SOTA, native Small, or strong-B3 speedup claim.
'''.replace('TABLE', '\n'.join(table)).replace('REPEATS', repeat_text or 'Pending repeated matched runs.')
    indexed_now = {r['method']: r for r in summaries}
    findings = ['\n## Updated measured findings (generated from the current table)\n']
    for family, primary in [('M', 'M: L + lexical source backfill'), ('N', 'N: M + adjacent source lines'), ('Notes+M', 'RAG+Notes + backfill')]:
        runs = [indexed_now[n] for n in (primary, family+' repeat 2', family+' repeat 3') if n in indexed_now]
        if runs:
            counts = ', '.join(str(r['correct'])+'/8' for r in runs)
            findings.append(f"- {family} repeated QA: {counts}; {sum(r['complete'] for r in runs)}/{8*len(runs)} complete outputs. Repeated answers are not distinct questions or independent cold builds.")
    for name in ('M minus chunks', 'M expanded20', 'N expanded20', 'Expanded20 RAG+Notes + backfill', 'O: Notes+M + query embedding reuse', 'O expanded20', 'Notes+M minus chunks', 'RAG+Notes + backfill', 'AgentRunbook-R + backfill', 'Strong B3-c1 + backfill', 'Ours-dev + backfill'):
        if name in indexed_now:
            r = indexed_now[name]
            findings.append(f"- {name}: {r['correct']}/8 correct, {r['complete']}/8 complete, source build {r['build_publish_s']:.3f}s; prompt + Reader wall {r['prompt_plus_reader_wall_s']}s.")
    if 'Strong B3-c1 adapted' in indexed_now and 'Ours-dev adapted' in indexed_now:
        b, o = indexed_now['Strong B3-c1 adapted'], indexed_now['Ours-dev adapted']
        findings.append(f"- Existing-core pair: B3 {b['build_publish_s']:.3f}s / {b['correct']}/8, Ours {o['build_publish_s']:.3f}s / {o['correct']}/8. Construction generation calls {b['build_controller_calls']} vs {o['build_controller_calls']}; input tokens {b['build_controller_input_tokens']} vs {o['build_controller_input_tokens']}; output tokens {b['build_controller_output_tokens']} vs {o['build_controller_output_tokens']}. Sampling differed, so observed runtime/QA differences do not isolate dependency scheduling; no demonstrated reduction of expensive model work.")
    draft += '\n'.join(findings) + '\n'
    (ROOT / 'reports/dev_adapted_paper_draft.md').write_text(draft)
    equivalence = []
    for domain in ('enterprise', 'web'):
        left = jsonl(RUNS / f'{domain}-rag-raw-optJ-r3-matched-v1/prompt_rows.jsonl')
        right = jsonl(RUNS / f'{domain}-rag-raw-optL-matched-v1/prompt_rows.jsonl')
        if len(left) == len(right) == 4:
            for a, b in zip(left, right):
                equivalence.append({'domain': domain, 'question_id': a['question_id'],
                                    'question_id_match': a['question_id'] == b['question_id'],
                                    'memory_context_equal': a['memory_context'] == b['memory_context'],
                                    'prompt_messages_equal': a['prompt_messages'] == b['prompt_messages'],
                                    'memory_tokens': a['memory_context_token_count']})
    (ROOT / 'results/tables/dev_adapted_tokenizer_equivalence.json').write_text(json.dumps(equivalence, indent=2) + '\n')
    failures = []
    for suffix, reason in [
        ('enterprise-workflow-b3-v1', 'Strict core parse rejected pre-think partial JSON; full responses retained, fixed in v2, not a successful build'),
        ('enterprise-agentrunbook-r-optE-ext4-v1', 'Invalid evidence selection by answer substring; not a valid expanded QA set')]:
        p = RUNS / suffix
        if not p.exists():
            continue
        calls = jsonl(p / 'memory_state/model_calls.jsonl')
        metrics = jsonl(p / 'memory_build_metrics.jsonl')
        qs = jsonl(p / 'per_question.jsonl')
        failures.append({'run': suffix, 'reason': reason, 'included_in_main_table': False,
                         'build_attempt_s': sum(m.get('elapsed_seconds', 0) for m in metrics),
                         'trajectories_published': sum(m.get('status') == 'success' for m in metrics),
                         'controller_api_calls_in_own_store': sum(c.get('channel') == 'controller' for c in calls),
                         'complete_answers': sum(q.get('reader_answer_complete') is True for q in qs),
                         'truncated_answers': sum(q.get('reader_truncated') is True for q in qs),
                         'raw_path': str(p)})
    if failures:
        with (ROOT / 'results/tables/dev_adapted_excluded_attempts.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=failures[0].keys())
            writer.writeheader()
            writer.writerows(failures)
    checkpoints = []
    for method in ('b3', 'ours'):
        for domain in ('enterprise', 'web'):
            p = RUNS / f'{domain}-workflow-{method}-v2'
            builds = jsonl(p / 'memory_build_metrics.jsonl')
            core = {r['trajectory_id']: r for r in jsonl(p / 'memory_state/workflow_checkpoints.jsonl')}
            for index, r in enumerate(builds):
                detail = core.get(r['trajectory_id'], {})
                stats = detail.get('stats', {})
                checkpoints.append({'method': method, 'domain': domain,
                    'phase': 'initial_full_trajectory' if index == 0 else 'append_full_trajectory',
                    'trajectory_id': r['trajectory_id'], 'status': r['status'],
                    'insert_and_persist_s': r['elapsed_seconds'],
                    'core_plus_index_s': detail.get('core_plus_index_s'),
                    'new_states': detail.get('events'), 'evidence_total': detail.get('evidence'),
                    'reused_nodes': stats.get('reused_nodes'), 'invalidated_nodes': stats.get('invalidated_nodes'),
                    'scope': 'checkpoints within cold corpus ingestion; not externally timed streaming Freshness',
                    'raw_path': str(p)})
    if checkpoints:
        with (ROOT / 'results/tables/dev_adapted_mechanism_checkpoints.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=checkpoints[0].keys())
            writer.writeheader()
            writer.writerows(checkpoints)

    # Reuse the existing development ledger without touching historical rows.
    decisions = {
        'A: bounded event AXTree': ('A', 'AgentRunbook-R', 'Retain reliability result; no build-time benefit'),
        'B: event concurrency=4': ('B', 'AgentRunbook-R', 'Reject: quality regression; backend not actually parallel'),
        'C: evidence-first packing': ('C', 'AgentRunbook-R', 'Reject alone: quality regression'),
        'D: raw-state index + notes (no generated events)': ('D', 'AgentRunbook-R', 'Reject alone: lower quality despite cheaper build'),
        'J matched repeat': ('J', 'RAG raw', 'Retain: evidence packing recovers one dev answer'),
        'L: J + tokenizer reuse': ('L', 'J matched repeat', 'Retain: identical prompts; lower prompt-stage wall time'),
        'M: L + lexical source backfill': ('M', 'L: J + tokenizer reuse', 'Retain cost-efficient candidate; 7/7/6 correct across three runs, not stable 7/8'),
        'N: M + adjacent source lines': ('N', 'M: L + lexical source backfill', 'Reject: adjacent context regresses to 6/8'),
        'RAG+Notes + backfill': ('NotesM', 'K matched + tokenizer reuse', 'Quality-oriented candidate; repeat and scale before claiming stability'),
        'O: Notes+M + query embedding reuse': ('O', 'RAG+Notes + backfill', 'Test exact within-query reuse; retain only with identical context'),
    }
    ledger_path = ROOT / 'results/tables/dev_iterations.csv'
    with ledger_path.open() as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        prior = [r for r in reader if not r['iteration'].startswith('TEXT-')]
    indexed = {r['method']: r for r in summaries}
    for method, (tag, reference, decision) in decisions.items():
        if method not in indexed or reference not in indexed:
            continue
        c, b = indexed[method], indexed[reference]
        scope = 'build_to_queryable_publish' if tag in 'ABD' else 'query_prompt_plus_reader_wall'
        bs = b['build_publish_s'] if tag in 'ABD' else b['prompt_plus_reader_wall_s']
        cs = c['build_publish_s'] if tag in 'ABD' else c['prompt_plus_reader_wall_s']
        values = {'iteration': 'TEXT-' + tag, 'change': method, 'decision': decision,
                  'qa_status': f"deterministic adapted dev {b['correct']}/8 -> {c['correct']}/8; complete {c['complete']}/8",
                  'reference_run': b['reader_suffix'], 'candidate_run': c['reader_suffix'],
                  'reference_method': reference, 'candidate_method': method, 'scope': scope,
                  'n_requested_pairs': 8, 'n_successful_pairs': c['complete'],
                  'paired_reference_total_s': bs, 'paired_candidate_total_s': cs,
                  'latency_reduction_pct': round(100*(1-cs/bs), 3) if bs and cs else '',
                  'reference_input_tokens': b['build_controller_input_tokens'],
                  'candidate_input_tokens': c['build_controller_input_tokens'],
                  'reference_live_calls': b['build_controller_calls'], 'candidate_live_calls': c['build_controller_calls'],
                  'reference_metrics': str(ROOT / 'results/tables/dev_adapted_first_compare.csv'),
                  'candidate_metrics': str(ROOT / 'results/tables/dev_adapted_per_question.csv')}
        prior.append({k: values.get(k, '') for k in fields})
    with ledger_path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(prior)


def main():
    summaries, details = [], []
    for name, build_suffix, reader_suffix in VARIANTS:
        domains = []
        for domain in ("enterprise", "web"):
            build = RUNS / (domain + "-" + build_suffix)
            reader = RUNS / (domain + "-" + reader_suffix)
            if not (build / "memory_build_summary.json").is_file() or not (reader / "per_question.jsonl").is_file():
                break
            state = json.loads((build / "memory_build_summary.json").read_text())
            qs = jsonl(reader / "per_question.jsonl")
            if not state.get("saved_memory_load_verified") or len(qs) != 4:
                break
            ids = {q.get("query_invocation_id") for q in jsonl(reader / "prompt_rows.jsonl")}
            all_calls = jsonl(build / "memory_state/model_calls.jsonl")
            builds = [c for c in all_calls if not c.get("query_invocation_id")]
            queries = [c for c in all_calls if c.get("query_invocation_id") and c.get("query_invocation_id") in ids]
            domains.append((domain, state, qs, builds, queries))
        if len(domains) != 2:
            continue
        all_qs = [q for _, _, qs, _, _ in domains for q in qs]
        prompt_summaries = [json.loads((RUNS / (domain + "-" + reader_suffix) / "prompt_build_summary.json").read_text()) for domain, _, _, _, _ in domains]
        reader_metrics = [json.loads((RUNS / (domain + "-" + reader_suffix) / "aggregated_metrics.json").read_text()) for domain, _, _, _, _ in domains]
        prompt_wall = [summary.get("prompt_build_wall_seconds") for summary in prompt_summaries]
        reader_wall = [(result.get("timing") or {}).get("reader_generation_wall_seconds") for result in reader_metrics]
        identities = []
        state_counts = []
        trajectory_counts = []
        for domain, _, _, _, _ in domains:
            build = RUNS / (domain + "-" + build_suffix)
            reader = RUNS / (domain + "-" + reader_suffix)
            actual = json.loads((build / 'memory_state/index.json').read_text())['inserted_trajectory_ids']
            expected = json.loads((reader / 'runtime_inputs/haystack.json').read_text())
            identities.append(all(ids == actual for ids in expected.values()))
            trajectory_counts.append(len(actual))
            state_counts.append(len(jsonl(build / 'memory_state/pools/raw_state_pool.jsonl')))
        row = {
            "method": name, "scope": "diagnostic-text-only/adapted", "questions": len(all_qs),
            "trajectories": sum(trajectory_counts), "states": sum(state_counts),
            "haystack_metadata": "matched" if all(identities) else "historical_requested_loaded_mismatch",
            "build_reused_for_query": build_suffix != reader_suffix,
            "build_suffix": build_suffix, "reader_suffix": reader_suffix,
            "token_accounting": "reported usage only; unknown-usage calls counted separately, not free",
            "construction_representation": "salient-v3/source-literals + fact-slice embeddings + raw backreferences" if 'workflow-' in build_suffix else "method-specific original representation",
            "construction_generation_ceiling": 1024 if 'workflow-' in build_suffix else 8192,
            "configuration_caveat": "historical embedding-model alias differs" if name.startswith('I:') else '',
            "reader_budget": 2048, "context_budget": 12000,
            "build_publish_s": round(sum(s["elapsed_seconds"] for _, s, _, _, _ in domains), 3),
            "retrieval_internal_s_sum": round(sum(q.get("memory_query_duration_seconds") or 0 for q in all_qs), 3),
            "reader_per_question_inclusive_s_sum": round(sum(q.get("reader_generation_duration_seconds") or 0 for q in all_qs), 3),
            "prompt_wall_s": round(sum(prompt_wall), 3) if all(x is not None for x in prompt_wall) else "",
            "reader_wall_s": round(sum(reader_wall), 3) if all(x is not None for x in reader_wall) else "",
            "prompt_plus_reader_wall_s": round(sum(prompt_wall) + sum(reader_wall), 3) if all(x is not None for x in prompt_wall + reader_wall) else "",
            "reader_request_s_sum": round(sum(q.get("reader_request_duration_seconds") or 0 for q in all_qs), 3) if all("reader_request_duration_seconds" in q for q in all_qs) else "",
            "reader_queue_s_sum": round(sum(q.get("reader_queue_duration_seconds") or 0 for q in all_qs), 3) if all("reader_queue_duration_seconds" in q for q in all_qs) else "",
            "complete": sum(q.get("reader_answer_complete") is True for q in all_qs),
            "correct": sum(q.get("score_bool") is True for q in all_qs),
            "wrong": sum(q.get("score_bool") is False for q in all_qs),
            "pending": sum(q.get("evaluation_status") == "pending_judge" for q in all_qs),
            "truncated": sum(q.get("reader_truncated") is True for q in all_qs),
            "service_failure": sum(q.get("reader_status") != "ok" for q in all_qs),
            "parse_failure": sum(q.get("reader_status") == "ok" and not q.get("reader_truncated") and q.get("reader_parse_status") != "boxed" for q in all_qs),
            "reader_calls": len(all_qs),
            "reader_input_tokens": sum((q.get("usage") or {}).get("prompt_tokens") or 0 for q in all_qs),
            "reader_output_tokens": sum((q.get("usage") or {}).get("completion_tokens") or 0 for q in all_qs),
            "reader_unknown_input_usage_calls": sum((q.get("usage") or {}).get("prompt_tokens") is None for q in all_qs),
            "reader_unknown_output_usage_calls": sum((q.get("usage") or {}).get("completion_tokens") is None for q in all_qs),
            "qa_scope": "deterministic dev scoring, not official multimodal/Judge",
        }
        row.update(tally([c for _, _, _, calls, _ in domains for c in calls], "build"))
        row.update(tally([c for _, _, _, _, calls in domains for c in calls], "retrieval"))
        row['retrieval_embedding_cache_hits'] = sum(c.get('channel') == 'embedding_cache' and c.get('status') == 'hit' for _, _, _, _, calls in domains for c in calls)
        summaries.append(row)
        for domain, _, qs, _, _ in domains:
            for q in qs:
                details.append({k: q.get(k) for k in ("question_id", "question_type", "answer_gold", "response_parsed_boxed", "eval_function", "score", "score_bool", "evaluation_status", "reader_status", "reader_answer_complete", "reader_truncated", "reader_finish_reason", "reader_parse_status", "memory_query_duration_seconds", "reader_generation_duration_seconds") } | {"method": name, "domain": domain})
    for rows, filename in ((summaries, "dev_adapted_first_compare.csv"), (details, "dev_adapted_per_question.csv")):
        if not rows:
            continue
        path = ROOT / "results/tables" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    if summaries:
        paper_outputs(summaries)
        chart = ROOT / "reports/dev_adapted_cost_quality.svg"
        chart.parent.mkdir(parents=True, exist_ok=True)
        maximum = max(r["build_publish_s"] for r in summaries)
        content = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="{60 + 52 * len(summaries)}">',
                   '<rect width="100%" height="100%" fill="white"/>',
                   '<text x="12" y="24" font-family="sans-serif" font-size="16">Adapted text-only: build cost versus dev QA (8 questions)</text>']
        for i, r in enumerate(summaries):
            y = 48 + 52 * i
            width = round(390 * r["build_publish_s"] / maximum)
            content += [f'<text x="10" y="{y+17}" font-size="12" font-family="sans-serif">{escape(r["method"])}</text>',
                        f'<rect x="500" y="{y}" width="{width}" height="24" fill="#2789b8"/>',
                        f'<text x="{510+width}" y="{y+17}" font-size="12" font-family="sans-serif">{r["build_publish_s"]:.0f}s, {r["correct"]}/{r["questions"]}, {r["trajectories"]} traj</text>']
        chart.write_text("\n".join(content + ["</svg>"]), encoding="utf-8")
    for row in summaries:
        print(row["method"], "build", row["build_publish_s"], "QA", str(row["correct"]) + "/8", "controller", row["build_controller_calls"], "failed", row["build_controller_failed"])


if __name__ == "__main__":
    main()
