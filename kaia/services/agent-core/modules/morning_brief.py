# modules/morning_brief.py
# Runs at 07:30 every day. Reads cached weather and news from Redis,
# asks the LLM for a short motivational line, and pushes the combined
# morning summary directly to the Telegram outbox queue.

import logging
import os

import redis

from core.profile import load_profile
from llm.client import ask_llm
from modules.base import BaseModule, ModuleResult

logger = logging.getLogger("module.morning_brief")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


class MorningBriefModule(BaseModule):
    name = "morning_briefing"
    schedule = "every day 07:30"
    catchup = False

    def run(self, profile: dict) -> ModuleResult:
        if not profile:
            profile = load_profile()

        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

        weather = r.get("latest:weather") or ""
        news = r.get("latest:news") or ""

        name = profile.get("name", "")
        greeting = f"Good morning{', ' + name if name else ''}! ☀️"

        parts = [greeting]

        if weather:
            parts.append(weather)

        if news:
            parts.append(news)

        if not weather and not news:
            context = "No weather or news data available for the morning brief."
        else:
            context = "\n\n".join(parts[1:])

        interests = profile.get("interests", [])

        motivation = ask_llm(
            f"Based on the following morning brief, write a short motivational message "
            f"in English (2 sentences). "
            f"User interests: {', '.join(interests) if interests else 'general'}.\n\n"
            f"{context}",
            temperature=0.7,
        )
        parts.append(motivation)

        message = "\n\n".join(parts)

        r.rpush("queue:telegram:outbox", __import__("json").dumps({"text": message}))

        return ModuleResult(success=True, message=message, proactive=True)
