# ─────────────────────────────────────────────────────────────────────────────
# Athena — Makefile
#
# Usage:
#   make setup      Create virtual environment and install dependencies
#   make data       Fetch StatsBomb Open Data into data/raw/
#   make validate   Run data validation and generate report
#   make test       Run all tests
#   make app        Launch Streamlit application
#   make api        Start FastAPI backend (uvicorn)
#   make format     Auto-format code with Black
#   make lint       Lint code with Ruff
#   make clean      Remove generated files and caches
#   make help       Show this message
#
# Note: On Windows, run via Git Bash, WSL, or install Make via Chocolatey:
#   choco install make
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help setup data validate test app api format lint clean

VENV        := .venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
STREAMLIT   := $(VENV)/bin/streamlit
UVICORN     := $(VENV)/bin/uvicorn
PYTEST      := $(VENV)/bin/pytest
BLACK       := $(VENV)/bin/black
RUFF        := $(VENV)/bin/ruff

# ── Windows compatibility ─────────────────────────────────────────────────────
ifeq ($(OS),Windows_NT)
  PYTHON    := $(VENV)/Scripts/python
  PIP       := $(VENV)/Scripts/pip
  STREAMLIT := $(VENV)/Scripts/streamlit
  UVICORN   := $(VENV)/Scripts/uvicorn
  PYTEST    := $(VENV)/Scripts/pytest
  BLACK     := $(VENV)/Scripts/black
  RUFF      := $(VENV)/Scripts/ruff
endif

# ─────────────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  Athena — Football Decision Intelligence Platform"
	@echo "  ─────────────────────────────────────────────────"
	@echo "  make setup      Create venv and install dependencies"
	@echo "  make data       Fetch StatsBomb Open Data"
	@echo "  make validate   Validate raw data and generate report"
	@echo "  make test       Run test suite"
	@echo "  make app        Launch Streamlit application"
	@echo "  make api        Start FastAPI backend"
	@echo "  make format     Auto-format with Black"
	@echo "  make lint       Lint with Ruff"
	@echo "  make clean      Remove generated artifacts"
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────

setup:
	@echo "→ Creating virtual environment..."
	python -m venv $(VENV)
	@echo "→ Upgrading pip..."
	$(PIP) install --upgrade pip
	@echo "→ Installing dependencies..."
	$(PIP) install -r requirements.txt
	@echo "→ Installing Athena in editable mode..."
	$(PIP) install -e .
	@echo "✓ Setup complete. Activate with: source .venv/bin/activate"

# ─────────────────────────────────────────────────────────────────────────────

data:
	@echo "→ Fetching StatsBomb Open Data..."
	$(PYTHON) -m backend.ingestion.load_data
	@echo "✓ Data downloaded to data/raw/"

# ─────────────────────────────────────────────────────────────────────────────

validate:
	@echo "→ Running data validation..."
	$(PYTHON) -m backend.ingestion.validator
	@echo "✓ Validation report written to logs/"

# ─────────────────────────────────────────────────────────────────────────────

test:
	@echo "→ Running test suite..."
	$(PYTEST) tests/ -v

test-unit:
	$(PYTEST) tests/ -v -m unit

test-integration:
	$(PYTEST) tests/ -v -m integration

# ─────────────────────────────────────────────────────────────────────────────

app:
	@echo "→ Starting Athena Streamlit application..."
	$(STREAMLIT) run frontend/app.py

# ─────────────────────────────────────────────────────────────────────────────

api:
	@echo "→ Starting FastAPI backend..."
	$(UVICORN) backend.api.main:app --reload --host 0.0.0.0 --port 8000

# ─────────────────────────────────────────────────────────────────────────────

format:
	@echo "→ Formatting with Black..."
	$(BLACK) backend/ frontend/ shared/ tests/

lint:
	@echo "→ Linting with Ruff..."
	$(RUFF) check backend/ frontend/ shared/ tests/

lint-fix:
	$(RUFF) check --fix backend/ frontend/ shared/ tests/

# ─────────────────────────────────────────────────────────────────────────────

clean:
	@echo "→ Cleaning generated files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "✓ Clean complete"

clean-data:
	@echo "⚠ Removing processed data (raw data preserved)..."
	rm -rf data/processed/* data/warehouse/*
	@echo "✓ Processed data removed"
