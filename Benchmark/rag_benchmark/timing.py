from __future__ import annotations

import math
import statistics
import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar


T = TypeVar("T")


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


@dataclass
class LatencyRecorder:
    samples_ms: list[float] = field(default_factory=list)

    def measure(self, operation: Callable[[], T]) -> T:
        started = time.perf_counter()
        try:
            return operation()
        finally:
            self.samples_ms.append((time.perf_counter() - started) * 1000)

    def summary(self) -> dict[str, float | int]:
        values = self.samples_ms
        return {
            "count": len(values),
            "mean_ms": statistics.fmean(values) if values else 0.0,
            "min_ms": min(values, default=0.0),
            "p50_ms": percentile(values, 0.50),
            "p95_ms": percentile(values, 0.95),
            "p99_ms": percentile(values, 0.99),
            "max_ms": max(values, default=0.0),
            "stdev_ms": statistics.pstdev(values) if len(values) > 1 else 0.0,
        }

