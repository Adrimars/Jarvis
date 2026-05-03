# core/tasks.py
# Celery task definitions. run_module() is called by the Beat scheduler for
# every timed module (weather, news, clothing…). run_backup() and
# run_normalize() handle nightly maintenance. Proactive results are
# automatically pushed to the Telegram outbox queue.

import json
import logging
import os

import redis

from core.celery_app import app
from core.module_loader import load_all_modules
from core.catchup import record_run

logger = logging.getLogger("tasks")

r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)


def _push_telegram(message: str, buttons: list = None):
    payload = {"text": message}
    if buttons:
        payload["buttons"] = buttons
    r.rpush("queue:telegram:outbox", json.dumps(payload))


@app.task(name="tasks.run_module", bind=True, max_retries=2)
def run_module(self, module_name: str, catchup: bool = False):
    modules = {m.name: m for m in load_all_modules()}
    module = modules.get(module_name)

    if not module:
        logger.error(f"Module not found: {module_name}")
        return

    prefix = "[catchup] " if catchup else ""
    logger.info(f"{prefix}Running module: {module_name}")

    try:
        result = module.run(profile={})
        record_run(module_name, result.success)

        if result.message:
            logger.info(f"{module_name}: {result.message[:120]}")

        # Push to Telegram for proactive modules (unless module already did it internally)
        if result.proactive and result.message and module_name not in ("morning_briefing",):
            _push_telegram(result.message, getattr(result, "buttons", None))

        return {"success": result.success, "message": result.message}
    except Exception as exc:
        logger.error(f"{module_name} failed: {exc}")
        record_run(module_name, False)
        raise self.retry(exc=exc, countdown=60)


@app.task(name="tasks.run_backup")
def run_backup():
    from core.learning import LearningEngine
    from core.profile import load_profile
    try:
        LearningEngine()._backup(load_profile())
        logger.info("Nightly backup complete")
    except Exception as e:
        logger.error(f"Backup failed: {e}")


@app.task(name="tasks.run_normalize")
def run_normalize():
    from core.learning import LearningEngine
    from core.profile import load_profile
    try:
        LearningEngine().weekly_normalize(load_profile())
        logger.info("Weekly interest normalization complete")
    except Exception as e:
        logger.error(f"Normalization failed: {e}")
