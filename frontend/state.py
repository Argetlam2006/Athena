"""
frontend/state.py — Application State Schema.

Defines the strongly-typed schema for lightweight application state.
Does not import streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ApplicationState:
    """
    Lightweight state container for the Athena frontend.
    Avoid caching large backend objects (like PlayerProfile) here.
    """

    active_workspace_id: str = "dashboard"

    # Context selectors
    selected_player_id: int | None = None
    selected_team_id: int | None = None

    # Recruitment / Filtering
    comparison_ids: list[int] = field(default_factory=list)
    recruitment_filters: dict[str, str | float | None] = field(default_factory=dict)
    active_tactical_style: str | None = None
