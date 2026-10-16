"""Read-only validity checks on a persisted real source snapshot; no inference."""
import importlib.util
import asyncio
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'runs/construction-pair-v1/screen-web-g2/memory_state'


@pytest.fixture
def updater(monkeypatch):
    monkeypatch.setenv('LME_TEXT_ONLY', '1')
    monkeypatch.setenv('LME_EVENT_OUTPUT_TOKENS', '2048')
    monkeypatch.setenv('LME_EMBEDDING_TOKENIZER_MODEL', '/data/predator/ly/Mem/models/Qwen3-Embedding-8B')
    monkeypatch.delenv('LME_EVENT_MAX_INPUT_TOKENS', raising=False)
    # The repository also contains an isolated async-fix-runtime package with
    # the same top-level ``memory_modules`` name.  Purge any earlier import so
    # this fixture always exercises the local text-only adapter used by the
    # updater, independent of pytest collection order.
    prior_memory_modules = {
        name: sys.modules[name]
        for name in sys.modules
        if name == 'memory_modules' or name.startswith('memory_modules.')
    }
    for name in list(sys.modules):
        if name == 'memory_modules' or name.startswith('memory_modules.'):
            del sys.modules[name]
    monkeypatch.syspath_prepend(str(ROOT / 'runs/agentrunbook-r-native-small-20261014/local-text-only'))
    spec = importlib.util.spec_from_file_location('update_experiment', ROOT / 'tools/run_agentrunbook_updates.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    memory = module.load_memory(SOURCE)
    memory.__class__ = module.UpdateRunbook
    # Dependency tests may emit cache/invalidation diagnostics. Never append
    # synthetic test records to the real historical experiment ledger.
    monkeypatch.setattr(memory, '_append_model_call_metric', lambda row: None)
    module.seed_caches(memory)
    # Unit fixture only: seed synthetic dependency entries to test invalidation
    # shape. Production now refuses to re-key legacy snapshot event outputs.
    for tid in memory.inserted_trajectory_ids:
        trajectory = memory._load_stored_trajectory(tid)
        for spec in memory._build_event_transition_specs(trajectory):
            memory.event_outputs[memory.event_dependency_key(trajectory, spec)] = {
                'overview': 'synthetic overview', 'state_transition': 'synthetic transition'}
    memory.initial_event_keys = set(memory.event_outputs)
    try:
        yield module, memory
    finally:
        for name in list(sys.modules):
            if name == 'memory_modules' or name.startswith('memory_modules.'):
                del sys.modules[name]
        sys.modules.update(prior_memory_modules)


def test_b3_all_original_group_and_note_requests_remain_legal(updater):
    module, memory = updater
    trajectory = memory._load_stored_trajectory('1ad1af4b')
    specs = memory._build_event_transition_specs(trajectory)
    for start in range(0, len(specs), 2):
        group = specs[start:start+2]
        if len(group) == 2:
            messages = memory._build_event_group_messages(trajectory_dir=SOURCE, simplified_trajectory=trajectory, specs=group)
        else:
            messages = memory._build_event_generation_messages(trajectory_dir=SOURCE, simplified_trajectory=trajectory, spec=group[0])
        key = memory.request_cache_key(messages, True, 2048*len(group))
        assert key in memory.exact_requests
    note_messages = memory._build_note_generation_messages(trajectory_dir=SOURCE, simplified_trajectory=trajectory)
    assert memory.request_cache_key(note_messages) in memory.exact_requests


@pytest.mark.parametrize('case,note_changes', [('state_revision', False), ('workflow_revision', True)])
def test_event_output_dependencies_not_whole_group(updater, case, note_changes):
    module, memory = updater
    trajectory, _ = module.changed_trajectory(SOURCE, case, None)
    specs = memory._build_event_transition_specs(trajectory)
    changed = [s['event_id'] for s in specs if memory.event_dependency_key(trajectory, s) not in memory.event_outputs]
    assert changed == ['event_0003_0004', 'event_0004_0005']
    groups_changed = []
    for start in range(0, 6, 2):
        messages = memory._build_event_group_messages(trajectory_dir=SOURCE, simplified_trajectory=trajectory, specs=specs[start:start+2])
        if memory.request_cache_key(messages, True, 4096) not in memory.exact_requests: groups_changed.append(start)
    assert groups_changed == [2, 4]
    note_messages = memory._build_note_generation_messages(trajectory_dir=SOURCE, simplified_trajectory=trajectory)
    assert (memory.request_cache_key(note_messages) not in memory.exact_requests) == note_changes


def test_same_trajectory_growth_is_distinct_from_new_trajectory_append(updater):
    module, memory = updater
    original = memory._load_stored_trajectory('1ad1af4b')
    grown, workload = module.changed_trajectory(
        SOURCE, 'trajectory_growth', '1ad1af4b', len(original['states']) - 1,
        '[controlled arrival] follow-up observed',
    )
    assert workload['kind'] == 'controlled_same_trajectory_growth'
    assert workload['no_new_trajectory'] is True
    assert grown['id'] == original['id']
    assert len(grown['states']) == len(original['states']) + 1
    assert grown['outcome'] is None
    specs = memory._build_event_transition_specs(grown)
    assert len(specs) == len(original['states'])
    assert specs[-1]['event_id'] == f"event_{original['states'][-1]['state_index']:04d}_{grown['states'][-1]['state_index']:04d}"
    # The current conservative cache key includes trajectory-global action/
    # length context; growth therefore does not get mislabeled as exact reuse.
    assert all(memory.event_dependency_key(grown, spec) not in memory.initial_event_keys for spec in specs)


def test_fresh_partition_baseline_clears_only_build_caches(updater):
    module, memory = updater
    assert memory.exact_requests
    assert memory.event_outputs
    assert memory._construction_embedding_memo
    original_event_count = len(memory.event_entries)
    original_ids = list(memory.inserted_trajectory_ids)

    module.clear_build_caches(memory)

    assert memory.exact_requests == {}
    assert memory.event_outputs == {}
    assert memory.initial_event_keys == set()
    assert memory._construction_embedding_memo == {}
    assert len(memory.event_entries) == original_event_count
    assert memory.inserted_trajectory_ids == original_ids


def test_delta_merge_preserves_unmodified_fields(updater):
    module, _ = updater
    old = {'overview': 'Create ticket T123.', 'state_transition': 'Status Open. Owner Alice.'}
    result = module.merge_event_edits(old, [{'field': 'state_transition', 'old': 'Status Open.', 'new': 'Status Closed.'}])
    assert result == {'overview': old['overview'], 'state_transition': 'Status Closed. Owner Alice.'}
    assert old['state_transition'] == 'Status Open. Owner Alice.'
    appended = module.merge_event_edits(old, [{'field': 'state_transition', 'old': '', 'new': 'Priority High.'}])
    assert appended['state_transition'] == old['state_transition'] + ' Priority High.'


def test_current_source_coalescing_retires_old_patch_and_keeps_other_state(updater):
    module, _ = updater
    fields = {'overview': 'Attempted action A. Owner Alice.', 'state_transition': 'Old interpretation.'}
    tr = {'states': [{'text': "[1] Name='Alice'\n[2] Title='B'"}, {'text': "[2] Title='A'"}]}
    observations = [{'state_index': 0, 'role': 'pre-state', 'current_evidence': "[1] Name='Alice'\n[2] Title='B'"},
                    {'state_index': 1, 'role': 'post-state', 'current_evidence': "[2] Title='A'"}]
    once = module.coalesce_current_evidence(fields, observations, tr, '012345')
    tr['states'][0]['text'] = "[1] Name='Alice'\n[2] Title='C'"
    twice = module.coalesce_current_evidence(once,
        [{'state_index': 0, 'role': 'pre-state', 'current_evidence': "[2] Title='C'"}], tr, 'abcdef')
    assert twice['overview'] == once['overview']
    assert twice['state_transition'].count(module.CURRENT_OBSERVATIONS) == 1
    assert twice['state_transition'].count('Prior-source interpretation') == 1
    assert "Title='B'" not in twice['state_transition']
    assert "Title='C'" in twice['state_transition']
    assert "Title='A'" in twice['state_transition']  # Other state is NOT revised.
    assert "Name='Alice'" in twice['state_transition']  # Different field retained.
    assert 'Old interpretation.' in twice['state_transition']


def test_current_source_coalescing_rejects_malformed_persisted_evidence(updater):
    module, _ = updater
    with pytest.raises(ValueError):
        module.coalesce_current_evidence({'overview': 'task',
            'state_transition': 'transition'+module.CURRENT_OBSERVATIONS+'[bad]'}, [], {'states': []}, 'abc')


def test_current_source_merge_does_not_promote_duplicate_obsolete_line(updater):
    module, _ = updater
    tr = {'states': [{'text': "[1] Name='A'\nStaticText 'A'\n[2] Title='B'\nStaticText 'B'"}]}
    fields = {'overview': 'task', 'state_transition': 'transition'+module.CURRENT_OBSERVATIONS+json.dumps([
        {'state_index': 0, 'role': 'post-state', 'current_evidence': "[2] Title='A'\nStaticText 'A'"}])}
    out = module.coalesce_current_evidence(fields,
        [{'state_index': 0, 'role': 'post-state', 'current_evidence': "[2] Title='B'\nStaticText 'B'"}],
        tr, 'abc', [{'state_index': 0, 'obsolete_source_lines': ["[2] Title='A'", "StaticText 'A'"]}])
    current = out['state_transition'].split(module.CURRENT_OBSERVATIONS)[1]
    assert "StaticText 'A'" not in current
    assert "Title='B'" in current


def test_text_only_coalesced_revision_does_not_reuse_generic_notes_when_source_lines_absent(updater, monkeypatch):
    module, memory = updater
    memory.update_policy = 'source_coalesced'
    tid = next(iter(memory.inserted_trajectory_ids))
    old = memory._load_stored_trajectory(tid)
    changed = json.loads(json.dumps(old))
    changed['states'][0]['text'] = changed['states'][0].get('text', '') + "\nStaticText 'new validation marker'"
    procedure = next(e for e in memory.procedure_note_entries if e['trajectory_id'] == tid)
    hint = next(e for e in memory.hint_note_entries if e['trajectory_id'] == tid)
    procedure['note_text'] = 'Generic workflow note without the exact source line.'
    hint['note_text'] = 'Generic hint without the exact source line.'
    sentinel = ({'note_type': 'procedure', 'note_text': 'regenerated procedure'},
                {'note_type': 'hint', 'note_text': 'regenerated hint'})
    monkeypatch.setattr(module.AgentRunbookR, '_build_note_entries',
                        lambda self, **kwargs: sentinel)
    result = memory._build_note_entries(trajectory_dir=memory.workspace_dir, simplified_trajectory=changed)
    assert result == sentinel


def test_source_only_keeps_prior_invalid_events_on_another_state_update(updater, monkeypatch):
    module, memory = updater
    memory.update_policy = 'source_only'
    old = memory._load_stored_trajectory('1ad1af4b')
    import copy
    changed = copy.deepcopy(old)
    changed['states'][4]['text'] += '\nNew local observation'
    previous = memory.event_entries[0]
    previous['validity_status'] = 'invalidated_source_change'
    previous['invalidated_source_state_indexes'] = [0]
    previous['invalidated_by_policy'] = 'source_only'
    monkeypatch.setattr(memory, '_append_model_call_metric', lambda row: None)
    entries = memory._build_event_entries(trajectory_dir=memory.workspace_dir/'trajectories/1ad1af4b', simplified_trajectory=changed)
    first = next(e for e in entries if e['event_id'] == previous['event_id'])
    assert first['validity_status'] == 'invalidated_source_change'
    assert first['invalidated_source_state_indexes'] == [0]


def test_source_only_marks_changed_events_invalid_but_keeps_raw_path(updater):
    module, memory = updater
    memory.update_policy = 'source_only'
    trajectory, _ = module.changed_trajectory(SOURCE, 'state_revision', '1ad1af4b', 4)
    entries = memory._build_event_entries(trajectory_dir=SOURCE, simplified_trajectory=trajectory)
    invalid = {e['event_id'] for e in entries if e.get('validity_status') == 'invalidated_source_change'}
    assert invalid == {'event_0003_0004', 'event_0004_0005'}
    assert len(entries) == len(memory.event_entries) // len(memory.inserted_trajectory_ids) or len(entries) > 0


def test_source_only_cross_state_invalidation_survives_actual_save_load(updater, tmp_path, monkeypatch):
    """Exercise persisted event flags and real retrieval filtering, without inference.

    Raw-state replacement is covered by real maintenance runs; here the
    regression is specifically that an earlier retired event must not revive.
    """
    import copy
    import shutil
    import numpy as np

    module, _ = updater
    cloned = tmp_path / 'memory_state'
    shutil.copytree(SOURCE, cloned)
    memory = module.load_memory(cloned)
    memory.__class__ = module.UpdateRunbook
    memory.update_policy = 'source_only'
    tid = '1ad1af4b'
    before_vectors = memory.event_embeddings.copy()
    before_notes = copy.deepcopy(memory.procedure_note_entries + memory.hint_note_entries)
    before = {e['event_id']: copy.deepcopy(e) for e in memory.event_entries if e['trajectory_id'] == tid}
    for state_index in (0, 4):
        trajectory = copy.deepcopy(memory._load_stored_trajectory(tid))
        trajectory['states'][state_index]['text'] += f'\nNew observation for state {state_index}'
        changed = memory._build_event_entries(
            trajectory_dir=cloned / 'trajectories' / tid, simplified_trajectory=trajectory)
        changed_by_id = {e['event_id']: e for e in changed}
        memory.event_entries = [changed_by_id[e['event_id']] if e['trajectory_id'] == tid else e
                                for e in memory.event_entries]
        module.save_json(cloned / 'trajectories' / tid / 'trajectory.json', trajectory)
        module.save_memory(memory, cloned)
        memory = module.load_memory(cloned)
        memory.__class__ = module.UpdateRunbook
        memory.update_policy = 'source_only'
    retired = {e['event_id'] for e in memory.event_entries
               if e['trajectory_id'] == tid and e.get('validity_status') == 'invalidated_source_change'}
    assert retired == {'event_0000_0001', 'event_0003_0004', 'event_0004_0005'}
    assert np.array_equal(memory.event_embeddings, before_vectors)
    assert memory.procedure_note_entries + memory.hint_note_entries == before_notes
    for entry in memory.event_entries:
        if entry['trajectory_id'] == tid and entry['event_id'] not in retired:
            assert entry['description'] == before[entry['event_id']]['description']
    monkeypatch.setattr(memory, '_embed_texts',
                        lambda texts, **kwargs: np.zeros((1, memory.event_embeddings.shape[1]), dtype=np.float32))
    results = memory._search_entries(entries=memory.event_entries, embeddings=memory.event_embeddings,
                                     query_text='current fact', top_k=len(memory.event_entries))
    assert all(r['entry'].get('validity_status') != 'invalidated_source_change' for r in results)
    assert len(results) == len(memory.event_entries) - len(retired)


@pytest.mark.parametrize('edit', [
    {'field': 'raw', 'old': '', 'new': 'invalid'},
    {'field': 'overview', 'old': 'missing', 'new': 'invalid'},
    {'field': 'overview', 'old': 'A', 'new': 'invalid'},
])
def test_delta_merge_rejects_ambiguous_edits(updater, edit):
    module, _ = updater
    with pytest.raises(ValueError):
        module.merge_event_edits({'overview': 'A A', 'state_transition': 'B'}, [edit])


def test_delta_uses_source_difference_and_rejects_growth(updater):
    module, memory = updater
    old = memory._load_stored_trajectory('1ad1af4b')
    changed, _ = module.changed_trajectory(SOURCE, 'state_revision')
    delta = module.source_delta(old, changed)
    assert len(delta) == 1 and delta[0]['field'] == 'text'
    assert "+[correction] status 'Title validation: saved', visible" in delta[0]['diff']
    grown, _ = module.changed_trajectory(SOURCE, 'trajectory_growth')
    assert module.source_delta(old, grown) is None


def test_additive_delta_cannot_delete_old_details(updater):
    module, _ = updater
    record = {'existing_memory': {'overview': 'Task T. Owner Alice.', 'state_transition': 'Empty before; value X after; control 126 focused.'},
              'changes_for_this_event': [{'state_index': 4, 'field': 'text', 'role': 'pre-state'}]}
    out = module.merge_additive_observations(record, [{'state_index': 4, 'source_field': 'text', 'fact': 'Status Ready visible.'}])
    assert out['overview'] == record['existing_memory']['overview']
    assert out['state_transition'].startswith(record['existing_memory']['state_transition'])
    assert out['state_transition'].endswith('Revised pre-state observation: Status Ready visible.')
    with pytest.raises(ValueError):
        module.merge_additive_observations(record, [])


def test_delta_json_recovers_only_redundant_closing_punctuation(updater):
    module, _ = updater
    good = '{"events": [{"event_id": "e1", "observations": []}]}'
    recovered = [json.loads(s) for s in module.delta_json_candidates(good + '}') if s == good]
    assert recovered and recovered[0]['events'][0]['event_id'] == 'e1'
    # Missing IDs still rejected by the candidate validator, not hallucinated
    # by parsing; incomplete JSON must not become a successful empty update.
    for candidate in module.delta_json_candidates('{"events": ['):
        with pytest.raises(ValueError):
            json.loads(candidate)


def test_literal_source_replacement_changes_only_exact_anchor(updater):
    module, memory = updater
    full_source = ROOT / 'runs/method-first-20261015/matched-web-v1/memory_state'
    manifest = json.loads((ROOT / 'configs/method_web_title_replacement.json').read_text())
    new, workload = module.changed_trajectory(full_source, 'literal_revision', revision_spec=manifest)
    old = json.loads((full_source / 'trajectories/1ad1af4b/trajectory.json').read_text())
    assert "value='Neon Harbor'" in new['states'][4]['text']
    assert old['states'][4]['thoughts'] == new['states'][4]['thoughts']
    assert old['actions'] == new['actions']
    assert old['states'][5] == new['states'][5]
    assert workload['state_indices'] == [4]
    changes = module.source_delta(old, new)
    assert len(changes) == 1 and not changes[0]['append_only']
    manifest['source_edits'][0]['count'] = 2
    with pytest.raises(ValueError, match='anchor mismatch'):
        module.changed_trajectory(full_source, 'literal_revision', revision_spec=manifest)


def test_literal_neighbor_evidence_retains_unchanged_title(updater):
    module, _ = updater
    full_source = ROOT / 'runs/method-first-20261015/matched-web-v1/memory_state'
    old = json.loads((full_source / 'trajectories/1ad1af4b/trajectory.json').read_text())
    manifest = json.loads((ROOT / 'configs/method_web_title_replacement.json').read_text())
    new, _ = module.changed_trajectory(full_source, 'literal_revision', revision_spec=manifest)
    record = {'pre_state_index': 4, 'post_state_index': 5,
              'changes_for_this_event': module.source_delta(old, new)}
    context = module.local_unchanged_evidence(new, record)
    assert len(context) == 1 and context[0]['state_index'] == 5
    assert "textbox 'Title" in context[0]['unchanged_entity_lines']
    assert "value='Cyberpunk'" in context[0]['unchanged_entity_lines']
    assert 'Neon Harbor' not in context[0]['unchanged_entity_lines']
    assert len(context[0]['unchanged_entity_lines']) < len(new['states'][5]['text'])


def test_changed_literals_do_not_treat_arbitrary_text_as_numeric(updater):
    module, _ = updater
    revision = {'obsolete_source_lines': ["StaticText 'Showing 101 records'"],
                'current_source_lines': ["StaticText 'Showing 103 records'"]}
    assert module.changed_literal_values([revision]) == {'101'}
    revision['current_source_lines'] = ["StaticText 'Deleted 103 records'"]
    assert module.changed_literal_values([revision]) is None


def test_rejected_delta_parse_cannot_return_a_partially_assigned_result(updater, monkeypatch):
    module, memory = updater
    memory.update_policy = 'delta_notes'
    monkeypatch.setenv('LME_EVENT_MAX_INPUT_TOKENS', '18000')
    monkeypatch.setattr(memory, '_event_group_input_tokens', lambda messages: 100)
    old = {'overview': 'Task', 'state_transition': 'Value101 in post-state.'}
    response = json.dumps({'edits': [{'field': 'state_transition', 'old': 'Value101', 'new': 'Value101'}]})
    async def call(*args, **kwargs):
        return response
    monkeypatch.setattr(memory, '_call_controller_text_async', call)
    record = {'event_id': 'event_0000_0001', 'pre_state_index': 0, 'post_state_index': 1,
              'local_action': 'observe', 'existing_memory': old,
              'changes_for_this_event': [{'state_index': 1, 'role': 'post-state', 'field': 'text',
                  'diff': '-Value101\n+Value103'}]}
    trajectory = {'id': 'synthetic', 'goal': 'Read', 'states': [{'text': 'Value101'}, {'text': 'Value103'}]}
    with pytest.raises(ValueError, match='invalid single-event'):
        asyncio.run(memory._edit_literal_event(trajectory, record))


@pytest.mark.parametrize('case_root', sorted((ROOT / 'runs/method-first-20261015').glob('v11-*-state*/*-delta_guarded')))
def test_v11_additive_generated_content_is_preserved(case_root):
    review = json.loads((case_root / 'derived_quality_review.json').read_text())
    assert review['checks']['derived_automated_checks_pass'] is True
    old_events = {e['event_id']: e for e in review['old_events']}
    for event in review['new_events']:
        old = old_events[event['event_id']]
        for field in ('overview', 'state_transition'):
            assert event[field].startswith(old[field])
        for field in ('pre_state_index', 'post_state_index', 'local_action'):
            assert event.get(field) == old.get(field)
    for old, new in zip(review['old_notes'], review['new_notes']):
        assert new['content'].startswith(old['content'])
        assert new['title'] == old['title']
        assert new['description'] == old['description']
