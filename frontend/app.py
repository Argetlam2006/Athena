"""
frontend/app.py — Athena Streamlit application entry point

This is the main application file. Run with:
    streamlit run frontend/app.py
    make app

The landing page introduces the platform, displays workspace navigation,
and shows system status. It is designed to look and feel like a professional
football decision intelligence platform.

Design principles:
  - Dark mode, minimal, enterprise-grade (Linear / Stripe / Palantir aesthetic)
  - Evidence before AI
  - Every screen answers a football question
  - Inter typography, muted color palette
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

from shared.constants import CAPABILITIES, CAPABILITY_DISPLAY_NAMES, WORKSPACES  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Page configuration
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Athena — Football Decision Intelligence",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get Help": "https://github.com/bhaskarpareek/athena",
        "Report a bug": "https://github.com/bhaskarpareek/athena/issues",
        "About": "Athena — AI-powered Football Decision Intelligence Platform",
    },
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS — Design system
# ─────────────────────────────────────────────────────────────────────────────

ATHENA_CSS = """
<style>
/* ── Google Fonts ─────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Global reset ─────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Streamlit chrome ─────────────────────────────────────────── */
[data-testid="stAppViewContainer"] {
    background-color: #0a0a0a;
}
[data-testid="stHeader"] {
    background-color: #0a0a0a;
    border-bottom: 1px solid #1a1a1a;
}
[data-testid="stSidebar"] {
    background-color: #0d0d0d;
}
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }

/* ── Typography ───────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif;
    color: #f0f0f0;
    letter-spacing: -0.02em;
}
p, li, span {
    color: #9ca3af;
    line-height: 1.6;
}

/* ── Athena logo ──────────────────────────────────────────────── */
.athena-logo {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.25em;
    color: #6366f1;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}
.athena-title {
    font-size: 3.5rem;
    font-weight: 700;
    color: #f9fafb;
    letter-spacing: -0.04em;
    line-height: 1.05;
    margin-bottom: 0;
}
.athena-tagline {
    font-size: 1.1rem;
    color: #6b7280;
    font-weight: 400;
    margin-top: 0.75rem;
    letter-spacing: -0.01em;
}

/* ── Divider ──────────────────────────────────────────────────── */
.athena-divider {
    border: none;
    border-top: 1px solid #1f1f1f;
    margin: 2rem 0;
}

/* ── Section header ───────────────────────────────────────────── */
.section-label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    color: #4b5563;
    text-transform: uppercase;
    margin-bottom: 1.25rem;
}

/* ── Workspace card ───────────────────────────────────────────── */
.workspace-card {
    background: #111111;
    border: 1px solid #1f1f1f;
    border-radius: 10px;
    padding: 1.5rem;
    transition: all 0.2s ease;
    position: relative;
    cursor: pointer;
    height: 100%;
    min-height: 160px;
}
.workspace-card:hover {
    border-color: #6366f1;
    background: #131320;
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(99, 102, 241, 0.08);
}
.workspace-icon {
    font-size: 1.2rem;
    color: #6366f1;
    margin-bottom: 0.75rem;
    display: block;
}
.workspace-name {
    font-size: 0.95rem;
    font-weight: 600;
    color: #e5e7eb;
    margin-bottom: 0.5rem;
    letter-spacing: -0.01em;
}
.workspace-question {
    font-size: 0.8rem;
    color: #4b5563;
    font-style: italic;
    line-height: 1.4;
}
.workspace-status {
    position: absolute;
    top: 1rem;
    right: 1rem;
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
}
.status-live {
    background: rgba(16, 185, 129, 0.1);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.2);
}
.status-building {
    background: rgba(245, 158, 11, 0.08);
    color: #f59e0b;
    border: 1px solid rgba(245, 158, 11, 0.15);
}
.status-planned {
    background: rgba(75, 85, 99, 0.2);
    color: #6b7280;
    border: 1px solid rgba(75, 85, 99, 0.3);
}

/* ── Capability pill ──────────────────────────────────────────── */
.capability-pill {
    display: inline-block;
    background: #111111;
    border: 1px solid #1f1f1f;
    border-radius: 6px;
    padding: 0.4rem 0.75rem;
    font-size: 0.75rem;
    color: #6b7280;
    margin: 0.2rem;
    font-weight: 500;
    letter-spacing: -0.01em;
    transition: all 0.15s ease;
}
.capability-pill:hover {
    border-color: #374151;
    color: #9ca3af;
}

/* ── Pipeline flow ────────────────────────────────────────────── */
.pipeline-step {
    text-align: center;
    padding: 0.75rem 0.5rem;
}
.pipeline-node {
    background: #111111;
    border: 1px solid #1f1f1f;
    border-radius: 8px;
    padding: 0.6rem 1rem;
    font-size: 0.78rem;
    font-weight: 500;
    color: #d1d5db;
    display: inline-block;
    letter-spacing: -0.01em;
}
.pipeline-arrow {
    color: #374151;
    font-size: 1rem;
    margin: 0.25rem 0;
    display: block;
}

/* ── Stat card ────────────────────────────────────────────────── */
.stat-card {
    background: #111111;
    border: 1px solid #1f1f1f;
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    text-align: left;
}
.stat-value {
    font-size: 2rem;
    font-weight: 700;
    color: #f9fafb;
    letter-spacing: -0.04em;
    line-height: 1;
    margin-bottom: 0.25rem;
}
.stat-label {
    font-size: 0.75rem;
    color: #4b5563;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* ── Notice banner ────────────────────────────────────────────── */
.notice-banner {
    background: rgba(99, 102, 241, 0.06);
    border: 1px solid rgba(99, 102, 241, 0.15);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    font-size: 0.82rem;
    color: #818cf8;
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
}

/* ── Footer ───────────────────────────────────────────────────── */
.athena-footer {
    font-size: 0.72rem;
    color: #374151;
    text-align: center;
    padding-top: 2rem;
    border-top: 1px solid #111111;
    margin-top: 3rem;
    letter-spacing: 0.02em;
}
.athena-footer a {
    color: #4b5563;
    text-decoration: none;
}
.athena-footer a:hover {
    color: #6366f1;
}
</style>
"""

st.markdown(ATHENA_CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# System status check
# ─────────────────────────────────────────────────────────────────────────────

def check_data_status() -> dict[str, bool]:
    """Check which data components are available."""
    data_dir = ROOT_DIR / "data"
    return {
        "raw_data": bool(list((data_dir / "raw").glob("*.csv"))) if (data_dir / "raw").exists() else False,
        "sample_data": (data_dir / "sample" / "competitions.csv").exists(),
        "warehouse": any((data_dir / "warehouse").glob("*.duckdb")) if (data_dir / "warehouse").exists() else False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Workspace definitions with status
# ─────────────────────────────────────────────────────────────────────────────

WORKSPACE_CARDS = [
    {
        "icon": "⬡",
        "name": "Executive Dashboard",
        "question": "What deserves my attention today?",
        "status": "building",
        "description": "KPIs, league snapshots, player spotlights",
    },
    {
        "icon": "◈",
        "name": "Player Intelligence",
        "question": "What kind of player is this?",
        "status": "building",
        "description": "Capability profile, trends, similar players, AI report",
    },
    {
        "icon": "◉",
        "name": "Team Intelligence",
        "question": "How does this team play?",
        "status": "building",
        "description": "Tactical identity, squad composition, style analysis",
    },
    {
        "icon": "◎",
        "name": "Recruitment Intelligence",
        "question": "Who should we sign?",
        "status": "planned",
        "description": "Candidate ranking, tactical fit, evidence-backed recommendations",
    },
    {
        "icon": "◇",
        "name": "Ask Athena",
        "question": "Help me understand this.",
        "status": "planned",
        "description": "Conversational AI grounded in structured analytics",
    },
]

STATUS_LABELS = {
    "live":     ("status-live",     "Live"),
    "building": ("status-building", "In Development"),
    "planned":  ("status-planned",  "Planned"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Render — Header
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="padding: 1rem 0 2rem 0;">
    <div class="athena-logo">Athena</div>
    <div class="athena-title">Football Decision<br>Intelligence</div>
    <div class="athena-tagline">
        Transforming football data into confident, explainable decisions.
    </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Render — System status notice
# ─────────────────────────────────────────────────────────────────────────────

status = check_data_status()
if not status["raw_data"] and not status["sample_data"]:
    st.markdown("""
    <div class="notice-banner">
        <span style="font-size:1rem;">ℹ</span>
        <div>
            <strong>No data loaded.</strong>
            Run <code style="background:#1f1f1f; padding:0.1rem 0.3rem; border-radius:3px; font-size:0.8rem;">make data</code>
            or
            <code style="background:#1f1f1f; padding:0.1rem 0.3rem; border-radius:3px; font-size:0.8rem;">python -m backend.ingestion.load_data --sample</code>
            to fetch the StatsBomb sample dataset.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Render — Platform stats
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("<div class='athena-divider'></div>", unsafe_allow_html=True)
st.markdown("<div class='section-label'>Platform Overview</div>", unsafe_allow_html=True)

stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

with stat_col1:
    st.markdown("""
    <div class="stat-card">
        <div class="stat-value">8</div>
        <div class="stat-label">Core Capabilities</div>
    </div>
    """, unsafe_allow_html=True)

with stat_col2:
    st.markdown("""
    <div class="stat-card">
        <div class="stat-value">5</div>
        <div class="stat-label">Intelligence Workspaces</div>
    </div>
    """, unsafe_allow_html=True)

with stat_col3:
    st.markdown("""
    <div class="stat-card">
        <div class="stat-value">7</div>
        <div class="stat-label">AIF Reasoning Layers</div>
    </div>
    """, unsafe_allow_html=True)

with stat_col4:
    # Show data status
    if status["raw_data"] or status["sample_data"]:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value" style="color:#10b981;">●</div>
            <div class="stat-label">Data Available</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value" style="color:#f59e0b;">○</div>
            <div class="stat-label">Awaiting Data</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Render — Workspace cards
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("<div class='section-label'>Intelligence Workspaces</div>", unsafe_allow_html=True)

cols = st.columns(5, gap="small")
for i, workspace in enumerate(WORKSPACE_CARDS):
    with cols[i]:
        status_class, status_text = STATUS_LABELS[workspace["status"]]
        st.markdown(f"""
        <div class="workspace-card">
            <span class="workspace-status {status_class}">{status_text}</span>
            <span class="workspace-icon">{workspace['icon']}</span>
            <div class="workspace-name">{workspace['name']}</div>
            <div class="workspace-question">"{workspace['question']}"</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 2.5rem;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Render — AIF pipeline
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("<div class='athena-divider'></div>", unsafe_allow_html=True)
st.markdown("<div class='section-label'>Athena Intelligence Framework — Reasoning Pipeline</div>", unsafe_allow_html=True)

aif_steps = [
    ("Football Events", "Raw event observations"),
    ("Statistics", "Aggregated per-90 metrics"),
    ("Capabilities", "8 composite ability scores"),
    ("Player Intelligence", "Complete analytical profile"),
    ("Team Intelligence", "Collective tactical identity"),
    ("Decision Intelligence", "Evidence-backed recommendations"),
    ("Explanation", "Natural language reasoning"),
]

pipeline_cols = st.columns(len(aif_steps), gap="small")
for i, (step_name, step_desc) in enumerate(aif_steps):
    with pipeline_cols[i]:
        connector = "▼" if i < len(aif_steps) - 1 else ""
        st.markdown(f"""
        <div class="pipeline-step">
            <div class="pipeline-node">{step_name}</div>
            <div style="font-size:0.65rem; color:#374151; margin-top:0.4rem;">{step_desc}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 2.5rem;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Render — Capabilities
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("<div class='athena-divider'></div>", unsafe_allow_html=True)

cap_left, cap_right = st.columns([1, 2])

with cap_left:
    st.markdown("""
    <div style="padding-right: 2rem; padding-top: 0.5rem;">
        <div class="section-label">Core Capabilities</div>
        <div style="font-size:0.9rem; font-weight:600; color:#e5e7eb; margin-bottom:0.75rem; letter-spacing:-0.02em;">
            8 composite football ability scores
        </div>
        <div style="font-size:0.8rem; color:#4b5563; line-height:1.6;">
            Each capability is derived from multiple StatsBomb metrics,
            normalized per 90 minutes and ranked by position group.
            <br><br>
            Capabilities intentionally avoid producing a single overall rating.
            Football decisions are context-dependent.
        </div>
    </div>
    """, unsafe_allow_html=True)

with cap_right:
    capability_html = ""
    for cap_key in CAPABILITIES:
        display = CAPABILITY_DISPLAY_NAMES[cap_key]
        capability_html += f'<span class="capability-pill">{display}</span>'
    st.markdown(
        f'<div style="padding-top:1.5rem;">{capability_html}</div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-bottom: 2.5rem;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Render — Getting started
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("<div class='athena-divider'></div>", unsafe_allow_html=True)
st.markdown("<div class='section-label'>Getting Started</div>", unsafe_allow_html=True)

gs_col1, gs_col2, gs_col3 = st.columns(3, gap="medium")

with gs_col1:
    st.markdown("""
    <div class="workspace-card" style="min-height:120px;">
        <div style="font-size:0.65rem; font-weight:600; color:#6366f1; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:0.75rem;">Step 1</div>
        <div class="workspace-name">Fetch Data</div>
        <div class="workspace-question" style="font-style:normal; margin-top:0.4rem;">
            <code style="background:#1a1a1a; padding:0.2rem 0.4rem; border-radius:4px; font-size:0.75rem; color:#818cf8;">make data</code>
            <br><span style="color:#374151; font-size:0.75rem;">Downloads StatsBomb Open Data</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with gs_col2:
    st.markdown("""
    <div class="workspace-card" style="min-height:120px;">
        <div style="font-size:0.65rem; font-weight:600; color:#6366f1; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:0.75rem;">Step 2</div>
        <div class="workspace-name">Validate</div>
        <div class="workspace-question" style="font-style:normal; margin-top:0.4rem;">
            <code style="background:#1a1a1a; padding:0.2rem 0.4rem; border-radius:4px; font-size:0.75rem; color:#818cf8;">make validate</code>
            <br><span style="color:#374151; font-size:0.75rem;">Runs data quality checks</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with gs_col3:
    st.markdown("""
    <div class="workspace-card" style="min-height:120px;">
        <div style="font-size:0.65rem; font-weight:600; color:#6366f1; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:0.75rem;">Step 3</div>
        <div class="workspace-name">Explore</div>
        <div class="workspace-question" style="font-style:normal; margin-top:0.4rem;">
            <code style="background:#1a1a1a; padding:0.2rem 0.4rem; border-radius:4px; font-size:0.75rem; color:#818cf8;">make app</code>
            <br><span style="color:#374151; font-size:0.75rem;">Launch the full platform</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Render — Footer
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="athena-footer">
    Athena &nbsp;·&nbsp; AI Football Decision Intelligence Platform &nbsp;·&nbsp; Version 1.0 &nbsp;·&nbsp;
    Data: <a href="https://github.com/statsbomb/open-data" target="_blank">StatsBomb Open Data</a> (CC BY-SA 4.0)
    &nbsp;·&nbsp;
    <a href="https://github.com/bhaskarpareek/athena" target="_blank">GitHub</a>
</div>
""", unsafe_allow_html=True)
