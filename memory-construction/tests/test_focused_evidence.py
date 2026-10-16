import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('focused_evidence', Path(__file__).resolve().parents[1]/'tools/focused_evidence.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_attempt_dedup_preserves_retries_and_unknown():
    a = dict(record_id='a', query_invocation_id='q', status='success', prompt_tokens=4, completion_tokens=2)
    b = dict(record_id='b', query_invocation_id='q', status='failed')
    r = m.attempt_costs([a, a, b], 'query_controller')
    assert r['query_controller_calls'] == 2
    assert r['query_controller_input_tokens'] is None
    assert r['query_controller_failed_calls'] == 1


def test_zero_requests_not_missing_usage():
    assert m.attempt_costs([], 'update_llm')['update_llm_input_tokens'] == 0


def test_unchanged_prose_not_required_in_current_block_but_stale_detected():
    import json
    event = {'event_id':'event', 'pre_state_index':0, 'post_state_index':1,
             'overview':'Name remains Alice.', 'state_transition':'Prior-source interpretation: count 101' + m.CURRENT +
             json.dumps([{'state_index':1,'role':'post-state','current_evidence':'count 103\nobsolete row'}])}
    review = {'workload': {'source_edits':[{'state_index':1,'field':'text','old':'count 101','new':'count 103'}],
                          'derived_rules':[{'target':'event','required':['103','Alice']}]},
              'new_events':[event], 'old_notes':[], 'new_notes':[], 'checks':{'old_failed': True}}
    result=m.fact_roles(review, {'states':[{'text':'count 101'},{'text':'count 103'}]}, 'source_coalesced')
    assert result['events'][0]['pattern_pass'] is True
    assert result['events'][0]['current_source_line_checks'][0]['changed_lines_present'] is True
    assert result['events'][0]['noncurrent_source_lines_labeled_current']
    assert result['semantic_quality_pass'] is None
