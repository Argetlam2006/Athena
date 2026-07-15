"""
backend/intelligence/normalization.py — Mathematical utilities for the Intelligence Engine.

Contains pure functions for percentile normalization, scaling, confidence adjustment,
and basic statistics.
"""

from __future__ import annotations

import math
from typing import Sequence


def percentile_rank(value: float, cohort: Sequence[float], invert: bool = False) -> float:
    """
    Compute the percentile rank (0-100) of a value within a cohort.
    
    Args:
        value: The player's metric value.
        cohort: A sequence of metric values for the comparison group (e.g., all forwards).
        invert: If True, lower values score higher (e.g., turnovers).
        
    Returns:
        A float between 0.0 and 100.0.
    """
    if not cohort:
        return 50.0  # Safe fallback for empty cohorts
        
    # Count how many scores are strictly below (or above if inverted) and equal
    if invert:
        strict_matches = sum(1 for v in cohort if v > value)
        ties = sum(1 for v in cohort if math.isclose(v, value, rel_tol=1e-9, abs_tol=1e-9))
    else:
        strict_matches = sum(1 for v in cohort if v < value)
        ties = sum(1 for v in cohort if math.isclose(v, value, rel_tol=1e-9, abs_tol=1e-9))
        
    # Standard percentile formula with tie splitting
    percentile = ((strict_matches + (0.5 * ties)) / len(cohort)) * 100.0
    return max(0.0, min(100.0, percentile))


def calculate_confidence(matches_played: int, high_confidence_threshold: int = 10) -> float:
    """
    Calculate a confidence score (0.0 to 1.0) based on sample size.
    
    Args:
        matches_played: Number of matches the player participated in.
        high_confidence_threshold: Matches required for 1.0 confidence.
        
    Returns:
        Confidence score clipped between 0.0 and 1.0.
    """
    if matches_played <= 0:
        return 0.0
    return min(1.0, float(matches_played) / high_confidence_threshold)


def confidence_label(confidence: float) -> str:
    """
    Convert a numeric confidence score to a categorical label.
    """
    if confidence >= 0.8:
        return "high"
    elif confidence >= 0.5:
        return "medium"
    else:
        return "low"


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
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vector_a, vector_b)))


def calculate_similarity(vector_a: Sequence[float], vector_b: Sequence[float], max_distance: float = 283.0) -> float:
    """
    Calculate a 0-100 similarity score based on Euclidean distance.
    Max distance of 283.0 is roughly sqrt(8 * 100^2) for an 8-dimensional capability vector.
    """
    dist = euclidean_distance(vector_a, vector_b)
    similarity = 100.0 * (1.0 - (dist / max_distance))
    return max(0.0, min(100.0, similarity))
