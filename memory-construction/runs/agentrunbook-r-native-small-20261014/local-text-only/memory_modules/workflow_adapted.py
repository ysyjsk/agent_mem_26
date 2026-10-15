"""Narrow local adapter for the existing strong B3 and incremental core.

Both methods use identical live extraction, source-literal augmentation,
state-slice embeddings, raw-evidence backreferences and Reader formatting.
This is an adapted serial-service comparison, not the historical batch2 run.
"""
from pathlib import Path
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
from workflow_memory.backends import ModelResponse
from workflow_memory.construction import Snapshot, apply_delta, build_fresh, validate_snapshot
from workflow_memory.ir import SourceEvent, stable_hash
from workflow_memory.strong_baseline import build_strong_prefix

from .memory import register_memory, require
from .rag import RagMemory, _empty_embedding_matrix
from .trajectory_store import save_json, load_json


class _Controller:
    def __init__(self, owner):
        self.owner = owner

    def fingerprint(self):
        o = self.owner
        return stable_hash({'model': o.controller_model, 'endpoint': o.controller_base_url,
                            'thinking': o.controller_disable_thinking,
                            'temperature': o.controller_temperature, 'top_p': o.controller_top_p,
                            'top_k': o.controller_top_k, 'adapter': 'live-core-v1'})

    def complete(self, request, **kwargs):
        # Existing client records actual tokens, failures and wall time.
        text = self.owner._call_controller_text(list(request.messages),
                    disable_thinking=True, max_completion_tokens=request.max_tokens)
        # Even with thinking disabled this checkpoint occasionally emits a
        # partial preamble and closing think marker. Parse only its final part;
        # the full provider response remains in model_calls.jsonl.
        text = text.rsplit('</think>', 1)[-1].strip()
        return ModelResponse(text=text, model=self.owner.controller_model)


class WorkflowMemory(RagMemory):
    strategy = ''

    def __init__(self, memory_params):
        super().__init__(memory_params)
        self.snapshot = None
        self.core_backend = _Controller(self)

    def core_config(self):
        return {'storage_path': str(self.workspace_dir / 'workflow.sqlite3'),
                'model_input_projection': 'salient-v3', 'source_literal_evidence': True,
                'source_literal_version': 'source-literals-v1', 'strict_model_output': True,
                'extraction_prompt': (ROOT / 'prompts/extract_evidence_v2.txt').read_text().strip(),
                'extract_operator_version': 'qwen-quality-v3', 'model_input_char_budget': 6000,
                'extraction_request_cache': True, 'extraction_request_cache_max_entries': 512,
                'source_context_window_events_default': 2, 'extraction_output_tokens': 1024,
                'temperature': self.controller_temperature}

    def insert(self, trajectory):
        require(self.workspace_dir is not None, 'workflow needs a workspace')
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        states = trajectory['states']
        events = []
        tid = trajectory['id']
        offset = len(self.snapshot.events) if self.snapshot else 0
        for i, state in enumerate(states):
            # Official schema actions are attached to destination states.
            events.append(SourceEvent(event_id=f'{tid}:{i}', trajectory_id=tid,
                environment_family=str(trajectory.get('domain', 'unknown')),
                source_sequence=i, arrival_sequence=offset+i, goal=trajectory.get('goal'),
                action=state.get('action'), pre_state_ref=states[i-1] if i else None,
                post_state_ref=state, raw_content_hash=stable_hash(state)))
        started = time.perf_counter()
        try:
            config = self.core_config()
            if self.strategy == 'strong_b3':
                prior = list(self.snapshot.events) if self.snapshot else []
                candidate, stats = build_strong_prefix(prior + events, self.core_backend,
                    config, previous=self.snapshot, concurrency=1)
            elif self.snapshot is None:
                candidate = build_fresh(events, model_backend=self.core_backend, config=config)
                stats = {'phase': 'initial_build'}
            else:
                receipt = apply_delta(self.snapshot, events, model_backend=self.core_backend, config=config)
                require(receipt.queryable and receipt.snapshot is not None, str(receipt.error))
                candidate = receipt.snapshot
                stats = {'reused_nodes': len(receipt.reused_node_ids),
                         'invalidated_nodes': len(receipt.invalidated_node_ids)}
            require(validate_snapshot(candidate).valid, 'invalid core snapshot')
            self.snapshot = candidate
            super().insert(trajectory)
            row = {'trajectory_id': tid, 'status': 'success', 'strategy': self.strategy,
                   'core_plus_index_s': time.perf_counter()-started, 'events': len(events),
                   'evidence': len(candidate.evidence), 'stats': stats}
        except Exception as exc:
            row = {'trajectory_id': tid, 'status': 'failed', 'strategy': self.strategy,
                   'core_plus_index_s': time.perf_counter()-started,
                   'error': str(exc), 'error_type': type(exc).__name__}
            with (self.workspace_dir / 'workflow_checkpoints.jsonl').open('a') as f:
                f.write(json.dumps(row) + '\n')
            raise
        with (self.workspace_dir / 'workflow_checkpoints.jsonl').open('a') as f:
            f.write(json.dumps(row) + '\n')

    def _build_trajectory_artifact_bundle(self, *, trajectory_dir, simplified_trajectory):
        entries = self._build_raw_state_entries(simplified_trajectory)
        by_source = {}
        for evidence in self.snapshot.evidence:
            fact = json.dumps({'predicate': evidence.predicate, 'value': evidence.value,
                               'kind': evidence.event_kind}, ensure_ascii=False, sort_keys=True)
            for ref in evidence.source_refs:
                by_source.setdefault(ref, []).append(fact)
        for entry in entries:
            facts = []
            for i in entry['slice_state_indexes']:
                for fact in by_source.get(f"{entry['trajectory_id']}:{i}", []):
                    line = f'State {i}: {fact}'
                    if line not in facts:
                        facts.append(line)
            entry['construction_facts'] = '\n'.join(facts)
        texts = [entry['construction_facts'] or entry['slice_axtree_text'] for entry in entries]
        return {'raw_state_entries': entries,
                'raw_state_embeddings': self._embed_texts(texts, is_query=False),
                'procedure_note_entry': None, 'hint_note_entry': None,
                'procedure_note_embedding': _empty_embedding_matrix(),
                'hint_note_embedding': _empty_embedding_matrix()}

    def _build_raw_state_context_items(self, raw_results, **kwargs):
        items = []
        for result in raw_results:
            entry = result['entry']
            if entry.get('construction_facts'):
                items.append({'type': 'text', 'value':
                    f"Structured evidence from {entry['trajectory_id']}, states {entry['slice_state_indexes']}\n"
                    + entry['construction_facts']})
            items.extend(super()._build_raw_state_context_items([result], **kwargs))
        return items

    def _save_backend(self, output_dir):
        require(output_dir.resolve() == self.workspace_dir.resolve(), 'save only to owned workspace')
        super()._save_backend(output_dir)
        save_json(output_dir / 'workflow_snapshot.json', self.snapshot.to_dict())
        save_json(output_dir / 'workflow_provenance.json', {
            'strategy': self.strategy, 'config': self.core_config(),
            'representation': 'salient-v3 + source-literals-v1, per-state-slice fact embeddings + full raw backreferences',
            'effective_backend_concurrency': 1, 'no_cross_method_cache': True,
            'official_small_claim': False})

    def _load_backend(self, input_dir):
        super()._load_backend(input_dir)
        self.snapshot = Snapshot.from_dict(load_json(input_dir / 'workflow_snapshot.json'))
        require(validate_snapshot(self.snapshot).valid, 'loaded core snapshot invalid')
        require({e.trajectory_id for e in self.snapshot.events} == set(self.inserted_trajectory_ids),
                'core/raw trajectory mismatch')
        require(len(self.snapshot.events) == len(self.raw_state_entries), 'core/raw state count mismatch')


@register_memory
class StrongB3Memory(WorkflowMemory):
    memory_type = 'workflow_b3'
    strategy = 'strong_b3'


@register_memory
class OursMemory(WorkflowMemory):
    memory_type = 'workflow_ours'
    strategy = 'ours_incremental'
