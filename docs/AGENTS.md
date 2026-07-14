# AGENTS.md

# Athena Engineering Guidelines

## Project Identity

Athena is an AI-powered Football Decision Intelligence Platform.

The purpose of Athena is to transform football data into explainable football decisions through analytics engineering, machine learning, interactive visualization and AI-assisted explanations.

Athena is a portfolio project intended to demonstrate:

- Product Thinking
- Analytics Engineering
- SQL
- Data Engineering
- Machine Learning
- Explainable AI
- Software Engineering

The objective is **not** to build the largest possible application.

The objective is to build the highest-quality implementation of Version 1.

---

# Source of Truth

The following documents define Athena.

They take precedence over all implementation decisions.

1. docs/00_PRODUCT_VISION.md
2. docs/01_PRD.md
3. docs/02_INTELLIGENCE_MODEL.md
4. docs/03_TECH_SPEC.md
5. docs/04_DATA_ARCHITECTURE.md
6. docs/05_PRODUCT_EXPERIENCE_AND_ENGINEERING_GUIDE.md
7. IMPLEMENTATION_TASKS.md

Never contradict these documents.

---

# Product Philosophy

Athena follows one analytical pipeline.

Football Events

↓

Statistics

↓

Capabilities

↓

Player & Team Intelligence

↓

Decision Intelligence

↓

Explanation

Never bypass this pipeline.

---

# Engineering Principles

Every module should have one responsibility.

Prefer:

- readability
- modularity
- maintainability
- explainability

over unnecessary complexity.

Avoid:

- premature optimization
- excessive abstraction
- enterprise-only patterns
- unnecessary dependencies

---

# Architecture Rules

Version 1 architecture is frozen.

Do not redesign it.

Do not introduce additional modules.

Do not simplify the architecture.

Major architectural changes require explicit approval.

---

# Technology Stack

Backend

- Python
- FastAPI

Analytics

- DuckDB
- Parquet
- Pandas
- NumPy

Machine Learning

- Scikit-Learn

Visualization

- Plotly

Frontend

- Streamlit

AI

- Gemini / OpenAI API

Do not introduce additional frameworks unless explicitly requested.

---

# Data

Version 1 uses only:

StatsBomb Open Data.

Do not implement multi-provider entity resolution.

Future datasets must remain optional.

---

# Machine Learning

Machine Learning supports football analysis.

Machine Learning does not replace football analysis.

Allowed

- Cosine Similarity
- Nearest Neighbours
- Recommendation Ranking

Use rule-based player archetypes.

Do not use:

- K-Means
- Deep Learning
- Black-box models
- Outcome prediction
- Betting models

Explainability takes priority over predictive accuracy.

---

# AI

The LLM is an explanation layer.

It must never:

- invent statistics
- invent football knowledge
- perform independent football analysis

The LLM only explains structured analytical outputs produced by Athena.

Always use retrieval/context injection.

Do not build autonomous agents.

---

# Football Metrics

Use real football terminology.

Examples

- Progressive Passes
- Progressive Carries
- Key Passes
- Expected Goals
- Expected Assists
- Recoveries
- Pressures

Do not invent fictional metrics.

Every metric must be traceable to StatsBomb data.

---

# Code Style

Every file should include:

- clear naming
- type hints where appropriate
- concise comments
- docstrings
- consistent formatting

Avoid overly clever code.

Prefer explicit code over implicit behavior.

---

# Repository Structure

Respect the existing folder structure.

Do not move modules unless instructed.

New files should only be created when they naturally belong within the architecture.

---

# Documentation

Every major implementation should update documentation when necessary.

Architecture decisions should be recorded in

ARCHITECTURE_DECISIONS.md

Every significant engineering decision should include:

- Decision
- Rationale
- Alternatives Considered

---

# Implementation Workflow

Never implement multiple milestones simultaneously.

For every task:

1. Restate the objective.
2. Explain why the task exists.
3. List files to be created or modified.
4. Explain the implementation approach.
5. Wait for approval.
6. Generate code.
7. Explain testing.
8. Suggest a Git commit message.

Never continue automatically.

---

# Testing

Every completed module should include appropriate tests.

Prefer deterministic tests.

Tests should verify:

- correctness
- reproducibility
- explainability

---

# User Experience

Athena is not a dashboard.

Athena is not a chatbot.

Athena is an analytical workspace.

Every screen should answer a football question.

Evidence should always appear before AI explanations.

---

# Performance

Use:

- DuckDB
- Parquet
- Streamlit caching

Avoid unnecessary optimization.

Optimize only where measurable bottlenecks exist.

---

# Portfolio Focus

Whenever multiple valid implementations exist, choose the one that best demonstrates:

- analytical thinking
- SQL proficiency
- data engineering
- explainable ML
- AI integration
- software architecture
- product thinking

Do not optimize for enterprise-scale infrastructure.

Optimize for clarity, maintainability and interview discussion.

---

# Definition of Success

Athena succeeds when a user can:

- understand a player
- understand a team
- compare footballers
- evaluate recruitment options
- receive evidence-backed explanations

without leaving the platform.

Every recommendation should answer:

- What happened?
- Why does it matter?
- What evidence supports it?
- What should the user do next?

If a feature does not improve football decision-making, it probably does not belong in Version 1.