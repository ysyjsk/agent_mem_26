#!/usr/bin/env python3
"""Offline structural checks. Never calls a model or marks research complete.

Use --current for the registered audit inputs, or select corrected artifacts
with --manifest, --reader-dir and --main-table/--cost-table. Exit 1 means the
selected evidence needs attention, not that research should stop. A passing
report is not proof of semantic quality, fairness or statistical equivalence.
"""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


class Audit:
    def __init__(self, root, contract):
        self.root = Path(root)
        self.contract = contract
        self.issues = []
        self.observations = []
        self.files = {}
        self.expected_history = {}

    def path(self, value):
        p = Path(value)
        return p if p.is_absolute() else self.root / p

    def issue(self, code, path, detail):
        self.issues.append({'code': code, 'path': str(path), 'detail': detail})

    def read(self, path, jsonl=False):
        p = self.path(path)
        try:
            raw = p.read_bytes()
            self.files[str(p)] = hashlib.sha256(raw).hexdigest()
            text = raw.decode('utf-8-sig')
            return [json.loads(x) for x in text.splitlines() if x.strip()] if jsonl else json.loads(text)
        except (OSError, ValueError) as exc:
            self.issue('unreadable_evidence', p, str(exc))
            return None

    def manifest(self, path):
        manifest = self.read(path)
        official = self.read(self.contract['official_haystack'])
        questions = self.read(self.contract['official_questions'], jsonl=True)
        if not isinstance(manifest, dict) or not isinstance(official, dict) or questions is None:
            return
        expected = {}
        for q in questions:
            if q['id'] in official:
                expected.setdefault(q['domain'], set()).update(official[q['id']])
        self.expected_history = expected
        declared = manifest.get('data', {})
        for domain in self.contract['domains']:
            required = expected.get(domain, set())
            ids = declared.get(domain, {}).get('trajectory_ids', [])
            if not required:
                self.issue('official_scope_unknown', path, domain)
            elif set(ids) != required or len(ids) != len(set(ids)):
                self.issue('history_scope_mismatch', path, {
                    'domain': domain, 'actual': len(set(ids)), 'required': len(required),
                    'missing': len(required-set(ids)), 'extra': len(set(ids)-required)})
        self.observations.append({'manifest': str(path), 'scope': manifest.get('scope'),
                                  'note': 'Checks declared IDs; inspect loaded snapshots/haystacks as well.'})

    @staticmethod
    def image_count(value):
        if isinstance(value, dict):
            return int(value.get('type') in ('image_url', 'image_path', 'input_image')) + sum(Audit.image_count(v) for v in value.values())
        if isinstance(value, list):
            return sum(Audit.image_count(v) for v in value)
        return 0

    def reader(self, directory):
        p = self.path(directory)
        requests = self.read(p/'prompt_rows.jsonl', jsonl=True)
        args = self.read(p/'run_args.json')
        if requests is not None:
            if not requests:
                self.issue('empty_reader_evidence', p, 'No actual serialized requests.')
            bad = sum('messages' not in r for r in requests)
            if bad:
                self.issue('actual_messages_missing', p, bad)
            image_requests = sum(self.image_count(r.get('messages', [])) > 0 for r in requests)
            if image_requests:
                self.issue('text_only_violation', p, {'requests_with_images': image_requests, 'requests': len(requests)})
            self.observations.append({'reader': str(p), 'requests': len(requests), 'image_requests': image_requests})
        if isinstance(args, dict):
            for key, expected in self.contract['reader'].items():
                if args.get(key) != expected:
                    self.issue('reader_config_mismatch', p, {'field': key, 'actual': args.get(key), 'expected': expected})
            expected_ids = self.expected_history.get(args.get('domain'))
            if expected_ids:
                if requests and any(set(r.get('haystack_ids', [])) != expected_ids for r in requests):
                    self.issue('reader_history_mismatch', p, 'Actual question haystack differs from full official domain history.')
                snapshot = args.get('load_memory_dir')
                if not snapshot:
                    self.issue('snapshot_provenance_missing', p, 'Saved source snapshot is required for maintenance evaluation.')
                else:
                    index = self.read(self.path(snapshot)/'index.json')
                    if isinstance(index, dict) and set(index.get('inserted_trajectory_ids', [])) != expected_ids:
                        self.issue('snapshot_history_mismatch', snapshot, 'Loaded memory does not cover the full domain history.')
        effective = self.read(p/'effective_runtime.json')
        if isinstance(effective, dict):
            if effective.get('origin') != 'observed_runtime':
                self.issue('runtime_not_observed', p, 'Capture effective values in the running entrypoint, not by copying a manifest.')
            environment = effective.get('environment', {})
            for key, expected in self.contract['common_environment'].items():
                if environment.get(key) != expected:
                    self.issue('runtime_config_mismatch', p, {'field': key, 'actual': environment.get(key), 'expected': expected})
        if isinstance(args, dict) and args.get('load_memory_dir'):
            snapshot=self.path(args['load_memory_dir'])
            config_path=snapshot/'memory_config.json'
            if config_path.exists():
                config=self.read(config_path)
                if isinstance(config, dict) and config.get('memory_type') == 'agentrunbook_r':
                    runtime=self.read(p/'effective_query_runtime.json')
                    if isinstance(runtime, dict):
                        settings=runtime.get('settings',{})
                        for key, expected in self.contract.get('query_runtime',{}).items():
                            if settings.get(key,{}).get('effective') != expected:
                                self.issue('loaded_query_runtime_mismatch',p,{'field':key,'expected':expected})
                    trace=snapshot/'model_calls.jsonl'
                    if trace.exists() and requests:
                        ids={r.get('query_invocation_id') for r in requests}-{None}
                        calls=self.read(trace,jsonl=True)
                        selected=[r for r in calls or [] if r.get('query_invocation_id') in ids and r.get('channel')=='controller']
                        for call in selected:
                            if call.get('enable_thinking') is not False:
                                self.issue('query_controller_thinking_mismatch',trace,call.get('record_id'))
                            if call.get('request_shape',{}).get('image_count',0):
                                self.issue('query_controller_image_violation',trace,call.get('record_id'))

    def table(self, path, main=False):
        p = self.path(path)
        try:
            raw = p.read_bytes()
            self.files[str(p)] = hashlib.sha256(raw).hexdigest()
            reader = csv.DictReader(raw.decode('utf-8-sig').splitlines())
            columns = set(reader.fieldnames or [])
            rows = list(reader)
        except (OSError, ValueError, csv.Error) as exc:
            self.issue('unreadable_table', p, str(exc))
            return
        if not rows:
            self.issue('empty_table', p, 'No measured rows.')
            return
        fields = self.contract['cost_components']
        missing = set(fields + ['update_plus_query_llm_tokens']) - columns
        if missing:
            self.issue('cost_components_missing', p, sorted(missing))
        else:
            for index, row in enumerate(rows, 2):
                def number(k):
                    try:
                        value = float(row[k])
                        return value if math.isfinite(value) and value >= 0 else None
                    except (TypeError, ValueError):
                        return None
                values = [number(k) for k in fields]
                total = number('update_plus_query_llm_tokens')
                if any(v is None for v in values):
                    if total is not None:
                        self.issue('unknown_usage_has_numeric_total', p, {'row': index})
                elif total is None or abs(sum(values)-total) > 0.01:
                    self.issue('cost_total_mismatch', p, {'row': index, 'components_sum': sum(values), 'reported': total})
        if main:
            by_domain = {}
            for row in rows:
                label = row.get('policy') or row.get('method')
                by_domain.setdefault(row.get('domain'), set()).add(label)
            for domain in self.contract['domains']:
                for method, aliases in self.contract['required_main_methods'].items():
                    if not by_domain.get(domain, set()).intersection(aliases):
                        self.issue('required_method_missing', p, {'domain': domain, 'method': method})
        self.observations.append({'table': str(p), 'rows': len(rows), 'role': 'public_main' if main else 'cost'})

    def queue(self, path):
        data = self.read(path)
        if not isinstance(data, dict):
            return
        tasks = data.get('tasks', [])
        by_id = {x['id']: x for x in tasks}
        if len(by_id) != len(tasks):
            self.issue('duplicate_task_id', path, 'Task IDs must be unique.')
        for name in self.contract['required_tasks']:
            if name not in by_id or by_id[name].get('status') == 'deferred':
                self.issue('required_task_removed_or_deferred', path, name)
        for task in tasks:
            for dep in task.get('depends_on', []):
                if dep not in by_id:
                    self.issue('unknown_dependency', path, {'task': task['id'], 'dependency': dep})
                elif task.get('status') == 'done' and by_id[dep].get('status') != 'done':
                    self.issue('completion_dependency_mismatch', path, {'task': task['id'], 'dependency': dep, 'status': by_id[dep].get('status')})
        remaining = [t['id'] for t in tasks if t['id'] in self.contract['required_tasks'] and t.get('status') != 'done']
        if by_id.get('PACKAGE', {}).get('status') == 'done' and remaining:
            self.issue('premature_research_completion', path, remaining)
        self.observations.append({'queue': str(path), 'remaining_required_tasks': remaining,
                                  'note': 'Task labels alone never prove completion.'})

    def result(self):
        return {'status': 'needs_attention' if self.issues else 'selected_structural_checks_passed',
                'scope': 'Offline structural checks only; not semantic quality, fair-comparison or complete-research certification.',
                'issue_counts': dict(Counter(i['code'] for i in self.issues)),
                'issues': self.issues, 'observations': self.observations, 'artifact_sha256': self.files,
                'next_action': 'Diagnose issues; preserve valid stages; repair and rerun affected units only. Continue other authorized work.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--contract', default='execution/experiment_contract.json')
    parser.add_argument('--current', action='store_true', help='Audit registered evidence; does not execute experiments.')
    parser.add_argument('--manifest', help='Check full official history coverage of this data manifest.')
    parser.add_argument('--reader-dir', action='append', default=[])
    parser.add_argument('--main-table')
    parser.add_argument('--cost-table', action='append', default=[])
    parser.add_argument('--check-queue', action='store_true')
    parser.add_argument('--report', help='Optional new report path; refuses to overwrite existing files.')
    args = parser.parse_args()
    cp = Path(args.contract)
    cp = cp if cp.is_absolute() else args.root/cp
    contract = json.loads(cp.read_text(encoding='utf-8-sig'))
    audit = Audit(args.root, contract)
    if args.current:
        current = contract['audit_inputs']
        args.manifest = args.manifest or current['manifest']
        args.main_table = args.main_table or current['main_table']
        args.cost_table += current.get('cost_tables', [])
        for pattern in current['reader_globs']:
            paths = sorted(args.root.glob(pattern))
            if not paths:
                audit.issue('reader_group_missing', pattern, 'No matching Reader artifacts.')
            args.reader_dir.extend(str(p) for p in paths)
        args.check_queue = True
    if not (args.manifest or args.main_table or args.cost_table or args.reader_dir or args.check_queue):
        parser.error('Choose --current or explicit artifacts.')
    if args.manifest:
        audit.manifest(args.manifest)
    for path in sorted(set(args.reader_dir)):
        audit.reader(path)
    if args.main_table:
        audit.table(args.main_table, main=True)
    for path in sorted(set(args.cost_table)):
        audit.table(path)
    if args.check_queue:
        audit.queue('execution/queue.json')
    result = audit.result()
    if args.report:
        dest = audit.path(args.report)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    print(json.dumps({k: result[k] for k in ('status','scope','issue_counts','next_action')}, ensure_ascii=False, indent=2))
    return int(bool(audit.issues))


if __name__ == '__main__':
    raise SystemExit(main())
