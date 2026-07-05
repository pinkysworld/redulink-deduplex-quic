"""Small deterministic statistics helpers for ReduLink benchmark summaries."""
from __future__ import annotations

import random
import statistics
from collections.abc import Iterable


def mean(values: Iterable[float]) -> float:
    xs = list(values)
    return sum(xs) / len(xs) if xs else 0.0


def stdev(values: Iterable[float]) -> float:
    xs = list(values)
    return statistics.stdev(xs) if len(xs) > 1 else 0.0


def bootstrap_ci(values: Iterable[float], *, rounds: int = 2000, alpha: float = 0.05,
                 seed: int = 20260705) -> tuple[float, float]:
    """Return a percentile bootstrap CI for the sample mean."""
    xs = [float(v) for v in values]
    if not xs:
        return (0.0, 0.0)
    if len(xs) == 1:
        return (xs[0], xs[0])
    rng = random.Random(seed)
    means = []
    n = len(xs)
    for _ in range(rounds):
        sample = [xs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = max(0, min(len(means) - 1, int((alpha / 2) * len(means))))
    hi_idx = max(0, min(len(means) - 1, int((1 - alpha / 2) * len(means)) - 1))
    return (means[lo_idx], means[hi_idx])


def round_float(value: float, digits: int = 6) -> float:
    return round(float(value), digits)
