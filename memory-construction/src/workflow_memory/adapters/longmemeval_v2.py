"""Conservative LongMemEval-V2 trajectory adapter.

The public benchmark has appeared in a few JSON/JSONL layouts over time.  The
adapter accepts a path, an in-memory record, or an iterable of records and
delegates field interpretation to ``normalize_trajectory``.  It does not
download data or infer labels from future events.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from ..ir import SourceEvent, normalize_trajectory


class LongMemEvalV2Adapter:
    dataset_id = "xiaowu0162/longmemeval-v2"
    reference_commit = "2cc8c540bdb87fe6761629b585e727e1c4704520"

    def __init__(self, source: str | Path | Iterable[Mapping[str, Any]] | None = None, *, revision: str | None = None) -> None:
        self.source = source
        self.revision = revision
        self._records: list[Mapping[str, Any]] | None = None

    def _iter_records(self) -> Iterator[Mapping[str, Any]]:
        source = self.source
        if source is None:
            return iter(())
        if isinstance(source, Mapping):
            return iter((source,))
        if isinstance(source, (str, Path)):
            path = Path(source).expanduser()
            if not path.is_file():
                raise FileNotFoundError(path)
            if path.suffix.lower() in {".jsonl", ".ndjson"}:
                def lines() -> Iterator[Mapping[str, Any]]:
                    with path.open("r", encoding="utf-8") as handle:
                        for line_number, line in enumerate(handle, 1):
                            if not line.strip():
                                continue
                            value = json.loads(line)
                            if not isinstance(value, Mapping):
                                raise ValueError(f"{path}:{line_number} is not a JSON object")
                            yield value
                return lines()
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return (value for value in payload if isinstance(value, Mapping))
            if isinstance(payload, Mapping):
                for key in ("data", "records", "examples", "trajectories", "items"):
                    values = payload.get(key)
                    if isinstance(values, list):
                        return (value for value in values if isinstance(value, Mapping))
                return iter((payload,))
            raise ValueError(f"unsupported JSON root in {path}")
        return (value for value in source if isinstance(value, Mapping))

    def records(self) -> list[Mapping[str, Any]]:
        if self._records is None:
            self._records = list(self._iter_records())
        return list(self._records)

    def trajectories(self) -> Iterator[list[SourceEvent]]:
        for record in self.records():
            yield normalize_trajectory(record)

    def normalize(self, record: Mapping[str, Any] | list[Any]) -> list[SourceEvent]:
        return normalize_trajectory(record)

    def metadata(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "reference_commit": self.reference_commit,
            "revision": self.revision,
            "record_count": len(self.records()),
        }

