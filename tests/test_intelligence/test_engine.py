"""
tests/test_intelligence/test_engine.py
"""

from backend.intelligence.engine import FootballIntelligenceEngine
from shared.schemas import PlayerFeatureVector


def test_engine_process_cohort():
    # Create a small cohort
    p1 = PlayerFeatureVector(
        player_id=1,
        player_name="Lionel Messi",
        season="2022/2023",
        competition="Ligue 1",
        position_group="Forward",
        minutes_played=2500,
        matches_played=30,
        npxg_p90=0.8,
        progressive_passes_p90=8.0,
    )
    p2 = PlayerFeatureVector(
        player_id=2,
        player_name="Kylian Mbappe",
        season="2022/2023",
        competition="Ligue 1",
        position_group="Forward",
        minutes_played=2800,
        matches_played=32,
        npxg_p90=0.9,
        progressive_passes_p90=4.0,
    )
    p3 = PlayerFeatureVector(
        player_id=3,
        player_name="Kevin De Bruyne",
        season="2022/2023",
        competition="Premier League",
        position_group="Midfielder",
        minutes_played=2700,
        matches_played=31,
        npxg_p90=0.3,
        progressive_passes_p90=9.5,
    )

    engine = FootballIntelligenceEngine(competition_matches=38)
    profiles = engine.process_cohort([p1, p2, p3])

    assert len(profiles) == 3

    # Check Lionel Messi
    messi = next(p for p in profiles if p.player_name == "Lionel Messi")
    assert messi.archetype is not None
    assert messi.capability_profile is not None
    assert messi.capability_profile.ball_progression is not None

    # Check Team aggregation
    team_profile = engine.process_team(
        team_id=101,
        team_name="PSG",
        competition="Ligue 1",
        season="2022/2023",
        players=[p for p in profiles if p.position_group == "Forward"],  # mock team
    )
    assert team_profile.team_name == "PSG"
    assert team_profile.squad_size == 2
    assert team_profile.style_label is not None
