"""Optional local Transformers backends for the frozen Qwen models.

The core package intentionally has no heavyweight ML dependency.  This module
is imported only by runs that explicitly choose a local model environment (for
example ``/data/predator/ly/Mem/.venv``).  It keeps model loading outside the
SQLite transaction and exposes the same protocols as the vLLM/OpenAI adapters.

The implementation is deliberately conservative: models are loaded lazily,
credentials are never read here, and every response carries request/token
metadata that the runner can persist in ``llm_calls.jsonl``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .backends import (
    EmbeddingResponse,
    ModelRequest,
    ModelResponse,
    request_from_any,
)
from .ir import stable_hash


class LocalBackendUnavailable(RuntimeError):
    """Raised when the optional Transformers environment is unavailable."""


def _dtype(name: str | None) -> Any:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - depends on optional env
        raise LocalBackendUnavailable("PyTorch is not installed in the selected environment") from exc
    value = str(name or "bfloat16").lower()
    return {
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
        "float16": torch.float16,
        "fp16": torch.float16,
        "float32": torch.float32,
        "fp32": torch.float32,
    }.get(value, torch.bfloat16)


def _device(value: str | int) -> str:
    if isinstance(value, int):
        return f"cuda:{value}"
    return str(value)


def _model_digest(path: str | os.PathLike[str]) -> str:
    root = Path(path).expanduser().resolve()
    # Hash only the local index/config metadata, not all multi-gigabyte shards.
    candidates = [root / "config.json", root / "model.safetensors.index.json", root / "tokenizer_config.json"]
    payload = []
    for candidate in candidates:
        if candidate.is_file():
            payload.append((candidate.name, hashlib.sha256(candidate.read_bytes()).hexdigest()))
    return stable_hash({"path": str(root), "metadata": payload})


@dataclass
class TransformersQwenBackend:
    """Qwen3.5 text/vision generation backend backed by ``transformers``."""

    model_path: str
    device: str | int = "cuda:0"
    dtype: str = "bfloat16"
    max_input_tokens: int = 32768
    trust_remote_code: bool = True
    enable_thinking: bool = False
    local_files_only: bool = True
    max_batch_size: int = 2

    def __post_init__(self) -> None:
        self.device = _device(self.device)
        if int(self.max_input_tokens) < 1 or int(self.max_batch_size) < 1:
            raise ValueError("max_input_tokens and max_batch_size must be positive")
        self._model = None
        self._tokenizer = None
        self._processor = None
        self._fingerprint = f"transformers-qwen:{Path(self.model_path).name}:{_model_digest(self.model_path)[:16]}:{self.device}"

    def fingerprint(self) -> str:
        return self._fingerprint

    @property
    def model(self) -> Any:
        self._ensure_loaded()
        return self._model

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - depends on optional env
            raise LocalBackendUnavailable("install torch and transformers in the selected environment") from exc
        path = str(Path(self.model_path).expanduser().resolve())
        kwargs = {
            "dtype": _dtype(self.dtype),
            "device_map": {"": self.device},
            "low_cpu_mem_usage": True,
            "trust_remote_code": self.trust_remote_code,
            "local_files_only": self.local_files_only,
        }
        try:
            self._model = AutoModelForImageTextToText.from_pretrained(path, **kwargs)
        except (ImportError, ValueError) as exc:
            raise LocalBackendUnavailable(f"unable to load Qwen model {path}: {exc}") from exc
        self._model.eval()
        # Tokenizer is sufficient for text-only calls; processor is lazy for
        # callers that supply actual image objects.
        self._tokenizer = AutoTokenizer.from_pretrained(
            path,
            trust_remote_code=self.trust_remote_code,
            local_files_only=self.local_files_only,
        )
        # Decoder-only generation must pad on the left: the last input
        # position, not the last non-padding position, predicts the next token.
        self._tokenizer.padding_side = "left"
        try:
            self._processor = AutoProcessor.from_pretrained(
                path,
                trust_remote_code=self.trust_remote_code,
                local_files_only=self.local_files_only,
            )
        except Exception:
            self._processor = None

    @staticmethod
    def _content_with_images(messages: Sequence[Mapping[str, Any]], images: Sequence[Any]) -> list[dict[str, Any]]:
        result = [dict(message) for message in messages]
        if not images:
            return result
        # OpenAI/Qwen processors accept a list of content blocks.  Preserve
        # caller-provided blocks and append explicit image inputs to the last
        # user message.  Paths/URLs are passed through unchanged; PIL/bytes
        # objects are accepted by the processor when available.
        target = next((item for item in reversed(result) if item.get("role") == "user"), None)
        if target is None:
            target = {"role": "user", "content": ""}
            result.append(target)
        content = target.get("content", "")
        blocks = list(content) if isinstance(content, list) else ([{"type": "text", "text": content}] if content else [])
        for image in images:
            if isinstance(image, str) and image.startswith(("http://", "https://", "data:")):
                source: Any = image
            else:
                source = image
            blocks.append({"type": "image", "image": source})
        target["content"] = blocks
        return result

    @staticmethod
    def _generation_settings(request: ModelRequest) -> tuple[int, float]:
        budget = 1024 if request.max_tokens is None else int(request.max_tokens)
        temperature = float(request.temperature or 0.0)
        if budget < 1 or not math.isfinite(temperature) or temperature < 0:
            raise ValueError("max_tokens must be positive and temperature must be finite/non-negative")
        return budget, temperature

    def _render_inputs(self, requests: Sequence[ModelRequest]) -> tuple[dict[str, Any], list[int]]:
        """Render without truncation and count only actual, unpadded tokens."""

        import torch

        if not requests:
            raise ValueError("cannot render an empty generation batch")
        if len(requests) > 1 and any(request.images for request in requests):
            raise ValueError("complete_batch currently supports text-only requests; use complete for images")
        messages = [self._content_with_images(request.messages, request.images) for request in requests]
        tokenizer = self._tokenizer
        tokenizer.padding_side = "left"
        if len(requests) > 1 and tokenizer.pad_token_id is None:
            if tokenizer.eos_token is None:
                raise ValueError("batched generation requires a pad token or EOS token")
            tokenizer.pad_token = tokenizer.eos_token
        if requests[0].images and self._processor is None:
            raise LocalBackendUnavailable("image inputs require a working Qwen processor; they cannot be ignored")
        renderer = self._processor if requests[0].images else tokenizer
        template_kwargs = {
            "tokenize": True,
            "add_generation_prompt": True,
            "return_tensors": "pt",
            "return_dict": True,
            "padding": len(requests) > 1,
            "truncation": False,
            "enable_thinking": self.enable_thinking,
        }
        conversation = messages if len(requests) > 1 else messages[0]
        try:
            rendered = renderer.apply_chat_template(conversation, **template_kwargs)
        except TypeError:
            # Older local tokenizers do not accept the thinking switch.
            template_kwargs.pop("enable_thinking")
            rendered = renderer.apply_chat_template(conversation, **template_kwargs)
        if hasattr(rendered, "items"):
            inputs = dict(rendered)
        else:  # pragma: no cover - older single-request tokenizer compatibility
            if len(requests) > 1:
                raise ValueError("batched chat rendering must return an attention mask")
            inputs = {"input_ids": rendered}
        input_ids = inputs["input_ids"]
        if input_ids.ndim != 2 or input_ids.shape[0] != len(requests):
            raise ValueError("chat rendering returned an unexpected input shape")
        if "attention_mask" not in inputs:
            if len(requests) > 1:
                raise ValueError("batched chat rendering must return an attention mask")
            inputs["attention_mask"] = torch.ones_like(input_ids)
        mask = inputs["attention_mask"]
        if mask.shape != input_ids.shape or bool(((mask != 0) & (mask != 1)).any().item()):
            raise ValueError("chat attention mask must be binary and match input_ids")
        prompt_lengths = [int(value) for value in mask.sum(dim=1).tolist()]
        for request, length in zip(requests, prompt_lengths):
            if length < 1:
                raise ValueError("generation request has no input tokens")
            if length > int(self.max_input_tokens):
                # Tail-only truncation can discard system instructions and
                # the question. The caller must explicitly reduce its context.
                raise ValueError(
                    f"request {request.fingerprint[:12]} has {length} input tokens, exceeds "
                    f"max_input_tokens={self.max_input_tokens}; prompt was not truncated"
                )
        # Left padding is required even if a tokenizer silently disregards
        # padding_side. Refuse right-padded batches instead of wrong generation.
        if len(requests) > 1 and bool((mask[:, -1] != 1).any().item()):
            raise ValueError("decoder-only generation requires left-padded inputs")
        return {
            key: value.to(self.device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }, prompt_lengths

    def _eos_token_ids(self) -> set[int]:
        generation_config = getattr(self._model, "generation_config", None)
        values = getattr(generation_config, "eos_token_id", None)
        if values is None:
            values = getattr(getattr(self._model, "config", None), "eos_token_id", None)
        if values is None:
            values = getattr(self._tokenizer, "eos_token_id", None)
        if values is None:
            return set()
        if isinstance(values, int):
            return {values}
        return {int(value) for value in values}

    def _complete_group(self, requests: Sequence[ModelRequest]) -> tuple[ModelResponse, ...]:
        self._ensure_loaded()
        import torch

        inputs, prompt_lengths = self._render_inputs(requests)
        budget, temperature = self._generation_settings(requests[0])
        generation_kwargs = {
            "max_new_tokens": budget,
            "do_sample": temperature > 0,
            "use_cache": True,
            "num_return_sequences": 1,
            "return_dict_in_generate": False,
        }
        if generation_kwargs["do_sample"]:
            generation_kwargs["temperature"] = temperature
        if self._tokenizer.pad_token_id is not None:
            generation_kwargs["pad_token_id"] = self._tokenizer.pad_token_id
        with torch.inference_mode():
            output = self._model.generate(**inputs, **generation_kwargs)
        if output.ndim != 2 or output.shape[0] != len(requests):
            raise ValueError("generation returned an unexpected output shape")
        # HF returns the padded prompt followed by generated tokens for every
        # batch member. Slicing by an unpadded prompt length leaks prompt text.
        padded_width = int(inputs["input_ids"].shape[-1])
        if output.shape[-1] < padded_width:
            raise ValueError("generation output does not contain the complete input prompt")
        eos_ids = self._eos_token_ids()
        responses: list[ModelResponse] = []
        for index, (request, prompt_tokens) in enumerate(zip(requests, prompt_lengths)):
            token_ids = [int(value) for value in output[index, padded_width:].tolist()]
            eos_index = next((i for i, value in enumerate(token_ids) if value in eos_ids), None)
            if eos_index is not None:
                # Count the sampled EOS, but not batch padding after it.
                token_ids = token_ids[: eos_index + 1]
                finish_reason, termination = "stop", "eos"
            elif len(token_ids) >= budget:
                finish_reason, termination = "length", "max_new_tokens"
            else:
                finish_reason, termination = "unknown", "other_stopping_condition"
            completion_tokens = len(token_ids)
            responses.append(ModelResponse(
                text=self._tokenizer.decode(token_ids, skip_special_tokens=True),
                model=Path(self.model_path).name,
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                raw={
                    "device": self.device,
                    "model_path": str(Path(self.model_path).resolve()),
                    "batch_size": len(requests),
                    "batch_limit": int(self.max_batch_size),
                    "generation_mode": "batched" if len(requests) > 1 else "serial",
                    "padded_input_tokens": padded_width,
                    "token_count_basis": "attention_mask_and_generated_ids_through_first_eos",
                    "termination": termination,
                    "completion_includes_eos": eos_index is not None,
                },
                request_fingerprint=request.fingerprint,
                finish_reason=finish_reason,
            ))
        return tuple(responses)

    def complete(self, request: ModelRequest | Mapping[str, Any] | str, **_: Any) -> ModelResponse:
        request = request_from_any(request)
        self._generation_settings(request)
        return self._complete_group((request,))[0]

    def complete_batch(
        self,
        requests: Sequence[ModelRequest | Mapping[str, Any] | str],
        *,
        batch_size: int | None = None,
        **_: Any,
    ) -> tuple[ModelResponse, ...]:
        """True bounded GPU batches with identical decoding settings.

        This is not a threaded wrapper around serial ``complete`` calls. Each
        group enters ``model.generate`` once, and response metadata records its
        actual batch size. Image batching is intentionally not claimed here.
        """

        requests = tuple(request_from_any(request) for request in requests)
        if not requests:
            return ()
        limit = int(self.max_batch_size if batch_size is None else batch_size)
        if limit < 1 or limit > int(self.max_batch_size):
            raise ValueError(f"batch_size must be between 1 and max_batch_size={self.max_batch_size}")
        settings = [self._generation_settings(request) for request in requests]
        if any(value != settings[0] for value in settings[1:]):
            raise ValueError("complete_batch requires identical max_tokens and temperature")
        if len(requests) > 1 and any(request.images for request in requests):
            raise ValueError("complete_batch currently supports text-only requests; use complete for images")
        responses: list[ModelResponse] = []
        for start in range(0, len(requests), limit):
            responses.extend(self._complete_group(requests[start : start + limit]))
        return tuple(responses)

    def answer(self, question: str, evidence: Any, **kwargs: Any) -> str:
        """Reader-compatible wrapper using the same pinned local checkpoint."""

        import json

        budget = int(kwargs.get("max_tokens", 256) or 256)
        # ``construction.query`` exposes the immutable snapshot views for
        # callers, but a reader request must obey the retrieval budget.  Never
        # serialize the complete state/workflow history (which can contain
        # multi-megabyte accessibility trees) into one prompt.
        if isinstance(evidence, Mapping):
            selected = evidence.get("evidence", ())
            state = evidence.get("state", {})
            workflow = evidence.get("workflow", {})
            evidence = {
                "evidence": list(selected)[:8] if isinstance(selected, (list, tuple)) else selected,
                "state_keys": list(state)[:16] if isinstance(state, Mapping) else [],
                "workflow_keys": list(workflow)[:16] if isinstance(workflow, Mapping) else [],
            }
        encoded = json.dumps({"question": str(question), "evidence": evidence}, ensure_ascii=False, sort_keys=True, default=str)
        prompt_prefix = (
            "Answer the question using only the supplied evidence. "
            "Return a concise answer and do not invent facts.\n"
        )
        prompt = prompt_prefix + encoded
        # Reader context reduction is explicit here rather than silently
        # tail-truncating every construction request in complete().
        self._ensure_loaded()
        limit = int(kwargs.get("max_input_tokens", self.max_input_tokens) or self.max_input_tokens)
        tokens = self._tokenizer.encode(prompt, add_special_tokens=False)
        truncated = len(tokens) > limit
        if truncated:
            prefix_tokens = self._tokenizer.encode(prompt_prefix + encoded[: min(len(encoded), 1200)], add_special_tokens=False)
            keep_head = min(len(prefix_tokens), max(1, limit // 3))
            keep_tail = max(1, limit - keep_head - 8)
            tokens = tokens[:keep_head] + self._tokenizer.encode("\n...[reader context truncated]\n", add_special_tokens=False)[:8] + tokens[-keep_tail:]
            prompt = self._tokenizer.decode(tokens, skip_special_tokens=False)
        request = ModelRequest(
            messages=(
                {
                    "role": "user",
                    "content": prompt,
                },
            ),
            max_tokens=budget,
            temperature=0.0,
        )
        complete = kwargs.get("_complete", self.complete)
        return complete(request).text.strip()


@dataclass
class TransformersEmbeddingBackend:
    """Qwen3-Embedding backend using last-token pooling and L2 normalization."""

    model_path: str
    device: str | int = "cuda:1"
    dtype: str = "bfloat16"
    max_length: int = 8192
    batch_size: int = 4
    trust_remote_code: bool = True
    local_files_only: bool = True

    def __post_init__(self) -> None:
        self.device = _device(self.device)
        if int(self.max_length) < 1 or int(self.batch_size) < 1:
            raise ValueError("max_length and batch_size must be positive")
        self._model = None
        self._tokenizer = None
        self._fingerprint = f"transformers-embedding:{Path(self.model_path).name}:{_model_digest(self.model_path)[:16]}:{self.device}"

    def fingerprint(self) -> str:
        return self._fingerprint

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:  # pragma: no cover
            raise LocalBackendUnavailable("install torch and transformers in the selected environment") from exc
        path = str(Path(self.model_path).expanduser().resolve())
        self._tokenizer = AutoTokenizer.from_pretrained(
            path,
            padding_side="left",
            trust_remote_code=self.trust_remote_code,
            local_files_only=self.local_files_only,
        )
        self._model = AutoModel.from_pretrained(
            path,
            dtype=_dtype(self.dtype),
            device_map={"": self.device},
            low_cpu_mem_usage=True,
            trust_remote_code=self.trust_remote_code,
            local_files_only=self.local_files_only,
        )
        self._model.eval()

    def embed(self, texts: Sequence[str], **_: Any) -> EmbeddingResponse:
        values = [str(text) for text in texts]
        if not values:
            return EmbeddingResponse(
                model=Path(self.model_path).name,
                usage={"input_texts": 0, "dimensions": 0, "prompt_tokens": 0, "input_tokens": 0, "total_tokens": 0},
                request_fingerprint=stable_hash({"texts": values, "model": self._fingerprint}),
            )
        self._ensure_loaded()
        import torch
        import torch.nn.functional as F

        vectors: list[tuple[float, ...]] = []
        input_tokens_per_text: list[int] = []
        for start in range(0, len(values), int(self.batch_size)):
            batch = values[start : start + int(self.batch_size)]
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=int(self.max_length),
                return_tensors="pt",
            )
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            mask = encoded["attention_mask"]
            if mask.ndim != 2 or mask.shape != encoded["input_ids"].shape:
                raise ValueError("embedding attention mask must match the input token shape")
            if bool(((mask != 0) & (mask != 1)).any().item()):
                raise ValueError("embedding attention mask must be binary")
            lengths = mask.sum(dim=1)
            if bool((lengths < 1).any().item()):
                raise ValueError("embedding input has no unmasked tokens")
            input_tokens_per_text.extend(int(value) for value in lengths.tolist())
            with torch.inference_mode():
                output = self._model(**encoded)
            # Qwen3-Embedding uses the last non-padding token. sum(mask)-1
            # works only with right padding; this backend explicitly pads left.
            # Last active index also handles right/mixed padding correctly.
            positions = torch.arange(mask.shape[1], device=mask.device).expand_as(mask)
            positions = positions.masked_fill(mask == 0, -1).max(dim=1).values
            if output.last_hidden_state.shape[:2] != mask.shape:
                raise ValueError("embedding model output shape does not match input tokens")
            pooled = output.last_hidden_state[
                torch.arange(output.last_hidden_state.shape[0], device=output.last_hidden_state.device),
                positions,
            ].float()
            if not bool(torch.isfinite(pooled).all().item()):
                raise ValueError("embedding model returned non-finite values")
            if bool((torch.linalg.vector_norm(pooled, dim=1) == 0).any().item()):
                raise ValueError("embedding model returned a zero-norm vector")
            pooled = F.normalize(pooled, p=2, dim=1)
            vectors.extend(tuple(float(value) for value in row.detach().cpu().tolist()) for row in pooled)
        return EmbeddingResponse(
            vectors=tuple(vectors),
            model=Path(self.model_path).name,
            usage={
                "input_texts": len(values),
                "dimensions": len(vectors[0]) if vectors else 0,
                "prompt_tokens": sum(input_tokens_per_text),
                "input_tokens": sum(input_tokens_per_text),
                "total_tokens": sum(input_tokens_per_text),
            },
            raw={
                "device": self.device,
                "model_path": str(Path(self.model_path).resolve()),
                "token_count_basis": "attention_mask",
                "input_tokens_per_text": input_tokens_per_text,
                "padding_side": self._tokenizer.padding_side,
                "max_length": int(self.max_length),
                "truncation_enabled": True,
                "batch_limit": int(self.batch_size),
            },
            request_fingerprint=stable_hash({"texts": values, "model": self._fingerprint}),
        )


__all__ = ["LocalBackendUnavailable", "TransformersQwenBackend", "TransformersEmbeddingBackend"]
