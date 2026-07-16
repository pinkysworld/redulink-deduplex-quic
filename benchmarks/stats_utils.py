"""Small deterministic statistics helpers for ReduLink experiments."""

from __future__ import annotations

import random
import statistics
from collections.abc import Iterable


BOOTSTRAP_SEED = 20260716


def mean(values: Iterable[float]) -> float:
    xs = [float(value) for value in values]
    return sum(xs) / len(xs) if xs else 0.0


def median(values: Iterable[float]) -> float:
    xs = [float(value) for value in values]
    return float(statistics.median(xs)) if xs else 0.0


def stdev(values: Iterable[float]) -> float:
    xs = [float(value) for value in values]
    return statistics.stdev(xs) if len(xs) > 1 else 0.0


def bootstrap_ci(
    values: Iterable[float],
    *,
    rounds: int = 5000,
    alpha: float = 0.05,
    seed: int = BOOTSTRAP_SEED,
    statistic: str = "mean",
) -> tuple[float, float]:
    """Return a deterministic percentile-bootstrap CI for a mean or median."""

    xs = [float(value) for value in values]
    if not xs:
        return (0.0, 0.0)
    if len(xs) == 1:
        return (xs[0], xs[0])
    rng = random.Random(seed)
    count = len(xs)
    if statistic not in {"mean", "median"}:
        raise ValueError("statistic must be 'mean' or 'median'")
    estimates = []
    for _ in range(rounds):
        sample = [xs[rng.randrange(count)] for _ in range(count)]
        estimates.append(
            sum(sample) / count
            if statistic == "mean"
            else float(statistics.median(sample))
        )
    estimates.sort()
    low_index = max(0, min(rounds - 1, int((alpha / 2.0) * rounds)))
    high_index = max(0, min(rounds - 1, int((1.0 - alpha / 2.0) * rounds) - 1))
    return estimates[low_index], estimates[high_index]


def jain_fairness(values: Iterable[float]) -> float:
    """Return Jain's fairness index for non-negative observed rates."""

    xs = [float(value) for value in values]
    if not xs or any(value < 0 for value in xs):
        return 0.0
    denominator = len(xs) * sum(value * value for value in xs)
    return (sum(xs) ** 2) / denominator if denominator else 0.0


def round_float(value: float, digits: int = 6) -> float:
    return round(float(value), digits)
