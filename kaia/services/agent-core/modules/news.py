# modules/news.py
# Runs every morning at 08:00. Fetches top headlines from NewsAPI filtered by
# the user's interests, then uses the LLM to summarise them in 3 sentences.
# Result is cached in Redis and consumed by the morning brief module.

import logging
import os

import httpx

from core.profile import load_profile
from llm.client import ask_llm
from modules.base import BaseModule, ModuleResult

logger = logging.getLogger("module.news")

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NEWS_API_URL = "https://newsapi.org/v2/top-headlines"


class NewsModule(BaseModule):
    name = "news"
    schedule = "every day 08:00"
    catchup = False

    def run(self, profile: dict) -> ModuleResult:
        if not profile:
            profile = load_profile()

        interests = profile.get("interests", [])
        language = profile.get("language", "en")
        country = profile.get("country", "us")

        if not NEWS_API_KEY:
            logger.warning("NEWS_API_KEY not set — skipping news module")
            return ModuleResult(success=False, message="NEWS_API_KEY is not set.")

        try:
            params = {
                "country": country,
                "pageSize": 10,
                "apiKey": NEWS_API_KEY,
            }
            if interests:
                params["q"] = " OR ".join(interests[:3])

            resp = httpx.get(NEWS_API_URL, params=params, timeout=10)
            resp.raise_for_status()
            articles = resp.json().get("articles", [])

            if not articles:
                return ModuleResult(success=True, message="No top headlines found for today.")

            headlines = "\n".join(
                f"- {a['title']} ({a.get('source', {}).get('name', '')})"
                for a in articles[:7]
                if a.get("title")
            )

            summary = ask_llm(
                f"Summarise these headlines in 3 sentences in English, "
                f"focusing on the 2-3 most important topics:\n{headlines}",
                temperature=0.5,
            )

            message = f"📰 Today's news:\n{summary}"

            import redis, json
            r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
            r.setex("latest:news", 3600 * 12, message)

            return ModuleResult(success=True, message=message)

        except httpx.TimeoutException:
            logger.warning("NewsAPI timeout")
            return ModuleResult(success=False, message="Could not fetch news (timeout).")
        except Exception as e:
            logger.error(f"News module error: {e}")
            return ModuleResult(success=False, message="Could not fetch news.")
