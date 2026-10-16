#!/usr/bin/env python3
"""Report the registered full-history workload from actual request records.

No model calls, no score changes, no automatic semantic certification. The
original outputs and legacy tables are never overwritten.
"""
import argparse
import csv
import hashlib
from html import escape
import importlib.util
import json
from pathlib import Path
import statistics
import sys

from focused_evidence import CURRENT, attempt_costs, fact_roles, jsonl, unique_attempts, usage

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'execution/full-small-recovery-v1/experiment_plan.json'
DEFAULT = Path('reports/execution-recovery-20261016/full-small-v1')
CORE = ['raw_rag', 'rag_notes', 'b3', 'source_coalesced']
POLICIES = CORE + ['source_only', 'source_overlay']


def load(path):
    return json.loads(Path(path).read_text())


def total(values):
    values = list(values)
    return None if any(v is None for v in values) else sum(values)


def initial_ledger_summary(records):
    """Observed non-query work only; ledger coverage is not inferred from IDs."""
    records = unique_attempts(r for r in records if not r.get('query_invocation_id'))
    controllers = [r for r in records if r.get('channel') == 'controller']
    embedding = [r for r in records if r.get('channel') == 'embedding']
    result = attempt_costs(controllers, 'initial_llm')
    result.update(initial_embedding_calls=len(embedding),
                  initial_embedding_vectors=usage(embedding,'input_text_count'),
                  initial_embedding_input_tokens=usage(embedding,'prompt_tokens'),
                  initial_embedding_failed_calls=sum(r.get('status') != 'success' for r in embedding),
                  initial_embedding_unknown_usage_calls=sum(r.get('prompt_tokens') is None for r in embedding))
    result['initial_embedding_transport_attempts'] = None
    result['embedding_call_scope'] = 'logged embedding operations; inherited SDK permits transport retries, whose individual attempts are not logged'
    result['initial_llm_tokens'] = total([result['initial_llm_input_tokens'], result['initial_llm_output_tokens']])
    result['ledger_coverage'] = 'observed non-query requests in inherited own-history ledger; not proof all historical work was logged'
    return result


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def table(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def reader_usage(answer):
    # The inherited harness used zero placeholders on service failure.
    # Those are not observed zero-cost requests.
    if answer.get('reader_status') != 'ok':
        return {}
    u = answer.get('usage') or {}
    if not u.get('prompt_tokens') and not u.get('completion_tokens'):
        return {}
    return u


def target_event_size(events, trajectory_id, policy):
    """Snapshot size, not cumulative work; invalidated events are not queryable."""
    if policy in ('raw_rag', 'rag_notes'):
        return dict(target_stored_event_chars=None, target_query_eligible_event_chars=None,
                    target_current_evidence_blocks=None)
    target = [event for event in events if event['trajectory_id'] == trajectory_id]
    eligible = [event for event in target if event.get('validity_status') != 'invalidated_source_change']
    return dict(target_stored_event_chars=sum(len(event.get('description', '')) for event in target),
                target_query_eligible_event_chars=sum(len(event.get('description', '')) for event in eligible),
                target_current_evidence_blocks=sum(event.get('state_transition', '').count(CURRENT) for event in eligible))


def snapshot_source_check(memory, expected, fingerprint):
    """Verify saved full text/actions, not just declared trajectory IDs."""
    memory = Path(memory)
    ids = load(memory/'index.json')['inserted_trajectory_ids']
    observed = {}; errors = []; states = 0; characters = 0
    for tid in ids:
        try:
            trajectory = load(memory/'trajectories'/tid/'trajectory.json')
            observed[tid] = fingerprint(trajectory)
            states += len(trajectory['states'])
            characters += sum(len(state['text']) for state in trajectory['states'])
        except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            errors.append({'trajectory_id':tid, 'error':str(exc)})
    mismatch = [tid for tid in observed if tid in expected and observed[tid] != expected[tid]]
    def digest(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    full_ids = len(ids)==len(set(ids)) and set(ids)==set(expected)
    return {'memory_path':str(memory), 'expected_trajectories':len(expected), 'loaded_trajectories':len(ids),
            'exact_id_set_matches':full_ids, 'checked_states':states, 'checked_source_characters':characters,
            'expected_text_fingerprint_sha256':digest(expected), 'observed_text_fingerprint_sha256':digest(observed),
            'mismatched_trajectory_ids':mismatch, 'unreadable_trajectories':errors,
            'full_text_matches':full_ids and not mismatch and not errors,
            'boundary':'Stored textual trajectory completeness; not generated-memory semantic certification.'}


def initial_source_evidence():
    """Read-only end-of-queue content acceptance of the six initial libraries."""
    runtime_path = ROOT/'runs/focused-maintenance-v4/full-small-recovery-v1/runtime_manifest.json'
    if not runtime_path.exists():
        return {'status':'pending_runtime_freeze', 'full_text_matches':False, 'snapshots':[]}
    runtime = load(runtime_path)
    manifest_path = ROOT/'manifests/focused-maintenance-v4/full-small-recovery-v1/data_manifest.json'
    manifest = load(manifest_path)
    helper_path = ROOT/'runs/agentrunbook-r-native-small-20261014/local-text-only/memory_modules/trajectory_store.py'
    spec = importlib.util.spec_from_file_location('formal_source_content_store',helper_path)
    helper = importlib.util.module_from_spec(spec); sys.modules[spec.name] = helper; spec.loader.exec_module(helper)
    data_root = ROOT/'third_party/LongMemEval-V2/data/longmemeval-v2'
    frozen = {tid:value for domain in manifest['data'].values() for tid,value in domain['trajectory_content_sha256'].items()}
    expected = {}; official_errors = []
    with (data_root/'trajectories.jsonl').open() as stream:
        for line in stream:
            trajectory = json.loads(line); tid = trajectory['id']
            if tid not in frozen:continue
            if tid in expected:official_errors.append({'trajectory_id':tid,'error':'duplicate official source'})
            if hashlib.sha256(json.dumps(trajectory,sort_keys=True).encode()).hexdigest() != frozen[tid]:
                official_errors.append({'trajectory_id':tid,'error':'official content differs from frozen manifest'})
            prepared = helper.prepare_trajectory_insert(trajectory,trajectories_root_dir=data_root)
            expected[tid] = prepared.fingerprint
    for tid in sorted(set(frozen)-set(expected)):
        official_errors.append({'trajectory_id':tid,'error':'official trajectory missing'})
    snapshots = []
    for domain in ('web','enterprise'):
        domain_expected = {tid:expected.get(tid) for tid in manifest['data'][domain]['trajectory_ids']}
        for policy in ('raw_rag','rag_notes','b3'):
            key=f'{domain}-{policy}'; memory=ROOT/runtime['initial_snapshots'][key]['path']
            snapshots.append({'library':key,**snapshot_source_check(memory,domain_expected,helper.logical_trajectory_fingerprint_from_simplified)})
    valid = not official_errors and all(row['full_text_matches'] for row in snapshots)
    return {'status':'verified' if valid else 'needs_attention', 'full_text_matches':valid,
            'normalizer_sha256':hashlib.sha256(helper_path.read_bytes()).hexdigest(),
            'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'normalization':'existing full textual trajectory fingerprint; screenshot paths excluded only',
            'official_source_errors':official_errors,'snapshots':snapshots,
            'new_model_calls':0,'semantic_generated_memory_certified':False}


def query_evidence(step):
    folder = ROOT / step['reader']
    prompts = jsonl(folder / 'prompt_rows.jsonl')
    answers = jsonl(folder / 'per_question.jsonl')
    ids = {r['query_invocation_id'] for r in prompts}
    calls = unique_attempts(r for r in jsonl(ROOT / step['memory'] / 'model_calls.jsonl')
                            if r.get('query_invocation_id') in ids)
    controller = [r for r in calls if r['channel'] == 'controller']
    embedding = [r for r in calls if r['channel'] == 'embedding']
    result = attempt_costs(controller, 'query_controller')
    if not controller and step['policy'] not in ('raw_rag', 'rag_notes'):
        result['query_controller_input_tokens'] = None
        result['query_controller_output_tokens'] = None
    au = [reader_usage(a) for a in answers]
    timing = load(folder / 'aggregated_metrics.json')['timing']
    question_path = ROOT / step['questions']
    fixed = load(question_path) if question_path.suffix == '.json' else jsonl(question_path)
    result.update(query_reader_calls=len(answers), query_reader_input_tokens=usage(au, 'prompt_tokens'),
                  query_reader_output_tokens=usage(au, 'completion_tokens'),
                  query_reader_unknown_usage_calls=sum(not u for u in au),
                  query_embedding_calls=len(embedding), query_embedding_vectors=usage(embedding, 'input_text_count'),
                  query_embedding_input_tokens=usage(embedding, 'prompt_tokens'),
                  query_embedding_failed_calls=sum(r['status'] != 'success' for r in embedding),
                  query_embedding_unknown_usage_calls=sum(r.get('prompt_tokens') is None for r in embedding),
                  query_wall_s=timing['prompt_build_wall_seconds'] + timing['reader_generation_wall_seconds'],
                  fixed_questions=len(fixed), emitted_answers=len(answers),
                  complete_answers=sum(bool(a.get('reader_answer_complete')) for a in answers),
                  correct=sum(a.get('score_bool') is True for a in answers),
                  pending=sum(a.get('evaluation_status') == 'pending_judge' for a in answers),
                  unscored_incomplete=sum(a.get('evaluation_status') == 'not_scored_incomplete' for a in answers),
                  truncated=sum(bool(a.get('reader_truncated')) for a in answers),
                  service_failures=sum(a.get('reader_status') != 'ok' for a in answers),
                  parse_failures=sum(a.get('reader_status') == 'ok' and not a.get('reader_truncated') and a.get('reader_parse_status') != 'boxed' for a in answers),
                  missing_answers=max(len(fixed) - len(answers), 0))
    result['query_embedding_transport_attempts'] = None
    result['query_llm_tokens'] = total(result[p+'_'+s] for p in ('query_controller', 'query_reader')
                                       for s in ('input_tokens', 'output_tokens'))
    return result, answers


def quality_record(update):
    folder = ROOT / update['marker']
    folder = folder.parent
    review = load(folder / 'derived_quality_review.json')
    trajectory = load(folder / 'update_input.json')['trajectory']
    # RAG has no generated events by design. Do not mark absent AR artifacts
    # as failed quality checks for a different memory architecture.
    if update['policy'] in ('raw_rag', 'rag_notes'):
        review = dict(review, workload=dict(review['workload']))
        review['workload']['derived_rules'] = [rule for rule in review['workload'].get('derived_rules', [])
            if rule['target'] == 'notes' and update['policy'] == 'rag_notes']
    roles = fact_roles(review, trajectory, update['policy'])
    roles['generated_events_applicable'] = update['policy'] not in ('raw_rag', 'rag_notes')
    roles['generated_notes_applicable'] = update['policy'] != 'raw_rag'
    blocks = []
    for event in review['new_events']:
        for number, part in enumerate(event.get('state_transition', '').split(CURRENT)[1:], start=1):
            observations, _ = json.JSONDecoder().raw_decode(part)
            for observation in observations:
                index = observation['state_index']
                source_lines = {line.strip() for line in trajectory['states'][index]['text'].splitlines()}
                lines = [line.strip() for line in observation['current_evidence'].splitlines() if line.strip()]
                blocks.append({'event_id':event['event_id'], 'block_number':number, 'state_index':index,
                    'role':observation['role'], 'lines':len(lines),
                    'lines_not_in_current_source':[line for line in lines if line not in source_lines],
                    'interpretation':'A historical overlay block may be superseded by a later block; retained old text alone is not stale-answer use.'})
    return {'unit': update['id'], 'domain': update['domain'], 'policy': update['policy'],
            'case_id': update['case_id'], 'review_path': str((folder / 'derived_quality_review.json').relative_to(ROOT)),
            'event_and_notes_checks': roles, 'all_versioned_evidence_blocks':blocks,
            'semantic_review_status': 'pending_manual',
            'instruction': 'Read changed current facts, untouched context, pre/post roles, old conclusions, and generated notes. Raw save success alone is insufficient.'}


def update_evidence(step, query_steps):
    folder = (ROOT / step['marker']).parent
    metric = load(folder / 'update_metrics.json')
    calls = unique_attempts(load(folder / 'update_calls.json'))
    controllers = [r for r in calls if r['channel'] == 'controller']
    embeddings = [r for r in calls if r['channel'] == 'embedding']
    if len(controllers) != metric['llm_calls']:
        raise ValueError(f'Attempt count mismatch: {folder}')
    row = {k: step[k] for k in ('id', 'domain', 'policy', 'phase', 'case_id', 'repeat', 'round')}
    row.update(history_trajectories=len(load(folder / 'memory_state/index.json')['inserted_trajectory_ids']),
               update_runner_sha256=metric.get('runner_sha256'),
               raw_update_path=str(folder.relative_to(ROOT)), update_publish_s=metric['update_to_queryable_publish_s'],
               artifact_build_s=metric.get('artifact_build_s'),
               publication_and_reload_s=metric.get('publication_and_reload_s'),
               excluded_setup_s=metric['setup_load_and_seed_s_excluded'],
               excluded_setup_scope=('clone + initial load + runtime/cache setup + preservation baseline copies'
                                     if step['policy'] in ('raw_rag', 'rag_notes') else
                                     'runtime/cache setup only; clone and initial load occur earlier and are unmeasured'),
               full_process_wall_s=None,
               update_timing_scope='artifact build + index/persistence + reload verification; excludes clone/initial load and post-publication reporting; NOT whole process wall',
               reextracted_events=metric['reextracted_event_outputs'], regenerated_notes=metric['regenerated_notes'],
               update_embedding_calls=len(embeddings), update_embedding_vectors=usage(embeddings, 'input_text_count'),
               update_embedding_input_tokens=usage(embeddings, 'prompt_tokens'),
               update_embedding_failed_calls=sum(r['status'] != 'success' for r in embeddings),
               update_embedding_unknown_usage_calls=sum(r.get('prompt_tokens') is None for r in embeddings),
               published_event_chars=metric.get('published_event_chars'),
               published_note_chars=metric.get('published_note_chars'),
               current_evidence_blocks=metric.get('current_evidence_blocks'),
               semantic_quality='pending_manual_generated_event_and_note_review')
    row.update(attempt_costs(controllers, 'update_llm'))
    row['update_fallback_groups'] = sum(r.get('channel') == 'event_delta' and r.get('status') == 'fallback' for r in calls)
    row['exact_request_cache_hits'] = sum(r.get('channel') == 'update_request_cache' and r.get('status') == 'hit' for r in calls)
    row['update_embedding_transport_attempts'] = None
    row['embedding_call_scope'] = 'logged embedding operations/returned vectors; SDK transport retries not individually observable; total retry work unknown'
    pools = folder/'memory_state/pools'
    event_path = pools/'event_pool.jsonl'
    stored_events = jsonl(event_path) if event_path.exists() else []
    eligible_events = [event for event in stored_events if event.get('validity_status') != 'invalidated_source_change']
    row.update(stored_event_count=len(stored_events), query_eligible_event_count=len(eligible_events),
               stored_event_chars=sum(len(event.get('description', '')) for event in stored_events),
               query_eligible_event_chars=sum(len(event.get('description', '')) for event in eligible_events))
    row.update(target_event_size(stored_events, metric['trajectory_id'], step['policy']))
    row['explicit_note_json_repair_calls'] = sum(any(
        message.get('role') == 'system' and isinstance(message.get('content'), str) and
        message['content'].startswith('Rewrite the draft into valid JSON only.')
        for message in call.get('messages', [])) for call in controllers)
    row['update_llm_tokens'] = total([row['update_llm_input_tokens'], row['update_llm_output_tokens']])
    question_rows, queries = [], []
    for query in query_steps:
        if not (ROOT / query['marker']).exists():
            continue
        q, answers = query_evidence(query)
        queries.append((query, q))
        for answer in answers:
            question_rows.append({
                'update_unit': step['id'], 'query_unit': query['id'], 'query_kind': query['query_kind'],
                'domain': step['domain'], 'policy': step['policy'], 'case_id': step['case_id'],
                'question_id': answer['question_id'], 'question': answer.get('question_text'),
                'answer': answer.get('response_parsed_boxed'), 'gold': answer.get('answer_gold'),
                'score': answer.get('score'), 'score_status': answer.get('evaluation_status'),
                'complete': answer.get('reader_answer_complete'), 'truncated': answer.get('reader_truncated'),
                'service_status': answer.get('reader_status'), 'parse_status': answer.get('reader_parse_status'),
                'scoring_rule': answer.get('eval_function'),
                'raw_path': str((Path(query['reader']) / 'per_question.jsonl'))})
    row['expected_query_batches'] = len(query_steps)
    row['completed_query_batches'] = len(queries)
    for key in dict.fromkeys(k for _, q in queries for k in q):
        row[key] = total(q.get(key) for _, q in queries)
    if len(queries) != len(query_steps):
        row['query_llm_tokens'] = None
        row['query_wall_s'] = None
    row['update_plus_query_llm_tokens'] = total([row['update_llm_tokens'], row.get('query_llm_tokens')])
    row['update_plus_query_wall_s'] = total([row['update_publish_s'], row.get('query_wall_s')])
    for name in ('revision', 'normal'):
        chosen = [q for s, q in queries if ('normal' in s['query_kind']) == (name == 'normal')]
        for key in ('fixed_questions', 'correct', 'pending', 'complete_answers', 'truncated', 'service_failures', 'parse_failures'):
            row[name+'_'+key] = sum(q[key] for q in chosen)
    return row, question_rows, queries


SUM_FIELDS = ['update_publish_s', 'update_llm_calls', 'update_llm_input_tokens', 'update_llm_output_tokens',
              'artifact_build_s', 'publication_and_reload_s', 'update_fallback_groups', 'exact_request_cache_hits',
              'update_llm_tokens', 'update_llm_failed_calls', 'update_llm_unknown_usage_calls',
              'reextracted_events', 'regenerated_notes', 'explicit_note_json_repair_calls', 'update_embedding_calls', 'update_embedding_vectors',
              'update_embedding_input_tokens', 'update_embedding_failed_calls', 'update_embedding_unknown_usage_calls',
              'query_controller_calls', 'query_controller_input_tokens', 'query_controller_output_tokens',
              'query_controller_failed_calls', 'query_controller_unknown_usage_calls',
              'query_reader_calls', 'query_reader_input_tokens', 'query_reader_output_tokens',
              'query_reader_unknown_usage_calls', 'query_embedding_calls', 'query_embedding_vectors',
              'query_embedding_input_tokens', 'query_embedding_failed_calls', 'query_embedding_unknown_usage_calls', 'query_wall_s',
              'update_plus_query_llm_tokens', 'update_plus_query_wall_s', 'complete_answers', 'fixed_questions',
              'correct', 'pending', 'unscored_incomplete', 'truncated', 'service_failures', 'parse_failures', 'missing_answers',
              'revision_fixed_questions', 'revision_correct', 'normal_fixed_questions', 'normal_correct']


def aggregate(rows, policies, expected_cases, *, case_definitions=None, domain=None):
    result = []
    for policy in policies:
        selected = [r for r in rows if r['policy'] == policy and (domain is None or r['domain'] == domain)]
        row = {'policy': policy, 'expected_revision_cases': expected_cases, 'measured_revision_cases': len(selected),
               'runtime_manifest':'runs/focused-maintenance-v4/full-small-recovery-v1/runtime_manifest.json',
               'histories': f'{domain}100' if domain else 'web100 + enterprise100',
               'independent_revision_trajectories': (len({c['trajectory_id'] for c in case_definitions})
                                                    if case_definitions is not None else 4 if expected_cases == 8 else 2),
               'exposure': 'fixed exposed development trajectories; full distractor history, not independent confirmation',
               'scope': 'update + fixed post-update queries; initial separately referenced',
               'update_timing_scope':'artifact build through save/reload verification; setup/clone/initial load excluded; setup submetrics differ by architecture and are not a full process wall',
               'embedding_call_scope':'logged operations/returned vectors; individual SDK transport retry attempts unknown',
               'update_embedding_transport_attempts':None, 'query_embedding_transport_attempts':None,
               'quality_equivalence': 'not_established', 'raw_paths': json.dumps([r['raw_update_path'] for r in selected])}
        for field in SUM_FIELDS:
            row[field] = total(r.get(field) for r in selected) if selected else None
        expected_ids = {c['id'] for c in case_definitions} if case_definitions is not None else None
        ids_match = expected_ids is None or {r['case_id'] for r in selected} == expected_ids
        row['complete_fixed_workload'] = len(selected) == expected_cases and ids_match and all(r['expected_query_batches'] == r['completed_query_batches'] for r in selected)
        if domain is not None:row['domain'] = domain
        if expected_ids is not None:row['expected_case_ids'] = json.dumps(sorted(expected_ids))
        result.append(row)
    return result


def continuous_figure(path, rows, *, title='Full-history fixed revisions: measured cumulative maintenance cost', policies=None,
                      columns=None, subtitle='Initial construction excluded; 2 fixed diagnostic queries/update; no extrapolation'):
    policies = POLICIES if policies is None else policies
    columns = columns or [('cumulative_update_query_llm_tokens', 'cumulative LLM tokens'),
                          ('cumulative_update_query_wall_s', 'cumulative seconds')]
    colors = dict(zip(POLICIES, ['#64748b','#9333ea','#2563eb','#059669','#d97706','#dc2626']))
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1060" height="640">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<g font-family="sans-serif" font-size="12">',
           f'<text x="25" y="24" font-size="17">{escape(title)}</text>',
           f'<text x="25" y="44">{escape(subtitle)}</text>']
    for di, domain in enumerate(('web', 'enterprise')):
        for fi, (field, label) in enumerate(columns):
            x, y, w, h = 85 + fi*520, 85 + di*265, 390, 175
            data = [r for r in rows if r['domain'] == domain and r.get(field) is not None and r['policy'] in policies]
            maximum = max([r[field] for r in data] + [1])
            for fraction in (0, .5, 1):
                yy = y + h*(1-fraction)
                svg.append(f'<line x1="{x}" y1="{yy}" x2="{x+w}" y2="{yy}" stroke="#ddd"/>')
                svg.append(f'<text x="{x-8}" y="{yy+4}" text-anchor="end">{maximum*fraction:,.0f}</text>')
            for policy in policies:
                rr = sorted((r for r in data if r['policy'] == policy), key=lambda r:r['round'])
                points = ' '.join(f'{x+(r["round"]-1)*w/2:.1f},{y+h*(1-r[field]/maximum):.1f}' for r in rr)
                if rr:
                    svg.append(f'<polyline points="{points}" fill="none" stroke="{colors[policy]}" stroke-width="2"/>')
                    for point in points.split():
                        cx,cy=point.split(',')
                        svg.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="{colors[policy]}"/>')
            for round_number in (1,2,3):
                svg.append(f'<text x="{x+(round_number-1)*w/2}" y="{y+h+18}">{round_number}</text>')
            svg.append(f'<text x="{x}" y="{y-12}">{domain}: {escape(label)}</text>')
    for i, policy in enumerate(policies):
        svg.append(f'<text x="{25+i*172}" y="625" fill="{colors[policy]}">{policy}</text>')
    svg.append('</g></svg>')
    Path(path).write_text('\n'.join(svg)+'\n')


def evidence_figure(path, rows, *, title='Full-history sequential revisions: published event size', policies=None):
    policies = ['b3', 'source_coalesced', 'source_only', 'source_overlay'] if policies is None else policies
    continuous_figure(path, rows, title=title, policies=policies,
        columns=[('target_query_eligible_event_chars', 'target query-eligible event characters'),
                 ('target_current_evidence_blocks', 'target current-evidence blocks')],
        subtitle='Snapshot after each revision, not cumulative cost; source/Notes excluded; retired events excluded; x = revision round')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=DEFAULT)
    a = p.parse_args()
    out = ROOT / a.output
    out.mkdir(parents=True, exist_ok=False)
    plan = load(PLAN); steps = plan['steps']
    manifest = load(ROOT/'manifests/focused-maintenance-v4/full-small-recovery-v1/data_manifest.json')
    case_definitions = manifest['cases']
    updates = [s for s in steps if s['kind'] == 'update']
    rows, questions, checks, missing, by_unit, query_by_unit = [], [], [], [], {}, {}
    for step in updates:
        if not (ROOT / step['marker']).exists():
            missing.append(step['id']); continue
        children = [q for q in steps if q['kind'] == 'reader' and step['id'] in q['depends_on']]
        row, answers, queries = update_evidence(step, children)
        rows.append(row); questions.extend(answers); checks.append(quality_record(step))
        by_unit[step['id']] = row; query_by_unit[step['id']] = queries
    table(out/'all_update_units.csv', rows); table(out/'per_question.csv', questions)
    dump(out/'generated_memory_quality.json', checks)
    main_rows = [r for r in rows if r['phase'] == 'main']
    public = aggregate(main_rows, CORE, 8, case_definitions=case_definitions)
    for result in public:
        units={r['id'] for r in main_rows if r['policy']==result['policy']}
        related=[q for q in questions if q['update_unit'] in units]
        result['unique_question_ids']=len({q['question_id'] for q in related})
        result['unique_normal_question_ids']=len({q['question_id'] for q in related if 'normal' in q['query_kind']})
        result['unique_revision_question_ids']=len({q['question_id'] for q in related if 'normal' not in q['query_kind']})
    table(out/'public_main.csv', public)
    by_domain = []
    for domain in ('web','enterprise'):
        cases = [c for c in case_definitions if c['domain']==domain]
        by_domain.extend(aggregate(main_rows,CORE,len(cases),case_definitions=cases,domain=domain))
    table(out/'public_main_by_domain.csv',by_domain)
    by_kind = []
    for kind in sorted({c['kind'] for c in case_definitions}):
        cases = [c for c in case_definitions if c['kind']==kind]
        case_ids = {c['id'] for c in cases}
        for row in aggregate([r for r in main_rows if r['case_id'] in case_ids],CORE,len(cases),case_definitions=cases):
            row['revision_kind'] = kind
            row['scope'] += '; per-kind subset, no extra samples; normal questions repeat across snapshots'
            by_kind.append(row)
    table(out/'maintenance_by_kind.csv',by_kind)
    core_cases = {'web-title', 'enterprise-count'}
    ablation = aggregate([r for r in rows if r['phase'] in ('main','ablation') and r['case_id'] in core_cases], POLICIES, 2,
                         case_definitions=[c for c in case_definitions if c['id'] in core_cases])
    table(out/'core_ablation.csv', ablation)
    paired = []
    for domain, case in [('web','web-title'),('enterprise','enterprise-count')]:
        for repetition in (1,2,3):
            prefix = 'main' if repetition == 1 else f'repeat{repetition}'
            b = by_unit.get(f'{prefix}-{case}-b3'); o = by_unit.get(f'{prefix}-{case}-source_coalesced')
            if b and o:
                paired.append({'domain':domain, 'repeat':repetition,
                    'b3_publish_s':b['update_publish_s'], 'ours_publish_s':o['update_publish_s'],
                    'paired_publish_difference_s':o['update_publish_s']-b['update_publish_s'],
                    'b3_tokens':b['update_llm_tokens'], 'ours_tokens':o['update_llm_tokens'],
                    'paired_token_difference':None if b['update_llm_tokens'] is None or o['update_llm_tokens'] is None else o['update_llm_tokens']-b['update_llm_tokens'],
                    'b3_raw':b['raw_update_path'], 'ours_raw':o['raw_update_path']})
    table(out/'paired_repeats.csv', paired)
    variation=[]
    for domain in ('web','enterprise'):
        selected=[r for r in paired if r['domain']==domain]
        values=[r['paired_publish_difference_s'] for r in selected]
        if values:
            variation.append({'domain':domain,'pairs':len(values),'mean_paired_difference_s':statistics.mean(values),
                              'sd_paired_difference_s':statistics.stdev(values) if len(values)>1 else None,
                              'min_paired_difference_s':min(values),'max_paired_difference_s':max(values)})
    table(out/'paired_variation.csv',variation)
    continuous=[]
    for domain, case in [('web','web-title'),('enterprise','enterprise-count')]:
        for policy in POLICIES:
            accumulated_tokens=0;accumulated_wall=0
            for n in (1,2,3):
                uid=f'main-{case}-{policy}' if n==1 else f'sequence-r{n}-{case}-{policy}'
                row=by_unit.get(uid)
                queries=[q for s,q in query_by_unit.get(uid,[]) if 'normal' not in s['query_kind']]
                if not row or len(queries)!=1:
                    break
                q=queries[0]
                accumulated_tokens=total([accumulated_tokens,row['update_llm_tokens'],q['query_llm_tokens']])
                accumulated_wall=total([accumulated_wall,row['update_publish_s'],q['query_wall_s']])
                continuous.append({'domain':domain,'policy':policy,'round':n,
                    'cumulative_update_query_llm_tokens':accumulated_tokens,
                    'cumulative_update_query_wall_s':accumulated_wall,
                    'published_event_chars':row['published_event_chars'],'published_note_chars':row['published_note_chars'],
                    'stored_event_chars':row['stored_event_chars'],'query_eligible_event_chars':row['query_eligible_event_chars'],
                    'target_stored_event_chars':row['target_stored_event_chars'],
                    'target_query_eligible_event_chars':row['target_query_eligible_event_chars'],
                    'target_current_evidence_blocks':row['target_current_evidence_blocks'],
                    'current_evidence_blocks':row['current_evidence_blocks'],'correct':q['correct'],
                    'fixed_questions':q['fixed_questions'],'raw_update_path':row['raw_update_path'],
                    'round1_reused_from_main':n==1})
    table(out/'continuous_cost.csv',continuous)
    continuous_figure(out/'continuous_cost.svg',continuous)
    evidence_figure(out/'evidence_size.svg',continuous)
    initial=[]
    initial_requests=[]
    for step in steps:
        if step['kind']!='expansion':continue
        folder=(ROOT/step['marker']).parent
        if not (folder/'expansion_origin.json').exists():continue
        origin=load(folder/'expansion_origin.json')
        metrics=jsonl(folder/'expansion_metrics.jsonl') if (folder/'expansion_metrics.jsonl').exists() else []
        failures=sorted(str(p.relative_to(ROOT)) for p in folder.glob('failure-*.json'))
        initial.append({'domain':step['domain'],'initial_library':step['id'],
            'historical_source':origin['source'],'historical_trajectory_count':len(origin['reused_ids']),
            'new_trajectories_measured':len(metrics),'expansion_publish_stage_sum_s':sum(r['publish_wall_s'] for r in metrics),
            'expansion_llm_calls':sum(r['llm_calls'] for r in metrics),
            'expansion_llm_tokens_known':sum(r['llm_tokens_known'] for r in metrics),
            'expansion_unknown_usage_calls':sum(r['unknown_usage_calls'] for r in metrics),
            'failed_or_interrupted_trajectory_records':len(failures), 'failure_paths':json.dumps(failures),
            'expansion_cost_completeness':'completed trajectories only; failure ledger costs need separate accounting' if failures else 'completed trajectory metrics; verify full-ID marker separately',
            'historical_cost_scope':'reference, not a new cold build; matched preparation separately recorded',
            'lifecycle_total_tokens':None,'lifecycle_status':'not summed without a complete compatible historical cost reference',
            'raw_path':str(folder.relative_to(ROOT))})
        historical=Path(origin['source'])/'model_calls.jsonl'
        initial_requests.append({'domain':step['domain'],'initial_library':step['id'],
            'stage':'historical_own_partitions_reference', 'raw_path':str(historical),
            **initial_ledger_summary(jsonl(historical))})
        expanded=folder/'memory_state/model_calls.jsonl'
        historical_ids={r.get('record_id') or hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()
                        for r in jsonl(historical)}
        new_records=[r for r in jsonl(expanded) if (r.get('record_id') or hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()) not in historical_ids]
        initial_requests.append({'domain':step['domain'],'initial_library':step['id'],
            'stage':'expansion_new_attempts_including_failed_attempts', 'raw_path':str(expanded.relative_to(ROOT)),
            **initial_ledger_summary(new_records)})
    for step in steps:
        if step['kind'] != 'preparation' or not (ROOT/step['marker']).exists():
            continue
        folder=(ROOT/step['marker']).parent
        calls_path=folder/'preparation_calls.json'
        metric=load(ROOT/step['marker'])
        initial_requests.append({'domain':step['domain'],'initial_library':step['id'],
            'stage':'matched_target_preparation_not_whole_library', 'raw_path':str(calls_path.relative_to(ROOT)),
            'preparation_wall_s':metric['elapsed_s_including_no_change_check'],
            **initial_ledger_summary(load(calls_path))})
    table(out/'initial_expansion.csv',initial)
    table(out/'initial_request_costs.csv',initial_requests)
    initial_queries=[]
    for step in steps:
        if step.get('query_kind') != 'initial_normal_shared_reference' or not (ROOT/step['marker']).exists():
            continue
        q, _ = query_evidence(step)
        initial_queries.append({'domain':step['domain'],'architecture':step['policy'],
                                'shared_by':'b3/source_coalesced/source_only/source_overlay' if step['policy']=='b3' else step['policy'],
                                'reader_path':step['reader'], **q})
    table(out/'initial_normal_qa.csv', initial_queries)
    source_contents=initial_source_evidence()
    dump(out/'initial_source_contents.json',source_contents)
    missing_queries=[s['id'] for s in steps if s['kind']=='reader' and not (ROOT/s['marker']).exists()]
    status={'scope':'official full Small histories; fixed local maintenance; text-only/adapted',
        'reporter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'accounting_helper_sha256':hashlib.sha256((ROOT/'tools/focused_evidence.py').read_bytes()).hexdigest(),
        'expected_update_units':len(updates),'observed_update_units':len(rows),'missing_updates':missing,
        'missing_query_units':missing_queries,'generated_memory_reviews':len(checks),
        'semantic_quality_status':'manual review required; structural/fact checks do not establish quality equivalence',
        'research_complete':False,'measurement_matrix_complete':not missing and not missing_queries,
        'initial_costs':'historical reference + measured expansion/preparation, never fresh cold measurements'}
    status['initial_source_contents_status']=source_contents['status']
    status['initial_source_full_text_matches']=source_contents['full_text_matches']
    dump(out/'report.json',status)
    lines=['# Full-history fixed maintenance results','',
        'Full histories are 100 trajectories/domain. Eight fixed state/workflow cases on four exposed trajectories; '
        'repeats and sequential rounds are not independent cases. Initial construction is separate. All Reader, '
        'retrieval-controller, embedding, failure and unknown-usage costs are retained.','',
        '| Method | Cases | Update LLM tokens | Update+query LLM tokens | Revision QA | Normal QA observations |',
        '|---|---:|---:|---:|---:|---:|']
    for r in public:
        lines.append(f"| {r['policy']} | {r['measured_revision_cases']}/8 | {r['update_llm_tokens']} | {r['update_plus_query_llm_tokens']} | {r['revision_correct']}/{r.get('revision_fixed_questions')} | {r['normal_correct']}/{r.get('normal_fixed_questions')} |")
    lines+=['','Normal questions repeat across changed snapshots; report unique questions separately. '
        'Generated event/notes semantic review remains pending until annotated. A small QA difference is not proof of equivalence or systematic loss.',
        '',f"Missing update units: {len(missing)}; missing query units: {len(missing_queries)}."]
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(status))


if __name__=='__main__':main()
