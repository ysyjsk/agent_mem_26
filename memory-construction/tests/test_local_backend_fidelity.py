"""CPU-only fidelity checks for the local Qwen adapter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")

from workflow_memory.backends import ModelRequest
from workflow_memory.local_backends import TransformersQwenBackend


class _Tokenizer:
    pad_token_id = 0
    eos_token_id = 99
    eos_token = "<eos>"
    padding_side = "right"

    def __init__(self, decoded: str = "answer"):
        self.decoded = decoded
        self.calls = []

    def apply_chat_template(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        batch = messages if messages and isinstance(messages[0], list) else [messages]
        rows = [[10, 11] for _ in batch]
        masks = [[1, 1] for _ in batch]
        return {"input_ids": torch.tensor(rows), "attention_mask": torch.tensor(masks)}

    def decode(self, token_ids, *, skip_special_tokens):
        return self.decoded


class _Processor(_Tokenizer):
    def __init__(self):
        super().__init__()
        self.processor_calls = []

    def apply_chat_template(self, messages, **kwargs):
        self.processor_calls.append((messages, kwargs))
        return super().apply_chat_template(messages, **kwargs)


class _Model:
    generation_config = SimpleNamespace(eos_token_id=[99])

    def __init__(self, tail=(50, 51, 99)):
        self.tail = list(tail)
        self.calls = []

    def generate(self, *, input_ids, attention_mask, **kwargs):
        self.calls.append({"input_ids": input_ids.clone(), "attention_mask": attention_mask.clone(), **kwargs})
        suffix = torch.tensor([self.tail])
        return torch.cat((input_ids, suffix), dim=1)


def _backend(*, decoded="answer", processor=None, **kwargs):
    backend = TransformersQwenBackend("/not-loaded/qwen", device="cpu", **kwargs)
    backend._tokenizer = _Tokenizer(decoded)
    backend._processor = processor
    backend._model = _Model()
    return backend


def test_content_blocks_keep_role_and_interleaved_order():
    messages = (
        {"role": "system", "content": "system"},
        {"role": "user", "content": [
            {"type": "text", "text": "before"},
            {"type": "image_url", "image_url": {"url": "img-a"}},
            {"type": "text", "text": "after"},
        ]},
        {"role": "assistant", "content": "reply"},
    )
    normalized = TransformersQwenBackend._content_with_images(messages, ())
    assert [item["role"] for item in normalized] == ["system", "user", "assistant"]
    assert normalized[1]["content"] == messages[1]["content"]
    assert [block["type"] for block in normalized[1]["content"]] == ["text", "image_url", "text"]


def test_explicit_image_not_injected_again_when_block_already_contains_it():
    messages = ({"role": "user", "content": [
        {"type": "text", "text": "look"},
        {"type": "image_url", "image_url": {"url": "img-a"}},
    ]},)
    normalized = TransformersQwenBackend._content_with_images(messages, ("img-a",))
    assert len(normalized[0]["content"]) == 2
    assert normalized[0]["content"][-1]["image_url"]["url"] == "img-a"


def test_duplicate_compatibility_images_are_injected_once():
    messages = ({"role": "user", "content": "look"},)
    normalized = TransformersQwenBackend._content_with_images(messages, ("img-a", "img-a"))
    assert [block["image"] for block in normalized[0]["content"] if block.get("type") == "image"] == ["img-a"]


def test_embedded_image_selects_processor_and_preserves_blocks():
    processor = _Processor()
    backend = _backend(processor=processor)
    request = ModelRequest(messages=({"role": "user", "content": [
        {"type": "text", "text": "before"},
        {"type": "image", "image": "img-a"},
        {"type": "text", "text": "after"},
    ]},), max_tokens=3)
    response = backend.complete(request)
    assert response.text == "answer"
    assert len(processor.processor_calls) == 1
    rendered_messages = processor.processor_calls[0][0]
    assert [block["type"] for block in rendered_messages[0]["content"]] == ["text", "image", "text"]
    assert backend._tokenizer.calls == []


def test_batch_rejects_any_mismatched_effective_decoding_metadata():
    backend = _backend()
    base = dict(max_tokens=3, temperature=0.4, metadata={"top_p": 0.95, "top_k": 20, "enable_thinking": True})
    request = ModelRequest(prompt="one", **base)
    for changed in (
        {"top_p": 0.9, "top_k": 20, "enable_thinking": True},
        {"top_p": 0.95, "top_k": 10, "enable_thinking": True},
        {"top_p": 0.95, "top_k": 20, "enable_thinking": False},
    ):
        other = ModelRequest(prompt="two", max_tokens=3, temperature=0.4, metadata=changed)
        with pytest.raises(ValueError, match="identical decoding settings"):
            backend.complete_batch((request, other))
    assert backend._model.calls == []


def test_generation_forwards_effective_sampling_settings():
    backend = _backend()
    request = ModelRequest(prompt="one", max_tokens=3, temperature=0.4, metadata={"top_p": 0.85, "top_k": 7, "enable_thinking": False})
    response = backend.complete(request)
    call = backend._model.calls[0]
    assert call["top_p"] == 0.85
    assert call["top_k"] == 7
    assert call["temperature"] == 0.4
    assert call["do_sample"] is True
    assert backend._tokenizer.calls[0][1]["enable_thinking"] is False
    assert response.usage["completion_tokens"] == 3


def test_reasoning_is_split_but_all_generated_tokens_remain_counted():
    backend = _backend(decoded="<think>internal reasoning</think> final answer")
    response = backend.complete(ModelRequest(prompt="one", max_tokens=3))
    assert response.text == "final answer"
    assert response.raw["reasoning_content"] == "internal reasoning"
    assert response.raw["completion_content"] == "final answer"
    assert response.raw["decoded_text"].startswith("<think>")
    assert response.usage["completion_tokens"] == 3
    assert response.raw["completion_tokens_including_reasoning"] == 3
