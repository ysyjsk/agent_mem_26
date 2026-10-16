"""Regression checks for observed execution failures; no model dependency."""
import csv
import importlib.util
import json
import tempfile
import unittest
import os
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('verify_evidence', ROOT/'execution/verify_evidence.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
RUNTIME_SPEC = importlib.util.spec_from_file_location('focused_runtime', ROOT/'tools/focused_runtime.py')
RUNTIME = importlib.util.module_from_spec(RUNTIME_SPEC)
RUNTIME_SPEC.loader.exec_module(RUNTIME)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.contract = json.loads((ROOT/'execution/experiment_contract.json').read_text(encoding='utf-8'))
        self.audit = MODULE.Audit(self.root, self.contract)

    def write(self, path, data, jsonl=False):
        p = self.root/path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(('\n'.join(json.dumps(r) for r in data) if jsonl else json.dumps(data))+'\n', encoding='utf-8')

    def reader(self, messages):
        self.write('run/prompt_rows.jsonl', [{'messages': messages}], jsonl=True)
        self.write('run/run_args.json', self.contract['reader'])
        self.write('run/effective_runtime.json', {'origin': 'observed_runtime', 'environment': self.contract['common_environment']})

    def codes(self):
        return {i['code'] for i in self.audit.issues}

    def test_serialized_images_override_text_only_declaration(self):
        self.reader([{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,fixture'}}]}])
        self.audit.reader('run')
        self.assertIn('text_only_violation', self.codes())

    def test_matching_text_request_passes_structural_checks(self):
        self.reader([{'role': 'user', 'content': [{'type': 'text', 'text': 'question'}]}])
        self.audit.reader('run')
        self.assertEqual([], self.audit.issues)

    def test_runtime_replaces_inherited_visual_mode_and_records_actual_values(self):
        self.write('execution/experiment_contract.json', self.contract)
        with patch.dict(os.environ, {'LME_TEXT_ONLY':'0', 'LME_LEXICAL_BACKFILL':'0'}):
            actual = RUNTIME.configure(self.root)
            self.assertEqual('1', os.environ['LME_TEXT_ONLY'])
            argv = RUNTIME.reader_arguments(actual)
            self.assertIn('--reader-disable-thinking', argv)
            self.assertEqual('2048', argv[argv.index('--max-completion-tokens')+1])
            RUNTIME.record_observed_runtime(self.root, self.root/'run', actual, argv)
            observation = json.loads((self.root/'run/effective_runtime.json').read_text())
            self.assertEqual('1', observation['environment']['LME_LEXICAL_BACKFILL'])
            self.assertEqual('observed_runtime', observation['origin'])

    def test_missing_actual_messages_not_silently_treated_as_text(self):
        self.reader([])
        self.write('run/prompt_rows.jsonl', [{'prompt_messages': []}], jsonl=True)
        self.audit.reader('run')
        self.assertIn('actual_messages_missing', self.codes())

    def test_full_scope_comes_from_official_mapping(self):
        self.write(self.contract['official_haystack'], {'w': ['a','b'], 'e': ['c','d']})
        self.write(self.contract['official_questions'], [{'id':'w','domain':'web'}, {'id':'e','domain':'enterprise'}], jsonl=True)
        self.write('manifest.json', {'scope':'complete Small', 'data':{'web':{'trajectory_ids':['a']},'enterprise':{'trajectory_ids':['c','d']}}})
        self.audit.manifest('manifest.json')
        self.assertIn('history_scope_mismatch', self.codes())

    def test_full_manifest_cannot_hide_partial_loaded_snapshot(self):
        self.reader([{'role':'user','content':'question'}])
        args = dict(self.contract['reader'], domain='web', load_memory_dir='snapshot')
        self.write('run/run_args.json', args)
        self.write('snapshot/index.json', {'inserted_trajectory_ids':['a']})
        self.audit.expected_history = {'web': {'a','b'}}
        self.audit.reader('run')
        self.assertIn('snapshot_history_mismatch', self.codes())

    def table(self, values):
        with (self.root/'cost.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values))
            writer.writeheader()
            writer.writerow(values)
        self.audit.table('cost.csv')

    def test_total_must_include_controller(self):
        row = dict.fromkeys(self.contract['cost_components'], 1)
        row['update_plus_query_llm_tokens'] = 4
        self.table(row)
        self.assertIn('cost_total_mismatch', self.codes())

    def test_unknown_usage_not_converted_to_zero(self):
        row = dict.fromkeys(self.contract['cost_components'], 1)
        row['query_controller_input_tokens'] = ''
        row['update_plus_query_llm_tokens'] = 5
        self.table(row)
        self.assertIn('unknown_usage_has_numeric_total', self.codes())

    def test_required_baseline_cannot_be_deferred_under_complete_package(self):
        tasks = [{'id': n, 'status': 'done', 'depends_on': []} for n in self.contract['required_tasks']]
        next(t for t in tasks if t['id']=='PUBLIC_BASELINES')['status'] = 'deferred'
        next(t for t in tasks if t['id']=='PACKAGE')['depends_on'] = ['PUBLIC_BASELINES']
        self.write('queue.json', {'tasks': tasks})
        self.audit.queue('queue.json')
        self.assertIn('required_task_removed_or_deferred', self.codes())
        self.assertIn('premature_research_completion', self.codes())


if __name__ == '__main__':
    unittest.main()
