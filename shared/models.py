"""
shared/models.py — Pydantic API models for FastAPI request/response contracts

These are separate from schemas.py (dataclasses) because they are used
exclusively at the API boundary. Internal modules use dataclasses.

Separation rationale:
  - Dataclasses (schemas.py) → fast, lightweight, used internally
  - Pydantic models (models.py) → validation + serialization at API boundary
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────────────────────


class PlayerSearchRequest(BaseModel):
    """Request to search for players."""

    query: str = Field(..., min_length=2, description="Player name or partial name")
    competition: str | None = Field(None, description="Filter by competition name")
    season: str | None = Field(None, description="Filter by season")
    position: str | None = Field(
        None, description="Filter by position group code (e.g. CM, ST)"
    )


class RecruitmentSearchRequest(BaseModel):
    """Request to generate recruitment recommendations."""

    position: str = Field(..., description="Target position group code")
    min_age: int = Field(16, ge=16, le=45)
    max_age: int = Field(35, ge=16, le=45)
    min_minutes: int = Field(450, ge=0, description="Minimum minutes played")
    competition: str | None = Field(None, description="Restrict to one competition")
    # Capability requirements — 0 means no requirement
    required_ball_progression: float = Field(0.0, ge=0.0, le=100.0)
    required_chance_creation: float = Field(0.0, ge=0.0, le=100.0)
    required_ball_security: float = Field(0.0, ge=0.0, le=100.0)
    required_defensive_activity: float = Field(0.0, ge=0.0, le=100.0)
    required_attacking_threat: float = Field(0.0, ge=0.0, le=100.0)
    required_tactical_versatility: float = Field(0.0, ge=0.0, le=100.0)
    top_n: int = Field(10, ge=1, le=50, description="Number of candidates to return")


class PlayerCompareRequest(BaseModel):
    """Request to compare two or more players."""

    player_ids: list[int] = Field(..., min_length=2, max_length=5)
    season: str | None = None


class AthenaQueryRequest(BaseModel):
    """Request to Ask Athena a question."""

    question: str = Field(..., min_length=5, max_length=1000)
    context_player_id: int | None = Field(
        None, description="Player context for the question"
    )
    context_team_name: str | None = Field(
        None, description="Team context for the question"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────


class CapabilityScoreResponse(BaseModel):
    """API representation of a single capability score."""

    capability: str
    display_name: str
    score: float
    confidence: float
    evidence: dict[str, float]


class PlayerSummaryResponse(BaseModel):
    """Lightweight player summary for search results and lists."""

    player_id: int
    player_name: str
    position_group: str
    team_name: str
    competition: str
    season: str
    age_years: float
    minutes_played: float
    archetype: str | None = None


class PlayerProfileResponse(BaseModel):
    """Full player intelligence profile response."""

    player_id: int
    player_name: str
    position_group: str
    team_name: str
    competition: str
    season: str
    age_years: float
    minutes_played: float
    archetype: str | None
    archetype_description: str | None
    capabilities: list[CapabilityScoreResponse]
    similar_players: list[PlayerSummaryResponse]
    is_analytically_sufficient: bool


class TeamProfileResponse(BaseModel):
    """Team intelligence profile response."""

    team_name: str
    competition: str
    season: str
    squad_size: int
    avg_age: float
    style_label: str | None
    strengths: list[str]
    weaknesses: list[str]
    capability_radar: dict[str, float]
    position_distribution: dict[str, int]


class RecruitmentCandidateResponse(BaseModel):
    """Single recruitment candidate."""

    rank: int
    player_id: int
    player_name: str
    position_group: str
    team_name: str
    age_years: float
    minutes_played: float
    fit_score: float
    capability_scores: dict[str, float]
    evidence_summary: str


class DashboardResponse(BaseModel):
    """Executive dashboard summary response."""

    total_players: int
    total_teams: int
    total_competitions: int
    total_matches: int
    top_progressors: list[PlayerSummaryResponse]
    top_creators: list[PlayerSummaryResponse]
    top_defenders: list[PlayerSummaryResponse]


class ScoutingReportResponse(BaseModel):
    """AI-generated scouting report."""

    player_name: str
    season: str
    overview: str
    strengths: str
    weaknesses: str
    recommendation: str
    risks: str
    confidence_level: str


class AthenaQueryResponse(BaseModel):
    """Response from Ask Athena."""

    question: str
    answer: str
    evidence_references: list[str]
    confidence_level: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: str
    code: int
