"""
tests/test_explanation/test_explanation_platform.py — Tests for Phase 7B Explanation Platform.
"""

from backend.explanation.context import EvidencePacket, PlayerExplanationContext
from backend.explanation.conversation import ConversationManager
from backend.explanation.prompt_builder import (
    PromptBuilder,
    PromptPackage,
    SystemPromptBuilder,
)
from backend.explanation.providers.demo_provider import DemoProvider
from backend.explanation.providers.factory import get_provider


def test_prompt_builder():
    ctx = PlayerExplanationContext(
        player_id=1,
        player_name="Test Player",
        team_name="Test Team",
        position_group="Forward",
        birth_date="2000-01-01",
        minutes_played=2000,
        archetype="Striker",
        overall_confidence=1.0,
        evidence_packets=[
            EvidencePacket(
                source="cap:1",
                title="Test Cap",
                confidence=1.0,
                supporting_metrics={"score": 90.0},
            )
        ],
    )

    pb = PromptBuilder()
    pkg = pb.build("Who is this?", ctx, "player")

    assert isinstance(pkg, PromptPackage)
    assert pkg.prompt_version == SystemPromptBuilder.VERSION
    assert "Evidence before AI" in pkg.system_prompt
    assert "Test Player" in pkg.serialized_context
    assert "Who is this?" in pkg.user_prompt
    assert pkg.metadata["context_type"] == "player"


def test_provider_factory():
    # Test specific fallback (demo)
    p = get_provider("demo")
    assert isinstance(p, DemoProvider)
    assert p.is_available() is True


def test_conversation_manager():
    mgr = ConversationManager()
    mgr.add_user_message("Hello")
    assert len(mgr.state.messages) == 1

    changed = mgr.detect_and_handle_context_change(
        current_player_id=1,
        current_team_id=None,
        current_workspace="player_intelligence",
    )
    assert changed is True
    assert len(mgr.state.messages) == 2
    assert mgr.state.messages[1].role == "system"
    assert "Context changed" in mgr.state.messages[1].content

    # Second check with no changes
    changed2 = mgr.detect_and_handle_context_change(
        current_player_id=1,
        current_team_id=None,
        current_workspace="player_intelligence",
    )
    assert changed2 is False
    assert len(mgr.state.messages) == 2
