"""
frontend/components/selectors.py — Reusable Context Selectors
"""
import streamlit as st

from frontend.data.player_service import get_player_index
from frontend.data.team_service import get_collective_index
from frontend.session import get_state, set_selected_player, set_selected_team


def render_player_selector(key_prefix: str = "global") -> None:
    df_players = get_player_index()
    state = get_state()
    if df_players.empty:
        st.warning("Player data not loaded.")
        return

    # Aggregate by player_id to create one unique identity per player
    df_unique = df_players.groupby("player_id").agg({
        "player_name": "first",
        "normalized_name": "first",
        "minutes_played": "sum",
        "team_name": lambda x: ", ".join(x.dropna().unique()),
        "competition": lambda x: ", ".join(x.dropna().unique())
    }).reset_index()

    search_query = st.text_input(
        "Search Player",
        placeholder="Search by name (e.g. Kevin De Bruyne, Messi)...",
        key=f"{key_prefix}_player_search"
    )

    if search_query:
        term = search_query.lower().strip()
        tokens = term.split()

        def calculate_score(row):
            name = str(row["normalized_name"])
            prominence_bonus = min(row["minutes_played"] / 10000.0, 50.0)

            if name == term:
                return 1000.0 + prominence_bonus
            if name.startswith(term):
                return 500.0 + prominence_bonus

            name_tokens = name.split()
            token_matches = sum(1 for t in tokens if any(t == nt or nt.startswith(t) for nt in name_tokens))

            if token_matches == len(tokens):
                return 200.0 + (token_matches * 10.0) + prominence_bonus

            if term in name:
                return 100.0 + prominence_bonus

            if token_matches > 0:
                return (token_matches * 10.0) + prominence_bonus

            return 0.0

        df_unique["_score"] = df_unique.apply(calculate_score, axis=1)
        matches = df_unique[df_unique["_score"] > 0].sort_values(
            by=["_score", "player_name"],
            ascending=[False, True]
        ).head(5)

        if not matches.empty:
            st.markdown("<div style='font-size: 0.8rem; color: #9ca3af; margin-bottom: 0.25rem;'>Top Results</div>", unsafe_allow_html=True)
            for _, row in matches.iterrows():
                is_selected = (row["player_id"] == state.selected_player_id)
                btn_label = f"{row['player_name']} • {row['team_name']}"
                if is_selected:
                    btn_label = "✅ " + btn_label
                if st.button(btn_label, key=f"{key_prefix}_sel_p_{row['player_id']}", use_container_width=True):
                    set_selected_player(row["player_id"])
                    st.rerun()
        else:
            st.info("No players found matching your query.")

def render_team_selector(key_prefix: str = "global") -> None:
    df_teams = get_collective_index()
    state = get_state()
    if df_teams.empty:
        st.warning("Team data not loaded.")
        return

    df_unique = df_teams.groupby("team_id").agg({
        "team_name": "first",
        "competition": lambda x: ", ".join(x.dropna().unique())
    }).reset_index()

    search_query = st.text_input(
        "Search Team",
        placeholder="Search by team name...",
        key=f"{key_prefix}_team_search"
    )

    if search_query:
        term = search_query.lower().strip()
        tokens = term.split()

        def calculate_team_score(row):
            name = str(row["team_name"]).lower()

            if name == term:
                return 1000.0
            if name.startswith(term):
                return 500.0

            name_tokens = name.split()
            token_matches = sum(1 for t in tokens if any(t == nt or nt.startswith(t) for nt in name_tokens))

            if token_matches == len(tokens):
                return 200.0 + (token_matches * 10.0)

            if term in name:
                return 100.0

            if token_matches > 0:
                return (token_matches * 10.0)

            return 0.0

        df_unique["_score"] = df_unique.apply(calculate_team_score, axis=1)
        matches = df_unique[df_unique["_score"] > 0].sort_values(
            by=["_score", "team_name"],
            ascending=[False, True]
        ).head(5)

        if not matches.empty:
            st.markdown("<div style='font-size: 0.8rem; color: #9ca3af; margin-bottom: 0.25rem;'>Top Results</div>", unsafe_allow_html=True)
            for _, row in matches.iterrows():
                is_selected = (row["team_id"] == state.selected_team_id)
                btn_label = f"{row['team_name']} • {row['competition']}"
                if is_selected:
                    btn_label = "✅ " + btn_label
                if st.button(btn_label, key=f"{key_prefix}_sel_t_{row['team_id']}", use_container_width=True):
                    set_selected_team(row["team_id"])
                    st.rerun()
        else:
            st.info("No teams found matching your query.")
