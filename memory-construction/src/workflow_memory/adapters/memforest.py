"""Adapter boundary for MemForest (batch and online paths kept distinct)."""

from __future__ import annotations

from typing import Any

from .agentrunbook_r import AdapterUnavailable
from ..ir import SourceEvent, normalize_trajectory


class MemForestAdapter:
    method_id = "memforest"

    def __init__(self, implementation: Any = None, *, path: str = "online") -> None:
        if path not in {"online", "batch"}:
            raise ValueError("MemForest path must be 'online' or 'batch'")
        self.implementation = implementation
        self.path = path

    @property
    def available(self) -> bool:
        return self.implementation is not None

    def insert(self, trajectory: Any) -> Any:
        if self.implementation is None or not hasattr(self.implementation, "insert"):
            raise AdapterUnavailable(f"MemForest {self.path} implementation is not configured")
        return self.implementation.insert(trajectory)

    def query(self, question: str, **kwargs: Any) -> Any:
        if self.implementation is None or not hasattr(self.implementation, "query"):
            raise AdapterUnavailable(f"MemForest {self.path} implementation is not configured")
        return self.implementation.query(question, **kwargs)

    def normalize(self, trajectory: Any) -> list[SourceEvent]:
        return normalize_trajectory(trajectory)

