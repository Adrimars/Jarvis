# core/logger.py
# Adds a rotating file handler to the root logger for each service.
# Log files live at /data/kaia/logs/<service>.log and are kept for 30 days.
# Called once at startup in main.py, celery_app.py, and scraper/main.py.

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path(os.getenv("KAIA_DATA_DIR", "/data/kaia")) / "logs"
_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
_configured = set()


def setup_file_logging(service_name: str):
    """Add a 30-day rotating file handler to the root logger for a service."""
    if service_name in _configured:
        return
    _configured.add(service_name)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{service_name}.log"

    handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.setLevel(logging.INFO)

    root = logging.getLogger()
    root.addHandler(handler)
