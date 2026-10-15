"""Content-addressed deterministic model replay for correctness experiments."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .backends import ModelRequest, ModelResponse, request_from_any
from .ir import canonical_json, stable_hash


class ReplayMissError(KeyError):
    """Raised when strict replay receives a request absent from its manifest."""


ReplayMiss = ReplayMissError


@dataclass(frozen=True, slots=True)
class ReplayEntry:
    request: Mapping[str, Any]
    response: Mapping[str, Any]


class DeterministicReplayBackend:
    """A request-content keyed backend, independent of invocation order.

    The backend never maps responses by call number.  This matters when Fresh
    and Incremental schedules issue equivalent requests in different orders.
    ``strict=True`` (the default) catches an accidental uncaptured request;
    ``strict=False`` may use a supplied ``fallback`` solely for exploratory
    development and marks the response as synthetic in ``last_call``.
    """

    schema_version = "workflow-memory/replay-v1"

    def __init__(
        self,
        responses: Mapping[str, Any] | None = None,
        *,
        model_fingerprint: str = "replay",
        strict: bool = True,
        fallback: Any = None,
    ) -> None:
        self.model_fingerprint = str(model_fingerprint)
        self.strict = bool(strict)
        self.fallback = fallback
        self._entries: dict[str, ReplayEntry] = {}
        self.last_call: dict[str, Any] | None = None
        if responses:
            # Accept either a plain ``{request_fingerprint: response}`` map or
            # the serialized manifest shape produced by ``to_dict``.
            if isinstance(responses.get("entries"), list):
                for item in responses["entries"]:
                    if not isinstance(item, Mapping):
                        continue
                    key = str(item.get("request_fingerprint") or stable_hash(item.get("request", {})))
                    self._entries[key] = ReplayEntry(
                        request=item.get("request", {}),
                        response=self._response_payload(item.get("response", {})),
                    )
            else:
                for key, value in responses.items():
                    key_string = str(key)
                    if re.fullmatch(r"[0-9a-fA-F]{64}", key_string):
                        self._entries[key_string] = ReplayEntry(
                            request={"fingerprint": key_string},
                            response=self._response_payload(value),
                        )
                    else:
                        self.record(key_string, value)

    def fingerprint(self) -> str:
        return self.model_fingerprint

    @property
    def responses(self) -> dict[str, Mapping[str, Any]]:
        return {key: entry.response for key, entry in self._entries.items()}

    @property
    def entries(self) -> tuple[ReplayEntry, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))

    @staticmethod
    def _response_payload(value: Any) -> Mapping[str, Any]:
        response = ModelResponse.from_any(value)
        return {
            "text": response.text,
            "model": response.model,
            "usage": dict(response.usage),
            "raw": response.raw,
            "finish_reason": response.finish_reason,
        }

    @staticmethod
    def _request_payload(request: ModelRequest) -> dict[str, Any]:
        return request.to_dict()

    def request_fingerprint(self, request: ModelRequest | Mapping[str, Any] | str) -> str:
        if isinstance(request, Mapping):
            explicit = request.get("request_fingerprint", request.get("fingerprint"))
            if explicit:
                return str(explicit)
        normalized = request_from_any(request)
        return normalized.fingerprint

    def record(self, request: ModelRequest | Mapping[str, Any] | str, response: Any) -> str:
        normalized = request_from_any(request)
        fingerprint = normalized.fingerprint
        self._entries[fingerprint] = ReplayEntry(
            request=self._request_payload(normalized),
            response=self._response_payload(response),
        )
        return fingerprint

    # Alias makes capture code read naturally.
    record_response = record
    register = record
    capture = record

    def has(self, request: ModelRequest | Mapping[str, Any] | str) -> bool:
        return self.request_fingerprint(request) in self._entries

    def complete(self, request: ModelRequest | Mapping[str, Any] | str, **_: Any) -> ModelResponse:
        normalized = request_from_any(request)
        fingerprint = self.request_fingerprint(request)
        entry = self._entries.get(fingerprint)
        synthetic = False
        if entry is None:
            if self.strict:
                raise ReplayMissError(
                    f"no deterministic replay response for request {fingerprint}; "
                    "capture the exact request before replay"
                )
            synthetic = True
            fallback = self.fallback
            if callable(fallback):
                fallback = fallback(normalized)
            if fallback is None:
                fallback = ""
            response = ModelResponse.from_any(fallback, request_fingerprint=fingerprint)
        else:
            response = ModelResponse.from_any(entry.response, request_fingerprint=fingerprint)
        self.last_call = {
            "request_fingerprint": fingerprint,
            "model_fingerprint": self.model_fingerprint,
            "synthetic": synthetic,
        }
        return response

    __call__ = complete

    async def acomplete(self, request: ModelRequest | Mapping[str, Any] | str, **kwargs: Any) -> ModelResponse:
        return self.complete(request, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_fingerprint": self.model_fingerprint,
            "strict": self.strict,
            "entries": [
                {
                    "request_fingerprint": key,
                    "request": self._entries[key].request,
                    "response": self._entries[key].response,
                }
                for key in sorted(self._entries)
            ],
        }

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(canonical_json(self.to_dict()) + "\n", encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path, *, strict: bool | None = None, fallback: Any = None) -> "DeterministicReplayBackend":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        backend = cls(
            model_fingerprint=str(payload.get("model_fingerprint", "replay")),
            strict=payload.get("strict", True) if strict is None else strict,
            fallback=fallback,
        )
        for item in payload.get("entries", []):
            request = item.get("request", {})
            response = item.get("response", {})
            fingerprint = str(item.get("request_fingerprint") or stable_hash(request))
            backend._entries[fingerprint] = ReplayEntry(request=request, response=response)
        return backend

    def manifest_digest(self) -> str:
        return stable_hash(self.to_dict())


# Short alias used by a few adapters and by older replay manifests.
ReplayBackend = DeterministicReplayBackend


__all__ = ["ReplayEntry", "ReplayMissError", "ReplayMiss", "DeterministicReplayBackend", "ReplayBackend"]
