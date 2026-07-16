"""
shared/config/ — Athena configuration package.

This package replaces the monolithic shared/constants.py for domain-specific constants.
"""

from shared.config.capabilities import (
    CAPABILITY_DESCRIPTIONS,
    CAPABILITY_DISPLAY_NAMES,
    CAPABILITY_METRIC_MAP,
    CAPABILITY_METRIC_WEIGHTS,
    CORE_CAPABILITIES,
    POSITION_GROUP_WEIGHTS,
)

__all__ = [
    "CORE_CAPABILITIES",
    "CAPABILITY_DISPLAY_NAMES",
    "CAPABILITY_DESCRIPTIONS",
    "CAPABILITY_METRIC_MAP",
    "CAPABILITY_METRIC_WEIGHTS",
    "POSITION_GROUP_WEIGHTS",
]
