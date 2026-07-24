"""Regression coverage for Retrieval v2's Track B user-facing boundary."""

from types import SimpleNamespace

import pytest

from backend.explanation.conversation import ConversationManager
from backend.explanation.prompt_builder import PromptPackage
from backend.retrieval.context import get_context
from backend.retrieval.debug import get_last_trace
from backend.retrieval.resolver import EntityIndex, _normalize, normalize_query
from frontend.data import retrieval_service
from frontend.data.retrieval_service import RetrievalAthenaService
from shared.schemas.retrieval import IntentType, StructuredIntent


def _player(player_id: int, name: str) -> dict:
    return {"id": player_id, "name": name, "norm": _normalize(name), "type": "player"}


def _team(entity_id: str, name: str) -> dict:
    return {"entity_id": entity_id, "name": name, "norm": _normalize(name), "type": "team"}


@pytest.fixture
def entity_index() -> EntityIndex:
    index = EntityIndex()
    index._loaded = True
    index._players = {
        "bernardo silva": _player(1, "Bernardo Silva"),
        "thiago silva": _player(2, "Thiago Silva"),
        "cristiano ronaldo": _player(3, "Cristiano Ronaldo"),
        "ronaldo nazario": _player(4, "Ronaldo Nazario"),
        "julian alvarez": _player(5, "Julian Alvarez"),
        "edson alvarez": _player(6, "Edson Alvarez"),
        "kevin de bruyne": _player(7, "Kevin De Bruyne"),
        "lautaro martinez": _player(8, "Lautaro Martinez"),
        "lisandro martinez": _player(9, "Lisandro Martinez"),
    }
    index._teams = {
        "manchester city": _team("mc", "Manchester City"),
        "leicester city": _team("lc", "Leicester City"),
        "manchester united": _team("mu", "Manchester United"),
        "newcastle united": _team("nu", "Newcastle United"),
    }
    index._build_alias_tables()
    return index


@pytest.mark.parametrize(
    "query", ["Silva", "Ronaldo", "Martinez", "Alvarez", "City", "United"]
)
def test_ambiguous_tokens_always_return_deterministic_candidates(entity_index, query):
    ambiguities = entity_index.find_ambiguities(query)

    assert len(ambiguities) == 1
    assert ambiguities[0]["query"].lower() == query.lower()
    assert len(ambiguities[0]["candidates"]) > 1


def test_explicit_alias_and_full_name_remain_unambiguous(entity_index):
    assert entity_index.find_ambiguities("KDB") == []
    assert entity_index.resolve_player("KDB")["name"] == "Kevin De Bruyne"
    assert entity_index.find_ambiguities("Manchester City") == []


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Analyse KDB", "analyze KDB"),
        ("Compare A vs B", "Compare A compare B"),
        ("Find a DM", "Find a defensive midfielder"),
        ("Assess the defence", "Assess the defense"),
    ],
)
def test_query_normalization_is_deterministic(query, expected):
    assert normalize_query(query) == expected


class _SuccessfulBridge:
    def build_prompt(self, user_query, intent):
        return PromptPackage(
            system_prompt="system",
            user_prompt="user",
            serialized_context="{}",
            prompt_version="test",
            metadata={
                "retrieval_used": True,
                "retrieval_strategy": "test_strategy",
                "retrieval_plan_id": "plan_test",
                "retrieval_entity_count": 1,
                "retrieval_traversal_count": 1,
                "retrieval_execution_time_ms": 2.0,
                "retrieval_claim_count": 1,
                "retrieval_coverage_satisfied": ["capability"],
                "retrieval_coverage_missing": [],
                "retrieval_coverage_complete": True,
                "context_size_bytes": 2,
                "debug_traversal_summary": ["traverse_edges:has_capability"],
                "debug_projected_claims": ["A deterministic claim."],
                "debug_evidence_bundle": {"claim_count": 1, "traversal_count": 1},
            },
        )


class _NoRetrievalBridge(_SuccessfulBridge):
    def build_prompt(self, user_query, intent):
        package = super().build_prompt(user_query, intent)
        package.metadata["retrieval_used"] = False
        return package


class _Provider:
    def __init__(self):
        self.called = False

    def generate(self, prompt_package):
        self.called = True
        return SimpleNamespace(generated_text="Evidence-backed answer", model="test", provider="test")


def _service(intent, bridge, provider, monkeypatch):
    has_entities = bool(intent.entities)
    monkeypatch.setattr(
        retrieval_service,
        "_adapt_intent",
        lambda *args: (intent, {"players": [{"name": "Test Player"}], "teams": []} if has_entities else {"players": [], "teams": []}),
    )
    monkeypatch.setattr(
        "backend.retrieval.resolver.get_entity_index",
        lambda: SimpleNamespace(
            find_ambiguities=lambda query: [],
            resolve_both=lambda query: {"players": [], "teams": []},
        ),
    )
    service = RetrievalAthenaService.__new__(RetrievalAthenaService)
    service.bridge = bridge
    service.provider = provider
    service.manager = ConversationManager()
    return service


@pytest.mark.parametrize(
    "intent_type",
    [
        IntentType.PLAYER_ANALYSIS,
        IntentType.TEAM_ANALYSIS,
        IntentType.COMPARE_PLAYERS,
        IntentType.RECRUITMENT,
    ],
)
def test_supported_request_types_use_retrieval_metadata(intent_type, monkeypatch):
    intent = StructuredIntent(intent_type, {"focus_player": "1"}, raw_text="test")
    provider = _Provider()
    service = _service(intent, _SuccessfulBridge(), provider, monkeypatch)

    assert service.process_turn("test", "workspace", None, None) == "Evidence-backed answer"
    assert provider.called
    metadata = service.manager.state.messages[-1].metadata
    assert metadata["retrieval_used"] is True
    assert metadata["retrieval_plan_id"] == "plan_test"


def test_empty_retrieval_never_falls_back_to_the_provider(monkeypatch):
    intent = StructuredIntent(
        IntentType.GENERAL, {"focus_player": "1"}, raw_text="malformed query"
    )
    provider = _Provider()
    service = _service(intent, _NoRetrievalBridge(), provider, monkeypatch)

    response = service.process_turn("malformed query", "workspace", None, None)

    assert not provider.called
    assert "won't fill the gaps with guesses" in response


@pytest.mark.parametrize("query", ["Unknown Prospect", "Out-of-dataset Player", "???"])
def test_unknown_or_malformed_queries_fail_without_a_provider_call(query, monkeypatch):
    context = get_context()
    context.current_player_id = None
    context.comparison_pair = None
    context.last_intent = ""
    intent = StructuredIntent(IntentType.PLAYER_ANALYSIS, {}, raw_text=query)
    provider = _Provider()
    service = _service(intent, _SuccessfulBridge(), provider, monkeypatch)

    response = service.process_turn(query, "workspace", None, None)

    assert not provider.called
    assert "couldn't confidently match" in response


def test_team_comparison_without_a_team_comparison_strategy_fails_safely(monkeypatch):
    intent = StructuredIntent(
        IntentType.TEAM_ANALYSIS,
        {"team_focus": "mc", "team_compare": "ars"},
        raw_text="Compare Manchester City and Arsenal",
    )
    provider = _Provider()
    service = _service(intent, _NoRetrievalBridge(), provider, monkeypatch)

    response = service.process_turn(intent.raw_text, "workspace", None, None)

    assert not provider.called
    assert "won't fill the gaps with guesses" in response


def test_ambiguity_returns_a_clarification_before_retrieval(monkeypatch):
    provider = _Provider()
    service = RetrievalAthenaService.__new__(RetrievalAthenaService)
    service.bridge = _SuccessfulBridge()
    service.provider = provider
    service.manager = ConversationManager()
    monkeypatch.setattr(
        "backend.retrieval.resolver.get_entity_index",
        lambda: SimpleNamespace(
            find_ambiguities=lambda query: [
                {
                    "query": "Ronaldo",
                    "candidates": [
                        _player(3, "Cristiano Ronaldo"),
                        _player(4, "Ronaldo Nazario"),
                    ],
                }
            ]
        ),
    )

    response = service.process_turn("Analyze Ronaldo", "workspace", None, None)

    assert not provider.called
    assert "Which one did you mean?" in response
    assert get_last_trace().outcome == "clarification"


def test_debug_report_is_attached_only_when_enabled(monkeypatch):
    intent = StructuredIntent(IntentType.PLAYER_ANALYSIS, {"focus_player": "1"}, raw_text="test")
    provider = _Provider()
    monkeypatch.setenv("ATHENA_DEBUG", "true")
    service = _service(intent, _SuccessfulBridge(), provider, monkeypatch)

    service.process_turn("test", "workspace", None, None)

    metadata = service.manager.state.messages[-1].metadata
    assert "ATHENA DEBUG REPORT" in metadata["debug_report"]
    assert "A deterministic claim." in metadata["debug_report"]
    assert "'claim_count': 1" in metadata["debug_report"]
    assert get_last_trace().outcome == "success"


def test_follow_up_context_resolves_without_generic_fallback(monkeypatch):
    context = get_context()
    context.current_player_id = 7
    context.last_intent = IntentType.PLAYER_ANALYSIS.value
    intent = StructuredIntent(IntentType.PLAYER_ANALYSIS, {}, raw_text="his strengths")
    provider = _Provider()
    service = _service(intent, _SuccessfulBridge(), provider, monkeypatch)

    assert service.process_turn("his strengths", "workspace", None, None) == "Evidence-backed answer"
    assert provider.called
