import logging
import os
from celery import Celery
from celery.schedules import crontab

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [celery] %(message)s",
)
from core.logger import setup_file_logging
setup_file_logging("celery-worker")

from core.config import schedule as cfg_schedule, timezone as cfg_timezone


def _parse(time_str: str):
    """Parse 'HH:MM' or 'day HH:MM' into a crontab."""
    parts = time_str.strip().split()
    if len(parts) == 2:
        day, hhmm = parts
    else:
        day, hhmm = None, parts[0]
    h, m = map(int, hhmm.split(":"))
    if day:
        return crontab(hour=h, minute=m, day_of_week=day)
    return crontab(hour=h, minute=m)


app = Celery(
    "kaia",
    broker=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    include=["core.tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=cfg_timezone(),
    enable_utc=True,
    beat_schedule={
        "hello-kaia-every-minute": {
            "task": "tasks.run_module",
            "schedule": 60.0,
            "args": ["hello_kaia"],
        },
        "weather-outfit-daily": {
            "task": "tasks.run_module",
            "schedule": _parse(cfg_schedule("weather_outfit") or "07:25"),
            "args": ["weather_outfit"],
        },
        "morning-briefing-daily": {
            "task": "tasks.run_module",
            "schedule": _parse(cfg_schedule("morning_briefing") or "07:30"),
            "args": ["morning_briefing"],
        },
        "news-daily": {
            "task": "tasks.run_module",
            "schedule": _parse(cfg_schedule("news") or "08:00"),
            "args": ["news"],
        },
        "weekly-events": {
            "task": "tasks.run_module",
            "schedule": _parse(cfg_schedule("events") or "monday 08:30"),
            "args": ["events"],
        },
        "price-check-daily": {
            "task": "tasks.run_module",
            "schedule": _parse(cfg_schedule("price_tracker") or "12:00"),
            "args": ["price_tracker"],
        },
        "clothing-scan": {
            "task": "tasks.run_module",
            "schedule": _parse(cfg_schedule("clothing") or "tuesday,friday 10:00"),
            "args": ["clothing"],
        },
        "nightly-backup": {
            "task": "tasks.run_backup",
            "schedule": _parse(cfg_schedule("nightly_backup") or "03:00"),
        },
        "weekly-normalize": {
            "task": "tasks.run_normalize",
            "schedule": _parse(cfg_schedule("weekly_normalize") or "sunday 04:00"),
        },
    },
)
