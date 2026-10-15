#!/usr/bin/env python3
"""Narrow matched AgentRunbook-R update experiment, no extra executor/service.

B3: invalidate the touched trajectory, keep every exact request/vector cache.
Ours: same, plus per-event dependency validation of partitioned group outputs.
Both start with independent copies of the SAME already-built source snapshot.
This is an adapted mechanism comparison, not the older workflow-core B3 run.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / 'runs/agentrunbook-r-native-small-20261014/local-text-only'
sys.path.insert(0, str(ADAPTER))
sys.path.append(str(ROOT / 'third_party/LongMemEval-V2'))
import numpy as np
from memory_modules.memory import load_memory, save_memory
from memory_modules.agentrunbook_r import AgentRunbookR
from memory_modules.trajectory_store import save_json


def jsonl(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.exists() else []


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def request_key(messages, model, url, budget, temperature, top_p, top_k, thinking):
    return digest([messages, model, url, budget, temperature, top_p, top_k, thinking])


class UpdateRunbook(AgentRunbookR):
    """Retains original representation, original extraction, notes and indexes."""

    def request_cache_key(self, messages, disable_thinking=None, max_completion_tokens=None):
        request = self._build_controller_request(messages, disable_thinking=self.controller_disable_thinking if disable_thinking is None else disable_thinking,
                                                 max_completion_tokens=max_completion_tokens)
        extra = request.get('extra_body') or {}
        return request_key(messages, request['model'], self.controller_base_url,
                           request.get('max_completion_tokens', request.get('max_tokens')), request.get('temperature'), request.get('top_p'),
                           extra.get('top_k'), extra.get('enable_thinking', (extra.get('chat_template_kwargs') or {}).get('enable_thinking')))

    def event_dependency_key(self, trajectory, spec):
        # Goal/outcome/full action trace/workflow position + exact pre/post source
        # evidence are dependencies. Other group members are packaging only:
        # the paired prompt explicitly grounds EACH output in its own pre/post.
        messages = self._build_event_generation_messages(trajectory_dir=self.workspace_dir / 'trajectories' / trajectory['id'],
                         simplified_trajectory=trajectory, spec=spec)
        return self.request_cache_key(messages, disable_thinking=True,
                                      max_completion_tokens=int(os.environ['LME_EVENT_OUTPUT_TOKENS']))

    async def _call_controller_text_async(self, messages, *, disable_thinking=None, max_completion_tokens=None, reject_truncated=False):
        key = self.request_cache_key(messages, disable_thinking, max_completion_tokens)
        if key in self.exact_requests:
            self._append_model_call_metric({'channel': 'update_request_cache', 'status': 'hit', 'key': key, 'stage': 'events'})
            return self.exact_requests[key]
        text = await super()._call_controller_text_async(messages, disable_thinking=disable_thinking,
                  max_completion_tokens=max_completion_tokens, reject_truncated=reject_truncated)
        self.exact_requests[key] = text
        self.update_event_outputs += 2 if 'events array' in messages[0]['content'] else 1
        return text

    def _call_controller_text(self, messages, *, disable_thinking=None, max_completion_tokens=None):
        key = self.request_cache_key(messages, disable_thinking, max_completion_tokens)
        if key in self.exact_requests:
            self._append_model_call_metric({'channel': 'update_request_cache', 'status': 'hit', 'key': key, 'stage': 'notes'})
            return self.exact_requests[key]
        text = super()._call_controller_text(messages, disable_thinking=disable_thinking, max_completion_tokens=max_completion_tokens)
        self.exact_requests[key] = text
        self.update_notes_regenerated = 2
        return text

    async def _extract_event_fields_batch_async(self, *, trajectory_dir, simplified_trajectory, transition_specs):
        if self.update_policy == 'b3':
            return await super()._extract_event_fields_batch_async(trajectory_dir=trajectory_dir,
                simplified_trajectory=simplified_trajectory, transition_specs=transition_specs)
        keys = [self.event_dependency_key(simplified_trajectory, spec) for spec in transition_specs]
        rows = [self.event_outputs.get(key) for key in keys]
        # Only adjacent dirty transitions share a request; isolated dirty events
        # execute immediately, without waiting for any future arrival.
        for start in range(len(rows)):
            if rows[start] is not None: continue
            end = start + 1
            if end < len(rows) and rows[end] is None: end += 1
            fields = await self._extract_event_group_async(trajectory_dir=trajectory_dir,
                simplified_trajectory=simplified_trajectory, specs=transition_specs[start:end])
            for i, value in zip(range(start, end), fields):
                rows[i] = value
                self.event_outputs[keys[i]] = copy.deepcopy(value)
        self._append_model_call_metric({'channel': 'update_event_dependency', 'status': 'validated',
                                       'events': len(keys), 'reused': sum(key in self.initial_event_keys for key in keys)})
        return rows


def seed_caches(memory):
    memory.exact_requests = {}
    for record in jsonl(memory.workspace_dir / 'model_calls.jsonl'):
        if record.get('query_invocation_id') or record.get('channel') != 'controller' or record.get('status') != 'success': continue
        if not record.get('messages') or record.get('finish_reason') != 'stop': continue
        key = request_key(record['messages'], record['model'], record['base_url'], record['max_completion_tokens'],
                          record['temperature'], record['top_p'], record['top_k'], record['enable_thinking'])
        memory.exact_requests[key] = record['response_text']
    memory.event_outputs = {}
    for tid in memory.inserted_trajectory_ids:
        trajectory = memory._load_stored_trajectory(tid)
        entries = {e['event_id']: e for e in memory.event_entries if e['trajectory_id'] == tid}
        for spec in memory._build_event_transition_specs(trajectory):
            entry = entries[spec['event_id']]
            memory.event_outputs[memory.event_dependency_key(trajectory, spec)] = {k: entry[k] for k in ('overview', 'state_transition')}
    memory.initial_event_keys = set(memory.event_outputs)
    # The source snapshot's vectors are legal exact-input cache entries for BOTH.
    for entries, vectors, field in [(memory.raw_state_entries, memory.raw_state_embeddings, 'slice_axtree_text'),
                                  (memory.event_entries, memory.event_embeddings, 'description'),
                                  (memory.procedure_note_entries, memory.procedure_note_embeddings, 'note_text'),
                                  (memory.hint_note_entries, memory.hint_note_embeddings, 'note_text')]:
        for entry, vector in zip(entries, vectors):
            text = memory._truncate_for_embedding(entry[field])
            memory._construction_embedding_memo[memory._construction_embedding_key(text)] = vector.copy()
    memory.update_event_outputs = 0
    memory.update_notes_regenerated = 0


def replace_partition(memory, trajectory, bundle):
    tid = trajectory['id']
    pools = [('raw_state_entries', 'raw_state_embeddings', bundle['raw_state_entries'], bundle['raw_state_embeddings']),
             ('event_entries', 'event_embeddings', bundle['event_entries'], bundle['event_embeddings']),
             ('procedure_note_entries', 'procedure_note_embeddings', [bundle['procedure_note_entry']], bundle['procedure_note_embedding']),
             ('hint_note_entries', 'hint_note_embeddings', [bundle['hint_note_entry']], bundle['hint_note_embedding'])]
    for entry_name, vector_name, new_entries, new_vectors in pools:
        entries, vectors = getattr(memory, entry_name), getattr(memory, vector_name)
        out_entries, out_vectors, inserted = [], [], False
        for entry, vector in zip(entries, vectors):
            if entry['trajectory_id'] == tid:
                if not inserted:
                    out_entries.extend(new_entries); out_vectors.extend(new_vectors); inserted = True
            else:
                out_entries.append(entry); out_vectors.append(vector)
        if not inserted:
            out_entries.extend(new_entries); out_vectors.extend(new_vectors)
        setattr(memory, entry_name, out_entries)
        setattr(memory, vector_name, np.asarray(out_vectors, dtype=np.float32))
    if tid not in memory.inserted_trajectory_ids: memory.inserted_trajectory_ids.append(tid)
    save_json(memory.workspace_dir / 'trajectories' / tid / 'trajectory.json', trajectory)
    memory._refresh_runtime_query_summary()


def changed_trajectory(source, case, trajectory_id, state_index, patch_text, append_source, append_id=None):
    """Materialize one controlled update for a selected complete trajectory.

    The old screen experiment silently hard-coded one web trajectory and state.
    Keep the patch deliberately small and source-backed, but make the identity,
    location, and wording explicit in the run manifest so multi-trajectory
    paired updates remain auditable.
    """
    trajectory_path = source / 'trajectories' / trajectory_id / 'trajectory.json'
    if not trajectory_path.exists():
        raise FileNotFoundError(f'unknown trajectory in source snapshot: {trajectory_id}')
    original = json.loads(trajectory_path.read_text())
    if not isinstance(state_index, int) or not 0 <= state_index < len(original.get('states', [])):
        raise ValueError(f'state index {state_index} outside trajectory {trajectory_id} ({len(original.get("states", []))} states)')
    if case == 'append':
        if append_source is None: raise ValueError('append requires a real additional complete trajectory source')
        if append_source.suffix == '.jsonl':
            trajectory = next(json.loads(line) for line in append_source.read_text().splitlines()
                              if line.strip() and (append_id is None or json.loads(line).get('id') == append_id))
        else:
            trajectory = json.loads(append_source.read_text())
        assert trajectory['id'] not in json.loads((source / 'index.json').read_text())['inserted_trajectory_ids']
        trajectory['states'] = trajectory['states'][:3]
        trajectory['states'][0]['action'] = None
        trajectory['actions'] = [state.get('action') or '<none>' for state in trajectory['states'][1:]]
        trajectory['outcome'] = None  # no future outcome information at arrival
        return trajectory, {'kind': 'arrival_prefix_of_new_real_trajectory', 'arrived_states': 3,
                            'source': str(append_source), 'no_future_states_or_outcome': True}
    trajectory = copy.deepcopy(original)
    if case == 'state_revision':
        # A controlled correction in an existing snapshot, not an official new QA set.
        patch = patch_text or "[correction] status 'Title validation: saved', visible"
        trajectory['states'][state_index]['text'] += '\n' + patch
        return trajectory, {'kind': 'controlled_state_correction', 'trajectory_id': trajectory_id,
                            'state_index': state_index, 'patch': patch,
                            'dirty_event_state_indexes': [state_index]}
    if case == 'workflow_revision':
        # Correct the workflow intent recorded at one step; retain all actions/state evidence.
        patch = patch_text or 'Workflow clarification: verify the required field before proceeding to the next form field.'
        trajectory['states'][state_index]['thoughts'] = (trajectory['states'][state_index].get('thoughts') or '') + ' ' + patch
        return trajectory, {'kind': 'controlled_workflow_fragment_revision', 'trajectory_id': trajectory_id,
                            'state_index': state_index, 'patch': patch,
                            'dirty_event_state_indexes': [state_index]}
    raise ValueError(case)


def _entry_digest(entry):
    return digest({k: v for k, v in entry.items() if k not in {'embedding', 'vector'}})


def _quality_checks(source_memory, updated_memory, original, changed, workload, case, trajectory_id, state_index, policy):
    """Cheap source-grounded checks run for every update, not a QA claim."""
    source_states = {s['state_index']: s for s in original.get('states', [])}
    changed_state = changed['states'][state_index]
    patch = workload.get('patch', '')
    raw_after = [e for e in updated_memory.raw_state_entries if e.get('trajectory_id') == trajectory_id]
    raw_other_before = [_entry_digest(e) for e in source_memory.raw_state_entries if e.get('trajectory_id') != trajectory_id]
    raw_other_after = [_entry_digest(e) for e in updated_memory.raw_state_entries if e.get('trajectory_id') != trajectory_id]
    event_before = {e['event_id']: e for e in source_memory.event_entries if e.get('trajectory_id') == trajectory_id}
    event_after = {e['event_id']: e for e in updated_memory.event_entries if e.get('trajectory_id') == trajectory_id}
    dirty_indexes = {i for i in (state_index - 1, state_index) if 0 <= i < len(original.get('states', [])) - 1}
    dirty_ids = {f"event_{original['states'][i]['state_index']:04d}_{original['states'][i+1]['state_index']:04d}" for i in dirty_indexes}
    reused_ids = sorted(set(event_before) - dirty_ids)
    reused_equal = all(_entry_digest(event_before[eid]) == _entry_digest(event_after.get(eid, {})) for eid in reused_ids)
    old_text = source_states[state_index].get('text', '')
    old_thoughts = source_states[state_index].get('thoughts', '') or ''
    target_text = '\n'.join(str(e.get('slice_axtree_text', '')) for e in raw_after)
    target_events = [e for e in updated_memory.event_entries if e.get('trajectory_id') == trajectory_id]
    target_notes = [e for e in (updated_memory.procedure_note_entries + updated_memory.hint_note_entries)
                    if e.get('trajectory_id') == trajectory_id]
    published_blob = target_text + '\n' + '\n'.join(json.dumps(e, ensure_ascii=False) for e in target_events + target_notes)
    # The source patch is expected to be visible in the rebuilt published views.
    new_fact_present = bool(patch) and patch in published_blob
    # Original visible evidence remains present for both update kinds; workflow
    # edits additionally retain the original thought/action context in events.
    old_fact_retained = (not old_text or old_text[:80] in published_blob)
    untouched_retained = sorted(raw_other_before) == sorted(raw_other_after)
    event_coverage = (set(event_before) == set(event_after) and len(event_after) == len(original.get('states', [])) - 1)
    reuse_check = reused_equal if policy == 'ours' else True
    return {
        'new_fact_present': new_fact_present,
        'old_fact_retained': old_fact_retained,
        'untouched_facts_retained': untouched_retained,
        'event_source_coverage': event_coverage,
        'reused_joint_events_complete': reused_equal if policy == 'ours' else 'not_applicable_b3',
        'dirty_event_ids': sorted(dirty_ids),
        'reused_event_count': len(reused_ids),
        'fixed_reader_regression': 'not_run',
        'quality_scope': 'source_grounded_update_checks; fixed Reader regression scheduled separately',
        'quality_pass': bool(new_fact_present and old_fact_retained and untouched_retained and event_coverage and reuse_check),
    }


def run_one(args, case, policy):
    out = args.output / f'{case}-{policy}'
    if out.exists(): raise FileExistsError(out)
    out.mkdir(parents=True)
    shutil.copytree(args.source, out / 'memory_state')
    memory = load_memory(out / 'memory_state')
    memory.__class__ = UpdateRunbook
    memory.update_policy = policy
    setup_started = time.perf_counter()
    memory.configure_runtime()
    seed_caches(memory)
    setup_s = time.perf_counter() - setup_started
    trajectory, workload = changed_trajectory(args.source, case, args.trajectory_id, args.state_index,
                                              args.patch_text, args.append_source, args.append_id)
    save_json(out / 'update_input.json', {'trajectory': trajectory, 'workload': workload})
    previous_calls = len(jsonl(memory.workspace_dir / 'model_calls.jsonl'))
    started = time.perf_counter()
    bundle = memory._build_trajectory_artifact_bundle(trajectory_dir=memory.workspace_dir / 'trajectories' / trajectory['id'],
                                                      simplified_trajectory=trajectory)
    replace_partition(memory, trajectory, bundle)
    save_memory(memory, memory.workspace_dir)
    loaded = load_memory(memory.workspace_dir)
    assert loaded.inserted_trajectory_ids == memory.inserted_trajectory_ids
    assert loaded.event_entries == memory.event_entries
    assert all(np.array_equal(getattr(loaded, key), getattr(memory, key)) for key in
               ('raw_state_embeddings', 'event_embeddings', 'procedure_note_embeddings', 'hint_note_embeddings'))
    elapsed = time.perf_counter() - started
    quality = _quality_checks(load_memory(args.source), loaded,
                              json.loads((args.source / 'trajectories' / args.trajectory_id / 'trajectory.json').read_text()),
                              trajectory, workload, case, args.trajectory_id, args.state_index, policy)
    calls = jsonl(memory.workspace_dir / 'model_calls.jsonl')[previous_calls:]
    c = [r for r in calls if r['channel'] == 'controller']
    e = [r for r in calls if r['channel'] == 'embedding']
    metrics = {'policy': policy, 'case': case, 'scope': 'adapted_AgentRunbookR_local_update',
        'starting_snapshot': str(args.source), 'starting_cache': 'independent clones; exact requests and vectors preserved equally',
        'setup_load_and_seed_s_excluded': setup_s, 'update_to_queryable_publish_s': elapsed,
        'reextracted_event_outputs': memory.update_event_outputs, 'regenerated_notes': memory.update_notes_regenerated,
        'llm_calls': len(c), 'llm_input_tokens_known': sum(r.get('prompt_tokens') or 0 for r in c),
        'llm_output_tokens_known': sum(r.get('completion_tokens') or 0 for r in c),
        'embedding_calls': len(e), 'embedding_vectors': sum(r['input_text_count'] for r in e),
        'embedding_tokens_known': sum(r.get('prompt_tokens') or 0 for r in e),
        'unknown_usage_calls': sum(r.get('prompt_tokens') is None for r in c+e),
        'api_failed_calls': sum(r['status'] == 'failed' for r in c+e),
        'exact_request_hits': sum(r['channel'] == 'update_request_cache' for r in calls),
        'embedding_hits': sum(r.get('cache_hits', 0) for r in calls if r['channel'] == 'build_embedding_cache'),
        'load_verified': True, 'event_count': len(memory.event_entries), 'note_count': len(memory.procedure_note_entries) + len(memory.hint_note_entries),
        'qa_status': 'source_grounded_checks_passed' if quality['quality_pass'] else 'source_grounded_checks_failed',
        'quality_checks': quality, 'trajectory_id': args.trajectory_id, 'state_index': args.state_index,
        'raw_path': str(out)}
    save_json(out / 'update_metrics.json', metrics)
    save_json(out / 'update_calls.json', calls)
    print(json.dumps(metrics), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--append-source', type=Path)
    parser.add_argument('--append-id', default='4ba5e9cb')
    parser.add_argument('--trajectory-id', default='1ad1af4b')
    parser.add_argument('--state-index', type=int, default=4)
    parser.add_argument('--patch-text', default=None, help='Controlled source-backed patch text; used for state/workflow revision')
    parser.add_argument('--cases', nargs='+', default=['append', 'state_revision', 'workflow_revision'])
    args = parser.parse_args()
    args.source, args.output = args.source.resolve(), args.output.resolve()
    construction_config = args.source / 'construction_config.json'
    if construction_config.exists():
        config = json.loads(construction_config.read_text())
        if config.get('event_max_input_tokens'):
            os.environ['LME_EVENT_MAX_INPUT_TOKENS'] = str(config['event_max_input_tokens'])
    for key, value in {'LME_TEXT_ONLY': '1', 'LME_EVENT_GROUP_SIZE': '2', 'LME_EVENT_OUTPUT_TOKENS': '2048',
                       'LME_EVENT_CONCURRENCY': '1', 'LME_REUSE_BUILD_EMBEDDING': '1', 'LME_RECORD_FULL_REQUESTS': '1',
                       'LME_EMBEDDING_TOKENIZER_MODEL': '/data/predator/ly/Mem/models/Qwen3-Embedding-8B'}.items(): os.environ[key] = value
    for case in args.cases:
        for policy in ('b3', 'ours'): run_one(args, case, policy)


if __name__ == '__main__': main()
