<div align="center">
  <h1>◇ Athena</h1>
  <p><b>An AI-Powered Football Decision Intelligence Platform</b></p>
  <p>
    <a href="#overview">Overview</a> •
    <a href="#evidence-before-ai">Philosophy</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#architecture">Architecture</a>
  </p>
</div>

---

## Overview

**Athena** is a modern football analytics platform designed to bridge the gap between raw, deterministic event data and explainable artificial intelligence. Rather than relying on black-box LLM analysis, Athena forces AI to act strictly as an *explanation layer* on top of a rigorously validated, deterministic **Football Intelligence Engine**.

## Evidence Before AI

Athena's core philosophy is **"Evidence Before AI"**. 

LLMs are prone to hallucinating statistics, especially in highly nuanced domains like football analytics. Athena solves this by implementing a strict, multi-layer firewall:
1. **Deterministic Processing**: Raw event data is mathematically processed into exactly 8 standard capabilities (e.g., *Ball Progression*, *Chance Creation*).
2. **Context Engine**: These capabilities are bundled into strongly-typed `EvidencePackets`.
3. **The AI Sandbox**: The AI (Claude, OpenAI, or Gemini) is restricted via a canonical System Prompt to *only* explain the structured evidence provided to it. It cannot invent numbers. It cannot infer capabilities that lack evidence.

## Features
- **Global Data Integration**: Athena automatically discovers and ingests the *complete* publicly available StatsBomb Open Data catalogue (across all competitions and seasons) dynamically, rather than relying on a fixed or hardcoded list of leagues.
- **Player Intelligence**: Deep capability profiling mapping event actions to overarching tactical skills.
- **Team Intelligence**: Aggregated squad analytics and tactical style identification.
- **Recruitment Intelligence**: Semantic player search utilizing deterministic fit-scoring algorithms.
- **Ask Athena**: A persistent, context-aware AI assistant capable of streaming intelligent explanations based entirely on validated telemetry.

## Download Football Data

Athena does NOT ship with the StatsBomb dataset because the generated data (several gigabytes of JSON and Parquet files) is intentionally excluded from GitHub to keep the repository lightweight.

However, you only need to run a single command to completely bootstrap the platform. The `scripts/bootstrap.py` script automatically:
1. Discovers and downloads every available competition, season, and match from the StatsBomb Open Data catalogue.
2. Runs the ETL pipeline to clean and normalize the JSON into Parquet.
3. Builds the DuckDB warehouse and creates all analytical views.

**Note:** The first time you run this bootstrap, it downloads and processes the complete StatsBomb Open Data catalogue, which may take **20-40 minutes**. However, the script is fully idempotent. Subsequent runs will safely reuse the local dataset whenever possible, skipping redundant downloads and ETL processing.

## Quick Start (Zero Config)

Athena is designed to run perfectly out of the box with zero configuration required, thanks to the built-in `DemoProvider`.

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/athena.git
cd athena

# 2. Install dependencies
pip install -r requirements.txt

# 3. Data Generation (First Bootstrap)
python scripts/bootstrap.py
```

**What happens during Bootstrap?**
The first time you run this command, Athena will download the dataset, run ETL, build the warehouse, and generate the Intelligence Store. This heavy analytical processing may take **20-40 minutes**.

However, `scripts/bootstrap.py` is entirely idempotent and safe to rerun. Only changed data will trigger a rebuild.

```bash
# 4. Launch the application
streamlit run frontend/app.py
```

**Subsequent Launches**: Because heavy computations are handled by the Intelligence Store during bootstrap, running the Streamlit app on subsequent launches is nearly **instantaneous**.

## Configuration & Real LLM Providers

If you wish to attach a real LLM for dynamic responses, Athena supports Anthropic, OpenAI, and Google Gemini.

1. Copy `.env.example` to `.env`.
2. Set `ATHENA_PROVIDER` to `auto`, `claude`, `openai`, or `gemini`.
3. Add your respective API keys (e.g., `OPENAI_API_KEY=sk-...`).

```env
ATHENA_ENV=development
ATHENA_PROVIDER=auto
OPENAI_API_KEY=your_key_here
```

## Architecture

Athena follows a strictly decoupled architecture designed to feel like a commercial analytics platform like Power BI or Tableau. 

**Data Flow Pipeline:**
```text
StatsBomb → ETL → Warehouse → Football Intelligence Engine → Intelligence Store → Frontend → Ask Athena
```

Heavy deterministic analytics execute **only once** during data generation. 
- **The Intelligence Store**: A set of Parquet files containing mathematically processed Player and Team capability profiles. 
- **Deterministic**: The Store is rebuilt *only* when the warehouse fingerprint changes.
- **Excluded from Git**: The generated Intelligence Store is treated exactly like raw JSON or DuckDB data.

### Subsystems
- **Ingestion & Warehouse**: DuckDB-powered analytics store.
- **Intelligence Framework**: Feature engineering and mathematical capability generation.
- **Intelligence Store**: O(1) Parquet storage enabling near-instantaneous frontend loading.
- **Decision Engine**: Recruitment algorithms, comparisons, and tactical fit scoring.
- **Explanation Platform**: Provider-agnostic Prompt Builders, Context Validators, and Conversation Managers.
- **Frontend**: A highly modular Streamlit application shell operating purely as a thin presentation layer.

## Tech Stack
- **Data**: DuckDB, Pandas, NumPy
- **Backend Core**: Python 3.11+, Pydantic (Dataclasses)
- **Frontend**: Streamlit
- **AI Integration**: Anthropic, OpenAI, Google GenAI SDKs

## License
Distributed under the MIT License. See `LICENSE` for more information.
