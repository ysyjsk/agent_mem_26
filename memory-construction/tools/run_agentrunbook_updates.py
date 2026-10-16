#!/usr/bin/env python3
"""Narrow matched AgentRunbook-R update experiment, no extra executor/service.

B3: invalidate the touched trajectory, keep every exact request/vector cache.
Ours: same, plus per-event dependency validation of partitioned group outputs.
Both start with independent copies of the SAME already-built source snapshot.
This is an adapted mechanism comparison, not the older workflow-core B3 run.
"""
import argparse
import copy
import difflib
import hashlib
import inspect
import json
import os
import re
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNNER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
ADAPTER = ROOT / 'runs/agentrunbook-r-native-small-20261014/local-text-only'
sys.path.insert(0, str(ADAPTER))
sys.path.append(str(ROOT / 'third_party/LongMemEval-V2'))
import numpy as np
from memory_modules.memory import load_memory, save_memory
from memory_modules.agentrunbook_r import AgentRunbookR
from memory_modules.agentrunbook_r import _json_candidates
from memory_modules.trajectory_store import save_json


def jsonl(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.exists() else []


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def request_key(messages, model, url, budget, temperature, top_p, top_k, thinking):
    return digest([messages, model, url, budget, temperature, top_p, top_k, thinking])


def matched_signature(memory):
    """Bind dependency outputs to the construction semantics that created them."""
    names = ('_build_event_generation_messages', '_build_event_group_messages',
             '_extract_single_event_fields_async', '_extract_event_group_async',
             '_build_note_generation_messages')
    return digest({'code': {n: inspect.getsource(getattr(AgentRunbookR, n)) for n in names},
                   'config': memory._trajectory_artifact_config_snapshot(),
                   'request': memory._build_controller_request([], disable_thinking=True),
                   'env': {k: os.getenv(k) for k in ('LME_TEXT_ONLY', 'LME_EVENT_GROUP_SIZE',
                       'LME_EVENT_OUTPUT_TOKENS', 'LME_EVENT_MAX_INPUT_TOKENS', 'LME_EVENT_STATE_MAX_CHARS')}})


def source_delta(old, new):
    """Exact changed lines plus two context lines; no semantic compression."""
    changes = []
    if any(old.get(k) != new.get(k) for k in ('id', 'goal', 'outcome', 'start_url', 'actions')):
        return None  # Global dependencies changed: use ordinary extraction.
    if len(old['states']) != len(new['states']):
        return None
    for before, after in zip(old['states'], new['states']):
        for key in set(before) | set(after):
            if before.get(key) == after.get(key):
                continue
            if key not in ('text', 'thoughts'):
                return None
            hunks = list(difflib.unified_diff(str(before.get(key) or '').splitlines(),
                                            str(after.get(key) or '').splitlines(), n=2, lineterm=''))
            old_value, new_value = str(before.get(key) or ''), str(after.get(key) or '')
            changes.append({'state_index': after['state_index'], 'field': key, 'diff': '\n'.join(hunks),
                            'append_only': new_value.startswith(old_value)})
    return changes


def merge_event_edits(old_fields, edits):
    """Strict literal edits preserve every untouched field and substring."""
    merged = copy.deepcopy(old_fields)
    if not isinstance(edits, list):
        raise ValueError('edits must be an array')
    for edit in edits:
        if set(edit) != {'field', 'old', 'new'} or edit['field'] not in ('overview', 'state_transition'):
            raise ValueError('unsupported event edit')
        field, old, new = edit['field'], edit['old'], edit['new']
        if not isinstance(old, str) or not isinstance(new, str):
            raise ValueError('edits must use literal strings')
        if old:
            if merged[field].count(old) != 1:
                raise ValueError('edit anchor absent or ambiguous')
            merged[field] = merged[field].replace(old, new, 1)
        elif new.strip():
            merged[field] = (merged[field].rstrip() + ' ' + new.strip()).strip()
    if not all(isinstance(merged[k], str) and merged[k].strip() for k in ('overview', 'state_transition')):
        raise ValueError('empty required event field')
    return merged


def merge_additive_observations(record, observations):
    """For additive source updates the model cannot erase existing facts."""
    expected = {(d['state_index'], d['field']): d['role'] for d in record['changes_for_this_event']}
    if not isinstance(observations, list) or len(observations) != len(expected):
        raise ValueError('missing/extra changed-source observation')
    result, seen = copy.deepcopy(record['existing_memory']), set()
    for obs in observations:
        if set(obs) != {'state_index', 'source_field', 'fact'}:
            raise ValueError('unexpected observation fields')
        key = (obs['state_index'], obs['source_field'])
        if key not in expected or key in seen or not isinstance(obs['fact'], str) or not obs['fact'].strip():
            raise ValueError('invalid observation source or empty fact')
        seen.add(key)
        field = 'overview' if obs['source_field'] == 'thoughts' else 'state_transition'
        kind = 'recorded intent' if obs['source_field'] == 'thoughts' else 'observation'
        result[field] += f" Revised {expected[key]} {kind}: {obs['fact'].strip()}"
    return result


def delta_json_candidates(text):
    """Parse a complete leading object despite redundant closing punctuation."""
    yield from _json_candidates(text)
    stripped = text.strip()
    if stripped.startswith('{'):
        try:
            parsed, end = json.JSONDecoder().raw_decode(stripped)
            if not stripped[end:].strip(' \t\r\n}]'):
                yield json.dumps(parsed, ensure_ascii=False)
        except ValueError:
            pass


def local_unchanged_evidence(trajectory, record):
    """Only neighboring lines for the changed AXTree entities, not whole pages.

    Node IDs and stable literal label prefixes come from exact diff lines;
    they are never semantic/vector approximations to source validity.
    """
    changed_lines = [line[1:].strip() for d in record['changes_for_this_event']
                     for line in d['diff'].splitlines()
                     if line.startswith(('+', '-')) and not line.startswith(('+++', '---'))]
    ids = {m.group(0) for line in changed_lines for m in re.finditer(r'\[[a-zA-Z]*\d+\]', line)}
    prefixes = set()
    for line in changed_lines:
        prefix = re.split(r'\d|\bvalue=', re.sub(r'^\[[^]]+\]\s*', '', line), maxsplit=1)[0]
        if len(prefix) >= 18:
            prefixes.add(prefix)
    changed = {d['state_index'] for d in record['changes_for_this_event']}
    result = []
    for idx in (record['pre_state_index'], record['post_state_index']):
        if idx in changed:
            continue
        lines = str(trajectory['states'][idx].get('text') or '').splitlines()
        selected = set()
        for i, line in enumerate(lines):
            if any(key in line for key in ids) or any(prefix in line for prefix in prefixes):
                selected.update(range(max(0, i-1), min(len(lines), i+2)))
        result.append({'state_index': idx, 'role': 'pre-state' if idx == record['pre_state_index'] else 'post-state',
                       'unchanged_entity_lines': '\n'.join(lines[i] for i in sorted(selected)),
                       'scope': 'exact node-ID/label-prefix matched excerpts, not a full observation'})
    return result


def explicit_source_revisions(record):
    """Expose old/current evidence as named arrays instead of diff notation."""
    rows = []
    for change in record['changes_for_this_event']:
        old_lines, current_lines = [], []
        for line in change['diff'].splitlines():
            if line.startswith('-') and not line.startswith('---'):
                old_lines.append(line[1:].strip())
            elif line.startswith('+') and not line.startswith('+++'):
                current_lines.append(line[1:].strip())
        rows.append({'state_index': change['state_index'], 'role': change.get('role', 'source-state'),
                     'field': change['field'], 'obsolete_source_lines': old_lines,
                     'current_source_lines': current_lines})
    return rows


def append_current_observations(fields, revisions):
    out = copy.deepcopy(fields)
    for revision in revisions:
        field = 'overview' if revision['field'] == 'thoughts' else 'state_transition'
        label = 'recorded intent' if revision['field'] == 'thoughts' else 'observation'
        out[field] += f"\nCurrent {revision['role']} {label} (state {revision['state_index']}, corrected source): " + '\n'.join(revision['current_source_lines'])
    return out


CURRENT_OBSERVATIONS = ('\nCURRENT STATE OBSERVATIONS (authoritative for the listed fields; '
    'pre-state and post-state are independent, not a claim that values persist):\n')


def coalesce_current_evidence(fields, observations, trajectory, prior_version, revisions=()):
    """One current evidence view, not an ever-growing stack of source patches.

    Old observation lines survive only if they still occur exactly in that
    state's current source. Newly changed lines and neighboring source evidence
    are then unioned. No similarity validity, generated compression or edits to
    the unchanged historical interpretation. Each state keeps its own scope.
    """
    out = copy.deepcopy(fields)
    prior_observations = []
    parts = out['state_transition'].split(CURRENT_OBSERVATIONS)
    out['state_transition'] = parts[0]
    for block in parts[1:]:
        rows, end = json.JSONDecoder().raw_decode(block)
        if block[end:].strip() or not isinstance(rows, list):
            raise ValueError('Malformed stored current evidence; do not silently discard it')
        prior_observations.extend(rows)
    prefix = re.compile(r'^Prior-source interpretation \([a-f0-9]+\); '
                        r'(?:superseded ONLY for the corrected observations below|not authoritative for corrected field observations): ')
    for field in ('overview', 'state_transition'):
        while prefix.match(out[field]):
            out[field] = prefix.sub('', out[field], count=1)
    obsolete = {}
    for revision in revisions:
        obsolete.setdefault(revision['state_index'], set()).update(revision['obsolete_source_lines'])
    selected = {}
    for is_prior, obs in [(True, r) for r in prior_observations] + [(False, r) for r in observations]:
        idx, role = obs['state_index'], obs['role']
        current_lines = [line.strip() for line in trajectory['states'][idx]['text'].splitlines()]
        current_set = set(current_lines)
        kept = selected.setdefault((idx, role), set())
        kept.update(line.strip() for line in obs['current_evidence'].splitlines()
                    if line.strip() and line.strip() in current_set and
                    not (is_prior and line.strip() in obsolete.get(idx, set())))
    merged = []
    for (idx, role), selected_lines in sorted(selected.items()):
        # Current source order, exact duplicates once; node IDs/values retained.
        lines = list(dict.fromkeys(line.strip() for line in trajectory['states'][idx]['text'].splitlines()
                                  if line.strip() in selected_lines))
        if lines:
            merged.append({'state_index': idx, 'role': role, 'current_evidence': '\n'.join(lines)})
    version_match = re.search(r'^Prior-source interpretation \(([a-f0-9]+)\)', fields['overview'])
    version = version_match.group(1) if version_match else prior_version
    out['overview'] = f'Prior-source interpretation ({version}); superseded ONLY for the corrected observations below: ' + out['overview']
    out['state_transition'] = (f'Prior-source interpretation ({version}); not authoritative for corrected field observations: '
                               + out['state_transition'] + CURRENT_OBSERVATIONS + json.dumps(merged, ensure_ascii=False))
    return out


def changed_literal_values(revisions):
    """Narrow numeric/value= edits only; other edits require semantic model work."""
    values = set()
    for revision in revisions:
        old, new = '\n'.join(revision['obsolete_source_lines']), '\n'.join(revision['current_source_lines'])
        old_values = set(re.findall(r"\bvalue='([^']*)'", old))
        new_values = set(re.findall(r"\bvalue='([^']*)'", new))
        if old_values != new_values:
            values.update(old_values - new_values)
        else:
            # Ignore node references, and restrict the change to number tokens
            # inside otherwise identical text (not a semantic label change).
            stripped_old = re.sub(r'\[[^]]+\]', '', old)
            stripped_new = re.sub(r'\[[^]]+\]', '', new)
            if re.sub(r'\d+', '#', stripped_old) != re.sub(r'\d+', '#', stripped_new):
                return None
            values.update(set(re.findall(r'\b\d+\b', stripped_old)) - set(re.findall(r'\b\d+\b', stripped_new)))
    return values or None


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
        if not messages[0]['content'].startswith(('Update retrieval-ready event memories', 'Summarize only newly added observations')):
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

    def _build_note_entries(self, *, trajectory_dir, simplified_trajectory):
        if self.update_policy in ('delta_notes', 'source_append', 'delta_guarded'):
            old = self._load_stored_trajectory(simplified_trajectory['id'])
            changes = source_delta(old, simplified_trajectory)
            thought_changes = [d for d in changes or [] if d['field'] == 'thoughts']
            # Narrow second candidate: an additive workflow clarification is
            # merged into the existing procedure, not a wholesale note rewrite.
            # Other cases retain normal extraction and its exact request cache.
            if (changes and thought_changes and all(d['append_only'] for d in changes) and
                    all((d['state_index'], d['field']) in self.delta_observations for d in thought_changes)):
                tid = simplified_trajectory['id']
                procedure = copy.deepcopy(next(e for e in self.procedure_note_entries if e['trajectory_id'] == tid))
                hint = copy.deepcopy(next(e for e in self.hint_note_entries if e['trajectory_id'] == tid))
                for d in thought_changes:
                    fact = self.delta_observations[(d['state_index'], d['field'])]
                    procedure['content'] += '\n- Recorded workflow clarification (intent, not verified execution): ' + fact
                procedure['note_text'] = f"Title: {procedure['title']}\nDescription: {procedure['description']}\n{procedure['content']}".strip()
                self._append_model_call_metric({'channel': 'note_delta', 'status': 'merged',
                    'trajectory_id': tid, 'modified_notes': 1, 'unchanged_notes': 1,
                    'source_state_indexes': [d['state_index'] for d in thought_changes],
                    'mode': 'additive_workflow_only; reuse_generated_source_observation'})
                return procedure, hint
        return super()._build_note_entries(trajectory_dir=trajectory_dir, simplified_trajectory=simplified_trajectory)

    def _build_event_entries(self, *, trajectory_dir, simplified_trajectory):
        """Source-only maintenance keeps raw evidence and retires stale Events.

        The old Event text remains persisted for auditability, but invalidated
        entries are excluded by the shared retrieval path.  No model event
        extraction is performed for this policy.
        """
        if self.update_policy != 'source_only':
            return super()._build_event_entries(trajectory_dir=trajectory_dir,
                                                 simplified_trajectory=simplified_trajectory)
        old = self._load_stored_trajectory(simplified_trajectory['id'])
        changes = source_delta(old, simplified_trajectory) or []
        changed_states = {d['state_index'] for d in changes}
        changed_events = set()
        for spec in self._build_event_transition_specs(simplified_trajectory):
            if spec['pre_state_index'] in changed_states or spec['post_state_index'] in changed_states:
                changed_events.add(spec['event_id'])
        previous = {e['event_id']: e for e in self.event_entries
                    if e.get('trajectory_id') == simplified_trajectory['id']}
        entries = []
        for spec in self._build_event_transition_specs(simplified_trajectory):
            entry = copy.deepcopy(previous.get(spec['event_id']))
            if entry is None:
                raise ValueError(f'source_only requires persisted event {spec["event_id"]}')
            if spec['event_id'] in changed_events:
                entry['validity_status'] = 'invalidated_source_change'
                entry['invalidated_source_state_indexes'] = sorted(
                    set(entry.get('invalidated_source_state_indexes', [])) | changed_states)
                entry['invalidated_by_policy'] = 'source_only'
            elif entry.get('validity_status') != 'invalidated_source_change':
                # A different-state correction does not rebuild old retired
                # events. Only actual reconstruction can make them current.
                entry['validity_status'] = 'current'
                entry.pop('invalidated_source_state_indexes', None)
                entry.pop('invalidated_by_policy', None)
            entries.append(entry)
        self._append_model_call_metric({'channel': 'source_only_invalidation', 'status': 'success',
            'trajectory_id': simplified_trajectory['id'], 'invalidated_event_ids': sorted(changed_events),
            'changed_source_state_indexes': sorted(changed_states), 'event_model_calls': 0})
        return entries

    async def _edit_event_group(self, trajectory, specs):
        previous = self._load_stored_trajectory(trajectory['id'])
        delta = source_delta(previous, trajectory)
        if delta is None or not delta:
            raise ValueError('delta candidate requires local text/thoughts change only')
        old_entries = {e['event_id']: e for e in self.event_entries if e['trajectory_id'] == trajectory['id']}
        relevant = [d for d in delta if any(d['state_index'] in (s['pre_state_index'], s['post_state_index']) for s in specs)]
        records = []
        for spec in specs:
            old = old_entries[spec['event_id']]
            records.append({k: spec[k] for k in ('event_id', 'pre_state_index', 'post_state_index',
                                                'local_action', 'pre_url', 'post_url', 'pre_thoughts', 'post_thoughts')})
            records[-1]['existing_memory'] = {k: old[k] for k in ('overview', 'state_transition')}
            records[-1]['changes_for_this_event'] = [
                {**d, 'role': 'pre-state' if d['state_index'] == spec['pre_state_index'] else 'post-state'}
                for d in relevant if d['state_index'] in (spec['pre_state_index'], spec['post_state_index'])]
        if self.update_policy in ('source_overlay', 'source_coalesced'):
            if not self.current_state_evidence or any(d['field'] != 'text' for d in relevant):
                raise ValueError('source_overlay requires current-state evidence and text-only revision')
            self._append_model_call_metric({'channel': 'event_delta', 'status': 'merged',
                'mode': 'versioned_source_overlay_v12' if self.update_policy == 'source_overlay' else 'current_source_coalesced_v13', 'trajectory_id': trajectory['id'],
                'event_ids': [r['event_id'] for r in records], 'source_delta': relevant,
                'before': [r['existing_memory'] for r in records],
                'after': [r['existing_memory'] for r in records],
                'validity': 'Prior interpretation is explicitly version-labeled by the common state-evidence publisher, NOT reused as current assertion'})
            return [copy.deepcopy(r['existing_memory']) for r in records]
        messages = [{'role': 'system', 'content':
            'Update retrieval-ready event memories using exact source revisions. Do not re-extract whole pages. '
            'Return JSON only: {"events":[{"event_id":"...","edits":[{"field":"state_transition",'
            '"old":"exact unique substring to replace","new":"replacement"}]}]}. '
            'Return ALL requested events, not just the first one. The mandatory output skeleton lists every ID. '
            'Allowed fields: overview, state_transition. For additive facts prefer old="" and a short new sentence; '
            'do NOT echo an entire unchanged paragraph. Replace a literal substring only if its assertion is invalidated. '
            'Preserve all unaffected facts, labels, actions and outcomes. Never copy the diff mechanically. '
            'Treat added visible statuses as observations at their specified state, not evidence of task success. '
            'Distinguish pre-state from post-state: a correction to pre-state does NOT imply the action caused it. '
            'Workflow thoughts are intended checks, not proof that a check was performed. '
            'Keep exact answer-bearing strings; mention a relevant added observation in each affected event. '
            'Use edits=[] only when the source revision has no effect on that event. No reasoning or extra keys.'},
            {'role': 'user', 'content': json.dumps({'goal': trajectory['goal'], 'outcome': trajectory.get('outcome'),
                'actions': trajectory.get('actions'), 'events': records,
                'mandatory_output_skeleton': {'events': [{'event_id': s['event_id'], 'edits': []} for s in specs]},
                'required_event_count': len(specs)}, ensure_ascii=False)}]
        additive = all(d['append_only'] for d in relevant)
        if not additive and self.update_policy != 'source_append':
            # A two-output contract repeatedly omitted its second event. Use
            # independent atomic edits for replacements; no generated IDs.
            # Unsupported/invalid output falls back for this event only.
            results = []
            for record, spec in zip(records, specs):
                try:
                    fields = await self._edit_literal_event(trajectory, record)
                except Exception as exc:
                    self._append_model_call_metric({'channel': 'event_delta', 'status': 'fallback',
                        'event_ids': [spec['event_id']], 'reason': str(exc)[:500]})
                    fields = (await self._extract_event_group_async(trajectory_dir=self.workspace_dir / 'trajectories' / trajectory['id'],
                                simplified_trajectory=trajectory, specs=[spec]))[0]
                results.append(fields)
            return results
        if additive:
            # An observation belongs to a changed source state, not to a group
            # output slot. Generate it once and map it to each affected event
            # using the exact pre/post dependencies already known by the code.
            messages = [{'role': 'system', 'content':
                'Summarize only newly added observations for the changed sources. '
                'Existing event fields are immutable and will be preserved by code. '
                'Return JSON only: {"facts":["short newly observed fact"]}. '
                'Return exactly one fact STRING per changed source in required_sources, in the SAME order, no duplicate event output. '
                'Source identifiers and event references are attached by deterministic code; do not generate them. '
                'Summarize only added (+) evidence, never repeat existing event paragraphs or unchanged context. '
                'Quote complete literal UI status/label text exactly, including punctuation (do not rename or split the label). '
                'For an added observation say it is visible/recorded, not that it changed from an unknown prior value. '
                'Keep values and ordering requirements. '
                'Do not add causality, validation success, persistence into another state, or task completion unless the added evidence explicitly states it. '
                'A thought is intended workflow, not proof of an executed check. '
                'Do not output overview, state_transition, edits, events, or extra keys.'},
                {'role': 'user', 'content': json.dumps({'goal': trajectory['goal'], 'outcome': trajectory.get('outcome'),
                    'actions': trajectory.get('actions'), 'events': records,
                    'required_sources': [{'state_index': d['state_index'], 'source_field': d['field'],
                        'added_text': str(trajectory['states'][d['state_index']].get(d['field']) or '')[
                            len(str(previous['states'][d['state_index']].get(d['field']) or '')):]}
                        for d in relevant]}, ensure_ascii=False)}]
        tokens = self._event_group_input_tokens(messages)
        if tokens > int(os.environ['LME_EVENT_MAX_INPUT_TOKENS']):
            raise ValueError('delta context exceeds safe input budget')
        if self.update_policy in ('source_append', 'delta_guarded'):
            # Explicit trivial comparator: no learned extraction is necessary
            # to copy an already concise added fact. Non-additive revisions
            # retain the ordinary extraction fallback, not unsafe appending.
            if not additive:
                raise ValueError('source_append supports additive changes only')
            facts = [str(trajectory['states'][d['state_index']].get(d['field']) or '')[
                     len(str(previous['states'][d['state_index']].get(d['field']) or '')):].strip()
                     for d in relevant]
            response = json.dumps({'facts': facts})
        else:
            response = await self._call_controller_text_async(messages, disable_thinking=True,
                        max_completion_tokens=len(specs) * int(os.environ['LME_EVENT_OUTPUT_TOKENS']), reject_truncated=True)
        result = None
        for candidate in delta_json_candidates(response):
            try:
                if additive:
                    facts = json.loads(candidate)['facts']
                    if not isinstance(facts, list) or len(facts) != len(relevant) or not all(isinstance(f, str) and f.strip() for f in facts):
                        continue
                    observations = [{'state_index': d['state_index'], 'source_field': d['field'], 'fact': f}
                                    for d, f in zip(relevant, facts)]
                    wanted = {(d['state_index'], d['field']) for d in relevant}
                    actual = [(d['state_index'], d['source_field']) for d in observations]
                    if len(actual) != len(wanted) or set(actual) != wanted:
                        continue
                    parsed = [{'event_id': record['event_id'], 'observations': [o for o in observations
                               if (o['state_index'], o['source_field']) in
                                  {(d['state_index'], d['field']) for d in record['changes_for_this_event']}]} for record in records]
                    result = [merge_additive_observations(record, edit['observations']) for record, edit in zip(records, parsed)]
                    for obs in observations:
                        self.delta_observations[(obs['state_index'], obs['source_field'])] = obs['fact']
                else:
                    parsed = json.loads(candidate)['events']
                    if [e['event_id'] for e in parsed] != [s['event_id'] for s in specs]:
                        continue
                    result = [merge_event_edits(record['existing_memory'], edit['edits']) for record, edit in zip(records, parsed)]
                break
            except (ValueError, KeyError, TypeError):
                continue
        if result is None:
            raise ValueError('invalid delta output or ambiguous edit anchor')
        self._append_model_call_metric({'channel': 'event_delta', 'status': 'merged',
            'trajectory_id': trajectory['id'], 'event_ids': [s['event_id'] for s in specs],
            'mode': ('deterministic_source_append' if self.update_policy in ('source_append', 'delta_guarded') else
                     'append_generated_observations' if additive else 'literal_replacement'),
            'input_tokens_preflight': tokens, 'source_delta': relevant,
            'edits': parsed, 'before': [r['existing_memory'] for r in records], 'after': result})
        return result

    async def _edit_literal_event(self, trajectory, record):
        revisions = explicit_source_revisions(record)
        old_literals = changed_literal_values(revisions)
        old_blob = '\n'.join(record['existing_memory'].values())
        if self.update_policy == 'delta_guarded' and old_literals and not any(v in old_blob for v in old_literals):
            # The original event never asserted this changed literal. Preserve
            # its full content; add the new fact only to the exact source role.
            result = append_current_observations(record['existing_memory'], revisions)
            self._append_model_call_metric({'channel': 'event_delta', 'status': 'merged',
                'mode': 'absent_literal_source_merge_v11', 'trajectory_id': trajectory['id'],
                'event_ids': [record['event_id']], 'source_delta': record['changes_for_this_event'],
                'before': [record['existing_memory']], 'after': [result],
                'absent_old_literals': sorted(old_literals),
                'scope': 'literal numeric/value changes only; paraphrase validity requires review'})
            return result
        messages = [{'role': 'system', 'content':
            'Update retrieval-ready event memories for ONE transition after a SOURCE CORRECTION. '
            'Return JSON only: {"edits":[{"field":"state_transition","old":"exact unique substring","new":"replacement"}]}. '
            'Only overview and state_transition are editable. Use the smallest unique literal anchor; '
            'do not rewrite unchanged paragraphs or omit unrelated facts. old="" appends an additional observation. '
            'Remove stale assertions invalidated by the revised source. Preserve old values when they refer to '
            'a different, unchanged state or to the attempted action/task goal. '
            'A source correction is NOT an extra environment action. Explicitly distinguish observed pre-state, '
            'attempted action and observed post-state; do not claim the action caused a conflicting corrected value. '
            'The diff is authoritative for the changed observation; current thoughts can contain mistaken beliefs. '
            'current_source_lines are the authoritative CURRENT value of the specified state; '
            'obsolete_source_lines are historical source errors, NOT another event state. '
            'Local unchanged evidence constrains the other state; never propagate a correction into that state. '
            'Even if an existing summary omitted the changed field, append its short, state-scoped new value. '
            'Thought changes concern recorded intent, not proof of execution. Preserve exact answer-bearing strings. '
            'No event IDs, reasoning, extra keys or full event object.'},
            {'role': 'user', 'content': json.dumps({'goal': trajectory['goal'],
                'transition': {k: record[k] for k in ('pre_state_index', 'post_state_index', 'local_action')},
                'existing_memory': record['existing_memory'],
                'current_unchanged_neighbor_evidence': local_unchanged_evidence(trajectory, record),
                'source_revisions': revisions,
                'instruction': 'Apply these corrections now. Return nonempty minimal literal edits; '
                               'the final memory must explicitly state the corrected observed value at its state, '
                               'and must not assert the obsolete value at that same state.'}, ensure_ascii=False)}]
        retract = self.update_policy == 'delta_retract'
        if retract:
            messages[0]['content'] = (
                'Update retrieval-ready event memories by selecting obsolete text to DELETE. '
                'Code supplies corrected facts separately with exact state references; you never generate new facts. '
                'Return JSON only: {"remove":[{"field":"state_transition","text":"exact unique obsolete substring"}]}. '
                'Allowed fields: overview, state_transition. Return only literal substrings of existing_memory. '
                'The obsolete_source_lines are no longer valid evidence at the specified pre/post-state. '
                'Delete the smallest clause or phrase asserting that obsolete value AT THAT STATE. '
                'Preserve unrelated facts, actions, field names, failures and outcomes, and assertions about '
                'the other unchanged state or intended action. If a sentence combines two fields but only one '
                'is invalid, remove the stale field from that joint assertion, not the other field. '
                'Do not delete entire paragraphs. Use remove=[] if there is no invalidated assertion. '
                'No replacement strings, explanations, IDs or extra keys.')
            payload = json.loads(messages[1]['content'])
            payload['source_revisions'] = [{k: v for k, v in revision.items() if k != 'current_source_lines'}
                                           for revision in revisions]
            payload['instruction'] = 'Return obsolete literal text spans to remove; code adds corrected source facts.'
            messages[1]['content'] = json.dumps(payload, ensure_ascii=False)
        tokens = self._event_group_input_tokens(messages)
        if tokens > int(os.environ['LME_EVENT_MAX_INPUT_TOKENS']):
            raise ValueError('literal delta context exceeds safe input budget')
        response = await self._call_controller_text_async(messages, disable_thinking=True,
            max_completion_tokens=int(os.environ['LME_EVENT_OUTPUT_TOKENS']), reject_truncated=True)
        result, edits = None, None
        for candidate in delta_json_candidates(response):
            try:
                parsed = json.loads(candidate)
                if retract:
                    removals = parsed['remove']
                    if not isinstance(removals, list) or any(set(r) != {'field', 'text'} or not r['text'] for r in removals):
                        raise ValueError('invalid removal spans')
                    edits = [{'field': r['field'], 'old': r['text'], 'new': ''} for r in removals]
                else:
                    edits = parsed['edits']
                result = merge_event_edits(record['existing_memory'], edits)
                if retract:
                    for revision in revisions:
                        new_source = '\n'.join(revision['current_source_lines'])
                        field = 'overview' if revision['field'] == 'thoughts' else 'state_transition'
                        label = 'recorded intent' if revision['field'] == 'thoughts' else 'observation'
                        result[field] += f"\nCurrent {revision['role']} {label} (state {revision['state_index']}, corrected source): " + new_source
                elif result == record['existing_memory']:
                    result = None
                    raise ValueError('non-additive source correction produced no memory edit')
                break
            except (ValueError, TypeError, KeyError):
                result = None
        if result is None:
            raise ValueError('invalid single-event literal edits or ambiguous anchor')
        self._append_model_call_metric({'channel': 'event_delta', 'status': 'merged',
            'mode': 'delete_spans_then_source_v10' if retract else 'literal_atomic_explicit_v8', 'trajectory_id': trajectory['id'],
            'event_ids': [record['event_id']], 'source_delta': record['changes_for_this_event'],
            'input_tokens_preflight': tokens, 'edits': edits,
            'before': [record['existing_memory']], 'after': [result]})
        return result

    async def _extract_event_fields_batch_async(self, *, trajectory_dir, simplified_trajectory, transition_specs):
        rows = await self._extract_update_event_fields_async(trajectory_dir=trajectory_dir,
            simplified_trajectory=simplified_trajectory, transition_specs=transition_specs)
        if not getattr(self, 'current_state_evidence', False):
            return rows
        prior = self._load_stored_trajectory(simplified_trajectory['id'])
        changes = source_delta(prior, simplified_trajectory)
        if changes is None:
            return rows
        for spec, row in zip(transition_specs, rows):
            relevant = [{**d, 'role': 'pre-state' if d['state_index'] == spec['pre_state_index'] else 'post-state'}
                        for d in changes if d['field'] == 'text' and not d['append_only'] and
                        d['state_index'] in (spec['pre_state_index'], spec['post_state_index'])]
            if not relevant:
                continue
            record = {**spec, 'changes_for_this_event': relevant}
            observations = [{'state_index': d['state_index'], 'role': d['role'],
                             'current_evidence': '\n'.join(d['current_source_lines'])}
                            for d in explicit_source_revisions(record)]
            observations.extend({'state_index': d['state_index'], 'role': d['role'],
                                 'current_evidence': d['unchanged_entity_lines']}
                                for d in local_unchanged_evidence(simplified_trajectory, record))
            observations.sort(key=lambda d: d['state_index'])
            if self.update_policy == 'source_coalesced':
                merged = coalesce_current_evidence(row, observations, simplified_trajectory, digest(prior)[:16],
                                                   explicit_source_revisions(record))
                self._append_model_call_metric({'channel': 'current_evidence_merge', 'status': 'success',
                    'event_id': spec['event_id'], 'before_chars': sum(len(v) for v in row.values()),
                    'after_chars': sum(len(v) for v in merged.values()),
                    'mode': 'retain_only_exact_current_source_lines; union_by_state; no_model'})
                row.clear()
                row.update(merged)
                continue
            if self.update_policy == 'source_overlay':
                version = digest(prior)[:16]
                row['overview'] = f'Prior-source interpretation ({version}); superseded ONLY for the corrected observations below: ' + row['overview']
                row['state_transition'] = f'Prior-source interpretation ({version}); not authoritative for corrected field observations: ' + row['state_transition']
            row['state_transition'] += (CURRENT_OBSERVATIONS +
                json.dumps(observations, ensure_ascii=False))
        return rows

    async def _extract_update_event_fields_async(self, *, trajectory_dir, simplified_trajectory, transition_specs):
        if self.update_policy in ('b3', 'fresh'):
            return await super()._extract_event_fields_batch_async(trajectory_dir=trajectory_dir,
                simplified_trajectory=simplified_trajectory, transition_specs=transition_specs)
        keys = [self.event_dependency_key(simplified_trajectory, spec) for spec in transition_specs]
        rows = [copy.deepcopy(self.event_outputs.get(key)) for key in keys]
        # Only adjacent dirty transitions share a request; isolated dirty events
        # execute immediately, without waiting for any future arrival.
        for start in range(len(rows)):
            if rows[start] is not None: continue
            end = start + 1
            if end < len(rows) and rows[end] is None: end += 1
            fields = None
            if self.update_policy in ('delta', 'delta_notes', 'source_append', 'delta_retract', 'delta_guarded', 'source_overlay', 'source_coalesced'):
                try:
                    fields = await self._edit_event_group(simplified_trajectory, transition_specs[start:end])
                except Exception as exc:
                    self._append_model_call_metric({'channel': 'event_delta', 'status': 'fallback',
                        'event_ids': [s['event_id'] for s in transition_specs[start:end]], 'reason': str(exc)[:500]})
            if fields is None:
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
    # Legacy persisted snapshots can be loaded by an older memory class that
    # predates exact-input construction embedding reuse.  Initialize the
    # runtime-only memo before hydrating persisted vectors; this preserves the
    # original vectors and cache keys without re-keying old model outputs.
    if not hasattr(memory, '_construction_embedding_memo'):
        memory._construction_embedding_memo = {}
    embedding_key = getattr(memory, '_construction_embedding_key', None)
    if embedding_key is None:
        # Older loaded classes predate the helper method itself.  Reproduce
        # the current actual-input key format locally so persisted vectors can
        # be reused without semantic or cross-model collisions.
        def embedding_key(text):
            config = (getattr(memory, 'embedding_model', None),
                      getattr(memory, 'embedding_base_url', None),
                      getattr(memory, 'embedding_max_input_tokens', None),
                      os.getenv('LME_EMBEDDING_TOKENIZER_MODEL'),
                      'default-dimensions/float/normalized-v1', text)
            return hashlib.sha256(json.dumps(config, ensure_ascii=False).encode('utf-8')).hexdigest()
    for record in jsonl(memory.workspace_dir / 'model_calls.jsonl'):
        if record.get('query_invocation_id') or record.get('channel') != 'controller' or record.get('status') != 'success': continue
        if not record.get('messages') or record.get('finish_reason') != 'stop': continue
        key = request_key(record['messages'], record['model'], record['base_url'], record['max_completion_tokens'],
                          record['temperature'], record['top_p'], record['top_k'], record['enable_thinking'])
        memory.exact_requests[key] = record['response_text']
    memory.event_outputs = {}
    provenance = memory.workspace_dir / 'matched_update_cache.json'
    if provenance.exists():
        saved = json.loads(provenance.read_text())
        if saved['signature'] != matched_signature(memory):
            raise ValueError('Source construction semantics differ: prepare a matched snapshot; never re-key old outputs')
        saved_policy = saved.get('output_policy')
        if saved_policy and saved_policy != getattr(memory, 'update_policy', None) and getattr(memory, 'update_policy', None) not in ('b3', 'fresh'):
            raise ValueError('Update-derived event cache belongs to another policy; do not reuse across candidate branches')
        memory.event_outputs = saved['event_outputs']
    # Legacy snapshots lack construction-bound event keys. Their recorded exact
    # requests remain legal, but old output fields must not be re-keyed here.
    memory.initial_event_keys = set(memory.event_outputs)
    # The source snapshot's vectors are legal exact-input cache entries for BOTH.
    for entries, vectors, field in [(memory.raw_state_entries, memory.raw_state_embeddings, 'slice_axtree_text'),
                                  (memory.event_entries, memory.event_embeddings, 'description'),
                                  (memory.procedure_note_entries, memory.procedure_note_embeddings, 'note_text'),
                                  (memory.hint_note_entries, memory.hint_note_embeddings, 'note_text')]:
        for entry, vector in zip(entries, vectors):
            text = memory._truncate_for_embedding(entry[field])
            memory._construction_embedding_memo[embedding_key(text)] = vector.copy()
    memory.update_event_outputs = 0
    memory.update_notes_regenerated = 0
    memory.delta_observations = {}


def prepare_matched_snapshot(args):
    """Rebuild only selected partitions and certify an unchanged B3 replay.

    Other domain histories are retained, not rebuilt or counted as fresh work.
    Exact old requests are reusable ONLY when their actual message/config key
    matches. Per-event dependency keys are saved only for outputs produced by
    the present construction path.
    """
    out = args.output / 'memory_state'
    if out.exists():
        raise FileExistsError(out)
    shutil.copytree(args.source, out)
    memory = load_memory(out)
    memory.__class__ = UpdateRunbook
    memory.update_policy = 'b3'
    memory.configure_runtime()
    seed_caches(memory)
    start = time.perf_counter()
    offset = len(jsonl(out / 'model_calls.jsonl'))
    bound_outputs = {}
    for tid in args.prepare_trajectories:
        tr = memory._load_stored_trajectory(tid)
        bundle = memory._build_trajectory_artifact_bundle(trajectory_dir=out / 'trajectories' / tid,
                                                          simplified_trajectory=tr)
        replace_partition(memory, tr, bundle)
        for spec, entry in zip(memory._build_event_transition_specs(tr), bundle['event_entries']):
            bound_outputs[memory.event_dependency_key(tr, spec)] = {k: entry[k] for k in ('overview', 'state_transition')}
        save_memory(memory, out)
        print(json.dumps({'prepared_trajectory': tid, 'events': len(bundle['event_entries'])}), flush=True)
    save_json(out / 'matched_update_cache.json', {'signature': matched_signature(memory),
        'trajectory_ids': args.prepare_trajectories, 'event_outputs': bound_outputs,
        'source_trajectories': {tid: digest(memory._load_stored_trajectory(tid)) for tid in args.prepare_trajectories}})
    before = len(jsonl(out / 'model_calls.jsonl'))
    seed_caches(memory)  # Rehydrate from actual persisted requests, not live-only cache.
    for tid in args.prepare_trajectories:
        tr = memory._load_stored_trajectory(tid)
        memory._build_trajectory_artifact_bundle(trajectory_dir=out / 'trajectories' / tid, simplified_trajectory=tr)
    verification_calls = jsonl(out / 'model_calls.jsonl')[before:]
    real = [r for r in verification_calls if r.get('channel') in ('controller', 'embedding')]
    metrics = {'reprepared_trajectories': args.prepare_trajectories, 'historical_base': str(args.source),
        'elapsed_s_including_no_change_check': time.perf_counter() - start,
        'no_change_real_calls': len(real), 'signature': matched_signature(memory),
        'scope': 'matched partition preparation, NOT full cold construction'}
    save_json(args.output / 'preparation_metrics.json', metrics)
    save_json(args.output / 'preparation_calls.json', jsonl(out / 'model_calls.jsonl')[offset:])
    if real:
        raise RuntimeError('Unchanged B3 rebuild made real requests; source cache cannot be used for a strong comparison')
    print(json.dumps(metrics), flush=True)


def clear_build_caches(memory):
    """Make one touched-trajectory rebuild a cold Fresh/B0 reference.

    The shared starting snapshot and all its evidence remain intact. Only the
    cloned method's controller-response, event-output, and construction-vector
    caches are cleared; untouched trajectory partitions are preserved.
    """
    memory.exact_requests = {}
    memory.event_outputs = {}
    memory.initial_event_keys = set()
    memory._construction_embedding_memo = {}
    memory.update_event_outputs = 0
    memory.update_notes_regenerated = 0


def persist_update_provenance(memory, trajectory, bundle, prior_provenance):
    """Bind this run's actual published outputs to this run's source, once.

    Historical cache entries keep their original keys. We never relabel an old
    snapshot as if it had been built for a new source or request configuration.
    Exact request/vector persistence remains identical for all policies.
    """
    saved = copy.deepcopy(prior_provenance)
    for spec, entry in zip(memory._build_event_transition_specs(trajectory), bundle['event_entries']):
        memory.event_outputs[memory.event_dependency_key(trajectory, spec)] = {
            k: copy.deepcopy(entry[k]) for k in ('overview', 'state_transition')}
    saved['event_outputs'] = memory.event_outputs
    saved['source_trajectories'][trajectory['id']] = digest(trajectory)
    if trajectory['id'] not in saved['trajectory_ids']:
        saved['trajectory_ids'].append(trajectory['id'])
    saved['output_policy'] = memory.update_policy
    saved['current_state_evidence'] = memory.current_state_evidence
    saved['update_runner_sha256'] = RUNNER_SHA256
    save_json(memory.workspace_dir / 'matched_update_cache.json', saved)


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


def changed_trajectory(source, case, trajectory_id='1ad1af4b', state_index=4, patch_text=None, append_source=None, append_id=None, revision_count=1, revision_spec=None):
    """Materialize one controlled update for a selected complete trajectory.

    The old screen experiment silently hard-coded one web trajectory and state.
    Keep the patch deliberately small and source-backed, but make the identity,
    location, and wording explicit in the run manifest so multi-trajectory
    paired updates remain auditable.
    """
    # Preserve the narrow legacy test/helper call changed_trajectory(source, case, None).
    if trajectory_id is None:
        trajectory_id = '1ad1af4b'
    if case == 'append' and append_source is None and isinstance(trajectory_id, Path):
        append_source, trajectory_id = trajectory_id, '1ad1af4b'
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
    if revision_spec is not None:
        if case != 'literal_revision':
            raise ValueError('revision_spec requires literal_revision case')
        if revision_spec['trajectory_id'] != trajectory_id:
            raise ValueError('revision spec trajectory does not match selected source')
        positions = []
        for edit in revision_spec['source_edits']:
            idx, field = edit['state_index'], edit['field']
            if field not in ('text', 'thoughts'):
                raise ValueError('only source text/thoughts revisions are supported')
            old, new = edit['old'], edit['new']
            value = trajectory['states'][idx].get(field) or ''
            if not old or value.count(old) != edit.get('count', 1):
                raise ValueError(f'literal revision anchor mismatch at {idx}/{field}')
            trajectory['states'][idx][field] = value.replace(old, new)
            positions.append(idx)
        return trajectory, {**revision_spec, 'kind': 'controlled_literal_source_revision',
                            'state_index': min(positions), 'state_indices': sorted(set(positions)),
                            'revision_count': len(set(positions)),
                            'dirty_event_state_indexes': sorted(set(positions))}
    if case == 'trajectory_growth':
        # Controlled same-trajectory growth: append one newly arrived state to
        # an already published trajectory.  The state reuses the last observed
        # page as source evidence and adds an explicit arrival marker; it is
        # deliberately distinct from cross-trajectory append.
        last = copy.deepcopy(original['states'][-1])
        next_index = int(last.get('state_index', len(original['states']) - 1)) + 1
        marker = patch_text or '[controlled arrival] follow-up observation appended to the existing trajectory'
        last['state_index'] = next_index
        last['step'] = int(last.get('step', next_index - 1)) + 1
        last['action'] = '<follow-up observation>'
        last['thoughts'] = (last.get('thoughts') or '') + ' ' + marker
        last['text'] = (last.get('text') or '') + '\n' + marker
        trajectory['states'].append(last)
        trajectory['actions'] = [state.get('action') or '<none>' for state in trajectory['states'][1:]]
        trajectory['outcome'] = None
        return trajectory, {'kind': 'controlled_same_trajectory_growth',
                            'trajectory_id': trajectory_id,
                            'state_index': next_index,
                            'patch': marker,
                            'arrived_states': 1,
                            'no_new_trajectory': True,
                            'dirty_event_state_indexes': [len(original.get('states', [])) - 1]}
    if case in ('state_revision', 'workflow_revision') and int(revision_count) > 1:
        count = max(1, int(revision_count))
        indices = list(range(state_index, min(state_index + count, len(original.get('states', [])) - 1)))
        base = patch_text or ("[correction] status 'Title validation: saved', visible" if case == 'state_revision' else 'Workflow clarification: verify the required field before proceeding to the next form field.')
        patches = [f"{base} [local revision {idx}]" for idx in indices]
        for idx, patch in zip(indices, patches):
            if case == 'state_revision':
                trajectory['states'][idx]['text'] += '\n' + patch
            else:
                trajectory['states'][idx]['thoughts'] = (trajectory['states'][idx].get('thoughts') or '') + ' ' + patch
        return trajectory, {'kind': 'controlled_multi_state_correction' if case == 'state_revision' else 'controlled_multi_workflow_revision',
                            'trajectory_id': trajectory_id, 'state_index': indices[0], 'state_indices': indices,
                            'patch': patches[0], 'patches': patches, 'revision_count': len(indices),
                            'dirty_event_state_indexes': indices}
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


def _quality_checks(source_memory, updated_memory, original, changed, workload, case, trajectory_id, state_index, policy, reused_event_ids=None):
    """Cheap source-grounded checks run for every update, not a QA claim."""
    source_states = {s['state_index']: s for s in original.get('states', [])}
    changed_state = changed['states'][state_index]
    patches = list(workload.get('patches') or ([workload.get('patch')] if workload.get('patch') else []))
    if case == 'literal_revision':
        patches.extend(edit.get('new', '') for edit in workload.get('source_edits', []) if edit.get('new'))
    raw_after = [e for e in updated_memory.raw_state_entries if e.get('trajectory_id') == trajectory_id]
    raw_other_before = [_entry_digest(e) for e in source_memory.raw_state_entries if e.get('trajectory_id') != trajectory_id]
    raw_other_after = [_entry_digest(e) for e in updated_memory.raw_state_entries if e.get('trajectory_id') != trajectory_id]
    event_before = {e['event_id']: e for e in source_memory.event_entries if e.get('trajectory_id') == trajectory_id}
    event_after = {e['event_id']: e for e in updated_memory.event_entries if e.get('trajectory_id') == trajectory_id}
    if workload.get('kind') == 'controlled_same_trajectory_growth':
        old_last = original['states'][-1]['state_index']
        new_last = changed['states'][-1]['state_index']
        dirty_ids = {f'event_{old_last:04d}_{new_last:04d}'}
    else:
        changed_positions = workload.get('state_indices') or [state_index]
        dirty_indexes = {i for position in changed_positions for i in (position - 1, position)
                         if 0 <= i < len(original.get('states', [])) - 1}
        dirty_ids = {f"event_{original['states'][i]['state_index']:04d}_{original['states'][i+1]['state_index']:04d}" for i in dirty_indexes}
    # Validate only events that the dependency cache actually reused. During
    # trajectory growth the conservative key includes global action/length
    # context, so unchanged-looking transitions may correctly be recomputed.
    reused_ids = sorted(set(reused_event_ids or ())) if policy in ('ours', 'delta', 'delta_notes', 'source_append', 'delta_retract', 'delta_guarded', 'source_overlay', 'source_coalesced') else []
    reused_equal = all(_entry_digest(event_before[eid]) == _entry_digest(event_after.get(eid, {})) for eid in reused_ids)
    touched_positions = workload.get('state_indices') or [state_index]
    old_texts = [source_states.get(index, {}).get('text', '') for index in touched_positions]
    target_text = '\n'.join(str(e.get('slice_axtree_text', '')) for e in raw_after)
    target_events = [e for e in updated_memory.event_entries if e.get('trajectory_id') == trajectory_id]
    target_notes = [e for e in (updated_memory.procedure_note_entries + updated_memory.hint_note_entries)
                    if e.get('trajectory_id') == trajectory_id]
    published_blob = target_text + '\n' + '\n'.join(json.dumps(e, ensure_ascii=False) for e in target_events + target_notes)
    # The source patch is expected to be visible in the rebuilt published views.
    new_fact_present = bool(patches) and all(patch in published_blob for patch in patches)
    # Original visible evidence remains present for both update kinds; workflow
    # edits additionally retain the original thought/action context in events.
    old_fact_retained = all(not text or text[:80] in published_blob for text in old_texts)
    untouched_retained = sorted(raw_other_before) == sorted(raw_other_after)
    expected_event_count = len(changed.get('states', [])) - 1
    event_coverage = (set(event_before).issubset(set(event_after)) and len(event_after) == expected_event_count)
    reuse_check = reused_equal if policy in ('ours', 'delta', 'delta_notes', 'source_append', 'delta_retract', 'delta_guarded', 'source_overlay', 'source_coalesced') else True
    # Exclude copied source metadata (raw, pre/post_thoughts) from the derived
    # check. Persisted source evidence alone cannot certify generated memory.
    derived_events = {e['event_id']: '\n'.join(e.get(k, '') for k in ('overview', 'state_transition')) for e in target_events}
    derived_notes = '\n'.join(e.get('note_text', '') for e in target_notes)
    source_only_invalid = {e['event_id'] for e in target_events
                           if e.get('validity_status') == 'invalidated_source_change'}
    source_only_expected = dirty_ids if policy == 'source_only' else set()
    if all('Title validation: saved' in patch for patch in patches):
        def has_change(text):
            return bool(re.search(r'title\s+validation\s*:\s*saved', text, re.I))
    elif all('verify the required field' in patch for patch in patches):
        def has_change(text):
            # Require the verification action and its ordering in the SAME
            # sentence/bullet. A heading "validation rules" elsewhere plus a
            # required-field bullet is not the added workflow clarification.
            return any(re.search(r'\b(verif\w*|check\w*|ensur\w*|validate|validating|validated)\b', part)
                       and 'required' in part and re.search(r'before|prior', part)
                       and re.search(r'next|proceed|moving|another', part)
                       for part in re.split(r'[\n.!?]', text.lower()))
    else:
        def has_change(text):
            return bool(patches) and all(patch.casefold() in text.casefold() for patch in patches)
    derived_hits = {eid: has_change(derived_events.get(eid, '')) for eid in sorted(dirty_ids)}
    notes_change = has_change(derived_notes) if case == 'workflow_revision' else None
    if policy == 'source_only':
        # Source-only intentionally does not rewrite Event prose. Its gate is
        # that the new raw observation is published, affected Events are
        # explicitly retired, and unaffected Events/Notes survive. Retrieval
        # filtering is checked separately on the reloaded memory.
        checks_pass = bool(new_fact_present and source_only_invalid == source_only_expected and
                           untouched_retained and event_coverage)
    else:
        checks_pass = bool(derived_hits and all(derived_hits.values()) and notes_change is not False and
                           untouched_retained and event_coverage and reuse_check)
    literal_rules = []
    if case == 'literal_revision' and policy == 'source_coalesced':
        # Coalesced Events deliberately retain prior prose for auditability.
        # Evaluate changed facts only inside the authoritative CURRENT block;
        # a stale value in the prior interpretation is not a current-fact leak.
        current_event_text = {}
        for eid, text in derived_events.items():
            current_event_text[eid] = text.split(CURRENT_OBSERVATIONS, 1)[1] if CURRENT_OBSERVATIONS in text else ''
        for rule in workload.get('derived_rules', []):
            text = current_event_text.get(rule['target'], '') if rule['target'] != 'notes' else derived_notes
            required = {p: bool(re.search(p, text, re.I | re.S)) for p in rule.get('required', [])}
            forbidden = {p: bool(re.search(p, text, re.I | re.S)) for p in rule.get('forbidden', [])}
            literal_rules.append({'target': rule['target'], 'required_hits': required,
                                  'forbidden_hits': forbidden,
                                  'pass': all(required.values()) and not any(forbidden.values())})
        derived_hits = {r['target']: r['pass'] for r in literal_rules if r['target'] != 'notes'}
        notes_change = next((r['pass'] for r in literal_rules if r['target'] == 'notes'), None)
        checks_pass = bool(literal_rules and all(r['pass'] for r in literal_rules) and
                           untouched_retained and event_coverage and reuse_check)
    elif case == 'literal_revision' and policy != 'source_only':
        for rule in workload.get('derived_rules', []):
            text = (derived_notes if rule['target'] == 'notes' else
                    derived_events.get(rule['target'], ''))
            required = {p: bool(re.search(p, text, re.I | re.S)) for p in rule.get('required', [])}
            forbidden = {p: bool(re.search(p, text, re.I | re.S)) for p in rule.get('forbidden', [])}
            literal_rules.append({'target': rule['target'], 'required_hits': required,
                                  'forbidden_hits': forbidden,
                                  'pass': all(required.values()) and not any(forbidden.values())})
        derived_hits = {r['target']: r['pass'] for r in literal_rules if r['target'] != 'notes'}
        notes_change = next((r['pass'] for r in literal_rules if r['target'] == 'notes'), None)
        checks_pass = bool(literal_rules and all(r['pass'] for r in literal_rules) and
                           untouched_retained and event_coverage and reuse_check)
    elif case == 'literal_revision' and policy == 'source_only':
        literal_rules = [{'target': 'raw_state', 'required_hits': {'new_fact': new_fact_present},
                          'forbidden_hits': {'affected_events_current': bool(source_only_invalid & source_only_expected)},
                          'pass': checks_pass}]
        derived_hits = {}
        notes_change = None
    return {
        'new_fact_present': new_fact_present,
        'old_fact_retained': old_fact_retained,
        'untouched_facts_retained': untouched_retained,
        'event_source_coverage': event_coverage,
        'reused_joint_events_complete': reused_equal if policy in ('ours', 'delta', 'delta_notes', 'source_append', 'delta_retract', 'delta_guarded', 'source_overlay', 'source_coalesced') else f'not_applicable_{policy}',
        'dirty_event_ids': sorted(dirty_ids),
        'reused_event_count': len(reused_ids),
        'unchanged_candidate_event_count': len(set(event_before) - dirty_ids),
        'fixed_reader_regression': 'not_run',
        'derived_event_change_hits': derived_hits,
        'derived_notes_change_hit': notes_change,
        'notes_change_required': case == 'workflow_revision' or any(r['target'] == 'notes' for r in literal_rules),
        'old_fact_semantics': ('local source replacement; role-specific old/new assertions require manual review'
                               if case == 'literal_revision' else 'additive controlled revision; no old fact is revoked'),
        'literal_derived_rules': literal_rules,
        'derived_automated_checks_pass': checks_pass,
        'quality_scope': 'generated overview/state_transition and note_text only; necessary lexical checks, NOT semantic certification',
        'quality_pass': None,
        'semantic_review': 'pending',
    }


def run_one(args, case, policy):
    provenance_path = args.source / 'matched_update_cache.json'
    if not provenance_path.exists():
        raise ValueError('Matched source required: use --prepare-trajectories for the target partitions first')
    provenance = json.loads(provenance_path.read_text())
    if args.trajectory_id not in provenance['trajectory_ids']:
        raise ValueError('Target partition has no matched construction provenance')
    original_source = json.loads((args.source / 'trajectories' / args.trajectory_id / 'trajectory.json').read_text())
    if digest(original_source) != provenance['source_trajectories'][args.trajectory_id]:
        raise ValueError('Source trajectory changed since matched cache was constructed')
    out = args.output / f'{case}-{policy}'
    if out.exists(): raise FileExistsError(out)
    out.mkdir(parents=True)
    shutil.copytree(args.source, out / 'memory_state')
    memory = load_memory(out / 'memory_state')
    memory.__class__ = UpdateRunbook
    memory.update_policy = policy
    memory.current_state_evidence = args.current_state_evidence
    setup_started = time.perf_counter()
    memory.configure_runtime()
    seed_caches(memory)
    if policy == 'fresh':
        clear_build_caches(memory)
    setup_s = time.perf_counter() - setup_started
    trajectory, workload = changed_trajectory(args.source, case, args.trajectory_id, args.state_index,
                                              args.patch_text, args.append_source, args.append_id, args.revision_count,
                                              json.loads(args.revision_file.read_text()) if args.revision_file else None)
    save_json(out / 'update_input.json', {'trajectory': trajectory, 'workload': workload})
    previous_calls = len(jsonl(memory.workspace_dir / 'model_calls.jsonl'))
    started_epoch = time.time()
    started = time.perf_counter()
    bundle = memory._build_trajectory_artifact_bundle(trajectory_dir=memory.workspace_dir / 'trajectories' / trajectory['id'],
                                                      simplified_trajectory=trajectory)
    build_elapsed = time.perf_counter() - started
    publish_started = time.perf_counter()
    replace_partition(memory, trajectory, bundle)
    save_memory(memory, memory.workspace_dir)
    persist_update_provenance(memory, trajectory, bundle, provenance)
    loaded = load_memory(memory.workspace_dir)
    assert loaded.inserted_trajectory_ids == memory.inserted_trajectory_ids
    assert loaded.event_entries == memory.event_entries
    assert all(np.array_equal(getattr(loaded, key), getattr(memory, key)) for key in
               ('raw_state_embeddings', 'event_embeddings', 'procedure_note_embeddings', 'hint_note_embeddings'))
    elapsed = time.perf_counter() - started
    publication_elapsed = time.perf_counter() - publish_started
    effective_state_index = int(workload.get('state_index', args.state_index))
    reused_event_ids = set()
    if policy in ('ours', 'delta', 'delta_notes', 'source_append', 'delta_retract', 'delta_guarded', 'source_overlay', 'source_coalesced'):
        for spec in memory._build_event_transition_specs(trajectory):
            key = memory.event_dependency_key(trajectory, spec)
            if key in memory.initial_event_keys:
                reused_event_ids.add(spec['event_id'])
    quality = _quality_checks(load_memory(args.source), loaded,
                              json.loads((args.source / 'trajectories' / args.trajectory_id / 'trajectory.json').read_text()),
                              trajectory, workload, case, args.trajectory_id, effective_state_index, policy, reused_event_ids)
    calls = jsonl(memory.workspace_dir / 'model_calls.jsonl')[previous_calls:]
    c = [r for r in calls if r['channel'] == 'controller']
    e = [r for r in calls if r['channel'] == 'embedding']
    metrics = {'policy': policy, 'case': case, 'scope': 'adapted_AgentRunbookR_local_update',
        'starting_snapshot': str(args.source),
        'starting_cache': ('independent clone; controller and construction-embedding caches cleared for touched-partition Fresh/B0 rebuild'
                           if policy == 'fresh' else 'independent clones; exact requests and vectors preserved equally'),
        'setup_load_and_seed_s_excluded': setup_s, 'update_to_queryable_publish_s': elapsed,
        'started_epoch': started_epoch, 'completed_epoch': time.time(),
        'artifact_build_s': build_elapsed, 'publication_and_reload_s': publication_elapsed,
        'runner_sha256': RUNNER_SHA256,
        'delta_version': ('source-only-invalidate-v4' if policy == 'source_only' else 'current-source-coalesced-v13' if policy == 'source_coalesced' else 'source-overlay-v12' if policy == 'source_overlay' else 'source-guarded-v11' if policy == 'delta_guarded' else 'source-retract-v10' if policy == 'delta_retract' else
                          'source-edit-v8' if policy in ('delta', 'delta_notes') else None),
        'source_append_comparator': policy == 'source_append',
        'current_state_evidence': args.current_state_evidence,
        'source_overlay_comparator': policy == 'source_overlay',
        'source_only_invalidation': policy == 'source_only',
        'reextracted_event_outputs': memory.update_event_outputs, 'regenerated_notes': memory.update_notes_regenerated,
        'llm_calls': len(c), 'llm_input_tokens_known': sum(r.get('prompt_tokens') or 0 for r in c),
        'llm_output_tokens_known': sum(r.get('completion_tokens') or 0 for r in c),
        'event_llm_elapsed_sum_s_not_wall': sum(r.get('elapsed_seconds', 0) for r in c if r.get('call_mode') == 'async_text'),
        'note_llm_elapsed_sum_s_not_wall': sum(r.get('elapsed_seconds', 0) for r in c if r.get('call_mode') != 'async_text'),
        'embedding_calls': len(e), 'embedding_vectors': sum(r['input_text_count'] for r in e),
        'embedding_tokens_known': sum(r.get('prompt_tokens') or 0 for r in e),
        'unknown_usage_calls': sum(r.get('prompt_tokens') is None for r in c+e),
        'api_failed_calls': sum(r['status'] == 'failed' for r in c+e),
        'exact_request_hits': sum(r['channel'] == 'update_request_cache' for r in calls),
        'dependency_reused_event_ids': sorted(reused_event_ids),
        'embedding_hits': sum(r.get('cache_hits', 0) for r in calls if r['channel'] == 'build_embedding_cache'),
        'load_verified': True, 'event_count': len(memory.event_entries), 'note_count': len(memory.procedure_note_entries) + len(memory.hint_note_entries),
        'published_event_chars': sum(len(e['description']) for e in memory.event_entries),
        'published_note_chars': sum(len(e['note_text']) for e in memory.procedure_note_entries + memory.hint_note_entries),
        'current_evidence_blocks': sum(e['state_transition'].count(CURRENT_OBSERVATIONS) for e in memory.event_entries),
        'edited_event_outputs': sum(len(r.get('event_ids', [])) for r in calls if r['channel'] == 'event_delta' and r['status'] == 'merged'),
        'edited_notes': sum(r.get('modified_notes', 0) for r in calls if r['channel'] == 'note_delta'),
        'delta_fallback_groups': sum(r['channel'] == 'event_delta' and r['status'] == 'fallback' for r in calls),
        'primary_metric': 'total_LLM_input_plus_output_tokens',
        'matched_construction_signature': provenance['signature'],
        'qa_status': 'derived_checks_passed_pending_semantics_and_reader' if quality['derived_automated_checks_pass'] else 'derived_checks_failed',
        'quality_checks': quality, 'trajectory_id': args.trajectory_id, 'state_index': effective_state_index,
        'revision_count': int(workload.get('revision_count', 1)), 'state_indices': workload.get('state_indices', [effective_state_index]),
        'raw_path': str(out)}
    save_json(out / 'update_metrics.json', metrics)
    save_json(out / 'update_calls.json', calls)
    source_mem = load_memory(args.source)
    save_json(out / 'derived_quality_review.json', {
        'workload': workload,
        'old_events': [e for e in source_mem.event_entries if e['trajectory_id'] == args.trajectory_id],
        'new_events': [e for e in loaded.event_entries if e['trajectory_id'] == args.trajectory_id],
        'old_notes': [e for e in source_mem.procedure_note_entries + source_mem.hint_note_entries if e['trajectory_id'] == args.trajectory_id],
        'new_notes': [e for e in loaded.procedure_note_entries + loaded.hint_note_entries if e['trajectory_id'] == args.trajectory_id],
        'checks': quality})
    print(json.dumps(metrics), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--prepare-trajectories', nargs='+', help='Prepare matched partitions, then verify zero-call unchanged B3 rebuild')
    parser.add_argument('--append-source', type=Path)
    parser.add_argument('--append-id', default='4ba5e9cb')
    parser.add_argument('--trajectory-id', default='1ad1af4b')
    parser.add_argument('--state-index', type=int, default=4)
    parser.add_argument('--patch-text', default=None, help='Controlled source-backed patch text; used for state/workflow revision')
    parser.add_argument('--revision-file', type=Path, help='Small literal source-edit manifest and predeclared derived checks')
    parser.add_argument('--revision-count', type=int, default=1, help='For state/workflow revision screen, apply this many adjacent state corrections')
    parser.add_argument('--current-state-evidence', action='store_true', help='Shared current pre/post source annotation for B3 and candidates, before Embedding')
    parser.add_argument('--policy-order', nargs='+', choices=['fresh', 'b3', 'ours', 'source_only', 'delta', 'delta_notes', 'source_append', 'delta_retract', 'delta_guarded', 'source_overlay', 'source_coalesced'], default=['b3', 'ours'],
                        help='Paired update policies; fresh rebuilds the touched partition without build caches')
    parser.add_argument('--cases', nargs='+', default=['append', 'state_revision', 'workflow_revision'])
    args = parser.parse_args()
    args.source, args.output = args.source.resolve(), args.output.resolve()
    construction_config = args.source / 'construction_config.json'
    if construction_config.exists():
        config = json.loads(construction_config.read_text())
        if config.get('event_max_input_tokens'):
            os.environ['LME_EVENT_MAX_INPUT_TOKENS'] = str(config['event_max_input_tokens'])
    # Match the persisted source snapshot rather than silently changing the
    # request shape during an update comparison.  A paired event request uses
    # len(specs) * LME_EVENT_OUTPUT_TOKENS, so the per-event value is read from
    # construction_config (the expanded20 snapshot uses 1024, i.e. 2048/group).
    config = json.loads(construction_config.read_text()) if construction_config.exists() else {}
    for key, value in {
        'LME_TEXT_ONLY': '1',
        'LME_EVENT_GROUP_SIZE': str(config.get('event_group_size', 2)),
        'LME_EVENT_OUTPUT_TOKENS': str(config.get('event_output_tokens', 1024)),
        'LME_EVENT_CONCURRENCY': str(config.get('event_concurrency') or 1),
        'LME_REUSE_BUILD_EMBEDDING': '1',
        'LME_RECORD_FULL_REQUESTS': '1',
        'LME_EMBEDDING_TOKENIZER_MODEL': '/data/predator/ly/Mem/models/Qwen3-Embedding-8B',
    }.items():
        os.environ[key] = value
    if config.get('event_state_max_chars'):
        os.environ['LME_EVENT_STATE_MAX_CHARS'] = str(config['event_state_max_chars'])
    else:
        os.environ.pop('LME_EVENT_STATE_MAX_CHARS', None)
    if args.prepare_trajectories:
        prepare_matched_snapshot(args)
        return
    for case in args.cases:
        for policy in args.policy_order:
            run_one(args, case, policy)


if __name__ == '__main__': main()
