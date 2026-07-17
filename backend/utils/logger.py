"""
backend/utils/logger.py - Centralized structured logging for Athena

All modules use this logger. Never use print() statements in production code.

Usage:
    from backend.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("etl.complete", rows_processed=1234, duration_s=2.3)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog

# -----------------------------------------------------------------------------
# Log directory
# -----------------------------------------------------------------------------

LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"
LOGS_DIR.mkdir(exist_ok=True)


# -----------------------------------------------------------------------------
# Configure stdlib logging (structlog delegates to this)
# -----------------------------------------------------------------------------


def _configure_stdlib_logging(level: int = logging.INFO) -> None:
    """Set up stdlib logging with both console and file handlers."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicate output
    if root_logger.handlers:
        root_logger.handlers.clear()

    fmt = "%(message)s"

    # Console handler - human-readable
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(fmt))
    root_logger.addHandler(console_handler)

    # File handler - machine-readable JSON
    log_file = LOGS_DIR / "athena.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(fmt))
    root_logger.addHandler(file_handler)


# -----------------------------------------------------------------------------
# Configure structlog
# -----------------------------------------------------------------------------


def _configure_structlog() -> None:
    """Configure structlog with consistent processors."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Run configuration once at import time
_configure_stdlib_logging()
_configure_structlog()


# -----------------------------------------------------------------------------
# Public interface
# -----------------------------------------------------------------------------


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Return a bound structlog logger for the given module name.

    Example:
        logger = get_logger(__name__)
        logger.info("pipeline.start", source="statsbomb", competition="La Liga")
    """
    return structlog.get_logger(name)


def get_validation_logger() -> structlog.stdlib.BoundLogger:
    """
    Return a logger that writes to a dedicated validation log file.

    Used by ingestion/validator.py.
    """
    validation_log = LOGS_DIR / "validation.log"
    validation_handler = logging.FileHandler(validation_log, encoding="utf-8")
    validation_handler.setLevel(logging.INFO)

    val_logger = logging.getLogger("athena.validation")
    if not val_logger.handlers:
        val_logger.addHandler(validation_handler)
        val_logger.propagate = False

    return structlog.wrap_logger(val_logger, logger_name="athena.validation")
