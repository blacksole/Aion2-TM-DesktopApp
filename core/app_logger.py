"""Shared file logger for the whole app (main window + ItemDatabase/Armory).

Writes to app.log in the per-user log directory when frozen (%APPDATA%\\Aion2 TM\\
on Windows -- unchanged -- , $XDG_STATE_HOME/aion2-tm on Linux, ~/Library/Logs
on macOS; see utils/paths.py) and in the project root when running from source
-- same place for both parts of the app, so there is exactly one log to check
regardless of which part something happened in.
"""

import logging
import sys
from datetime import date
from pathlib import Path

from utils import paths

_ROOT_LOGGER_NAME = "aion2tm"
_root_logger = logging.getLogger(_ROOT_LOGGER_NAME)


def _log_dir() -> Path:
    if getattr(sys, "frozen", False):
        return paths.user_log_dir()
    # From source the log stays in the repo root, next to the dev config.json.
    return paths.app_root()


def setup_logging() -> logging.Logger:
    """Configure the shared file handler. Safe to call more than once."""
    if _root_logger.handlers:
        return _root_logger

    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.log"

    # Reset once a day instead of size-based rotation -- if the existing log
    # is from a previous day, start fresh so it never grows unbounded across
    # sessions; multiple runs on the same day keep appending to one file.
    if log_path.exists():
        modified_date = date.fromtimestamp(log_path.stat().st_mtime)
        if modified_date < date.today():
            log_path.unlink()

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    _root_logger.addHandler(handler)
    _root_logger.setLevel(logging.DEBUG)
    _root_logger.propagate = False
    return _root_logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger under the shared app logger, configuring it on first use."""
    setup_logging()
    return _root_logger.getChild(name) if name else _root_logger


def get_log_path() -> Path:
    """Where app.log actually lives -- used by Settings' "View Log" button
    (User-Wunsch, 2026-08-27) so the user can see what happened (which
    window opened when, which assets/colors loaded or failed to) without
    having to find the file manually."""
    setup_logging()
    return _log_dir() / "app.log"
