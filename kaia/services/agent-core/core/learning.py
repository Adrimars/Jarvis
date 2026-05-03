import json
import logging
import os

import redis

from core.profile import save_profile

logger = logging.getLogger("learning")
r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)


class LearningEngine:
    def process_feedback(self, item_id: str, feedback: str, profile: dict):
        item_raw = r.get(f"item:{item_id}")
        if not item_raw:
            return
        item = json.loads(item_raw)
        category = item.get("category", "general")

        delta = 0.02 if feedback == "like" else -0.01
        interests = profile.setdefault("interests_scores", {})
        current = interests.get(category, 0.5)
        interests[category] = max(0.0, min(1.0, current + delta))
        save_profile(profile)
        logger.info(f"Feedback '{feedback}' on {category}: {current:.2f} → {interests[category]:.2f}")

    def weekly_normalize(self, profile: dict):
        scores = profile.get("interests_scores", {})
        total = sum(scores.values()) or 1
        for key in scores:
            scores[key] /= total
        save_profile(profile)
        logger.info("Interest weights normalized")
