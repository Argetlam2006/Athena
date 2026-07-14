# ─────────────────────────────────────────────────────────────────────────────
# Athena — Makefile
#
# Usage:
#   make setup                 Create virtual environment and install dependencies
#   make data                  Fetch sample StatsBomb data (fast, ~30s)
#   make data-full             Fetch complete StatsBomb catalogue (slow, GB+)
#   make data-competition      Fetch one competition: COMPETITION="La Liga"
#   make data-list             List available StatsBomb competitions
#   make validate              Validate raw JSON files and generate report
#   make test                  Run all tests
#   make test-unit             Run unit tests only (no network)
#   make test-integration      Run integration tests only (no network)
#   make app                   Launch Streamlit application
#   make api                   Start FastAPI backend (uvicorn)
#   make format                Auto-format code with Black
#   make lint                  Lint code with Ruff
#   make clean                 Remove generated files and caches
#   make clean-data            Remove processed data only (raw preserved)
#   make help                  Show this message
#
# Note: On Windows, run via Git Bash, WSL, or install Make via Chocolatey:
#   choco install make
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help setup data data-full data-competition data-list validate validate-json \
        test test-unit test-integration app api format lint lint-fix clean clean-data

# Override COMPETITION on the command line:
#   make data-competition COMPETITION="Champions League"
COMPETITION ?= La Liga

# Override N_MATCHES for sample size:
#   make data N_MATCHES=10
N_MATCHES ?= 5

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
	@echo "  ─────────────────────────────────────────────────────────────"
	@echo "  make setup                 Create venv and install dependencies"
	@echo "  make data                  Fetch sample data (5 matches, ~30s)"
	@echo "  make data-full             Fetch full StatsBomb catalogue"
	@echo "  make data-competition      Fetch one competition (set COMPETITION=)"
	@echo "  make data-list             List available competitions"
	@echo "  make validate              Validate raw JSON files"
	@echo "  make test                  Run all tests"
	@echo "  make test-unit             Unit tests only (no network)"
	@echo "  make test-integration      Integration tests only (no network)"
	@echo "  make app                   Launch Streamlit UI"
	@echo "  make api                   Start FastAPI backend"
	@echo "  make format                Auto-format with Black"
	@echo "  make lint                  Lint with Ruff"
	@echo "  make clean                 Remove caches and generated files"
	@echo "  make clean-data            Remove processed data only"
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
	@echo "→ Fetching StatsBomb sample data ($(N_MATCHES) matches from La Liga)..."
	$(PYTHON) -m backend.ingestion.load_data --sample --n-matches $(N_MATCHES)
	@echo "✓ Sample data downloaded to data/raw/"
	@echo "  Run 'make validate' to check data quality."

# ─────────────────────────────────────────────────────────────────────────────

data-full:
	@echo "→ Fetching full StatsBomb Open Data catalogue (this may take 20-40 min)..."
	$(PYTHON) -m backend.ingestion.load_data
	@echo "✓ Full catalogue downloaded to data/raw/"

# ─────────────────────────────────────────────────────────────────────────────

data-competition:
	@echo "→ Fetching competition: $(COMPETITION)..."
	$(PYTHON) -m backend.ingestion.load_data --competition "$(COMPETITION)"
	@echo "✓ Competition data downloaded to data/raw/"

# ─────────────────────────────────────────────────────────────────────────────

data-list:
	@echo "→ Available StatsBomb competitions:"
	$(PYTHON) -m backend.ingestion.load_data --list-competitions

# ─────────────────────────────────────────────────────────────────────────────

validate:
	@echo "→ Validating raw JSON files in data/raw/..."
	$(PYTHON) -m backend.ingestion.validator
	@echo "✓ Validation report written to logs/validation.log"

validate-json: validate

# ─────────────────────────────────────────────────────────────────────────────

test:
	@echo "→ Running full test suite..."
	$(PYTEST) tests/ -v --tb=short

test-unit:
	@echo "→ Running unit tests (no network required)..."
	$(PYTEST) tests/test_constants.py tests/test_schemas.py tests/test_ingestion.py -v --tb=short

test-integration:
	@echo "→ Running integration tests (no network required)..."
	$(PYTEST) tests/test_ingestion_integration.py -v --tb=short

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
