"""Protocols and request/response records for model integrations.

No network or GPU dependency is imported here.  Implementations can call vLLM,
an OpenAI-compatible service, or a local test provider while retaining the same
construction interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from typing import Any, Awaitable, Mapping, Protocol, Sequence, runtime_checkable
from urllib import request as urllib_request

from .ir import canonical_json, stable_hash


@dataclass(frozen=True, slots=True)
class ModelRequest:
    messages: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    model: str | None = None
    temperature: float | None = 0.0
    max_tokens: int | None = None
    images: tuple[Any, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    prompt: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.messages, Mapping):
            object.__setattr__(self, "messages", (self.messages,))
        if isinstance(self.messages, str) and self.prompt is None:
            object.__setattr__(self, "prompt", self.messages)
            object.__setattr__(self, "messages", ())
        if not self.messages and self.prompt is not None:
            object.__setattr__(self, "messages", ({"role": "user", "content": self.prompt},))
        object.__setattr__(self, "messages", tuple(self.messages or ()))
        object.__setattr__(self, "images", tuple(self.images or ()))
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})
        if self.max_tokens is not None:
            object.__setattr__(self, "max_tokens", int(self.max_tokens))

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": list(self.messages),
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "images": list(self.images),
            "metadata": dict(self.metadata),
            # request_id is a tracing field, not semantic request content.
        }

    @property
    def fingerprint(self) -> str:
        return stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str = ""
    model: str | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)
    raw: Any = None
    request_fingerprint: str | None = None
    finish_reason: str | None = None

    def __post_init__(self) -> None:
        if self.usage is None:
            object.__setattr__(self, "usage", {})

    @classmethod
    def from_any(cls, value: Any, *, request_fingerprint: str | None = None) -> "ModelResponse":
        if isinstance(value, cls):
            if value.request_fingerprint or request_fingerprint is None:
                return value
            return cls(value.text, value.model, value.usage, value.raw, request_fingerprint, value.finish_reason)
        if isinstance(value, str):
            return cls(text=value, raw=value, request_fingerprint=request_fingerprint)
        if isinstance(value, Mapping):
            text = value.get("text")
            if text is None:
                text = value.get("content", value.get("output", ""))
            if not text and isinstance(value.get("choices"), (list, tuple)):
                # OpenAI-compatible chat responses commonly nest text under
                # choices[0].message.content (or choices[0].text).
                first = value["choices"][0] if value["choices"] else {}
                if isinstance(first, Mapping):
                    message = first.get("message")
                    if isinstance(message, Mapping):
                        text = message.get("content", "")
                    if not text:
                        text = first.get("text", "")
            if isinstance(text, list):
                text = "".join(str(item.get("text", item)) if isinstance(item, Mapping) else str(item) for item in text)
            usage = value.get("usage", {})
            finish_reason = value.get("finish_reason")
            if finish_reason is None and isinstance(value.get("choices"), (list, tuple)) and value["choices"]:
                choice = value["choices"][0]
                if isinstance(choice, Mapping):
                    finish_reason = choice.get("finish_reason")
            return cls(
                text=str(text or ""),
                model=value.get("model"),
                usage=usage if isinstance(usage, Mapping) else {},
                raw=value,
                request_fingerprint=request_fingerprint,
                finish_reason=finish_reason,
            )
        return cls(text=str(value), raw=value, request_fingerprint=request_fingerprint)


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    vectors: tuple[tuple[float, ...], ...] = field(default_factory=tuple)
    model: str | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)
    raw: Any = None
    request_fingerprint: str | None = None

    @classmethod
    def from_any(cls, value: Any, *, request_fingerprint: str | None = None) -> "EmbeddingResponse":
        if isinstance(value, cls):
            if value.request_fingerprint or request_fingerprint is None:
                return value
            return cls(value.vectors, value.model, value.usage, value.raw, request_fingerprint)
        if isinstance(value, Mapping):
            rows = value.get("vectors", value.get("embeddings", value.get("data", ())))
            if isinstance(rows, Mapping):
                rows = rows.get("embedding", ())
            if isinstance(rows, (list, tuple)) and rows and isinstance(rows[0], Mapping):
                rows = [row.get("embedding", row.get("vector", ())) for row in rows]
            elif isinstance(rows, (list, tuple)) and rows and not isinstance(rows[0], (list, tuple)):
                rows = [rows]
            return cls(
                vectors=tuple(tuple(float(x) for x in row) for row in (rows or ())),
                model=value.get("model"),
                usage=value.get("usage", {}) if isinstance(value.get("usage", {}), Mapping) else {},
                raw=value,
                request_fingerprint=request_fingerprint,
            )
        return cls(vectors=tuple(tuple(float(x) for x in row) for row in (value or ())), raw=value, request_fingerprint=request_fingerprint)

    def __post_init__(self) -> None:
        object.__setattr__(self, "vectors", tuple(tuple(float(x) for x in row) for row in (self.vectors or ())))
        if self.usage is None:
            object.__setattr__(self, "usage", {})

    @property
    def embeddings(self) -> tuple[tuple[float, ...], ...]:
        return self.vectors


@runtime_checkable
class ModelBackend(Protocol):
    """Text/vision construction backend.

    A backend may implement either ``complete`` synchronously or return an
    awaitable.  Callers that need concurrency can use :func:`maybe_await` (or
    ``acomplete`` when supplied by the implementation).
    """

    def complete(self, request: ModelRequest | Mapping[str, Any] | str, **kwargs: Any) -> ModelResponse | Awaitable[ModelResponse]:
        ...


@runtime_checkable
class EmbeddingBackend(Protocol):
    def embed(self, texts: Sequence[str], **kwargs: Any) -> EmbeddingResponse | Awaitable[EmbeddingResponse]:
        ...


@runtime_checkable
class ReaderBackend(Protocol):
    def answer(self, question: str, evidence: Any, **kwargs: Any) -> Any | Awaitable[Any]:
        ...


@runtime_checkable
class JudgeBackend(Protocol):
    def judge(self, question: str, answer: Any, reference: Any = None, **kwargs: Any) -> Any | Awaitable[Any]:
        ...


# More explicit aliases are useful for adapters and preserve a pleasant API
# for callers that think in terms of LLMs rather than generic models.
LLMBackend = ModelBackend
ConstructionBackend = ModelBackend
EmbeddingProvider = EmbeddingBackend
ReaderProvider = ReaderBackend
JudgeProvider = JudgeBackend


def request_from_any(request: ModelRequest | Mapping[str, Any] | str) -> ModelRequest:
    if isinstance(request, ModelRequest):
        return request
    if isinstance(request, str):
        return ModelRequest(messages=({"role": "user", "content": request},))
    payload = dict(request)
    messages = payload.pop("messages", None)
    if messages is None:
        content = payload.pop("prompt", payload.pop("content", ""))
        messages = ({"role": "user", "content": content},)
    allowed = {"model", "temperature", "max_tokens", "images", "metadata", "request_id"}
    known = {key: payload.pop(key) for key in tuple(payload) if key in allowed}
    if payload:
        metadata = dict(known.get("metadata") or {})
        metadata.update(payload)
        known["metadata"] = metadata
    return ModelRequest(messages=tuple(messages), **known)


def backend_fingerprint(backend: Any) -> str:
    """Best-effort stable backend identity without exposing credentials."""

    method = getattr(backend, "fingerprint", None)
    if callable(method):
        value = method()
        if value:
            return str(value)
    for key in ("model", "model_id", "name"):
        value = getattr(backend, key, None)
        if value:
            return str(value)
    return f"{type(backend).__module__}.{type(backend).__qualname__}"


class BackendNotConfigured(RuntimeError):
    """Raised when a live model endpoint was requested but not configured."""


class OpenAICompatibleBackend:
    """Small injectable OpenAI-compatible client.

    The class is deliberately dependency-free and does not read credentials at
    import time.  It is an interface for a later vLLM/API hookup; callers can
    use ``complete`` when an endpoint is explicitly configured, while offline
    tests should use :class:`DeterministicReplayBackend` instead.
    """

    def __init__(self, *, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, timeout: float = 120.0, endpoint_path: str = "/v1/chat/completions") -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = float(timeout)
        self.endpoint_path = endpoint_path

    @classmethod
    def from_env(cls, *, base_url_env: str = "CONSTRUCTION_BASE_URL", api_key_env: str = "CONSTRUCTION_API_KEY", model: str | None = None, **kwargs: Any) -> "OpenAICompatibleBackend":
        return cls(base_url=os.environ.get(base_url_env), api_key=os.environ.get(api_key_env), model=model, **kwargs)

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)

    def fingerprint(self) -> str:
        # Never include endpoint URLs or key material in manifests.
        return f"openai-compatible:{self.model or 'unset'}"

    def complete(self, request: ModelRequest | Mapping[str, Any] | str, **kwargs: Any) -> ModelResponse:
        normalized = request_from_any(request)
        if not self.configured:
            raise BackendNotConfigured("OpenAI-compatible base URL/model is not configured")
        payload = {
            "model": normalized.model or self.model,
            "messages": list(normalized.messages),
            "temperature": normalized.temperature,
        }
        if normalized.max_tokens is not None:
            payload["max_tokens"] = normalized.max_tokens
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = self.base_url + (self.endpoint_path if self.endpoint_path.startswith("/") else "/" + self.endpoint_path)
        req = urllib_request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib_request.urlopen(req, timeout=self.timeout) as response:  # nosec B310 - explicit user-configured endpoint
            raw = json.loads(response.read().decode("utf-8"))
        return ModelResponse.from_any(raw, request_fingerprint=normalized.fingerprint)


class VLLMBackend(OpenAICompatibleBackend):
    """vLLM's OpenAI-compatible endpoint adapter."""

    def __init__(self, *, base_url: str | None = None, api_key: str | None = None, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(base_url=base_url, api_key=api_key or "EMPTY", model=model, **kwargs)

    @classmethod
    def from_env(cls, *, base_url_env: str = "CONSTRUCTION_BASE_URL", api_key_env: str = "CONSTRUCTION_API_KEY", model: str | None = None, **kwargs: Any) -> "VLLMBackend":
        return cls(base_url=os.environ.get(base_url_env), api_key=os.environ.get(api_key_env) or "EMPTY", model=model, **kwargs)

    def fingerprint(self) -> str:
        return f"vllm:{self.model or 'unset'}"


class OpenAICompatibleEmbeddingBackend:
    """Optional embeddings endpoint interface; no request is made until used."""

    def __init__(self, *, base_url: str | None = None, api_key: str | None = None, model: str | None = None, timeout: float = 120.0) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = float(timeout)

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)

    def fingerprint(self) -> str:
        return f"openai-compatible-embedding:{self.model or 'unset'}"

    def embed(self, texts: Sequence[str], **_: Any) -> EmbeddingResponse:
        if not self.configured:
            raise BackendNotConfigured("OpenAI-compatible embedding base URL/model is not configured")
        payload = {"model": self.model, "input": list(texts)}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib_request.Request(self.base_url + "/v1/embeddings", data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib_request.urlopen(req, timeout=self.timeout) as response:  # nosec B310 - explicit user-configured endpoint
            raw = json.loads(response.read().decode("utf-8"))
        rows = raw.get("data", []) if isinstance(raw, Mapping) else []
        vectors = []
        for row in rows:
            if isinstance(row, Mapping):
                vectors.append(tuple(float(value) for value in row.get("embedding", ())))
        return EmbeddingResponse(vectors=tuple(vectors), model=raw.get("model") if isinstance(raw, Mapping) else self.model, usage=raw.get("usage", {}) if isinstance(raw, Mapping) else {}, raw=raw)


__all__ = [
    "ModelRequest",
    "ModelResponse",
    "EmbeddingResponse",
    "ModelBackend",
    "LLMBackend",
    "ConstructionBackend",
    "EmbeddingBackend",
    "EmbeddingProvider",
    "ReaderBackend",
    "ReaderProvider",
    "JudgeBackend",
    "JudgeProvider",
    "request_from_any",
    "backend_fingerprint",
    "BackendNotConfigured",
    "OpenAICompatibleBackend",
    "VLLMBackend",
    "OpenAICompatibleEmbeddingBackend",
]
