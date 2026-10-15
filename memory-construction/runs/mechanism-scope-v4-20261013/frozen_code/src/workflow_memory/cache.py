"""Content-addressed cache for compute nodes and model responses.

Cache entries intentionally omit global snapshot epochs and whole-history
hashes.  A key contains the operator/prompt/model identity, the complete
request, and only the versions of objects actually read by that node.  This is
what permits unrelated workflow updates to reuse local extraction results.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .ir import canonical_json, stable_hash


def _to_data(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(k): _to_data(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_to_data(v) for v in value]
    return value


@dataclass(frozen=True)
class CacheKey:
    operator: str
    schema_version: str = "1"
    prompt_hash: str | None = None
    model_fingerprint: str | None = None
    request: Any = None
    read_versions: Mapping[str, Any] = field(default_factory=dict)
    context_rules: Mapping[str, Any] = field(default_factory=dict)
    sampling: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        # Sort read versions and context fields through canonical_json; do not
        # include process IDs, run IDs or parent epoch.
        payload = {
            "operator": self.operator,
            "schema_version": self.schema_version,
            "prompt_hash": self.prompt_hash,
            "model_fingerprint": self.model_fingerprint,
            "request": _to_data(self.request),
            "read_versions": _to_data(self.read_versions),
            "context_rules": _to_data(self.context_rules),
            "sampling": _to_data(self.sampling),
        }
        return stable_hash(payload)


def make_cache_key(
    *,
    operator: str,
    request: Any,
    operator_version: str = "1",
    prompt_hash: str | None = None,
    model_fingerprint: str | None = None,
    read_versions: Mapping[str, Any] | None = None,
    context_rules: Mapping[str, Any] | None = None,
    sampling: Mapping[str, Any] | None = None,
) -> CacheKey:
    return CacheKey(
        operator=operator,
        schema_version=str(operator_version),
        prompt_hash=prompt_hash,
        model_fingerprint=model_fingerprint,
        request=request,
        read_versions=read_versions or {},
        context_rules=context_rules or {},
        sampling=sampling or {},
    )


class NodeCache:
    """Thread-safe in-memory cache with optional JSON persistence."""

    def __init__(self, path: str | Path | None = None):
        self.path = None if path is None or str(path) == ":memory:" else Path(path)
        self._items: dict[str, Any] = {}
        self._metadata: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._load()

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                self._items.update(payload.get("items", {}))
                self._metadata.update(payload.get("metadata", {}))
        except (OSError, ValueError, TypeError):
            # A corrupt cache is a miss, never a reason to fabricate a result.
            self._items.clear()
            self._metadata.clear()

    def _flush(self) -> None:
        if not self.path:
            return
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"items": self._items, "metadata": self._metadata}, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def get(self, key: CacheKey | str) -> Any | None:
        digest = key.digest if isinstance(key, CacheKey) else str(key)
        with self._lock:
            return self._items.get(digest)

    def contains(self, key: CacheKey | str) -> bool:
        digest = key.digest if isinstance(key, CacheKey) else str(key)
        with self._lock:
            return digest in self._items

    def put(self, key: CacheKey | str, value: Any, *, metadata: Mapping[str, Any] | None = None) -> str:
        digest = key.digest if isinstance(key, CacheKey) else str(key)
        with self._lock:
            self._items[digest] = _to_data(value)
            if metadata:
                self._metadata[digest] = _to_data(metadata)
            self._flush()
        return digest

    def delete(self, key: CacheKey | str) -> bool:
        digest = key.digest if isinstance(key, CacheKey) else str(key)
        with self._lock:
            existed = digest in self._items
            self._items.pop(digest, None)
            self._metadata.pop(digest, None)
            if existed:
                self._flush()
            return existed

    def invalidate(self, digests: Iterable[str]) -> int:
        count = 0
        with self._lock:
            for digest in digests:
                if str(digest) in self._items:
                    count += 1
                    self._items.pop(str(digest), None)
                    self._metadata.pop(str(digest), None)
            if count:
                self._flush()
        return count

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._metadata.clear()
            self._flush()

    def metadata(self, key: CacheKey | str) -> dict[str, Any]:
        digest = key.digest if isinstance(key, CacheKey) else str(key)
        with self._lock:
            return dict(self._metadata.get(digest, {}))

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


__all__ = ["CacheKey", "NodeCache", "make_cache_key"]
