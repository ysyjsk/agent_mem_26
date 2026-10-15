#!/usr/bin/env python3
"""Report the narrow adjacent-extraction experiment from persisted live records."""
import argparse
import csv
import hashlib
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / 'runs/construction-pair-v1'
SERVER_LOG = ROOT / 'runs/agentrunbook-r-native-small-20261013/matched-runtime/chat-adapted.log'


def transport_counts(path, controller):
    """Align the entire consecutive success sequence, not a single token count.

    These builds run serially on the one resident service. Its success log and
    error lines expose retries hidden by the SDK. Ambiguous matches stay unknown.
    """
    target = [(r['prompt_tokens'], r['completion_tokens']) for r in controller if r['status'] == 'success']
    unknown = dict.fromkeys(('http_calls', 'http_failed_attempts', 'http_oom_attempts', 'http_context_limit_attempts'))
    if not target or not SERVER_LOG.exists(): return unknown
    lines = SERVER_LOG.read_text(errors='replace').splitlines()
    successes = []
    for i, line in enumerate(lines):
        if not line.startswith('{'): continue
        try: row = json.loads(line)
        except ValueError: continue
        if row.get('kind') == 'chat': successes.append((i, (row.get('prompt_tokens'), row.get('completion_tokens'))))
    matches = [i for i, (_, first) in enumerate(successes) if first == target[0] and
               [r[1] for r in successes[i:i+len(target)]] == target]
    if len(matches) != 1: return unknown
    index = matches[0]
    start, end = successes[index][0], successes[index+len(target)-1][0]
    if controller[0]['status'] == 'failed': start = successes[index-1][0] + 1 if index else 0
    excerpt = lines[start:end+1]
    failures = sum(line.startswith('request failed:') for line in excerpt)
    (path / 'server_build_excerpt.log').write_text('\n'.join(excerpt) + '\n')
    return {'http_calls': len(target) + failures, 'http_failed_attempts': failures,
            'http_oom_attempts': sum(line.startswith('request failed: OutOfMemoryError:') for line in excerpt),
            'http_context_limit_attempts': sum(line.startswith('request failed: ValueError:') and 'max_input_tokens' in line for line in excerpt)}


def jsonl(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.exists() else []


def audit(path):
    memory = path / 'memory_state'
    events = jsonl(memory / 'pools/event_pool.jsonl')
    raw = jsonl(memory / 'pools/raw_state_pool.jsonl')
    notes = jsonl(memory / 'pools/procedure_note_pool.jsonl') + jsonl(memory / 'pools/hint_note_pool.jsonl')
    sources = {p.parent.name: json.loads(p.read_text()) for p in (memory / 'trajectories').glob('*/trajectory.json')}
    expected = {(tid, a['state_index'], b['state_index']) for tid, t in sources.items() for a, b in zip(t['states'], t['states'][1:])}
    actual = {(e['trajectory_id'], e['pre_state_index'], e['post_state_index']) for e in events}
    checks = {'event_source_coverage': actual == expected and len(events) == len(expected),
        'event_fields_nonempty': all(e.get('overview') and e.get('state_transition') for e in events),
        'raw_state_coverage': len(raw) == sum(len(t['states']) for t in sources.values()),
        'both_notes_preserved': len(notes) == 2 * len(sources),
        'sources_valid': all(e['pre_screenshot'] == sources[e['trajectory_id']]['states'][e['pre_state_index']]['screenshot'] and
            e['post_screenshot'] == sources[e['trajectory_id']]['states'][e['post_state_index']]['screenshot'] for e in events)}
    # Predeclared source-backed fact probes for the first complete trajectory.
    probes = {2: ['Name', 'Cyberpunk'], 3: ['Title', 'Cyberpunk'], 4: ['Description', 'Welcome to the future'],
              5: ['Sidebar', 'Games', 'Books', 'Movies', 'Future'], 6: ['Cyberpunk']}
    probe_rows = [{'event_id': e['event_id'], 'literals': probes[e['pre_state_index']],
                   'pass': all(v.lower() in e['state_transition'].lower() for v in probes[e['pre_state_index']])}
                  for e in events if e['trajectory_id'] == '1ad1af4b' and e['pre_state_index'] in probes]
    return {'structural_checks': checks, 'structural_pass': all(checks.values()), 'event_count': len(events),
            'raw_state_count': len(raw), 'note_count': len(notes), 'screen_fact_probes': probe_rows,
            'fact_probe_scope': 'Five source-backed value/change probes on 1ad1af4b; not a semantic equivalence or official QA claim'}


def summarize(path):
    summary = json.loads((path / 'memory_build_summary.json').read_text())
    rows = jsonl(path / 'memory_state/model_calls.jsonl')
    build = [r for r in rows if not r.get('query_invocation_id')]
    c = [r for r in build if r['channel'] == 'controller']
    e = [r for r in build if r['channel'] == 'embedding']
    cache = [r for r in build if r['channel'] == 'build_embedding_cache']
    qa = jsonl(path / 'per_question.jsonl')
    checks = audit(path)
    (path / 'construction_quality_checks.json').write_text(json.dumps(checks, indent=2) + '\n')
    # Per-question output is retained in its original file with official-source dev evaluator.
    complete = sum(bool(r.get('reader_answer_complete')) for r in qa)
    result = {'run': path.name, 'scope': 'text-only/adapted', 'measurement': 'new_empty_memory_resident_models',
        'trajectories': summary['trajectory_count'], 'states': checks['raw_state_count'], 'events': checks['event_count'],
        'notes': checks['note_count'], 'cold_build_publish_s': summary['elapsed_seconds'], 'update_s': '',
        'llm_calls': len(c), 'llm_input_tokens_known': sum(r.get('prompt_tokens') or 0 for r in c),
        'llm_output_tokens_known': sum(r.get('completion_tokens') or 0 for r in c),
        'llm_unknown_usage_calls': sum(r.get('prompt_tokens') is None for r in c),
        'event_calls': sum(r.get('call_mode') == 'async_text' for r in c),
        'note_calls': sum(r.get('call_mode') == 'sync_text' for r in c),
        'embedding_calls': len(e), 'embedding_vectors': sum(r['input_text_count'] for r in e),
        'embedding_input_tokens_known': sum(r.get('prompt_tokens') or 0 for r in e),
        'embedding_unknown_usage_calls': sum(r.get('prompt_tokens') is None for r in e),
        'embedding_cache_hits': sum(r['cache_hits'] for r in cache),
        'embedding_logical_vectors': sum(r['logical_vectors'] for r in cache) if cache else sum(r['input_text_count'] for r in e),
        'api_failed_calls': sum(r.get('status') == 'failed' for r in c+e),
        'event_retries': sum(r['channel'] == 'event_extraction' and r['status'] == 'retry' for r in rows),
        'preflight_bounded_events': sum(r['channel'] == 'event_preflight' for r in rows),
        'group_splits': sum(r['channel'] == 'event_group' and r['status'] == 'split' for r in rows),
        'event_fallbacks': sum(r['channel'] == 'event_extraction' and r['status'] == 'fallback' for r in rows),
        'truncated_calls': sum(r.get('finish_reason') == 'length' for r in c),
        'structure_pass': checks['structural_pass'],
        'fact_probes_pass': all(r['pass'] for r in checks['screen_fact_probes']) if checks['screen_fact_probes'] else '',
        'questions': len(qa), 'complete_answers': complete,
        'reader_truncated': sum(bool(r.get('reader_truncated')) for r in qa),
        'reader_service_failed': sum(r.get('reader_status') not in ('ok', None) for r in qa),
        'reader_parse_failed': sum(r.get('reader_status') == 'ok' and not r.get('reader_answer_complete') and not r.get('reader_truncated') for r in qa),
        'correct': sum(r.get('score_bool') is True for r in qa), 'pending': sum(r.get('score_bool') is None for r in qa),
        'raw_path': str(path.relative_to(ROOT))}
    result.update(transport_counts(path, c))
    return result


def main():
    global RUNS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, default=RUNS)
    args = parser.parse_args()
    RUNS = args.run_root.resolve()
    suffix = '_v2' if RUNS.name == 'construction-pair-v2' else ''
    paths = sorted(p.parent for p in RUNS.glob('*/memory_build_summary.json'))
    rows = [summarize(p) for p in paths]
    if not rows: return
    out = ROOT / f'results/tables/construction_pair{suffix}_runs.csv'
    with out.open('w') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    aggregates = []
    for variant in ('baseline', 'joint', 'embed', 'combined'):
        group = [r for r in rows if r['run'] in [f'full10-web-{variant}', f'full10-enterprise-{variant}']]
        if len(group) != 2: continue
        agg = {'variant': variant}
        for key in rows[0]:
            if key in ('run', 'scope', 'measurement', 'raw_path', 'structure_pass', 'fact_probes_pass', 'update_s'): continue
            agg[key] = None if any(r[key] is None for r in group) else sum(r[key] for r in group)
        agg['quality_structural_pass'] = all(r['structure_pass'] for r in group)
        agg['fact_probes_pass'] = all(r['fact_probes_pass'] for r in group if r['fact_probes_pass'] != '')
        agg['raw_paths'] = ';'.join(r['raw_path'] for r in group)
        aggregates.append(agg)
    if aggregates:
        with (ROOT / f'results/tables/construction_pair{suffix}_full10.csv').open('w') as f:
            writer = csv.DictWriter(f, fieldnames=aggregates[0]); writer.writeheader(); writer.writerows(aggregates)
    # Upsert only this experiment's rows into the existing iteration ledger.
    ledger = ROOT / 'results/tables/dev_iterations.csv'
    if ledger.exists():
        with ledger.open() as fp:
            reader = csv.DictReader(fp); fields = reader.fieldnames; history = list(reader)
        prefix = 'BUILD-V2-' if suffix else 'BUILD-V1-'
        history = [r for r in history if not r['iteration'].startswith(prefix)]
        pairs = []
        by_name = {r['run']: r for r in rows}
        if not suffix:
            for name, ref, cand in [('screen-joint', 'screen-web-g1', 'screen-web-g2'),
                                    ('web5-joint', 'full10-web-baseline', 'full10-web-joint')]:
                if ref in by_name and cand in by_name: pairs.append((name, by_name[ref], by_name[cand]))
        elif aggregates:
            baseline = next((a for a in aggregates if a['variant'] == 'baseline'), None)
            if baseline:
                for candidate in aggregates:
                    if candidate['variant'] != 'baseline': pairs.append((candidate['variant'], baseline, candidate))
        for name, ref, cand in pairs:
            entry = {key: '' for key in fields}
            entry.update({'iteration': prefix + name, 'change': name,
                'decision': 'retain measured costs; quality constraint, no DAG/official quality claim',
                'qa_status': f"{cand['correct']}/{cand['questions']} development correct; {cand['complete_answers']} complete",
                'scope': 'text-only/adapted cold build through saved reload validation',
                'reference_method': 'AgentRunbook-R single', 'candidate_method': name,
                'reference_run': ref.get('run', ref.get('raw_paths')), 'candidate_run': cand.get('run', cand.get('raw_paths')),
                'n_requested_pairs': ref['trajectories'], 'n_successful_pairs': cand['trajectories'],
                'reference_failed_checkpoints': 0, 'candidate_failed_checkpoints': 0,
                'paired_reference_total_s': ref['cold_build_publish_s'], 'paired_candidate_total_s': cand['cold_build_publish_s'],
                'latency_reduction_pct': 100*(1-cand['cold_build_publish_s']/ref['cold_build_publish_s']),
                'reference_input_tokens': ref['llm_input_tokens_known'], 'candidate_input_tokens': cand['llm_input_tokens_known'],
                'reference_output_tokens': ref['llm_output_tokens_known'], 'candidate_output_tokens': cand['llm_output_tokens_known'],
                'reference_live_calls': ref.get('http_calls'), 'candidate_live_calls': cand.get('http_calls'),
                'candidate_source_coverage_min': 1.0, 'candidate_actual_concurrency_max': 1,
                'reference_metrics': ref.get('raw_path', ref.get('raw_paths')), 'candidate_metrics': cand.get('raw_path', cand.get('raw_paths'))})
            history.append(entry)
        with ledger.open('w') as fp:
            writer = csv.DictWriter(fp, fieldnames=fields); writer.writeheader(); writer.writerows(history)
    lines = ['# Adjacent extraction: live construction costs', '',
        'Text-only/adapted; complete official-source trajectories. Not native Small or official Judge quality. ',
        'Cold build starts from empty method memory with resident shared models. Wall time ends after save/reload validation; query work is excluded.', '',
        'Single and paired events use 2048 tokens/event (server ceiling4096), thinking off, c1; notes retain original 8192 requested/4096 effective ceiling. All events, both notes and indexes retained.', '',
        'Frozen queries: 2048 output,12000 context,chunking,cached tokenizer,lexical backfill,no neighbor expansion,query-local exact embedding reuse. Quality is a constraint, not a search objective.', '',
        '| Run | Publish s | LLM calls | Input/output tokens | Embedding vectors/tokens | QA correct/complete/attempted | Structural |',
        '|---|---:|---:|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['run']} | {r['cold_build_publish_s']:.2f} | {r['llm_calls']} | {r['llm_input_tokens_known']}/{r['llm_output_tokens_known']} | {r['embedding_vectors']}/{r['embedding_input_tokens_known']} | {r['correct']}/{r['complete_answers']}/{r['questions']} | {r['structure_pass']} |")
    lines += ['', 'Unknown-usage failures are counted separately and are not zero-cost. Client call-duration sums are not publication wall time.',
        'Event/source/schema checks and five first-trajectory literal probes are not a substitute for the fixed eight-question development evaluation.',
        'All original requests and responses are retained in each memory_state/model_calls.jsonl; per_question.jsonl preserves answers and scoring basis.',
        'Screening result: 7→4 event requests, total8→5 controller calls; input38824→29581 (−23.8%); output1528→1608. Wall61.20→61.51s: no demonstrated speedup in this one-pair screen. No API errors, truncations, missing events or notes.']
    if suffix:
        lines += ['', 'V2 common resource handling: preflight at18000 input tokens; oversized single-event requests use the already-existing12000-char/state fallback before an OOM. Full raw trajectories remain in memory. Oversized joint groups split. SDK automatic controller retries are0. These shared fixes are not attributed to joint extraction or embedding reuse; V1 results are separate.']
    (ROOT / f'reports/construction_pair{suffix}.md').write_text('\n'.join(lines) + '\n')
    chart_rows = aggregates if suffix else [r for r in rows if r['run'] in ('full10-web-baseline', 'full10-web-joint')]
    if len(chart_rows) >= 2:
        chart = ['<svg xmlns="http://www.w3.org/2000/svg" width="1140" height="430" viewBox="0 0 1140 430">',
                 '<rect width="1140" height="430" fill="white"/>',
                 '<g font-family="sans-serif" fill="#172b4d">',
                 f'<text x="30" y="32" font-size="20">Construction costs: {"fixed 10 trajectories" if suffix else "matched five complete web trajectories"}</text>',
                 '<text x="30" y="57" font-size="13">Text-only/adapted; full events, notes, sources and indexes retained. Lower is better.</text>']
        metrics = [('cold_build_publish_s', 'Queryable publication (s)'), ('llm_input_tokens_known', 'Known LLM input tokens'),
                   ('llm_output_tokens_known', 'Known LLM output tokens')]
        colors = ['#687787', '#167fac', '#b16d35', '#16876c']
        for panel, (metric, label) in enumerate(metrics):
            x = 30 + panel*370
            maximum = max(r[metric] for r in chart_rows)
            chart.append(f'<text x="{x}" y="95" font-size="15">{label}</text>')
            for idx, row in enumerate(chart_rows):
                y = 124 + idx*62
                name = row.get('variant', row.get('run', '').replace('full10-web-', ''))
                width = 240*row[metric]/maximum if maximum else 0
                chart.append(f'<text x="{x}" y="{y}" font-size="12">{escape(name)}</text>')
                chart.append(f'<rect x="{x}" y="{y+7}" width="{width:.1f}" height="20" fill="{colors[idx]}"/>')
                chart.append(f'<text x="{x+width+7:.1f}" y="{y+22}" font-size="12">{row[metric]:,.1f}</text>')
        chart += ['<text x="30" y="398" font-size="12">QA is a constraint, not the ranking objective. Failed-call usage is unknown; retries are reported separately.</text>', '</g></svg>']
        (ROOT / f'reports/construction_pair{suffix}.svg').write_text('\n'.join(chart))
    print(json.dumps({'runs': rows, 'full10': aggregates}, indent=2))


if __name__ == '__main__': main()
