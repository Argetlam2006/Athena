"""
tests/test_intelligence/test_normalization.py
"""

from backend.intelligence.normalization import (
    percentile_rank,
    calculate_confidence,
    confidence_label,
    standard_deviation,
    euclidean_distance,
    calculate_similarity
)

def test_percentile_rank():
    cohort = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile_rank(1.0, cohort) == 10.0  # (0 + 0.5*1)/5 = 0.1
    assert percentile_rank(3.0, cohort) == 50.0  # (2 + 0.5*1)/5 = 0.5
    assert percentile_rank(5.0, cohort) == 90.0  # (4 + 0.5*1)/5 = 0.9

def test_percentile_rank_inverted():
    cohort = [1.0, 2.0, 3.0, 4.0, 5.0]
    # If inverted, lower is better. So 1.0 is the best (highest percentile)
    assert percentile_rank(1.0, cohort, invert=True) == 90.0  # (4 + 0.5*1)/5 = 0.9
    assert percentile_rank(5.0, cohort, invert=True) == 10.0  # (0 + 0.5*1)/5 = 0.1

def test_calculate_confidence():
    assert calculate_confidence(0) == 0.0
    assert calculate_confidence(5, 10) == 0.5
    assert calculate_confidence(15, 10) == 1.0

def test_confidence_label():
    assert confidence_label(0.9) == "high"
    assert confidence_label(0.6) == "medium"
    assert confidence_label(0.2) == "low"

def test_standard_deviation():
    assert standard_deviation([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]) == 2.0

def test_euclidean_distance():
    assert euclidean_distance([0.0, 0.0], [3.0, 4.0]) == 5.0

def test_calculate_similarity():
    # Identical
    assert calculate_similarity([50.0], [50.0]) == 100.0
