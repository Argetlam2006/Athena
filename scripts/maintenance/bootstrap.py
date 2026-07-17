#!/usr/bin/env python3
"""
scripts/bootstrap.py - Athena Data Pipeline Orchestrator

This script provides a single-command onboarding experience for new users.
It orchestrates the entire data pipeline from zero to a production-ready
analytics warehouse without duplicating any business logic.

Pipeline Sequence:
  0. Verify Dependencies
  1. Ingestion: Download the complete StatsBomb Open Data catalogue.
  2. ETL: Normalize the raw JSON into Parquet files.
  3. Warehouse: Build the DuckDB analytical views.
  4. Intelligence Store: Build the parquet store.
  5. Validation: Ensure the generated artifacts exist.
"""

import subprocess
import sys
from pathlib import Path

# Identify project root (scripts/maintenance/bootstrap.py -> parents[2] is root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_command(command: list[str], description: str) -> None:
    """Run a subprocess command with error handling."""
    print(f">> {description}...")
    try:
        # Use sys.executable to ensure we use the current virtual environment's python
        subprocess.run(
            [sys.executable] + command,
            cwd=PROJECT_ROOT,
            check=True,
        )
        print(f"OK {description.split(':')[0]} complete.\n")
    except subprocess.CalledProcessError as e:
        print(f"\nFAIL Bootstrap failed during: {description}")
        print(f"Command returned non-zero exit status {e.returncode}.")
        sys.exit(1)


def verify_dependencies() -> None:
    """Verify core dependencies are installed before starting."""
    print(">> Step 0: Verifying Dependencies...")
    try:
        import pandas
        import duckdb
        import pydantic
        import streamlit
    except ImportError as e:
        print(f"\nFAIL Missing dependency: {e.name}")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)
    print("OK Dependencies verified.\n")


def validate_artifacts() -> None:
    """Verify that the generated artifacts actually exist."""
    print(">> Step 5: Validating Generated Artifacts...")
    duckdb_path = PROJECT_ROOT / "data" / "warehouse" / "athena.duckdb"
    player_profiles_path = PROJECT_ROOT / "data" / "warehouse" / "player_profiles.parquet"
    collective_profiles_path = PROJECT_ROOT / "data" / "warehouse" / "collective_profiles.json"

    missing = []
    if not duckdb_path.exists():
        missing.append("athena.duckdb")
    if not player_profiles_path.exists():
        missing.append("player_profiles.parquet")
    if not collective_profiles_path.exists():
        missing.append("collective_profiles.json")
    
    if missing:
        print(f"\nFAIL Validation failed. Missing artifacts: {', '.join(missing)}")
        sys.exit(1)
        
    print(f"OK Validated: {duckdb_path.name} ({duckdb_path.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"OK Validated: {player_profiles_path.name} ({player_profiles_path.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"OK Validated: {collective_profiles_path.name} ({collective_profiles_path.stat().st_size / 1024 / 1024:.2f} MB)")
    print("OK Artifacts verified.\n")


def main() -> None:
    print("\n" + "=" * 60)
    print("  Athena - Canonical Data Bootstrap")
    print("=" * 60 + "\n")
    print("This script will verify dependencies, download the complete")
    print("StatsBomb Open Data catalogue, process it, and build the")
    print("deterministic intelligence store.\n")

    # Step 0: Verify Dependencies
    verify_dependencies()

    # Step 1: Ingestion (Idempotent by default)
    run_command(
        ["-m", "backend.ingestion.load_data"], "Step 1: Downloading StatsBomb Open Data"
    )

    # Step 2: ETL (Skips if processed files already exist)
    run_command(
        ["-m", "backend.etl.pipeline"], "Step 2: Running ETL Pipeline (JSON -> Parquet)"
    )

    # Step 3: Warehouse Build (Idempotent view recreation)
    run_command(
        ["-m", "backend.warehouse.warehouse"],
        "Step 3: Building DuckDB Analytics Warehouse",
    )

    # Step 4: Intelligence Store Build (Skips if warehouse is unchanged)
    run_command(
        ["-m", "backend.intelligence.build_store"],
        "Step 4: Building Intelligence Store",
    )
    
    # Step 5: Validate Artifacts
    validate_artifacts()

    print("=" * 60)
    print("  Bootstrap Successful!")
    print("  Athena is now fully initialized with a canonical dataset.")
    print("  You can now launch the application or run tests:")
    print("\n      streamlit run frontend/app.py")
    print("      pytest")
    print("\n=" * 60 + "\n")


if __name__ == "__main__":
    main()
