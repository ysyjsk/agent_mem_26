"""Batch logging must preserve request tokens without doubling GPU wall time."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from workflow_memory.backends import ModelRequest, ModelResponse

spec = importlib.util.spec_from_file_location("fast_batch_runner", Path(__file__).parents[1] / "tools/run_fast_compare.py")
fast = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fast)


class BatchBackend:
    max_batch_size = 2

    def complete_batch(self, requests):
        return tuple(ModelResponse(text='{"evidence":[]}', usage={"prompt_tokens": 11+i, "completion_tokens": 5},
                                   raw={"batch_size": len(requests)}, finish_reason="stop") for i, _ in enumerate(requests))


class BatchAccountingTests(unittest.TestCase):
    def test_batch_wall_counted_once_tokens_per_request(self):
        with tempfile.TemporaryDirectory() as folder:
            recorder = fast.RecordingBackend(BatchBackend(), Path(folder))
            requests = [ModelRequest(prompt="a"), ModelRequest(prompt="b"), ModelRequest(prompt="c")]
            self.assertEqual(len(recorder.complete_batch(requests)), 3)
            self.assertEqual([c["actual_batch_size"] for c in recorder.calls], [2, 2, 1])
            self.assertEqual(fast.token_sum(recorder.calls, "input_tokens"), 34)
            self.assertEqual(fast.model_wall_ns(recorder.calls), recorder.calls[0]["elapsed_ns"] + recorder.calls[2]["elapsed_ns"])


if __name__ == "__main__":
    unittest.main()
