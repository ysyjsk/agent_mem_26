"""Small JSONL telemetry primitives used by every execution stage.

The logger is deliberately boring: one event per line, flushed after each
write, with no model credentials or prompt contents unless a caller explicitly
passes them.  This makes interrupted runs inspectable and easy to replay.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_run_id(*, suite: str, config_hash: str, now: datetime | None = None) -> str:
    """Create a sortable run identifier with a short config suffix."""

    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    suffix = (config_hash or "unknown")[:10]
    # A UUID fragment prevents collisions when two runs start in one second,
    # while the timestamp and suite keep directory listings human-readable.
    return f"{stamp}-{suite}-{suffix}-{uuid.uuid4().hex[:8]}"


class JsonlLogger:
    """Thread-safe append-only structured logger."""

    def __init__(self, path: str | os.PathLike[str], *, run_id: str, suite: str) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.suite = suite
        self._lock = threading.Lock()
        self._closed = False

    def event(self, name: str, **fields: Any) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("logger is closed")
        if not name or not isinstance(name, str):
            raise ValueError("event name must be a non-empty string")
        record = {
            "event_time": utc_now(),
            "monotonic_ns": time.monotonic_ns(),
            "run_id": self.run_id,
            "suite": self.suite,
            "event": name,
            **fields,
        }
        encoded = json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        return record

    @contextmanager
    def span(self, name: str, **fields: Any) -> Iterator[dict[str, Any]]:
        start_ns = time.monotonic_ns()
        self.event(f"{name}.start", **fields)
        result: dict[str, Any] = {"name": name, "start_ns": start_ns}
        try:
            yield result
        except BaseException as exc:
            elapsed = time.monotonic_ns() - start_ns
            self.event(
                f"{name}.error",
                elapsed_ns=elapsed,
                error_type=type(exc).__name__,
                error=str(exc),
                **fields,
            )
            raise
        else:
            elapsed = time.monotonic_ns() - start_ns
            result["elapsed_ns"] = elapsed
            self.event(f"{name}.finish", elapsed_ns=elapsed, **fields)

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> "JsonlLogger":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


def safe_fields(values: Mapping[str, Any], *, secret_keys: tuple[str, ...] = ()) -> dict[str, Any]:
    """Return fields with obvious credential values removed.

    Most callers should pass only already-safe values.  This helper is a final
    guard for generic environment/config metadata and deliberately records
    presence as ``<configured>`` rather than the secret itself.
    """

    secret = {key.lower() for key in secret_keys}
    output: dict[str, Any] = {}
    for key, value in values.items():
        lowered = str(key).lower()
        if any(token in lowered for token in ("api_key", "token", "password", "secret", "credential")) or lowered in secret:
            output[str(key)] = bool(value)
        else:
            output[str(key)] = value
    return output

