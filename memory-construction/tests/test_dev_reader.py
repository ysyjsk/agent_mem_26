"""CPU-only contracts for fixed source questions and evaluator/Reader isolation."""
from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from workflow_memory.backends import ModelResponse
from workflow_memory.config import write_json
from workflow_memory.construction import build_fresh
from workflow_memory.ir import canonical_json, normalize_trajectory, stable_hash
from workflow_memory.local_backends import TransformersQwenBackend

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
spec = importlib.util.spec_from_file_location("dev_reader_runner", Path(__file__).parents[1] / "tools/run_dev_reader.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class _CharTokenizer:
    @staticmethod
    def encode(text, **kwargs):
        return list(text.encode("utf-8"))

    @staticmethod
    def decode(tokens, **kwargs):
        return bytes(tokens).decode("utf-8")


class _FixtureReader(TransformersQwenBackend):
    """Use the real Reader prompt wrapper, but no model in CPU contract tests."""
    def __post_init__(self):
        super().__post_init__()
        self._tokenizer, self._model = _CharTokenizer(), object()
        self.requests = []

    def complete(self, request, **kwargs):
        self.requests.append(request)
        return ModelResponse(text="unknown", usage={"prompt_tokens": 11, "completion_tokens": 1},
                             raw={"batch_size": 1}, finish_reason="stop", request_fingerprint=request.fingerprint)


class DevReaderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def workload(self):
        source = {"trajectory_id": "t", "environment_family": "web", "steps": [
            {"source_sequence": index, "action": f"click('command-{index}')", "post_state": {"url": f"https://example.test/{index}"}}
            for index in range(12)]}
        events = normalize_trajectory(source)
        source_file = self.root / "source.jsonl"
        source_file.write_text(canonical_json(source) + "\n", encoding="utf-8")
        return {"source_file": str(source_file), "source_sha256": reader.file_hash(source_file), "windows": [
            {"window_id": "t-prefix12", "trajectory_id": "t", "event_count": 12,
             "event_ids": [event.event_id for event in events], "checkpoint_prefix_lengths": [4, 8, 12]}]}

    def test_questions_are_deterministic_source_fields_and_prefix_scoped(self):
        workload = self.workload()
        first = reader.prepare_questions(workload)
        second = reader.prepare_questions(workload)
        self.assertEqual(first, second)
        reader.verify_questions(first)
        questions = first["questions"]
        self.assertEqual([question["category"] for question in questions], ["observed_url", "attempt_action", "workflow_order"])
        self.assertEqual(questions[0]["reference"]["expected"], "https://example.test/3")
        self.assertEqual(questions[1]["reference"]["expected"], "click('command-7')")
        self.assertEqual(questions[2]["reference"]["expected"], ["click('command-10')", "click('command-11')"])
        self.assertEqual(first["reader_settings"]["retrieval_budget"], 8)
        self.assertIn("not official", first["purpose"])
        for question in questions:
            self.assertNotIn("t:", question["question"])
            for source in question["reference"]["source_fields"]:
                self.assertLess(int(source["event_id"].split(":")[1]), question["checkpoint_prefix_length"])

    def test_changed_source_and_changed_manifest_hash_are_rejected(self):
        workload = self.workload()
        manifest = reader.prepare_questions(workload)
        manifest["questions"][0]["question"] += "tamper"
        with self.assertRaisesRegex(ValueError, "manifest hash"):
            reader.verify_questions(manifest)
        Path(workload["source_file"]).write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            reader.prepare_questions(workload)

    def test_reader_prompt_has_only_question_retrieved_memory_and_ordinals(self):
        snapshot = build_fresh(normalize_trajectory({"trajectory_id": "private-id", "steps": [
            {"action": "click actual evidence", "post_state": {"url": "https://memory.test"}}]}),
            config={"storage_path": str(self.root / "snapshot.sqlite3")})
        backend = _FixtureReader("/not-loaded/qwen", device="cpu")
        recording = reader.RecordingBackend(backend, self.root / "reader")
        question = {"question": "What action was attempted at source step 1?", "reference": {
            "expected": "SECRET_GOLD_ONLY", "source_fields": [{"event_id": "GOLD_SOURCE_ID"}]}}
        result = reader.answer_snapshot(snapshot, question, backend, recording,
                 {"retrieval_budget": 1, "output_tokens": 256, "max_input_tokens": 8192})
        self.assertEqual(result["answer"], "unknown")
        self.assertEqual(len(backend.requests), 1)
        request = backend.requests[0]
        prompt = request.messages[0]["content"]
        self.assertNotIn("SECRET_GOLD_ONLY", prompt)
        self.assertNotIn("GOLD_SOURCE_ID", prompt)
        self.assertNotIn("private-id:0", prompt)
        self.assertNotIn("source_refs", prompt)
        self.assertIn('"source_positions": [1]', prompt)
        self.assertLessEqual(result["evidence_count"], 1)
        self.assertEqual(request.max_tokens, 256)
        self.assertEqual(recording.calls[0]["input_tokens"], 11)
        self.assertEqual(recording.calls[0]["output_tokens"], 1)

    def test_unknown_and_missing_evidence_are_real_failures_not_reference_fallback(self):
        snapshot = build_fresh(normalize_trajectory({"trajectory_id": "t", "steps": [{"action": "open"}]}),
                               config={"storage_path": str(self.root / "snapshot.sqlite3")})
        backend = _FixtureReader("/not-loaded/qwen", device="cpu")
        recording = reader.RecordingBackend(backend, self.root / "reader")
        question = {"question": "zqxj nevermatches", "reference": {"expected": "open"}}
        result = reader.answer_snapshot(snapshot, question, backend, recording,
                 {"retrieval_budget": 8, "output_tokens": 256, "max_input_tokens": 8192})
        self.assertEqual(result["reader_evidence"], [])
        self.assertEqual(result["answer"], "unknown")
        self.assertEqual(reader.score_answer(result["answer"], question), {"proxy_exact": 0, "proxy_token_f1": 0.0, "unknown": True})
        self.assertNotIn('"open"', backend.requests[0].messages[0]["content"])

    def test_exact_scalar_and_ordered_workflow_scoring_are_conservative(self):
        scalar = {"reference": {"expected": "click('a74')"}}
        self.assertEqual(reader.score_answer("`click('a74')`", scalar)["proxy_exact"], 1)
        self.assertEqual(reader.score_answer("clicked a74", scalar)["proxy_exact"], 0)
        self.assertGreater(reader.score_answer("click('a75')", scalar)["proxy_token_f1"], 0)
        array = {"reference": {"expected": ["open", "save"]}}
        self.assertEqual(reader.score_answer('```json\n["open", "save"]\n```', array)["proxy_exact"], 1)
        self.assertEqual(reader.score_answer('["save", "open"]', array)["proxy_exact"], 0)

    def test_identical_json_scalar_tokens_are_not_misclassified_by_python_type(self):
        for value in ("false", "true", "0", "12", "02139", "null"):
            with self.subTest(value=value):
                question = {"reference": {"expected": value}}
                self.assertEqual(reader.score_answer(value, question)["proxy_exact"], 1)
                self.assertEqual(reader.score_answer(json.dumps(value), question)["proxy_exact"], 1)
        self.assertEqual(reader.score_answer("true", {"reference": {"expected": "false"}})["proxy_exact"], 0)

    def test_quality_type_summary_uses_separate_denominators(self):
        base = {"construction_run_id": "run1", "method": "Ours-dev", "status": "completed", "unknown": False,
                "proxy_exact": 1, "proxy_token_f1": 1.0, "retrieval_source_recall": 1.0,
                "reader_calls": 1, "input_tokens": 11, "output_tokens": 1, "reader_s": 0.5}
        rows = [{**base, "quality_type": "exact_field"},
                {**base, "quality_type": "semantic", "proxy_exact": 0}]
        summaries = reader.summarize_by_quality_type(rows, self.root / "raw.jsonl")
        self.assertEqual({row["quality_type"]: row["dev_proxy_exact_rate"] for row in summaries},
                         {"exact_field": 1.0, "semantic": 0.0})

    def test_checkpoint_is_pinned_read_only_and_tampering_is_rejected(self):
        snapshot = build_fresh(normalize_trajectory({"trajectory_id": "t", "steps": [{"action": "open"}]}),
                               config={"storage_path": str(self.root / "snapshot.sqlite3")})
        path = self.root / "snapshot.json"
        write_json(path, snapshot.to_dict())
        row = {"status": "completed", "snapshot_valid": True, "snapshot_id": snapshot.snapshot_id, "snapshot_path": str(path)}
        question = {"checkpoint_prefix_length": 1}
        loaded = reader.load_checkpoint(row, question)
        self.assertEqual(stable_hash(loaded.to_dict()), stable_hash(snapshot.to_dict()))
        tampered = replace(snapshot, metadata={"tamper": True})
        write_json(path, tampered.to_dict())
        with self.assertRaisesRegex(ValueError, "differs"):
            reader.load_checkpoint(row, question)
        with self.assertRaisesRegex(ValueError, "did not complete"):
            reader.load_checkpoint({**row, "status": "failed"}, question)

    def test_summary_denominator_includes_failures_and_keeps_tokens_null(self):
        base = {"construction_run_id": "run1", "method": "Ours-dev", "status": "completed", "unknown": False,
                "proxy_exact": 1, "proxy_token_f1": 1.0, "retrieval_source_recall": 1.0,
                "reader_calls": 1, "input_tokens": 11, "output_tokens": 1, "reader_s": 0.5}
        failed = {**base, "status": "failed", "proxy_exact": 0, "proxy_token_f1": 0.0,
                  "retrieval_source_recall": 0.0, "input_tokens": None, "output_tokens": None}
        summary = reader.summarize([base, failed], self.root / "raw.jsonl")[0]
        self.assertEqual(summary["n_questions"], 2)
        self.assertEqual(summary["failed_questions"], 1)
        self.assertEqual(summary["dev_proxy_exact_rate"], 0.5)
        self.assertEqual(summary["retrieval_source_recall"], 0.5)
        self.assertIsNone(summary["input_tokens"])
        self.assertEqual(summary["official_qa_status"], "not_evaluated")

    def test_explicit_empty_step_filter_exposes_no_derived_views(self):
        snapshot = build_fresh(normalize_trajectory({"trajectory_id": "t", "steps": [
            {"action": "open", "post_state": {"url": "https://memory.test/one"}},
            {"action": "save", "post_state": {"url": "https://memory.test/two"}},
        ]}), config={"storage_path": str(self.root / "views.sqlite3")})
        selected = [item.evidence_id for item in snapshot.evidence]
        positions = {event.event_id: index + 1 for index, event in enumerate(snapshot.events)}
        unrestricted = reader._bounded_reader_views(snapshot, selected, positions)
        self.assertTrue(any(unrestricted.values()))
        restricted = reader._bounded_reader_views(snapshot, selected, positions, allowed_positions=[])
        self.assertEqual(restricted, {"state": [], "workflow": [], "index": []})


if __name__ == "__main__":
    unittest.main()
