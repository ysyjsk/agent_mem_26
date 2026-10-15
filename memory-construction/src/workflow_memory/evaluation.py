"""Protocol-level metrics derived from raw event/snapshot timestamps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .statistics import summarize


@dataclass(frozen=True)
class FreshnessRecord:
    event_id: str
    scheduled_arrival_time: float
    queryable_time: float | None
    required_views: tuple[str, ...] = ()
    status: str = "completed"

    @property
    def latency(self) -> float | None:
        if self.queryable_time is None:
            return None
        return self.queryable_time - self.scheduled_arrival_time


def freshness_summary(records: Iterable[FreshnessRecord]) -> dict[str, Any]:
    rows = list(records)
    completed = [row.latency for row in rows if row.latency is not None]
    return {
        "latency": summarize(completed),
        "total": len(rows),
        "completed": len(completed),
        "censored": len(rows) - len(completed),
        "completion_rate": (len(completed) / len(rows)) if rows else None,
    }


def goodput(records: Iterable[FreshnessRecord], *, deadline: float | None = None) -> float:
    rows = list(records)
    if deadline is None:
        return float(sum(row.latency is not None for row in rows))
    return float(sum(row.latency is not None and row.latency <= deadline for row in rows))


def extract_metric_rows(run: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only auditable scalar fields for CSV/report generation."""
    allowed = {"run_id", "status", "duration_ns", "events", "fresh_evidence", "incremental_reused_nodes", "incremental_invalidated_nodes", "protocol", "backend"}
    return {key: run[key] for key in allowed if key in run}


__all__ = ["FreshnessRecord", "freshness_summary", "goodput", "extract_metric_rows"]
