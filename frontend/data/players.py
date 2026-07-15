"""
frontend/data/players.py — Frontend Data Access for Players.

Retrieves and caches PlayerProfile objects for the UI.
Delegates to backend services or mocked stubs for the frontend shell.
"""

import streamlit as st
from shared.schemas import PlayerProfile, CapabilityProfile, CapabilityScore

@st.cache_data
def _get_mock_profiles() -> list[PlayerProfile]:
    """Generates mock profiles for the UI skeleton."""
    cap1 = CapabilityProfile(
        player_id=1, player_name="Lionel Messi", season="2023", competition="Ligue 1", position_group="Forward", minutes_played=2000,
        ball_progression=CapabilityScore("ball_progression", 85.0, 1.0),
        chance_creation=CapabilityScore("chance_creation", 98.0, 1.0),
        ball_security=CapabilityScore("ball_security", 80.0, 1.0),
        press_resistance=CapabilityScore("press_resistance", 90.0, 1.0),
        defensive_activity=CapabilityScore("defensive_activity", 25.0, 1.0),
        attacking_threat=CapabilityScore("attacking_threat", 95.0, 1.0),
        physical_availability=CapabilityScore("physical_availability", 85.0, 1.0),
        tactical_versatility=CapabilityScore("tactical_versatility", 70.0, 1.0)
    )
    p1 = PlayerProfile(
        player_id=1, player_name="Lionel Messi", position_group="Forward", team_name="Paris Saint-Germain", competition="Ligue 1", season="2023",
        age_years=35, minutes_played=2000, capability_profile=cap1, decision_signals=["elite_goal_scorer", "strong_chance_creator"],
        archetype="Complete Forward", archetype_description="Elite creator and goal threat."
    )
    
    cap2 = CapabilityProfile(
        player_id=2, player_name="Kylian Mbappé", season="2023", competition="Ligue 1", position_group="Forward", minutes_played=2100,
        ball_progression=CapabilityScore("ball_progression", 90.0, 1.0),
        chance_creation=CapabilityScore("chance_creation", 85.0, 1.0),
        ball_security=CapabilityScore("ball_security", 70.0, 1.0),
        press_resistance=CapabilityScore("press_resistance", 75.0, 1.0),
        defensive_activity=CapabilityScore("defensive_activity", 30.0, 1.0),
        attacking_threat=CapabilityScore("attacking_threat", 98.0, 1.0),
        physical_availability=CapabilityScore("physical_availability", 90.0, 1.0),
        tactical_versatility=CapabilityScore("tactical_versatility", 60.0, 1.0)
    )
    p2 = PlayerProfile(
        player_id=2, player_name="Kylian Mbappé", position_group="Forward", team_name="Paris Saint-Germain", competition="Ligue 1", season="2023",
        age_years=24, minutes_played=2100, capability_profile=cap2, decision_signals=["elite_goal_scorer", "clinical_finisher"],
        archetype="Advanced Forward", archetype_description="Pace and elite attacking threat."
    )
    
    cap3 = CapabilityProfile(
        player_id=3, player_name="Erling Haaland", season="2023", competition="Premier League", position_group="Forward", minutes_played=2200,
        ball_progression=CapabilityScore("ball_progression", 50.0, 1.0),
        chance_creation=CapabilityScore("chance_creation", 45.0, 1.0),
        ball_security=CapabilityScore("ball_security", 65.0, 1.0),
        press_resistance=CapabilityScore("press_resistance", 60.0, 1.0),
        defensive_activity=CapabilityScore("defensive_activity", 35.0, 1.0),
        attacking_threat=CapabilityScore("attacking_threat", 99.0, 1.0),
        physical_availability=CapabilityScore("physical_availability", 92.0, 1.0),
        tactical_versatility=CapabilityScore("tactical_versatility", 40.0, 1.0)
    )
    p3 = PlayerProfile(
        player_id=3, player_name="Erling Haaland", position_group="Forward", team_name="Manchester City", competition="Premier League", season="2023",
        age_years=22, minutes_played=2200, capability_profile=cap3, decision_signals=["elite_goal_scorer", "clinical_finisher"],
        archetype="Poacher", archetype_description="In-box goalscoring machine."
    )
    
    cap4 = CapabilityProfile(
        player_id=4, player_name="Rodri", season="2023", competition="Premier League", position_group="Midfielder", minutes_played=2800,
        ball_progression=CapabilityScore("ball_progression", 95.0, 1.0),
        chance_creation=CapabilityScore("chance_creation", 75.0, 1.0),
        ball_security=CapabilityScore("ball_security", 98.0, 1.0),
        press_resistance=CapabilityScore("press_resistance", 92.0, 1.0),
        defensive_activity=CapabilityScore("defensive_activity", 88.0, 1.0),
        attacking_threat=CapabilityScore("attacking_threat", 60.0, 1.0),
        physical_availability=CapabilityScore("physical_availability", 95.0, 1.0),
        tactical_versatility=CapabilityScore("tactical_versatility", 85.0, 1.0)
    )
    p4 = PlayerProfile(
        player_id=4, player_name="Rodri", position_group="Midfielder", team_name="Manchester City", competition="Premier League", season="2023",
        age_years=26, minutes_played=2800, capability_profile=cap4, decision_signals=["elite_ball_progressor", "defensive_specialist"],
        archetype="Deep-Lying Playmaker", archetype_description="Midfield controller and progressor."
    )
    
    return [p1, p2, p3, p4]

@st.cache_data
def get_all_players() -> list[PlayerProfile]:
    """Retrieve all available players."""
    return _get_mock_profiles()

@st.cache_data
def get_player_profile(player_id: int) -> PlayerProfile | None:
    """Retrieve a specific PlayerProfile by ID."""
    for p in get_all_players():
        if p.player_id == player_id:
            return p
    return None
