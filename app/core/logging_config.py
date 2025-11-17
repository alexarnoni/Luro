"""Centralized logging configuration for the application."""
from __future__ import annotations

import logging
import logging.handlers
import os
import time

from app.core.config import settings


def setup_logging() -> None:
    """Configure application and uvicorn loggers with sane defaults."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    os.makedirs("logs", exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)sZ | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logging.Formatter.converter = time.gmtime

    file_handler = logging.handlers.RotatingFileHandler(
        "logs/app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [file_handler, stream_handler]

    # Explicit security logger with same handlers for quick filtering.
    security_logger = logging.getLogger("app.security")
    security_logger.setLevel(log_level)
    security_logger.propagate = True

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(log_level)


__all__ = ["setup_logging"]
