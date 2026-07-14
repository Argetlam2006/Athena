"""
shared/schemas.py — Athena data schemas and typed dataclasses

These are the structured data contracts between every layer of the AIF pipeline.

Layer communication flow:
  ETL → PlayerRaw
  Analytics Engine → PlayerFeatureVector
  AIF / Capability Engine → CapabilityProfile
  Intelligence Layer → PlayerProfile, TeamProfile
  Decision Engine → RecruitmentCandidate, ComparisonResult
  AI Layer → ScoutingReport

No layer should access another layer's internal data structures directly.
Always communicate through these schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1–2: Raw and Statistical Data
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PlayerRaw:
    """
    Minimal representation of a player as loaded from StatsBomb.
    Produced by the ETL pipeline.
    """

    statsbomb_id: int
    name: str
    position: str
    team_name: str
    competition_name: str
    season_name: str

    # Optional fields populated if available
    nationality: str | None = None
    birth_date: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None


@dataclass
class MatchRaw:
    """
    Minimal match record from StatsBomb.
    """

    match_id: int
    competition_id: int
    season_id: int
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    match_date: str
    stadium: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2–3: Feature Engineering Output
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PlayerFeatureVector:
    """
    Normalized per-90 features for a player in a given season.
    Produced by the Analytics Engine.

    All numeric features are:
      - normalized to per-90-minute rates (where applicable)
      - expressed as percentiles within position group (0–100)

    This is the direct input to the Athena Intelligence Framework.
    """

    player_id: int
    player_name: str
    season: str
    competition: str
    position_group: str
    minutes_played: float

    # Ball Progression features
    progressive_passes_per90: float = 0.0
    progressive_carries_per90: float = 0.0
    deep_completions_per90: float = 0.0
    final_third_entries_per90: float = 0.0
    penalty_area_entries_per90: float = 0.0

    # Chance Creation features
    key_passes_per90: float = 0.0
    xa_per90: float = 0.0
    shot_assists_per90: float = 0.0
    through_balls_per90: float = 0.0
    crosses_per90: float = 0.0

    # Ball Security features
    pass_completion_pct: float = 0.0
    turnovers_per90: float = 0.0
    dispossessions_per90: float = 0.0
    miscontrols_per90: float = 0.0
    progressive_pass_accuracy: float = 0.0

    # Press Resistance features
    successful_dribbles_per90: float = 0.0
    dribble_success_pct: float = 0.0
    carries_into_final_third_per90: float = 0.0

    # Defensive Activity features
    pressures_per90: float = 0.0
    ball_recoveries_per90: float = 0.0
    interceptions_per90: float = 0.0
    blocks_per90: float = 0.0
    counterpressures_per90: float = 0.0

    # Attacking Threat features
    xg_per90: float = 0.0
    touches_in_box_per90: float = 0.0
    shot_quality_pct: float = 0.0
    goals_per90: float = 0.0
    shots_on_target_per90: float = 0.0

    # Physical Availability features
    matches_started: int = 0
    availability_pct: float = 0.0
    age_years: float = 0.0

    # Tactical Versatility features
    positions_played_count: int = 1
    primary_position_pct: float = 100.0
    formation_appearances_count: int = 1
    performance_consistency_score: float = 0.0

    def to_vector(self) -> list[float]:
        """
        Return all numeric features as a flat list for ML computations.

        Vector composition (36 features):
          Ball Progression (5) + Chance Creation (5) + Ball Security (5)
          + Press Resistance (3) + Defensive Activity (5) + Attacking Threat (5)
          + Physical Availability (4) + Tactical Versatility (4) = 36

        Physical Availability raw features (minutes_played, matches_started,
        availability_pct, age_years) are normalized before similarity computation
        in the ML layer — they are included here as raw values.
        """
        return [
            # Ball Progression (5)
            self.progressive_passes_per90,
            self.progressive_carries_per90,
            self.deep_completions_per90,
            self.final_third_entries_per90,
            self.penalty_area_entries_per90,
            # Chance Creation (5)
            self.key_passes_per90,
            self.xa_per90,
            self.shot_assists_per90,
            self.through_balls_per90,
            self.crosses_per90,
            # Ball Security (5)
            self.pass_completion_pct,
            self.turnovers_per90,
            self.dispossessions_per90,
            self.miscontrols_per90,
            self.progressive_pass_accuracy,
            # Press Resistance (3)
            self.successful_dribbles_per90,
            self.dribble_success_pct,
            self.carries_into_final_third_per90,
            # Defensive Activity (5)
            self.pressures_per90,
            self.ball_recoveries_per90,
            self.interceptions_per90,
            self.blocks_per90,
            self.counterpressures_per90,
            # Attacking Threat (5)
            self.xg_per90,
            self.touches_in_box_per90,
            self.shot_quality_pct,
            self.goals_per90,
            self.shots_on_target_per90,
            # Physical Availability (4)
            self.minutes_played,
            float(self.matches_started),
            self.availability_pct,
            self.age_years,
            # Tactical Versatility (4)
            float(self.positions_played_count),
            self.primary_position_pct,
            float(self.formation_appearances_count),
            self.performance_consistency_score,
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3: Capability Scores
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CapabilityScore:
    """
    A single capability score with supporting evidence.

    score: 0–100, higher is better (always)
    confidence: 0–1, based on sample size and data completeness
    evidence: dict of metric_name → raw_value for traceability
    """

    capability: str
    score: float
    confidence: float
    evidence: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 100.0):
            raise ValueError(f"Capability score must be 0–100, got {self.score}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be 0–1, got {self.confidence}")


@dataclass
class CapabilityProfile:
    """
    Complete capability profile for a player.
    The primary output of the Athena Intelligence Framework.

    All 8 capabilities must be present. None may be skipped.
    """

    player_id: int
    player_name: str
    season: str
    competition: str
    position_group: str
    minutes_played: float

    # The 8 capabilities
    ball_progression: CapabilityScore | None = None
    chance_creation: CapabilityScore | None = None
    ball_security: CapabilityScore | None = None
    press_resistance: CapabilityScore | None = None
    defensive_activity: CapabilityScore | None = None
    attacking_threat: CapabilityScore | None = None
    physical_availability: CapabilityScore | None = None
    tactical_versatility: CapabilityScore | None = None

    def as_radar_dict(self) -> dict[str, float]:
        """Return capability scores suitable for radar chart rendering."""
        return {
            "Ball Progression":     self.ball_progression.score if self.ball_progression else 0.0,
            "Chance Creation":      self.chance_creation.score if self.chance_creation else 0.0,
            "Ball Security":        self.ball_security.score if self.ball_security else 0.0,
            "Press Resistance":     self.press_resistance.score if self.press_resistance else 0.0,
            "Defensive Activity":   self.defensive_activity.score if self.defensive_activity else 0.0,
            "Attacking Threat":     self.attacking_threat.score if self.attacking_threat else 0.0,
            "Physical Availability": self.physical_availability.score if self.physical_availability else 0.0,
            "Tactical Versatility": self.tactical_versatility.score if self.tactical_versatility else 0.0,
        }

    def overall_confidence(self) -> float:
        """Mean confidence across all populated capabilities."""
        scores = [
            cap.confidence
            for cap in [
                self.ball_progression, self.chance_creation, self.ball_security,
                self.press_resistance, self.defensive_activity, self.attacking_threat,
                self.physical_availability, self.tactical_versatility,
            ]
            if cap is not None
        ]
        return sum(scores) / len(scores) if scores else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Layer 4: Player Intelligence
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PlayerProfile:
    """
    Complete player intelligence profile.

    Combines:
      - Biographical metadata
      - Feature vector (statistics)
      - Capability profile
      - Archetype label

    This is the primary object consumed by the UI and Decision Engine.
    """

    player_id: int
    player_name: str
    position_group: str
    team_name: str
    competition: str
    season: str
    age_years: float
    minutes_played: float

    capability_profile: CapabilityProfile | None = None
    feature_vector: PlayerFeatureVector | None = None

    # Computed by rule-based archetype engine
    archetype: str | None = None
    archetype_description: str | None = None

    # Similarity results (populated on demand)
    similar_players: list[dict[str, Any]] = field(default_factory=list)

    def is_analytically_sufficient(self) -> bool:
        """True if player has enough minutes for reliable analytics."""
        from shared.constants import MIN_MINUTES_THRESHOLD
        return self.minutes_played >= MIN_MINUTES_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────────
# Layer 5: Team Intelligence
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TeamProfile:
    """
    Team intelligence profile.

    Aggregates player capabilities into collective tactical characteristics.
    """

    team_id: int
    team_name: str
    competition: str
    season: str
    squad_size: int

    # Average capability scores across squad
    avg_ball_progression: float = 0.0
    avg_chance_creation: float = 0.0
    avg_ball_security: float = 0.0
    avg_press_resistance: float = 0.0
    avg_defensive_activity: float = 0.0
    avg_attacking_threat: float = 0.0
    avg_physical_availability: float = 0.0
    avg_tactical_versatility: float = 0.0

    # Squad composition
    avg_age: float = 0.0
    position_distribution: dict[str, int] = field(default_factory=dict)

    # Identified tactical identity (derived from capability profile)
    style_label: str | None = None
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    def as_radar_dict(self) -> dict[str, float]:
        """Return average capability scores for radar chart rendering."""
        return {
            "Ball Progression":      self.avg_ball_progression,
            "Chance Creation":       self.avg_chance_creation,
            "Ball Security":         self.avg_ball_security,
            "Press Resistance":      self.avg_press_resistance,
            "Defensive Activity":    self.avg_defensive_activity,
            "Attacking Threat":      self.avg_attacking_threat,
            "Physical Availability": self.avg_physical_availability,
            "Tactical Versatility":  self.avg_tactical_versatility,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Layer 6: Decision Intelligence
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RecruitmentCandidate:
    """
    A ranked recruitment candidate produced by the Decision Engine.

    Every candidate must have:
      - A composite fitness score
      - A breakdown of how that score was computed
      - The evidence supporting it
    """

    player_id: int
    player_name: str
    position_group: str
    team_name: str
    season: str
    age_years: float
    minutes_played: float

    # Overall fitness for the specified requirements
    fit_score: float = 0.0

    # Component scores (subset of capabilities relevant to the query)
    capability_scores: dict[str, float] = field(default_factory=dict)

    # Evidence text for explainability
    evidence_summary: str = ""

    # Rank within the candidate list
    rank: int = 0


@dataclass
class ComparisonResult:
    """
    Side-by-side comparison of two or more players.
    """

    players: list[PlayerProfile]
    capability_comparison: dict[str, dict[str, float]] = field(default_factory=dict)
    # capability_comparison structure:
    # { "ball_progression": {"Player A": 87.0, "Player B": 72.0}, ... }

    winner_by_capability: dict[str, str] = field(default_factory=dict)
    # { "ball_progression": "Player A", ... }

    summary: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Layer 7: AI / Explanation Output
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScoutingReport:
    """
    AI-generated scouting report for a player.

    The LLM produces this only after receiving a structured context
    containing capability scores, feature vectors, and evidence.
    The report must reference analytical evidence — never invent statistics.
    """

    player_name: str
    season: str
    report_type: str  # "player" | "team" | "recruitment" | "comparison"

    # Structured sections
    overview: str = ""
    strengths: str = ""
    weaknesses: str = ""
    recommendation: str = ""
    risks: str = ""

    # The structured context injected into the prompt (for auditability)
    analytical_context: dict[str, Any] = field(default_factory=dict)

    # Confidence in the report (derived from data quality)
    confidence_level: str = "medium"  # "low" | "medium" | "high"


# ─────────────────────────────────────────────────────────────────────────────
# Validation utilities
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """
    Result of a data validation check.
    """

    dataset: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        True if there are no invalid rows AND no errors.

        Checking invalid_rows alone is insufficient: a file-not-found error
        sets invalid_rows=0 (there were no rows to invalidate) but the result
        is definitely not valid.
        """
        return self.invalid_rows == 0 and len(self.errors) == 0

    @property
    def validity_pct(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return round(self.valid_rows / self.total_rows * 100, 2)
