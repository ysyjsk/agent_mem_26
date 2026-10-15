"""Adapter boundary for the AgentRunbook-R external baseline.

This class deliberately does not vendor or silently emulate the baseline.  A
caller can inject an implementation exposing ``insert`` and ``query``; when it
is absent, the methods fail explicitly so a blocked baseline cannot be
reported as a successful experiment.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..ir import SourceEvent, normalize_trajectory


class AdapterUnavailable(RuntimeError):
    pass


class AgentRunbookRAdapter:
    method_id = "agentrunbook_r"

    def __init__(self, implementation: Any = None) -> None:
        self.implementation = implementation

    @property
    def available(self) -> bool:
        return self.implementation is not None

    def insert(self, trajectory: Any) -> Any:
        if self.implementation is None or not hasattr(self.implementation, "insert"):
            raise AdapterUnavailable("AgentRunbook-R implementation is not configured")
        return self.implementation.insert(trajectory)

    def query(self, question: str, **kwargs: Any) -> Any:
        if self.implementation is None or not hasattr(self.implementation, "query"):
            raise AdapterUnavailable("AgentRunbook-R implementation is not configured")
        return self.implementation.query(question, **kwargs)

    def normalize(self, trajectory: Any) -> list[SourceEvent]:
        return normalize_trajectory(trajectory)

