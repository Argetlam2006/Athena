import pytest

from backend.collective.engine import compute_team_grade
from backend.explanation.conversation import ConversationManager
from backend.intelligence.store import IntelligenceStore
from frontend.data.dashboard import get_dashboard_summary
from frontend.data.recruitment_service import search_candidates
from shared.schemas import CollectiveProfile, ProfileType, RecruitmentCriteria


@pytest.fixture
def store():
    return IntelligenceStore()


def test_store_contains_competition_profiles(store):
    comp_profiles = store.get_all_players(ProfileType.COMPETITION)
    if not comp_profiles:
        pytest.skip("Intelligence Store not found. Run: python scripts/maintenance/bootstrap.py before running integration tests.")
    assert len(comp_profiles) > 0, "Store is missing Competition profiles"


def test_store_contains_season_profiles(store):
    season_profiles = store.get_all_players(ProfileType.SEASON)
    if not season_profiles:
        pytest.skip("Intelligence Store not found. Run: python scripts/maintenance/bootstrap.py before running integration tests.")
    assert len(season_profiles) > 0, "Store is missing Season profiles"


def test_store_contains_career_profiles(store):
    career_profiles = store.get_all_players(ProfileType.CAREER)
    if not career_profiles:
        pytest.skip("Intelligence Store not found. Run: python scripts/maintenance/bootstrap.py before running integration tests.")
    assert len(career_profiles) > 0, "Store is missing Career profiles"


def test_dashboard_counts_match_store_metadata(store):
    summary = get_dashboard_summary()

    comp_count = len(store.get_all_players(ProfileType.COMPETITION))
    season_count = len(store.get_all_players(ProfileType.SEASON))
    career_count = len(store.get_all_players(ProfileType.CAREER))

    assert summary["competition_profiles"] == comp_count
    assert summary["season_profiles"] == season_count
    assert summary["career_profiles"] == career_count


def test_recruitment_returns_non_empty_results():
    from backend.intelligence.store import IntelligenceStore
    store = IntelligenceStore()
    if not store.get_all_players(ProfileType.COMPETITION):
        pytest.skip("Intelligence Store not found. Run: python scripts/maintenance/bootstrap.py before running integration tests.")

    criteria = RecruitmentCriteria(
        position="Central Midfielder", required_capabilities={"ball_progression": 1.0}
    )
    candidates = search_candidates(criteria)
    assert len(candidates) > 0, (
        "Recruitment returned no candidates for a generic search"
    )


def test_team_grades_computed_dynamically():
    # Mock a team with average capability of 82.0 (Should be 'A')
    team = CollectiveProfile(
        team_id=1,
        team_name="Test",
        competition="Test",
        season="Test",
        avg_capabilities={
            "ball_progression": 82.0,
            "chance_creation": 82.0,
            "ball_security": 82.0,
            "press_resistance": 82.0,
            "defensive_activity": 82.0,
            "attacking_threat": 82.0,
        },
    )
    grade = compute_team_grade(team)
    assert grade == "A", f"Expected grade A, got {grade}"


def test_conversation_manager_interaction():
    manager = ConversationManager()
    manager.add_user_message("Hello Athena")
    manager.add_assistant_message("Hello User")

    history = manager.get_history()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
