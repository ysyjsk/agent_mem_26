"""Read-only validity checks on a persisted real source snapshot; no inference."""
import importlib.util
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
    spec = importlib.util.spec_from_file_location('update_experiment', ROOT / 'tools/run_agentrunbook_updates.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    memory = module.load_memory(SOURCE)
    memory.__class__ = module.UpdateRunbook
    module.seed_caches(memory)
    return module, memory


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
