"""
shared/config/signals.py — Decision signal constants.
"""

SIGNAL_DEFINITIONS: dict[str, dict[str, str]] = {
    # Attacking
    "elite_goal_scorer": {"label": "Elite Goal Scorer", "category": "Attacking"},
    "strong_chance_creator": {"label": "Strong Chance Creator", "category": "Attacking"},
    "clinical_finisher": {"label": "Clinical Finisher", "category": "Attacking"},
    "xg_efficient_attacker": {"label": "xG-Efficient Attacker", "category": "Attacking"},
    "dual_threat_forward": {"label": "Dual Threat Forward", "category": "Attacking"},
    
    # Progression
    "elite_ball_progressor": {"label": "Elite Ball Progressor", "category": "Progression"},
    "progressive_fullback": {"label": "Progressive Fullback", "category": "Progression"},
    "line_breaking_passer": {"label": "Line-Breaking Passer", "category": "Progression"},
    "ball_carrying_threat": {"label": "Ball-Carrying Threat", "category": "Progression"},
    
    # Technical
    "high_press_resistant": {"label": "High Press Resistant", "category": "Technical"},
    "technical_ball_retainer": {"label": "Technical Ball Retainer", "category": "Technical"},
    "reliable_passer": {"label": "Reliable Passer", "category": "Technical"},
    
    # Defensive
    "defensive_specialist": {"label": "Defensive Specialist", "category": "Defensive"},
    "high_intensity_presser": {"label": "High-Intensity Presser", "category": "Defensive"},
    "ball_winner": {"label": "Ball Winner", "category": "Defensive"},
    
    # Profile
    "tactically_versatile": {"label": "Tactically Versatile", "category": "Profile"},
    "box_to_box_profile": {"label": "Box-to-Box Profile", "category": "Profile"},
    "well_rounded": {"label": "Well-Rounded", "category": "Profile"},
    "low_availability_risk": {"label": "Low Availability Risk", "category": "Profile"},
    "small_sample_warning": {"label": "Small Sample Warning", "category": "Profile"},
}
