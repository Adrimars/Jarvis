import json
import logging
import os
import uuid

import redis

from core.profile import load_profile
from llm.client import ask_llm
from modules.base import BaseModule, ModuleResult

logger = logging.getLogger("module.events")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Default sources — more can be added by the user via /addsite
DEFAULT_EVENT_SOURCES = [
    "https://www.biletix.com/bolge/IZMIR/",
    "https://www.passo.com.tr/tr/etkinlik/izmir",
]


class EventsModule(BaseModule):
    name = "events"
    schedule = "every monday 08:30"
    catchup = False

    def run(self, profile: dict) -> ModuleResult:
        if not profile:
            profile = load_profile()

        categories = profile.get("events", {}).get("categories", ["tiyatro", "sinema", "konser"])
        min_score = profile.get("events", {}).get("min_interest_score", 0.75)
        location = profile.get("location", "Izmir").split(",")[0]

        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

        # Dispatch scrape job for each event source
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "query": " ".join(categories[:3]),
            "sites": DEFAULT_EVENT_SOURCES,
            "max_items": 30,
        }
        r.rpush("queue:scraper:inbox", json.dumps(job))
        logger.info(f"Dispatched event scrape job {job_id}")

        # Wait for results (shorter timeout than clothing — events pages are faster)
        import time
        result_key = f"scraper:result:{job_id}"
        deadline = time.time() + 120
        raw_items = []
        while time.time() < deadline:
            raw = r.get(result_key)
            if raw:
                r.delete(result_key)
                raw_items = json.loads(raw)
                break
            time.sleep(3)

        if not raw_items:
            logger.warning("Events scraper returned no results")
            return ModuleResult(success=False, message="Bu hafta etkinlik bilgisi alınamadı.")

        # Score each event with LLM against user interests
        scored = self._score_events(raw_items, categories, location, min_score)
        if not scored:
            return ModuleResult(
                success=True,
                message=f"Bu hafta {location} için ilgi çekici etkinlik bulunamadı.",
            )

        # Cache items for feedback
        for item in scored:
            item_id = item.setdefault("id", str(uuid.uuid4()))
            r.setex(f"item:{item_id}", 3600 * 72, json.dumps(item))

        message = self._format_message(scored[:6], location)
        buttons = [
            [{"label": f"❤️ {item.get('title','')[:20]}", "data": f"feedback_like_{item['id']}"},
             {"label": "👎", "data": f"feedback_dislike_{item['id']}"}]
            for item in scored[:3]
        ]

        r.rpush("queue:telegram:outbox", json.dumps({"text": message, "buttons": buttons}))
        return ModuleResult(success=True, items=scored, message=message, proactive=True)

    def _score_events(self, items: list, categories: list, location: str, min_score: float) -> list:
        if not items:
            return []

        listing = "\n".join(
            f"{i+1}. {item.get('title', '')} — {item.get('source', '')}"
            for i, item in enumerate(items[:20])
        )
        prompt = (
            f"Kullanıcı {location}'da yaşıyor ve şu etkinlikleri seviyor: {', '.join(categories)}.\n"
            f"Aşağıdaki etkinlikleri ilgi düzeyine göre 0.0–1.0 arasında puanla.\n"
            f"Sadece JSON döndür: [{{\"index\": 1, \"score\": 0.9}}, ...]\n\n{listing}"
        )
        try:
            raw = ask_llm(prompt, temperature=0.1)
            import re
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                scores = json.loads(match.group())
                result = []
                for s in scores:
                    idx = s.get("index", 0) - 1
                    sc = float(s.get("score", 0))
                    if 0 <= idx < len(items) and sc >= min_score:
                        result.append({**items[idx], "score": sc})
                return sorted(result, key=lambda x: x["score"], reverse=True)
        except Exception as e:
            logger.error(f"Event scoring failed: {e}")
        return []

    def _format_message(self, events: list, location: str) -> str:
        lines = [f"🎭 Bu hafta {location}'da seçtiğim etkinlikler:"]
        for i, ev in enumerate(events, 1):
            score_pct = int(ev.get("score", 0) * 100)
            title = ev.get("title", "")[:60]
            source = ev.get("source", "")
            link = ev.get("link", "")
            line = f"{i}. {title} — {source} (%{score_pct} eşleşme)"
            if link:
                line += f"\n   {link}"
            lines.append(line)
        return "\n".join(lines)

    def should_notify_proactively(self, item: dict, profile: dict) -> bool:
        return item.get("score", 0) > 0.88
