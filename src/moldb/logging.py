"""
Logging configuration for moldb-api.

Provides separate log setup for API, builder, and store components.
Each can be directed to its own log file or share the same file.
"""

import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Logger name constants
# ---------------------------------------------------------------------------

API_LOGGER = "moldb.api"
BUILDER_LOGGER = "moldb.builder"
STORE_LOGGER = "moldb.store"

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}

DEFAULT_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_logging(
    name: str,
    level: str = "INFO",
    log_file: str | None = None,
) -> logging.Logger:
    """Configure a named logger with console and optional file output.

    Always adds a stderr StreamHandler. Optionally adds a FileHandler if
    *log_file* is provided. The call is idempotent — existing handlers are
    cleared before re-configuring.

    Args:
        name: Logger name (e.g. ``"moldb.api"``, ``"moldb.builder"``).
        level: Log level string (``"DEBUG"`` | ``"INFO"`` | ``"WARNING"``
               | ``"ERROR"``).
        log_file: Path to log file. ``None`` = console only.

    Returns:
        Configured :class:`logging.Logger` instance.
    """
    if level.upper() not in _VALID_LEVELS:
        raise ValueError(
            f"log_level must be one of {sorted(_VALID_LEVELS)}, got {level!r}"
        )

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.propagate = False

    # Idempotent: clear any handlers from a previous call
    logger.handlers.clear()

    formatter = logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)

    # Always log to stderr
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # Optionally log to file
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper around :func:`logging.getLogger`."""
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Uvicorn log config
# ---------------------------------------------------------------------------


def build_uvicorn_log_config(
    log_file: str | None = None,
    level: str = "INFO",
) -> dict:
    """Build a uvicorn log config dict that mirrors our app log format.

    Args:
        log_file: Path to log file. ``None`` = stderr only.
        level: Log level string.

    Returns:
        A dict suitable for ``uvicorn.run(..., log_config=...)``.
    """
    handlers = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    }

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers["default_file"] = {
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": log_file,
        }
        handlers["access_file"] = {
            "formatter": "access",
            "class": "logging.FileHandler",
            "filename": log_file,
        }
        default_handlers = ["default", "default_file"]
        access_handlers = ["access", "access_file"]
    else:
        default_handlers = ["default"]
        access_handlers = ["access"]

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": DEFAULT_FORMAT,
                "datefmt": DEFAULT_DATE_FORMAT,
            },
            "access": {
                "format": "%(asctime)s [%(levelname)-8s] moldb.api: %(client_addr)s - "
                '"%(request_line)s" %(status_code)s',
                "datefmt": DEFAULT_DATE_FORMAT,
            },
        },
        "handlers": handlers,
        "loggers": {
            "uvicorn": {
                "handlers": default_handlers,
                "level": level.upper(),
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": access_handlers,
                "level": level.upper(),
                "propagate": False,
            },
            "uvicorn.error": {"level": level.upper()},
        },
    }
