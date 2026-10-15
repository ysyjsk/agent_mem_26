"""CPU-only contracts for local model accounting and genuinely batched calls.

No checkpoint, CUDA allocation, network access or optional model loading is
needed. The selected local environment supplies torch for tensor operations.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
import unittest

try:
    import torch
except ImportError:  # The lightweight core environment need not install torch.
    torch = None

from workflow_memory.backends import ModelRequest
from workflow_memory.local_backends import TransformersEmbeddingBackend, TransformersQwenBackend


class _ChatTokenizer:
    pad_token_id = 0
    eos_token_id = 99
    eos_token = "<eos>"
    padding_side = "right"

    def __init__(self):
        self.calls = []

    def apply_chat_template(self, messages, **kwargs):
        self.calls.append(kwargs)
        if isinstance(messages[0], dict):
            messages = [messages]
        lengths = [int(conversation[0]["content"]) for conversation in messages]
        width = max(lengths)
        rows = [[0] * (width - length) + list(range(10, 10 + length)) for length in lengths]
        mask = [[0] * (width - length) + [1] * length for length in lengths]
        return {"input_ids": torch.tensor(rows), "attention_mask": torch.tensor(mask)}

    @staticmethod
    def decode(token_ids, *, skip_special_tokens):
        values = [int(value) for value in token_ids]
        if skip_special_tokens:
            values = [value for value in values if value not in (0, 99, 98)]
        return ",".join(str(value) for value in values)


class _GenerateModel:
    generation_config = SimpleNamespace(eos_token_id=[99, 98])

    def __init__(self, tails):
        self.tails = list(tails)
        self.calls = []

    def generate(self, *, input_ids, attention_mask, **kwargs):
        self.calls.append({"input_ids": input_ids.clone(), "attention_mask": attention_mask.clone(), **kwargs})
        count = input_ids.shape[0]
        tails, self.tails = self.tails[:count], self.tails[count:]
        width = max(len(tail) for tail in tails)
        suffix = torch.tensor([tail + [0] * (width - len(tail)) for tail in tails])
        return torch.cat((input_ids, suffix), dim=1)


class _EmbeddingTokenizer:
    def __init__(self, *, padding_side="left", empty_mask=False):
        self.padding_side = padding_side
        self.empty_mask = empty_mask

    def __call__(self, texts, **kwargs):
        sequences = {"short": [11, 12], "long": [21, 22, 23, 24]}
        rows = [sequences[text][: kwargs["max_length"]] for text in texts]
        width = max(len(row) for row in rows)
        ids, masks = [], []
        for row in rows:
            padding = [0] * (width - len(row))
            if self.padding_side == "left":
                ids.append(padding + row)
                masks.append(padding + [1] * len(row))
            else:
                ids.append(row + padding)
                masks.append([1] * len(row) + padding)
        if self.empty_mask:
            masks[0] = [0] * width
        return {"input_ids": torch.tensor(ids), "attention_mask": torch.tensor(masks)}


class _EmbeddingModel:
    def __init__(self, *, bad_value=None):
        self.calls = 0
        self.bad_value = bad_value

    def __call__(self, *, input_ids, **kwargs):
        self.calls += 1
        hidden = torch.stack((input_ids.float(), torch.ones_like(input_ids).float()), dim=-1)
        if self.bad_value is not None:
            hidden.fill_(self.bad_value)
        return SimpleNamespace(last_hidden_state=hidden)


@unittest.skipIf(torch is None, "torch is optional; use the local model Python for these CPU tests")
class LocalGenerationMetricsTests(unittest.TestCase):
    @staticmethod
    def backend(tails, **kwargs):
        backend = TransformersQwenBackend("/not-loaded/qwen", device="cpu", **kwargs)
        backend._tokenizer = _ChatTokenizer()
        backend._model = _GenerateModel(tails)
        return backend

    @staticmethod
    def request(length, *, max_tokens=4, temperature=0):
        return ModelRequest(messages=({"role": "user", "content": str(length)},),
                            max_tokens=max_tokens, temperature=temperature)

    def test_real_batch_uses_one_generate_and_exact_unpadded_usage(self):
        backend = self.backend([[50, 99], [51, 52, 53, 54]])
        requests = (self.request(3), self.request(5))
        responses = backend.complete_batch(requests)
        self.assertEqual(len(backend._model.calls), 1)
        self.assertEqual(backend._model.calls[0]["input_ids"].shape, (2, 5))
        self.assertEqual(backend._model.calls[0]["attention_mask"].tolist(), [[0, 0, 1, 1, 1], [1, 1, 1, 1, 1]])
        self.assertEqual([response.usage["prompt_tokens"] for response in responses], [3, 5])
        self.assertEqual([response.usage["completion_tokens"] for response in responses], [2, 4])
        self.assertEqual([response.text for response in responses], ["50", "51,52,53,54"])
        self.assertEqual([response.finish_reason for response in responses], ["stop", "length"])
        self.assertEqual(responses[0].usage["total_tokens"], 5)
        self.assertEqual(responses[0].raw["batch_size"], 2)
        self.assertEqual(responses[0].raw["generation_mode"], "batched")
        self.assertEqual(responses[0].request_fingerprint, requests[0].fingerprint)
        self.assertTrue(responses[0].raw["completion_includes_eos"])
        self.assertEqual(backend._tokenizer.padding_side, "left")
        self.assertFalse(backend._tokenizer.calls[0]["truncation"])

    def test_batch_cap_is_real_and_final_single_member_is_not_called_parallel(self):
        backend = self.backend([[50, 99], [51, 99], [52, 99]], max_batch_size=2)
        responses = backend.complete_batch([self.request(2), self.request(3), self.request(4)])
        self.assertEqual([call["input_ids"].shape[0] for call in backend._model.calls], [2, 1])
        self.assertEqual([response.raw["batch_size"] for response in responses], [2, 2, 1])
        self.assertEqual(responses[-1].raw["generation_mode"], "serial")
        with self.assertRaisesRegex(ValueError, "max_batch_size"):
            backend.complete_batch([self.request(2)], batch_size=3)

    def test_generation_eos_wins_even_at_budget_and_multiple_eos_ids_work(self):
        backend = self.backend([[50, 51, 52, 98]])
        response = backend.complete(self.request(3))
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.usage["completion_tokens"], 4)
        self.assertEqual(response.text, "50,51,52")
        self.assertEqual(response.raw["generation_mode"], "serial")

    def test_oversize_request_fails_without_silent_tail_truncation(self):
        backend = self.backend([[50, 99]], max_input_tokens=4)
        with self.assertRaisesRegex(ValueError, "5 input tokens.*not truncated"):
            backend.complete(self.request(5))
        self.assertEqual(backend._model.calls, [])

    def test_mixed_budgets_and_image_batch_fail_before_generation(self):
        backend = self.backend([[50, 99]])
        with self.assertRaisesRegex(ValueError, "identical"):
            backend.complete_batch([self.request(2), self.request(2, max_tokens=3)])
        with self.assertRaisesRegex(ValueError, "identical"):
            backend.complete_batch([self.request(2), self.request(2, temperature=1)])
        with self.assertRaisesRegex(ValueError, "text-only"):
            backend.complete_batch([self.request(2), ModelRequest(prompt="2", images=("local.png",), max_tokens=4)])
        self.assertEqual(backend._model.calls, [])

    def test_empty_batch_does_not_load_optional_model(self):
        backend = TransformersQwenBackend("/not-loaded/qwen", device="cpu")
        self.assertEqual(backend.complete_batch([]), ())
        self.assertIsNone(backend._model)


@unittest.skipIf(torch is None, "torch is optional; use the local model Python for these CPU tests")
class LocalEmbeddingMetricsTests(unittest.TestCase):
    @staticmethod
    def backend(*, padding_side="left", bad_value=None, empty_mask=False, **kwargs):
        backend = TransformersEmbeddingBackend("/not-loaded/embedding", device="cpu", **kwargs)
        backend._tokenizer = _EmbeddingTokenizer(padding_side=padding_side, empty_mask=empty_mask)
        backend._model = _EmbeddingModel(bad_value=bad_value)
        return backend

    def test_last_token_pooling_is_correct_for_left_and_right_padding(self):
        for padding_side in ("left", "right"):
            with self.subTest(padding_side=padding_side):
                backend = self.backend(padding_side=padding_side, batch_size=2)
                response = backend.embed(["short", "long"])
                expected = torch.nn.functional.normalize(torch.tensor([[12.0, 1.0], [24.0, 1.0]]), dim=1)
                torch.testing.assert_close(torch.tensor(response.vectors), expected)
                self.assertEqual(response.usage["prompt_tokens"], 6)
                self.assertEqual(response.usage["input_tokens"], 6)
                self.assertEqual(response.usage["total_tokens"], 6)
                self.assertEqual(response.raw["input_tokens_per_text"], [2, 4])
                self.assertEqual(response.usage["input_texts"], 2)
                self.assertEqual(response.usage["dimensions"], 2)
                for vector in response.vectors:
                    self.assertAlmostEqual(sum(value * value for value in vector), 1.0, places=6)

    def test_truncated_embedding_usage_counts_only_model_input_and_chunks(self):
        backend = self.backend(batch_size=1, max_length=3)
        response = backend.embed(["short", "long", "short"])
        self.assertEqual(backend._model.calls, 3)
        self.assertEqual(response.raw["input_tokens_per_text"], [2, 3, 2])
        self.assertEqual(response.usage["input_tokens"], 7)
        self.assertTrue(response.raw["truncation_enabled"])
        self.assertEqual(response.raw["max_length"], 3)

    def test_nonfinite_and_zero_embeddings_are_errors_not_safe_looking_vectors(self):
        for bad_value, message in ((math.nan, "non-finite"), (math.inf, "non-finite"), (0.0, "zero-norm")):
            with self.subTest(bad_value=bad_value):
                with self.assertRaisesRegex(ValueError, message):
                    self.backend(bad_value=bad_value).embed(["short"])

    def test_empty_mask_is_rejected_before_model_call(self):
        backend = self.backend(empty_mask=True)
        with self.assertRaisesRegex(ValueError, "no unmasked tokens"):
            backend.embed(["short"])
        self.assertEqual(backend._model.calls, 0)

    def test_empty_embeddings_do_not_load_optional_model(self):
        backend = TransformersEmbeddingBackend("/not-loaded/embedding", device="cpu")
        response = backend.embed([])
        self.assertEqual(response.vectors, ())
        self.assertEqual(response.usage["input_tokens"], 0)
        self.assertIsNone(backend._model)


if __name__ == "__main__":
    unittest.main()
