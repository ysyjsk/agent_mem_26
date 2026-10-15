"""Boundary for the native Codex memory system.

Native integration has additional scheduling and workspace-eligibility
semantics.  This adapter records that boundary and refuses to pretend those
semantics are available through the internal builder.
"""

from __future__ import annotations

from typing import Any

from .agentrunbook_r import AdapterUnavailable
from ..ir import SourceEvent, normalize_trajectory


class CodexNativeAdapter:
    method_id = "codex_native"

    def __init__(self, implementation: Any = None, *, workspace: str | None = None) -> None:
        self.implementation = implementation
        self.workspace = workspace

    @property
    def available(self) -> bool:
        return self.implementation is not None

    def insert(self, trajectory: Any) -> Any:
        if self.implementation is None or not hasattr(self.implementation, "insert"):
            raise AdapterUnavailable("native Codex memory implementation is not configured")
        return self.implementation.insert(trajectory)

    def query(self, question: str, **kwargs: Any) -> Any:
        if self.implementation is None or not hasattr(self.implementation, "query"):
            raise AdapterUnavailable("native Codex memory implementation is not configured")
        return self.implementation.query(question, **kwargs)

    def normalize(self, trajectory: Any) -> list[SourceEvent]:
        return normalize_trajectory(trajectory)

