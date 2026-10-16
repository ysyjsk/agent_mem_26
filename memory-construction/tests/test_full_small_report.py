import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
spec = importlib.util.spec_from_file_location('full_small_report', ROOT/'tools/report_full_small_formal.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def test_legacy_failed_reader_zero_placeholders_are_unknown():
    answer = {'reader_status':'service_failure','usage':{'prompt_tokens':0,'completion_tokens':0}}
    assert report.reader_usage(answer) == {}
    assert report.total([10,None]) is None
    assert report.reader_usage({'reader_status':'ok','usage':{'prompt_tokens':5,'completion_tokens':2}})['prompt_tokens'] == 5


def test_target_event_size_excludes_retired_and_other_trajectory_events():
    events=[{'trajectory_id':'a','description':'123','state_transition':report.CURRENT+'[]'},
            {'trajectory_id':'a','description':'12345','state_transition':report.CURRENT+'[]','validity_status':'invalidated_source_change'},
            {'trajectory_id':'b','description':'1234567','state_transition':report.CURRENT+'[]'}]
    assert report.target_event_size(events,'a','source_only') == {
        'target_stored_event_chars':8,'target_query_eligible_event_chars':3,'target_current_evidence_blocks':1}
    assert all(v is None for v in report.target_event_size([], 'a', 'raw_rag').values())


def test_same_ids_do_not_hide_truncated_saved_source(tmp_path):
    import json
    (tmp_path/'trajectories/a').mkdir(parents=True)
    (tmp_path/'index.json').write_text(json.dumps({'inserted_trajectory_ids':['a']}))
    file=tmp_path/'trajectories/a/trajectory.json'
    file.write_text(json.dumps({'states':[{'text':'prefix'}]}))
    fingerprint=lambda trajectory:'|'.join(state['text'] for state in trajectory['states'])
    result=report.snapshot_source_check(tmp_path,{'a':'prefix|required final state'},fingerprint)
    assert result['exact_id_set_matches']
    assert not result['full_text_matches']
    assert result['mismatched_trajectory_ids']==['a']
    file.write_text(json.dumps({'states':[{'text':'prefix'},{'text':'required final state'}]}))
    assert report.snapshot_source_check(tmp_path,{'a':'prefix|required final state'},fingerprint)['full_text_matches']


def test_missing_runtime_does_not_certify_initial_source_content(tmp_path,monkeypatch):
    monkeypatch.setattr(report,'ROOT',tmp_path)
    result=report.initial_source_evidence()
    assert result['status']=='pending_runtime_freeze'
    assert not result['full_text_matches']


def test_disaggregated_workloads_keep_declared_cases_and_trajectory_count():
    cases=[{'id':'state-a','trajectory_id':'a'}, {'id':'workflow-a','trajectory_id':'a'}]
    row={'policy':'b3','domain':'web','case_id':'state-a','raw_update_path':'p',
         'expected_query_batches':2,'completed_query_batches':2,'update_llm_tokens':10}
    missing=report.aggregate([row,row],['b3'],2,case_definitions=cases,domain='web')[0]
    assert not missing['complete_fixed_workload']  # duplicates cannot replace the workflow case
    complete=report.aggregate([row,dict(row,case_id='workflow-a',update_llm_tokens=20)],
                              ['b3'],2,case_definitions=cases,domain='web')[0]
    assert complete['complete_fixed_workload']
    assert complete['independent_revision_trajectories']==1
    assert complete['histories']=='web100'
    assert complete['update_llm_tokens']==30


def test_evidence_figure_is_labeled_snapshot_size_not_cumulative_cost(tmp_path):
    import xml.etree.ElementTree as ET
    path=tmp_path/'evidence.svg'
    report.evidence_figure(path,[{'domain':'web','policy':'source_coalesced','round':1,
                                'target_query_eligible_event_chars':500,'target_current_evidence_blocks':2}],
                           title='Evidence & size')
    tree=ET.parse(path)
    text=' '.join(tree.getroot().itertext())
    assert 'Evidence & size' in text
    assert 'Snapshot after each revision' in text
    assert 'cumulative LLM tokens' not in text
    assert len(tree.findall('.//{http://www.w3.org/2000/svg}circle')) == 2


def test_real_query_trace_includes_controller_without_inherited_history():
    update='runs/focused-maintenance-v4/formal/web-update/literal_revision-source_coalesced'
    reader='runs/focused-maintenance-v4/repair-20261016/pair-v1/web-source_coalesced'
    if not (ROOT/reader).exists():
        import pytest
        pytest.skip('Saved development evidence not installed')
    result,answers=report.query_evidence({'reader':reader,'memory':update+'/memory_state',
        'policy':'source_coalesced','questions':'runs/focused-maintenance-v4/formal/query-data/web/questions.jsonl'})
    assert result['query_llm_tokens'] == 25715
    assert result['query_controller_calls'] > 0
    assert result['query_reader_calls'] == len(answers) == 2


def test_initial_ledger_excludes_queries_and_keeps_failed_attempt_unknown():
    records=[{'record_id':'a','channel':'controller','status':'success','prompt_tokens':8,'completion_tokens':2},
             {'record_id':'b','channel':'controller','status':'failed'},
             {'record_id':'q','channel':'controller','status':'success','prompt_tokens':100,'completion_tokens':10,'query_invocation_id':'q1'}]
    result=report.initial_ledger_summary(records+[records[0]])
    assert result['initial_llm_calls']==2
    assert result['initial_llm_tokens'] is None
    assert result['initial_llm_failed_calls']==1


def test_saved_update_reports_publication_boundary_without_inventing_total_wall():
    import pytest
    folder='runs/focused-maintenance-v4/formal/web-update/literal_revision-source_coalesced'
    if not (ROOT/folder/'update_metrics.json').exists():
        pytest.skip('Saved development evidence not installed')
    step={'id':'saved-web-coalesced','domain':'web','policy':'source_coalesced',
          'phase':'development','case_id':'web-title','repeat':1,'round':1,
          'marker':folder+'/update_metrics.json'}
    row,_,_=report.update_evidence(step,[])
    assert row['full_process_wall_s'] is None
    assert 'unmeasured' in row['excluded_setup_scope']
    assert row['artifact_build_s'] + row['publication_and_reload_s'] == pytest.approx(row['update_publish_s'],abs=0.01)
    assert row['update_fallback_groups'] == 0
    assert row['exact_request_cache_hits'] > 0


def test_pending_judge_and_failure_categories_are_separate(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(report,'ROOT',tmp_path)
    reader=tmp_path/'reader';memory=tmp_path/'memory'
    reader.mkdir();memory.mkdir()
    answers=[
        {'question_id':'a','reader_status':'ok','reader_truncated':True,'reader_parse_status':'parse_failure','evaluation_status':'not_scored_incomplete'},
        {'question_id':'b','reader_status':'service_failure','reader_truncated':False,'reader_parse_status':'empty','evaluation_status':'not_scored_incomplete'},
        {'question_id':'c','reader_status':'ok','reader_truncated':False,'reader_parse_status':'parse_failure','evaluation_status':'not_scored_incomplete'},
        {'question_id':'d','reader_status':'ok','reader_truncated':False,'reader_parse_status':'boxed','reader_answer_complete':True,'evaluation_status':'pending_judge'}]
    (reader/'per_question.jsonl').write_text('\n'.join(json.dumps(r) for r in answers)+'\n')
    (reader/'prompt_rows.jsonl').write_text('\n'.join(json.dumps({'query_invocation_id':r['question_id']}) for r in answers)+'\n')
    (reader/'aggregated_metrics.json').write_text(json.dumps({'timing':{'prompt_build_wall_seconds':1,'reader_generation_wall_seconds':2}}))
    (memory/'model_calls.jsonl').write_text('')
    (tmp_path/'questions.json').write_text(json.dumps([{'id':r['question_id']} for r in answers]))
    costs,_=report.query_evidence({'reader':'reader','memory':'memory','policy':'raw_rag','questions':'questions.json'})
    assert costs['pending']==1
    assert costs['unscored_incomplete']==3
    assert costs['truncated']==costs['service_failures']==costs['parse_failures']==1
    assert costs['query_reader_input_tokens'] is None
