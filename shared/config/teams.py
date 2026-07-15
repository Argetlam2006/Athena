"""
shared/config/teams.py — Team intelligence configuration.
"""

# Priorities for team playing styles.
PLAYING_STYLE_DEFINITIONS: list[dict[str, str]] = [
    {
        "id": "possession_dominant",
        "label": "Possession-Dominant",
        "description": "Retains and advances the ball deliberately",
    },
    {
        "id": "high_press",
        "label": "High Press",
        "description": "Presses relentlessly and can handle counter-press",
    },
    {
        "id": "direct_progressive",
        "label": "Direct and Progressive",
        "description": "Advances quickly through direct passing",
    },
    {
        "id": "counter_attacking",
        "label": "Counter-Attacking",
        "description": "Defends deep and transitions quickly",
    },
    {
        "id": "defensive_resilient",
        "label": "Defensive and Resilient",
        "description": "Organised defensively; limited attacking threat",
    },
    {
        "id": "balanced",
        "label": "Balanced",
        "description": "Tactically neutral — no dominant characteristic",
    },
]
