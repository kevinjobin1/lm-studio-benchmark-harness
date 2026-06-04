"""
Model Lens structured logging.

Replaces raw print() calls with configurable, leveled logging that supports:
  - Rich console output (with colors) when available
  - Plain text fallback
  - File logging to results/ directory
  - Log level control via MODELLENS_LOG_LEVEL env var

Usage:
    from packages.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Starting benchmark", model="qwen", provider="lm-studio")
    logger.warning("Provider unreachable", url=base_url)
    logger.error("Connection failed", exc_info=True)
"""

import logging
import os
import sys
from typing import Optional

# ── Rich integration ──────────────────────────────────────────────
try:
    from rich.logging import RichHandler

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False

# ── Log level from environment ────────────────────────────────────
_LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_DEFAULT_LEVEL = "INFO"


def _get_log_level() -> int:
    """Read MODELLENS_LOG_LEVEL from environment, defaulting to INFO."""
    raw = os.environ.get("MODELLENS_LOG_LEVEL", _DEFAULT_LEVEL).upper()
    return _LOG_LEVEL_MAP.get(raw, logging.INFO)


# ── Formatter ─────────────────────────────────────────────────────

class ModelLensFormatter(logging.Formatter):
    """Lightweight formatter that includes the logger name for context."""

    def format(self, record: logging.LogRecord) -> str:
        # Include module name for disambiguation
        if record.name.startswith("packages."):
            record.shortname = record.name[len("packages."):]
        elif record.name.startswith("apps."):
            record.shortname = record.name[len("apps."):]
        else:
            record.shortname = record.name

        return super().format(record)


# ── Root logger setup ─────────────────────────────────────────────

_root_logger: Optional[logging.Logger] = None
_initialized = False


def _init_logging() -> None:
    """Configure the root logger once."""
    global _root_logger, _initialized
    if _initialized:
        return

    level = _get_log_level()
    root = logging.getLogger("modellens")
    root.setLevel(level)

    # Prevent propagation to avoid duplicate output from the root logger
    root.propagate = False

    if root.handlers:
        # Already configured (e.g., by a previous call)
        _root_logger = root
        _initialized = True
        return

    if _RICH_AVAILABLE:
        handler = RichHandler(
            console=None,  # auto-detect
            show_time=True,
            show_level=True,
            show_path=False,
            rich_tracebacks=True,
            markup=True,
        )
        handler.setFormatter(ModelLensFormatter("%(message)s"))
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            ModelLensFormatter(
                "%(asctime)s [%(levelname)-7s] %(shortname)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    root.addHandler(handler)
    _root_logger = root

    # ── File handler (optional) ──────────────────────────────────
    log_dir = os.environ.get("MODELLENS_LOG_DIR", "")
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        file_path = os.path.join(log_dir, "modellens.log")
        fh = logging.FileHandler(file_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
            )
        )
        root.addHandler(fh)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance for the given module name.

    Usage:
        from packages.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Hello")
    """
    _init_logging()
    return logging.getLogger(f"modellens.{name}")


def set_level(level: str) -> None:
    """Change the log level at runtime.

    Args:
        level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
    """
    _init_logging()
    numeric = _LOG_LEVEL_MAP.get(level.upper(), logging.INFO)
    logging.getLogger("modellens").setLevel(numeric)


# ── Legacy bridge ─────────────────────────────────────────────────
# To ease migration, provide a logger instance usable from older code
# that doesn't yet have __name__ context.

_default_logger: Optional[logging.Logger] = None


def _legacy_logger() -> logging.Logger:
    global _default_logger
    if _default_logger is None:
        _init_logging()
        _default_logger = logging.getLogger("modellens")
    return _default_logger


def info(msg: str, **kwargs) -> None:
    _legacy_logger().info(msg, **kwargs)


def warning(msg: str, **kwargs) -> None:
    _legacy_logger().warning(msg, **kwargs)


def error(msg: str, **kwargs) -> None:
    _legacy_logger().error(msg, **kwargs)


def debug(msg: str, **kwargs) -> None:
    _legacy_logger().debug(msg, **kwargs)
