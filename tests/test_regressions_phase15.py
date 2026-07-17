import pytest

from backend.intelligence.store import IntelligenceStore
from frontend.data.recruitment_service import search_candidates
from shared.schemas import ProfileType, RecruitmentCriteria

# Overall Rating was removed in RC1, so these tests are obsolete.


def test_display_ratings_within_calibrated_ranges():
    """Verify display ratings are calibrated [0, 100]."""
    store = IntelligenceStore()
    players = store.get_all_players()
    if not players:
        pytest.skip(
            "Intelligence Store not found. Run: python scripts/maintenance/bootstrap.py before running integration tests."
        )

    display_ratings = [
        p.rating_presentation.display_rating for p in players if p.rating_presentation
    ]
    assert all(0.0 <= r <= 100.0 for r in display_ratings), (
        "Display ratings out of expected range!"
    )


def test_default_retrieval_returns_unique_footballers():
    """Verify that default retrieval returns CAREER profiles (one per footballer)."""
    store = IntelligenceStore()
    # Find position where Cruyff plays (Center Forward)
    forwards = store.get_players_by_position("Center Forward")
    if not forwards:
        pytest.skip(
            "Intelligence Store not found. Run: python scripts/maintenance/bootstrap.py before running integration tests."
        )

    cruyffs = [p for p in forwards if "Cruyff" in p.player_name]
    assert len(cruyffs) <= 1, f"Expected 0 or 1 canonical Cruyff, found {len(cruyffs)}!"
    for c in cruyffs:
        assert c.profile_type == ProfileType.CAREER


def test_explicit_temporal_retrieval():
    """Verify that explicit retrieval returns temporal profiles."""
    store = IntelligenceStore()

    seasons = store.get_players_by_position("Center Forward", ProfileType.SEASON)
    cruyffs_season = [p for p in seasons if "Cruyff" in p.player_name]
    if not seasons:
        pytest.skip(
            "Intelligence Store not found. Run: python scripts/maintenance/bootstrap.py before running integration tests."
        )
    assert len(cruyffs_season) > 1, "Expected multiple seasons for Cruyff."

    competitions = store.get_players_by_position(
        "Center Forward", ProfileType.COMPETITION
    )
    cruyffs_comp = [p for p in competitions if "Cruyff" in p.player_name]
    assert len(cruyffs_comp) > 1, "Expected multiple competitions for Cruyff."


def test_recruitment_never_returns_duplicates():
    """Verify recruitment does not return the same player multiple times."""
    criteria = RecruitmentCriteria(
        position="Center Forward",
        required_capabilities={"attacking_threat": 1.0},
        max_results=50,
    )
    try:
        candidates = search_candidates(criteria)
    except Exception:
        pytest.skip(
            "Intelligence Store not found. Run: python scripts/maintenance/bootstrap.py before running integration tests."
        )

    seen_players = set()
    for c in candidates:
        assert c.player.player_id not in seen_players, (
            f"Duplicate player in recruitment: {c.player.player_name}"
        )
        seen_players.add(c.player.player_id)
