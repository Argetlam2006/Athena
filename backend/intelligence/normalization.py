"""
backend/intelligence/normalization.py — Mathematical utilities for the Intelligence Engine.

Contains pure functions for percentile normalization, scaling, confidence adjustment,
and basic statistics.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def calculate_confidence(
    matches_played: int | None, high_confidence_threshold: int = 10
) -> float:
    """
    Calculate a confidence multiplier (0.0 to 1.0) based on sample size (matches played).
    Used to penalize grades for players with very small sample sizes.
    """
    if matches_played is None or matches_played <= 0:
        return 0.0
    return min(1.0, float(matches_played) / high_confidence_threshold)


def standard_deviation(values: Sequence[float]) -> float:
    """Compute the population standard deviation of a sequence."""
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


def euclidean_distance(vector_a: Sequence[float], vector_b: Sequence[float]) -> float:
    """Compute Euclidean distance between two vectors of equal length."""
    if len(vector_a) != len(vector_b):
        raise ValueError("Vectors must be of equal length")
    return math.sqrt(
        sum((a - b) ** 2 for a, b in zip(vector_a, vector_b, strict=False))
    )
