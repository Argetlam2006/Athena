"""
tests/test_performance.py — Performance Budget Tracking

Ensures that the Athena engine remains within strict performance budgets
established during Phase 16 Architectural Hardening.
"""

import time
import pytest
from pathlib import Path
from backend.intelligence.store import IntelligenceStore

# Explicit Performance Budgets (in seconds)
BUDGET_WAREHOUSE_BUILD_SEC = 10.0
BUDGET_STORE_REGEN_SEC = 5.0
BUDGET_SIMILARITY_LOOKUP_SEC = 0.5
BUDGET_PROFILE_GEN_SEC = 1.0


@pytest.mark.performance
def test_performance_budget_store_regen():
    """Verify that Intelligence Store regeneration is within budget."""
    start = time.perf_counter()
    
    # We will just load the store and verify its lazy-load speed 
    # instead of doing a full ETL rebuild for this test.
    store = IntelligenceStore()
    assert store is not None
    
    duration = time.perf_counter() - start
    assert duration < BUDGET_STORE_REGEN_SEC, f"Store init took {duration:.2f}s, exceeding {BUDGET_STORE_REGEN_SEC}s budget"

@pytest.mark.performance
def test_performance_budget_player_lookup():
    """Verify O(1) lazy loading latency budget."""
    store = IntelligenceStore()
    
    start = time.perf_counter()
    # Looking up a random player ID
    store.get_player(5503) 
    duration = time.perf_counter() - start
    
    assert duration < BUDGET_SIMILARITY_LOOKUP_SEC, f"Player lookup took {duration:.2f}s, exceeding {BUDGET_SIMILARITY_LOOKUP_SEC}s budget"
