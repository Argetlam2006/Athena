# Contributing to Athena

First off, thank you for considering contributing to Athena! It's people like you that make this tool such a great open-source platform.

## Getting Started

1. **Fork the Repository**: Start by forking the repository to your own GitHub account.
2. **Clone the Repo**: Clone it locally to your machine.
3. **Install Dependencies**: 
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
4. **Environment**: Copy `.env.example` to `.env` and configure it.

## Development Workflow

1. Create a feature branch (`git checkout -b feature/amazing-feature`).
2. Make your changes, adhering to the "Evidence before AI" philosophy.
3. Run the tests: `pytest tests/`
4. Run formatting and linting: `black .` and `ruff check .`
5. Commit your changes (`git commit -m 'Add amazing feature'`).
6. Push to your branch (`git push origin feature/amazing-feature`).
7. Open a Pull Request.

## Architecture Philosophy

Please ensure any contributions adhere to the strict separation of concerns outlined in the documentation. The **Football Intelligence Engine** must remain deterministic, and the **AI Explanation Layer** must never generate its own statistics.

Thank you for contributing!
