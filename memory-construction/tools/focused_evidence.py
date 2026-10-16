"""Offline, stage-specific accounting and fact-role checks for saved runs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CURRENT = '\nCURRENT STATE OBSERVATIONS (authoritative for the listed fields; pre-state and post-state are independent, not a claim that values persist):\n'


def jsonl(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def unique_attempts(records):
    """Deduplicate copied records, NOT logical queries (which may retry)."""
    seen, result = set(), []
    for row in records:
        key = row.get('record_id') or hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
        if key not in seen:
            result.append(row)
            seen.add(key)
    return result


def usage(records, field):
    values = [row.get(field) for row in records]
    return None if any(value is None for value in values) else sum(values)


def attempt_costs(records, prefix):
    records = unique_attempts(records)
    return {
        prefix+'_calls': len(records),
        prefix+'_input_tokens': usage(records, 'prompt_tokens'),
        prefix+'_output_tokens': usage(records, 'completion_tokens'),
        prefix+'_unknown_usage_calls': sum(r.get('prompt_tokens') is None or r.get('completion_tokens') is None for r in records),
        prefix+'_failed_calls': sum(r.get('status') not in ('success',) for r in records),
    }


def costs(update_dir, reader_dir):
    update_dir, reader_dir = Path(update_dir), Path(reader_dir)
    update = json.loads((update_dir/'update_metrics.json').read_text())
    queries = jsonl(reader_dir/'prompt_rows.jsonl')
    ids = {row['query_invocation_id'] for row in queries}
    calls = unique_attempts(r for r in jsonl(update_dir/'memory_state/model_calls.jsonl')
                            if r.get('query_invocation_id') in ids)
    controller = [r for r in calls if r.get('channel') == 'controller']
    embedding = [r for r in calls if r.get('channel') == 'embedding']
    updates = json.loads((update_dir/'update_calls.json').read_text())
    updates = [r for r in updates if r.get('channel') == 'controller']
    result = attempt_costs(updates, 'update_llm')
    result.update(attempt_costs(controller, 'query_controller'))
    answers = jsonl(reader_dir/'per_question.jsonl')
    answer_usage = [r.get('usage') or {} for r in answers]
    result.update({
        'query_reader_input_tokens': usage(answer_usage, 'prompt_tokens'),
        'query_reader_output_tokens': usage(answer_usage, 'completion_tokens'),
        'query_reader_unknown_usage_calls': sum(not r or r.get('prompt_tokens') is None or r.get('completion_tokens') is None for r in answer_usage),
        'query_embedding_calls': len(embedding),
        'query_embedding_vectors': usage(embedding, 'input_text_count'),
        'query_embedding_input_tokens': usage(embedding, 'prompt_tokens'),
        'query_embedding_failed_calls': sum(r.get('status') != 'success' for r in embedding),
        'query_embedding_unknown_usage_calls': sum(r.get('prompt_tokens') is None for r in embedding),
        'query_invocation_ids': sorted(ids),
        'query_controller_record_ids': [r.get('record_id') for r in controller],
    })
    # With no controller trace, a positive logged update count is unknown,
    # not proof that the update was free.
    if len(updates) != update['llm_calls']:
        raise ValueError(f'Update trace/count mismatch: {update_dir}')
    saved_config = json.loads((update_dir/'memory_state/memory_config.json').read_text())
    if not controller and saved_config['memory_type'] != 'rag':
        result['query_controller_input_tokens'] = None
        result['query_controller_output_tokens'] = None
    components = [result[p+'_'+f] for p in ('update_llm', 'query_controller', 'query_reader')
                  for f in ('input_tokens', 'output_tokens')]
    result['update_plus_query_llm_tokens'] = None if any(x is None for x in components) else sum(components)
    result['update_plus_query_llm_tokens_known'] = sum(x for x in components if x is not None)
    timing = json.loads((reader_dir/'aggregated_metrics.json').read_text())['timing']
    result['update_query_stage_wall_s'] = (update['update_to_queryable_publish_s'] +
        timing['prompt_build_wall_seconds'] + timing['reader_generation_wall_seconds'])
    result['wall_scope'] = 'sequential update publish + prompt-build + Reader; nested retrieval not added twice; initial/setup excluded'
    return result


def fact_roles(review, trajectory, policy):
    """Necessary source/lexical checks, never a semantic certification.

    New values must appear in current evidence. Unchanged assertions may stay
    in preserved event prose. We retain the original gate and explicitly mark
    natural-language state attribution/stale use as pending manual review.
    """
    work = review['workload']
    events = {e['event_id']: e for e in review['new_events']}
    edits = work.get('source_edits', [])
    old = '\n'.join(e.get('old', '') for e in edits)
    new = '\n'.join(e.get('new', '') for e in edits)
    states = {s.get('state_index', i): s for i, s in enumerate(trajectory['states'])}
    rows = []
    for rule in work.get('derived_rules', []):
        event = events.get(rule['target'], {})
        text = '\n'.join(event.get(k, '') for k in ('overview', 'state_transition'))
        if rule['target'] == 'notes':
            text = '\n'.join(n.get('note_text', '') for n in review['new_notes'])
        current = text.split(CURRENT, 1)[1] if CURRENT in text else text
        changed, unchanged = {}, {}
        for pattern in rule.get('required', []):
            is_changed = bool(re.search(pattern, new, re.I | re.S)) and not re.search(pattern, old, re.I | re.S)
            target = changed if is_changed else unchanged
            target[pattern] = bool(re.search(pattern, current if is_changed else text, re.I | re.S))
        exact_checks, stale_lines, role_errors = [], [], []
        if CURRENT in text:
            observations = json.JSONDecoder().raw_decode(current)[0]
            for obs in observations:
                idx = obs['state_index']
                expected_idx = event.get('pre_state_index') if obs['role'] == 'pre-state' else event.get('post_state_index')
                if idx != expected_idx:
                    role_errors.append({'state': idx, 'role': obs['role'], 'expected_state': expected_idx})
                source = {line.strip() for line in states[idx]['text'].splitlines()}
                lines = {line.strip() for line in obs['current_evidence'].splitlines() if line.strip()}
                stale_lines.extend({'state': idx, 'line': line} for line in lines if line not in source)
                for edit in edits:
                    if edit['state_index'] == idx and edit['field'] == 'text':
                        required = {line.strip() for line in edit['new'].splitlines() if line.strip()}
                        exact_checks.append({'state': idx, 'role': obs['role'], 'changed_lines_present': required <= lines})
        retired = event.get('validity_status') == 'invalidated_source_change'
        rows.append({'target': rule['target'], 'retired_event': retired,
            'changed_pattern_hits': changed, 'unchanged_full_event_pattern_hits': unchanged,
            'current_source_line_checks': exact_checks, 'noncurrent_source_lines_labeled_current': stale_lines,
            'state_role_errors': role_errors,
            'pattern_pass': None if retired else all(changed.values()) and all(unchanged.values()),
            'semantic_state_attribution_and_stale_use': 'not_applicable_retired' if retired else 'pending',
        })
    return {'version': 'fact-roles-v1', 'policy': policy,
        'legacy_checks_preserved': review['checks'], 'events': rows,
        'notes_preserved_exactly': review['old_notes'] == review['new_notes'],
        'notes_semantic_review': 'pending', 'semantic_quality_pass': None,
        'scope': 'offline diagnostics; no gate relaxation or semantic equivalence claim; unchanged facts checked over full retained event'}
