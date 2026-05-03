"""
Agent-core side of the site registry.
Only handles Redis reads/writes — no Playwright here.
The actual scraping happens in the scraper service.
"""
import json
import logging
import os
from urllib.parse import urlparse

import redis

logger = logging.getLogger("scraper.registry")
r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)


def _domain(url: str) -> str:
    netloc = urlparse(url).netloc.replace("www.", "")
    return netloc or url


def register_site(url: str, rate_limit_rpm: int = 6, note: str = "") -> bool:
    domain = _domain(url)
    data = {
        "base_url": f"https://{domain}",
        "rate_limit_rpm": rate_limit_rpm,
        "note": note,
        "score": 1.0,
    }
    r.hset("site_registry", domain, json.dumps(data))
    logger.info(f"Registered site: {domain}")
    return True


def list_sites() -> list[dict]:
    result = []
    for domain, raw in r.hgetall("site_registry").items():
        data = json.loads(raw)
        result.append({"domain": domain, **data})
    return sorted(result, key=lambda x: x.get("score", 1.0), reverse=True)


def update_site_score(url: str, delta: float):
    domain = _domain(url)
    stored = r.hget("site_registry", domain)
    if stored:
        data = json.loads(stored)
        data["score"] = max(0.1, min(2.0, data.get("score", 1.0) + delta))
        r.hset("site_registry", domain, json.dumps(data))
