import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

import redis

from core.profile import load_profile, save_profile

logger = logging.getLogger("learning")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DATA_DIR = Path(os.getenv("KAIA_DATA_DIR", "/data/kaia"))
BACKUP_DIR = DATA_DIR / "backups"
PROFILE_PATH = DATA_DIR / "user_profile.yaml"

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)


class LearningEngine:
    def process_feedback(self, item_id: str, feedback: str, profile: dict):
        item_raw = r.get(f"item:{item_id}")
        if not item_raw:
            return
        item = json.loads(item_raw)
        category = item.get("category", "general")

        delta = 0.02 if feedback == "like" else -0.01
        scores = profile.setdefault("interests_scores", {})
        current = scores.get(category, 0.5)
        scores[category] = round(max(0.0, min(1.0, current + delta)), 3)
        save_profile(profile)
        logger.info(f"Feedback '{feedback}' on '{category}': {current:.3f} → {scores[category]:.3f}")

    def weekly_normalize(self, profile: dict):
        scores = profile.get("interests_scores", {})
        if not scores:
            return
        total = sum(scores.values()) or 1
        for key in scores:
            scores[key] = round(scores[key] / total, 4)
        save_profile(profile)
        self._backup(profile)
        logger.info("Interest weights normalized and profile backed up")

    def _backup(self, profile: dict):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")

        # Profile backup
        profile_backup = BACKUP_DIR / f"profile_{today}.yaml"
        if PROFILE_PATH.exists() and not profile_backup.exists():
            shutil.copy2(PROFILE_PATH, profile_backup)

        # Job state backup
        state_backup = BACKUP_DIR / f"job_state_{today}.json"
        if not state_backup.exists():
            state = {k: r.get(k) for k in r.scan_iter("catchup:*")}
            state_backup.write_text(json.dumps(state, indent=2), encoding="utf-8")

        # Purge backups older than 30 days
        self._purge_old_backups()

    def _purge_old_backups(self):
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=30)
        for f in BACKUP_DIR.glob("*.yaml"):
            try:
                date_str = f.stem.split("_")[-1]
                if datetime.strptime(date_str, "%Y-%m-%d") < cutoff:
                    f.unlink()
            except Exception:
                pass
        for f in BACKUP_DIR.glob("*.json"):
            try:
                date_str = f.stem.split("_")[-1]
                if datetime.strptime(date_str, "%Y-%m-%d") < cutoff:
                    f.unlink()
            except Exception:
                pass
