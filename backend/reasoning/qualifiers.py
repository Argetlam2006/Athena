"""
backend/reasoning/qualifiers.py — Qualifier derivation for Claims.

Every qualifier is derived from existing deterministic engine outputs
(confidence bands, decision signals, sample thresholds).  No qualifier
introduces new football knowledge.

This is the declared qualifier registry: adding a new qualifier kind
requires registering it here with its derivation logic and test fixture.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.schemas.retrieval import ClaimQualifier, QualifierKind, Severity


@dataclass(frozen=True)
class QualifierRule:
    """Declares one qualifier kind's derivation logic."""

    kind: QualifierKind
    category: str
    """sample_quality | context | methodological"""

    source: str
    """What engine output this derives from (e.g. 'small_sample_warning signal',
    'CapabilityScore.confidence', 'matches_played')."""

    description: str


# ─── Qualifier Rule Registry ──────────────────────────────────────────────────

QUALIFIER_RULES: list[QualifierRule] = [
    QualifierRule(
        kind=QualifierKind.SAMPLE_SIZE,
        category="sample_quality",
        source="decision_signals: small_sample_warning; matches_played threshold",
        description="Derived from matches_played vs. confidence thresholds (spec sec.10.3).",
    ),
    QualifierRule(
        kind=QualifierKind.LEAGUE_CONTEXT,
        category="context",
        source="PlayerProfile.competition field",
        description="Always informational; material only in cross-competition comparisons.",
    ),
    QualifierRule(
        kind=QualifierKind.REGRESSION_RISK,
        category="methodological",
        source="goals_minus_xg > 0 on low volume (CapabilityScore.evidence)",
        description="Attaching threat overperformance on small sample. See spec sec.4.6.",
    ),
    QualifierRule(
        kind=QualifierKind.ROLE_DEPENDENCE,
        category="context",
        source="position_group field; signal definitions gated on position",
        description="Claim interpretation depends on positional context.",
    ),
    QualifierRule(
        kind=QualifierKind.DATA_COVERAGE,
        category="sample_quality",
        source="minutes_played; position-specific metric stabilization thresholds",
        description="Below stabilisation point for underlying metrics.",
    ),
    QualifierRule(
        kind=QualifierKind.OVERPERFORMANCE_CAVEAT,
        category="methodological",
        source="goals_minus_xg capped at 0 downside (spec sec.4.6)",
        description="Asymmetrical qualifier — overperformance is noted, underperformance is not.",
    ),
]


# ─── Derivation functions ─────────────────────────────────────────────────────


def derive_qualifiers(
    matches_played: int | None = None,
    minutes_played: float | None = None,
    competition: str | None = None,
    decision_signals: list[str] | None = None,
    score: float | None = None,
    evidence_count: int | None = None,
    position_group: str | None = None,
    goals_minus_xg: float | None = None,
    goals_total: int | None = None,
) -> list[ClaimQualifier]:
    """Derive all applicable qualifiers for a claim from existing engine data.

    Args:
        matches_played: Player's match count for this profile.
        minutes_played: Total minutes played.
        competition: League/competition name.
        decision_signals: List of generated signal names.
        score: Capability score (0-100).
        evidence_count: Number of supporting metrics.
        position_group: Player's position group.
        goals_minus_xg: xG overperformance (from raw_metrics).
        goals_total: Total goals scored.

    Returns:
        List of ClaimQualifiers (empty if no qualifying conditions met).
    """
    qualifiers: list[ClaimQualifier] = []
    signals = set(decision_signals or [])

    # SAMPLE_SIZE: < 5 matches = material; 5-9 = cautionary
    if matches_played is not None:
        if matches_played < 3:
            qualifiers.append(ClaimQualifier(
                kind=QualifierKind.SAMPLE_SIZE,
                severity=Severity.MATERIAL,
                statement=f"Sample size too small ({matches_played} matches) — score is provisional.",
            ))
        elif matches_played < 5:
            qualifiers.append(ClaimQualifier(
                kind=QualifierKind.SAMPLE_SIZE,
                severity=Severity.CAUTIONARY,
                statement=f"Limited sample ({matches_played} matches) — treat as indicative.",
            ))
        elif matches_played < 10:
            qualifiers.append(ClaimQualifier(
                kind=QualifierKind.SAMPLE_SIZE,
                severity=Severity.INFORMATIONAL,
                statement=f"Developing sample ({matches_played} matches) — confidence increases with more data.",
            ))

    # DATA_COVERAGE: low minutes = cautionary
    if minutes_played is not None and minutes_played < 450:
        qualifiers.append(ClaimQualifier(
            kind=QualifierKind.DATA_COVERAGE,
            severity=Severity.CAUTIONARY,
            statement=f"Low minutes ({int(minutes_played)}) — metric reliability may be reduced.",
        ))

    # LEAGUE_CONTEXT: always informational when a competition is known
    if competition and competition not in ("Multiple", "All Competitions Career"):
        qualifiers.append(ClaimQualifier(
            kind=QualifierKind.LEAGUE_CONTEXT,
            severity=Severity.INFORMATIONAL,
            statement=f"Based on {competition} data only.",
        ))

    # REGRESSION_RISK: goals_minus_xg > 0 on small volume
    if goals_minus_xg is not None and goals_minus_xg > 0:
        if goals_total is not None and goals_total < 5:
            qualifiers.append(ClaimQualifier(
                kind=QualifierKind.REGRESSION_RISK,
                severity=Severity.CAUTIONARY,
                statement=f"xG overperformance on small goal sample ({goals_total} goals) — may regress.",
            ))

    # ROLE_DEPENDENCE: certain signals are position-gated
    if "progressive_fullback" in signals and position_group:
        if position_group not in ("Fullback", "Defender"):
            qualifiers.append(ClaimQualifier(
                kind=QualifierKind.ROLE_DEPENDENCE,
                severity=Severity.INFORMATIONAL,
                statement="Signal 'Progressive Fullback' is position-dependent — verify role fit.",
            ))

    # OVERPERFORMANCE_CAVEAT: asymmetric qualifier per spec sec.4.6
    if goals_minus_xg is not None and goals_minus_xg > 2.0:
        qualifiers.append(ClaimQualifier(
            kind=QualifierKind.OVERPERFORMANCE_CAVEAT,
            severity=Severity.INFORMATIONAL,
            statement=f"Goals significantly exceed xG (+{goals_minus_xg:.1f}) — may not be sustained.",
        ))

    return qualifiers


def derive_qualifiers_from_profile(
    profile,
    capability_name: str | None = None,
) -> list[ClaimQualifier]:
    """Convenience wrapper: derive qualifiers from a PlayerProfile (or profile-like object).

    Extracts the fields needed by derive_qualifiers() from the profile,
    including capability-specific data where applicable.
    """
    matches = getattr(profile, "matches_played", None)
    mins = getattr(profile, "minutes_played", None)
    comp = getattr(profile, "competition", None)
    signals = getattr(profile, "decision_signals", None) or []
    pos = getattr(profile, "position_group", None)

    # Extract goals/xG from raw_metrics if available
    raw = getattr(profile, "raw_metrics", None) or {}
    goals_minus_xg = None
    goals_total = None
    if raw:
        goals_minus_xg = raw.get("goals_minus_xg", None)
        goals_total = raw.get("goals", None)
    # Also check feature_vector
    fv = getattr(profile, "feature_vector", None)
    if fv:
        gm = getattr(fv, "goals_minus_xg", None)
        if gm is not None:
            goals_minus_xg = gm
        g = getattr(fv, "goals_p90", None)
        if g is not None and goals_total is None and mins:
            goals_total = int(g * mins / 90)

    return derive_qualifiers(
        matches_played=matches,
        minutes_played=mins,
        competition=comp,
        decision_signals=signals,
        position_group=pos,
        goals_minus_xg=goals_minus_xg,
        goals_total=goals_total,
    )
