"""Dependency-free descriptive statistics for run logs."""

from __future__ import annotations

import math
from typing import Iterable, Sequence


def percentile(values: Iterable[float], q: float) -> float | None:
    data = sorted(float(value) for value in values if value is not None and math.isfinite(float(value)))
    if not data:
        return None
    if not 0 <= q <= 100:
        raise ValueError("q must be between 0 and 100")
    if len(data) == 1:
        return data[0]
    position = (len(data) - 1) * q / 100.0
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return data[lower]
    weight = position - lower
    return data[lower] * (1 - weight) + data[upper] * weight


def summarize(values: Iterable[float]) -> dict[str, float | int | None]:
    data = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return {
        "count": len(data),
        "p50": percentile(data, 50),
        "p95": percentile(data, 95),
        "p99": percentile(data, 99),
        "mean": (sum(data) / len(data)) if data else None,
        "min": min(data) if data else None,
        "max": max(data) if data else None,
    }


def paired_differences(left: Sequence[float], right: Sequence[float]) -> list[float]:
    if len(left) != len(right):
        raise ValueError("paired samples must have equal length")
    return [float(a) - float(b) for a, b in zip(left, right)]


def noninferior(differences: Sequence[float], *, margin: float = 0.02) -> bool | None:
    if not differences:
        return None
    # This is a descriptive pre-check, not a replacement for a registered CI.
    return min(float(value) for value in differences) >= -float(margin)


__all__ = ["percentile", "summarize", "paired_differences", "noninferior"]
