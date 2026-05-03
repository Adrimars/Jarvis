import os
from celery import Celery
from celery.schedules import crontab

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
    timezone="Europe/Istanbul",
    enable_utc=True,
    beat_schedule={
        "hello-kaia-every-minute": {
            "task": "tasks.run_module",
            "schedule": 60.0,
            "args": ["hello_kaia"],
        },
        "price-check-daily": {
            "task": "tasks.run_module",
            "schedule": crontab(hour=12, minute=0),
            "args": ["price_tracker"],
        },
        "morning-briefing-daily": {
            "task": "tasks.run_module",
            "schedule": crontab(hour=7, minute=30),
            "args": ["morning_briefing"],
        },
        "evening-reading-daily": {
            "task": "tasks.run_module",
            "schedule": crontab(hour=21, minute=0),
            "args": ["evening_reading"],
        },
        "weekly-events-monday": {
            "task": "tasks.run_module",
            "schedule": crontab(hour=9, minute=0, day_of_week="monday"),
            "args": ["events"],
        },
        "clothing-scan-tue-fri": {
            "task": "tasks.run_module",
            "schedule": crontab(hour=10, minute=0, day_of_week="tuesday,friday"),
            "args": ["clothing"],
        },
        "weather-outfit-daily": {
            "task": "tasks.run_module",
            "schedule": crontab(hour=7, minute=25),
            "args": ["weather_outfit"],
        },
        "news-daily": {
            "task": "tasks.run_module",
            "schedule": crontab(hour=8, minute=0),
            "args": ["news"],
        },
    },
)
