#!/usr/bin/env python3
"""
scripts/bootstrap.py — Athena Data Pipeline Orchestrator

This script provides a single-command onboarding experience for new users.
It orchestrates the entire data pipeline from zero to a production-ready
analytics warehouse without duplicating any business logic.

Pipeline Sequence:
  1. Ingestion: Download the complete StatsBomb Open Data catalogue.
  2. ETL: Normalize the raw JSON into Parquet files.
  3. Warehouse: Build the DuckDB analytical views.
"""

import subprocess
import sys
from pathlib import Path

# Identify project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]

def run_command(command: list[str], description: str) -> None:
    """Run a subprocess command with error handling."""
    print(f"▶ {description}...")
    try:
        # Use sys.executable to ensure we use the current virtual environment's python
        subprocess.run(
            [sys.executable] + command,
            cwd=PROJECT_ROOT,
            check=True,
        )
        print(f"✓ {description.split(':')[0]} complete.\n")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Bootstrap failed during: {description}")
        print(f"Command returned non-zero exit status {e.returncode}.")
        sys.exit(1)

def main() -> None:
    print("\n" + "=" * 60)
    print("  Athena — Data Bootstrap")
    print("=" * 60 + "\n")
    print("This script will download the complete StatsBomb Open Data")
    print("catalogue, process it, and build the analytics warehouse.\n")

    # Step 1: Ingestion (Idempotent by default)
    run_command(
        ["-m", "backend.ingestion.load_data"],
        "Step 1: Downloading StatsBomb Open Data"
    )

    # Step 2: ETL (Skips if processed files already exist)
    run_command(
        ["-m", "backend.etl.pipeline"],
        "Step 2: Running ETL Pipeline (JSON -> Parquet)"
    )

    # Step 3: Warehouse Build (Idempotent view recreation)
    run_command(
        ["-m", "backend.warehouse.warehouse"],
        "Step 3: Building DuckDB Analytics Warehouse"
    )

    print("=" * 60)
    print("  Bootstrap Successful!")
    print("  Athena is now fully initialized with real data.")
    print("  You can now launch the application:")
    print("\n      streamlit run frontend/app.py\n")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
