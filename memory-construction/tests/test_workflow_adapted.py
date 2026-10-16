"""CPU contracts for the real-core adapter; fake inference is test-only."""
import json
import importlib
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LOCAL_ADAPTER = ROOT / 'runs/agentrunbook-r-native-small-20261014/local-text-only'
from workflow_memory.ir import Evidence
from workflow_memory import construction as core


def local_memory_api():
    # This repository contains two packages named ``memory_modules``.  Resolve
    # the adapted local registry at call time so pytest collection order cannot
    # silently select the async-fix-runtime registry.
    for name in list(sys.modules):
        if name == 'memory_modules' or name.startswith('memory_modules.'):
            del sys.modules[name]
    # Presence alone is insufficient: another test can have prepended the
    # legacy package ahead of this already-present path.
    if str(LOCAL_ADAPTER) in sys.path:
        sys.path.remove(str(LOCAL_ADAPTER))
    sys.path.insert(0, str(LOCAL_ADAPTER))
    module = importlib.import_module('memory_modules.memory')
    assert Path(module.__file__).resolve().is_relative_to(LOCAL_ADAPTER)
    return module.build_memory, module.load_memory


class Fake:
    def fingerprint(self):
        return 'test-only'

    def extract_event(self, event, **kwargs):
        return [Evidence(evidence_id=event.event_id + ':test', source_refs=(event.event_id,),
                         source_versions={event.event_id: event.source_revision},
                         valid_scope=core._scope(event), subject_ref='agent',
                         predicate='action', value=event.action, event_kind='attempt')]


def test_independent_core_publication_and_load(tmp_path):
    build_memory, load_memory = local_memory_api()
    data = ROOT / 'runs/dev-adapted-text-v1/data/web'
    trajectories = [json.loads(l) for l in (data / 'trajectories.jsonl').read_text().splitlines()][:2]
    snapshots = []
    for typ in ('workflow_b3', 'workflow_ours'):
        cfg = json.loads((ROOT / 'runs/dev-adapted-text-v1/results/web-rag-raw-v1/runtime_inputs/memory_config.json').read_text())
        cfg['memory_type'] = typ
        cfg['memory_params'].update(workspace_dir=str(tmp_path / typ), trajectories_root_dir=str(data))
        memory = build_memory(cfg)
        memory.core_backend = Fake()
        memory._embed_texts = lambda texts, **kwargs: np.ones((len(texts), 3), dtype=np.float32)
        for trajectory in trajectories:
            memory.insert(trajectory)
            memory.save_memory(tmp_path / typ)
        reloaded = load_memory(tmp_path / typ)
        assert reloaded.inserted_trajectory_ids == [t['id'] for t in trajectories]
        assert len(reloaded.snapshot.events) == sum(len(t['states']) for t in trajectories)
        assert all(e.get('construction_facts') for e in reloaded.raw_state_entries)
        snapshots.append(reloaded.snapshot)
    assert [e.to_dict() for e in snapshots[0].evidence] == [e.to_dict() for e in snapshots[1].evidence]
    assert snapshots[0].store_path != snapshots[1].store_path
