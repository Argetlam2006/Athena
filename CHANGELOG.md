# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-15

### Added
- **Football Intelligence Engine**: Complete deterministic pipeline mapping raw event data to 8 core capabilities (Ball Progression, Chance Creation, etc.).
- **Decision Engine**: High-level intelligence layer supporting tactical recruitment filtering, player comparisons, and capability profiling.
- **Explanation Platform**: A provider-agnostic Generative AI layer strictly adhering to the "Evidence before AI" philosophy.
- **Ask Athena**: An ever-present contextual assistant seamlessly integrated into the application shell.
- **Multi-Provider Support**: Seamless support for Anthropic Claude, OpenAI, and Google Gemini via a unified Prompt Package structure.
- **Demo Provider**: Zero-configuration mock provider enabling full application functionality without API keys.
- **Core Workspaces**: Player Intelligence, Team Intelligence, Recruitment Intelligence, and a unified Dashboard.
- **Docker Support**: Lightweight containerization optimized for Render and Railway deployments.

### Known Limitations
- The underlying DuckDB data warehouse currently relies on static sample data rather than live event streams.
- The `Ask Athena` drawer is restricted to analyzing the explicitly selected context (Player, Team, or Recruitment list) and does not yet query the entire warehouse globally.

### Future Roadmap
- **Phase 2 Data Integration**: Connect to live APIs (e.g., StatsBomb or Opta) for real-time event updates.
- **Advanced Tactical Archetypes**: Expand the rules engine to classify players into deeper tactical archetypes (e.g., Inverted Fullback, Deep-Lying Playmaker).
- **Global Context Assistant**: Upgrade `Ask Athena` to support global text-to-SQL for open-ended dataset querying.
