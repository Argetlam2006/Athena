"""
tests/test_intelligence/test_normalization.py
"""

from backend.intelligence.normalization import (
    calculate_confidence,
    euclidean_distance,
    standard_deviation,
)


def test_calculate_confidence():
    assert calculate_confidence(0) == 0.0
    assert calculate_confidence(5, 10) == 0.5
    assert calculate_confidence(15, 10) == 1.0





def test_standard_deviation():
    assert standard_deviation([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]) == 2.0


def test_euclidean_distance():
    assert euclidean_distance([0.0, 0.0], [3.0, 4.0]) == 5.0


