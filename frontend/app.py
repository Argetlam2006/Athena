"""
# ruff: noqa: E402
frontend/app.py — Athena Streamlit application entry point.

This is the main application shell. Run with:
    streamlit run frontend/app.py

It delegates styling, state management, and navigation to their respective modules,
and routes to the active workspace.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Path setup — allow imports from project root
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Workspace imports
import frontend.workspaces.dashboard as dashboard  # noqa: E402
import frontend.workspaces.player_intelligence as player_intelligence  # noqa: E402
import frontend.workspaces.recruitment_intelligence as recruitment_intelligence  # noqa: E402
import frontend.workspaces.team_intelligence as team_intelligence  # noqa: E402
from frontend.components.states import render_empty_state  # noqa: E402
from frontend.layout import render_page_header  # noqa: E402
from frontend.session import get_state, init_session  # noqa: E402
from frontend.sidebar import render_global_sidebar  # noqa: E402
from frontend.theme import load_theme  # noqa: E402
from shared.config.navigation import get_workspace_by_id  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Application Initialization
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Athena — Football Decision Intelligence",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_resource
def _print_startup_diagnostic():
    from shared.config.settings import settings
    from backend.explanation.providers.factory import get_provider
    from backend.explanation.providers.base import GenerationResponse
    from backend.explanation.prompt_builder import PromptPackage

    print("\n" + "="*50)
    print("ATHENA LLM PROVIDER STARTUP DIAGNOSTIC")
    print("="*50)
    
    provider = get_provider(settings.ATHENA_PROVIDER)
    
    provider_name = provider.__class__.__name__
    model_name = getattr(provider, "model_name", "Unknown")
    
    base_url = "Default Provider Endpoint"
    if provider_name == "OpenAIProvider" and hasattr(provider, "client") and provider.client:
        base_url = str(provider.client.base_url)
        
    def _is_valid_key(key):
        return bool(key) and "your_" not in key
        
    print(f"Provider:        {provider_name}")
    print(f"Base URL:        {base_url}")
    print(f"Model:           {model_name}")
    print("")
    print(f"NVIDIA_API_KEY detected:   {'Yes' if _is_valid_key(settings.NVIDIA_API_KEY) else 'No'}")
    print(f"OPENAI_API_KEY detected:   {'Yes' if _is_valid_key(settings.OPENAI_API_KEY) else 'No'}")
    print(f"GEMINI_API_KEY detected:   {'Yes' if _is_valid_key(settings.GEMINI_API_KEY) else 'No'}")
    print(f"ANTHROPIC_API_KEY detected: {'Yes' if _is_valid_key(settings.ANTHROPIC_API_KEY) else 'No'}")
    
    print("\nValidating Provider Contract... ", end="")
    try:
        prompt = PromptPackage(
            system_prompt="You are a diagnostic tool.",
            user_prompt="Reply with the single word 'OK'.",
            serialized_context="",
            prompt_version="v1",
            metadata={"context_type": "diagnostic"}
        )
        response = provider.generate(prompt)
        
        assert isinstance(response, GenerationResponse), f"Provider must return GenerationResponse, got {type(response)}"
        assert isinstance(response.generated_text, str), "response.generated_text must be a string"
        assert hasattr(response, "provider"), "response must have 'provider' field"
        assert hasattr(response, "model"), "response must have 'model' field"
        
        print("PASS ✓")
    except Exception as e:
        print("FAIL ✗")
        print("\nFATAL ERROR: Provider validation failed. Does not meet Canonical Interface.")
        print(f"Exception: {e}")
        raise RuntimeError(f"Provider validation failed: {e}") from e
        
    print("="*50 + "\n")

# 1. Initialize State
init_session()
_print_startup_diagnostic()
state = get_state()

# 2. Inject Enterprise Theme
load_theme()

# 3. Render Global Chrome (Navigation & Selectors)
render_global_sidebar()


# ─────────────────────────────────────────────────────────────────────────────
# Main Layout & Routing
# ─────────────────────────────────────────────────────────────────────────────

active_ws = get_workspace_by_id(state.active_workspace_id)

if not active_ws:
    render_page_header("Error", "Invalid Workspace")
    render_empty_state(
        "⚠",
        "Workspace Not Found",
        "The requested workspace does not exist in the configuration.",
    )
elif state.active_workspace_id == "dashboard":
    dashboard.render()
elif state.active_workspace_id == "player_intelligence":
    player_intelligence.render()
elif state.active_workspace_id == "team_intelligence":
    team_intelligence.render()
elif state.active_workspace_id == "recruitment":
    recruitment_intelligence.render()
elif state.active_workspace_id == "ask_athena":
    from frontend.components.ask_athena import render_ask_athena_section
    render_ask_athena_section()
else:
    # Fallback for future workspaces
    render_page_header(active_ws.name, active_ws.question, active_ws.icon)
    render_empty_state(
        icon=active_ws.icon,
        title=f"{active_ws.name} Workspace",
        description="This workspace is currently under construction.",
        suggestion="Use the sidebar to navigate to a different workspace.",
    )
