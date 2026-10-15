"""CPU-only tests for evaluator-only Reader re-scoring."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import rescore_dev_reader as rescore  # noqa: E402


class ReaderRescoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def make_source_run(self, *, old_exact=0, old_f1=0.0) -> tuple[Path, str]:
        source = self.root / "reader-source"
        source.mkdir()
        (source / "status.json").write_text(json.dumps({"status": "completed"}) + "\n", encoding="utf-8")
        (source / "manifest.json").write_text(json.dumps({
            "schema_version": "development-reader-run/1",
            "question_manifest_hash": "question-hash",
        }) + "\n", encoding="utf-8")
        row = {
            "answer": "false",
            "category": "observed_url",
            "construction_run_id": "construction-1",
            "elapsed_s": 0.25,
            "input_tokens": 23,
            "method": "Ours-dev",
            "output_tokens": 2,
            "proxy_exact": old_exact,
            "proxy_token_f1": old_f1,
            "quality_type": "exact_field",
            "reader_calls": 1,
            "reader_s": 0.2,
            "reference": {
                "expected": "false",
                "reference_status": "available",
            },
            "retrieval_s": 0.01,
            "retrieval_source_recall": 1.0,
            "status": "completed",
            "unknown": False,
            "wall_s": 0.25,
        }
        qa = source / "qa_per_question.jsonl"
        text = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        qa.write_text(text, encoding="utf-8")
        return source, text

    def test_false_scalar_is_rescored_and_real_usage_is_reused(self):
        source, source_text = self.make_source_run()
        output = self.root / "rescored"

        manifest = rescore.rescore_run(source, output)

        rows = [json.loads(line) for line in (output / "qa_per_question.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["old_proxy_exact"], 0)
        self.assertEqual(row["old_proxy_token_f1"], 0.0)
        self.assertEqual(row["proxy_exact"], 1)
        self.assertEqual(row["proxy_token_f1"], 1.0)
        self.assertTrue(row["score_correction"])
        self.assertIn("proxy_exact", row["score_correction_fields"])
        self.assertIn("proxy_token_f1", row["score_correction_fields"])
        self.assertEqual(row["reader_calls"], 1)
        self.assertEqual(row["input_tokens"], 23)
        self.assertEqual(row["output_tokens"], 2)
        self.assertTrue(row["evaluator_only"])
        self.assertTrue(row["no_new_model_calls"])
        self.assertEqual(row["source_run"], str(source.resolve()))
        self.assertEqual(manifest["new_model_calls"], 0)
        self.assertTrue(manifest["evaluator_only"])
        self.assertTrue(manifest["no_new_model_calls"])
        self.assertEqual(manifest["score_corrections"], 1)
        for name in ("dev_quality.csv", "dev_quality_by_type.csv", "dev_quality_by_category.csv",
                     "manifest.json", "status.json", "metrics.json"):
            self.assertTrue((output / name).is_file(), name)

        # Re-scoring is read-only with respect to the completed source run.
        self.assertEqual((source / "qa_per_question.jsonl").read_text(encoding="utf-8"), source_text)

    def test_unchanged_input_is_preserved_and_marked_without_correction(self):
        source, source_text = self.make_source_run(old_exact=1, old_f1=1.0)
        output = self.root / "rescored"

        rescore.rescore_run(source, output)

        row = json.loads((output / "qa_per_question.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(row["old_proxy_exact"], 1)
        self.assertEqual(row["old_proxy_token_f1"], 1.0)
        self.assertEqual(row["proxy_exact"], 1)
        self.assertEqual(row["proxy_token_f1"], 1.0)
        self.assertFalse(row["score_correction"])
        self.assertEqual(row["score_correction_status"], "unchanged")
        self.assertEqual(row["score_correction_fields"], [])
        self.assertEqual((source / "qa_per_question.jsonl").read_text(encoding="utf-8"), source_text)

    def test_existing_destination_is_rejected_without_touching_source(self):
        source, source_text = self.make_source_run()
        output = self.root / "rescored"
        output.mkdir()
        marker = output / "keep.txt"
        marker.write_text("keep", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "overwrite"):
            rescore.rescore_run(source, output)

        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        self.assertEqual((source / "qa_per_question.jsonl").read_text(encoding="utf-8"), source_text)


if __name__ == "__main__":
    unittest.main()
