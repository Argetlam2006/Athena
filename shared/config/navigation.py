"""
shared/config/navigation.py — Navigation configuration.

Defines the dynamic workspace navigation structure for the Athena frontend.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkspaceConfig:
    id: str
    name: str
    icon: str
    question: str
    status: str
    description: str


WORKSPACES: list[WorkspaceConfig] = [
    WorkspaceConfig(
        id="dashboard",
        name="Executive Dashboard",
        icon="⬡",
        question="What deserves my attention today?",
        status="live",
        description="KPIs, league snapshots, player spotlights",
    ),
    WorkspaceConfig(
        id="player_intelligence",
        name="Player Intelligence",
        icon="◈",
        question="What kind of player is this?",
        status="live",
        description="Capability profile, trends, similar players, AI report",
    ),
    WorkspaceConfig(
        id="team_intelligence",
        name="Team Intelligence",
        icon="◉",
        question="How does this team play?",
        status="live",
        description="Tactical identity, squad composition, style analysis",
    ),
    WorkspaceConfig(
        id="recruitment",
        name="Recruitment Intelligence",
        icon="◎",
        question="Who should we sign?",
        status="live",
        description="Candidate ranking, tactical fit, evidence-backed recommendations",
    ),
    WorkspaceConfig(
        id="ask_athena",
        name="Ask Athena",
        icon="◇",
        question="Help me understand this.",
        status="live",
        description="Conversational AI grounded in structured analytics",
    ),
]


def get_workspace_by_id(workspace_id: str) -> WorkspaceConfig | None:
    for w in WORKSPACES:
        if w.id == workspace_id:
            return w
    return None
