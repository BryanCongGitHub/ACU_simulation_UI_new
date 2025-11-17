from __future__ import annotations

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent.parent
LOG_PATH = BASE_DIR / "acu_simulator.log"


def configure_logging(
    log_path: Path = LOG_PATH,
) -> tuple[logging.Logger, Optional[RotatingFileHandler]]:
    """Configure application logging in a centralized, idempotent way.

    Returns (logger, file_handler).
    """
    app_logger = logging.getLogger("ACUSim")
    file_h: Optional[RotatingFileHandler] = None
    if not app_logger.handlers:
        app_logger.setLevel(logging.INFO)
        file_h = RotatingFileHandler(
            str(log_path),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_h.setFormatter(formatter)
        app_logger.addHandler(file_h)

        console = logging.StreamHandler()
        console.setLevel(logging.WARNING)
        console.setFormatter(formatter)
        app_logger.addHandler(console)

        if file_h is not None:
            _data_buffer_logger = logging.getLogger("DataBuffer")
            _data_buffer_logger.setLevel(logging.INFO)
            _data_buffer_logger.addHandler(file_h)

            _waveform_logger = logging.getLogger("WaveformController")
            _waveform_logger.setLevel(logging.INFO)
            _waveform_logger.addHandler(file_h)
    return app_logger, file_h


logger: logging.Logger = logging.getLogger("ACUSim")
file_handler: Optional[RotatingFileHandler] = None
if os.environ.get("ACU_INIT_LOGGING_ON_IMPORT", "1") == "1":
    logger, file_handler = configure_logging(LOG_PATH)


def initialize_app_environment(log_path: Path = LOG_PATH) -> None:
    """Initialize environment and logging for application entry points.

    Safe to call multiple times (idempotent).
    """
    try:
        # Keep Qt environment setup separate so tests can import logging
        # without forcing Qt imports at module import time.
        from setup_qt_environment import setup_qt_environment

        setup_qt_environment()
    except Exception:
        # If setup fails, keep going — tests may run without Qt available
        pass

    global logger, file_handler
    logger, file_handler = configure_logging(log_path)
