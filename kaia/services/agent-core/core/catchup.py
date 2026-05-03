# core/catchup.py
# Runs at startup to detect modules that missed their scheduled execution
# while the computer was off. Re-queues them via Celery so nothing is skipped.
# Modules listed in NO_CATCHUP are intentionally excluded (e.g. morning news
# is useless if delivered at 3pm).

import json
import logging
import os
import redis
from datetime import datetime, timedelta

r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
logger = logging.getLogger("catchup")

NO_CATCHUP = {"news", "morning_briefing", "clothing", "events", "hello_kaia"}


def record_run(module_name: str, success: bool):
    r.set(
        f"job_state:{module_name}",
        json.dumps({
            "last_run": datetime.now().isoformat(),
            "status": "completed" if success else "failed",
        }),
    )


class CatchUpService:
    def run(self, modules: list):
        from core.celery_app import app as celery_app

        for module in modules:
            if module.name in NO_CATCHUP:
                continue
            if not module.catchup or not module.schedule:
                continue

            state = self._get_state(module.name)
            if self._should_catchup(module, state):
                self._enqueue(module.name, celery_app)
                logger.info(f"[catchup] {module.name} missed, added to queue")

    def _should_catchup(self, module, state: dict) -> bool:
        last_run = state.get("last_run")
        if not last_run:
            return True

        last_run_dt = datetime.fromisoformat(last_run)
        offline = datetime.now() - last_run_dt

        if offline > timedelta(hours=6):
            already_queued = r.get(f"catchup_done:{module.name}:{datetime.today().date()}")
            return not already_queued

        return True

    def _get_state(self, name: str) -> dict:
        raw = r.get(f"job_state:{name}")
        return json.loads(raw) if raw else {}

    def _enqueue(self, name: str, celery_app):
        celery_app.send_task("tasks.run_module", args=[name], kwargs={"catchup": True})
        r.setex(f"catchup_done:{name}:{datetime.today().date()}", 86400, "1")
