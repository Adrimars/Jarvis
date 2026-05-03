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
        language = profile.get("language", "tr")
        country = "tr" if language == "tr" else "us"

        if not NEWS_API_KEY:
            logger.warning("NEWS_API_KEY not set — skipping news module")
            return ModuleResult(success=False, message="Haber anahtarı ayarlanmamış.")

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
                return ModuleResult(success=True, message="Bugün öne çıkan haber bulunamadı.")

            headlines = "\n".join(
                f"- {a['title']} ({a.get('source', {}).get('name', '')})"
                for a in articles[:7]
                if a.get("title")
            )

            lang_hint = "Türkçe" if language == "tr" else "English"
            summary = ask_llm(
                f"Bu haber başlıklarını {lang_hint} olarak 3 cümlede özetle, "
                f"en önemli 2-3 konuya odaklan:\n{headlines}",
                temperature=0.5,
            )

            message = f"📰 Günün haberleri:\n{summary}"

            import redis, json
            r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
            r.setex("latest:news", 3600 * 12, message)

            return ModuleResult(success=True, message=message)

        except httpx.TimeoutException:
            logger.warning("NewsAPI timeout")
            return ModuleResult(success=False, message="Haberler alınamadı (timeout).")
        except Exception as e:
            logger.error(f"News module error: {e}")
            return ModuleResult(success=False, message="Haberler alınamadı.")
