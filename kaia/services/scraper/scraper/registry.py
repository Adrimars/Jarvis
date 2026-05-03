"""
Site registry — maps domains to scrapers and tracks performance.
Add any new site by calling register() or via Telegram /addsite command.
"""
import json
import logging
import os
from urllib.parse import urlparse

import redis

from .generic import GenericScraper

logger = logging.getLogger("scraper.registry")

r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)

# Built-in known sites — scrapers imported lazily to avoid circular deps
KNOWN_SITES: dict[str, dict] = {
    "trendyol.com":  {"module": "scraper.trendyol",  "class": "TrendyolScraper"},
    "zara.com":      {"module": "scraper.zara",       "class": "ZaraScraper"},
    "hm.com":        {"module": "scraper.hm",         "class": "HMScraper"},
    "defacto.com.tr":{"module": "scraper.defacto",    "class": "DefactoScraper"},
    "koton.com":     {"module": "scraper.koton",      "class": "KotonScraper"},
    "bershka.com":   {"module": "scraper.bershka",    "class": "BershkaScraper"},
}


def _domain(url: str) -> str:
    netloc = urlparse(url).netloc.replace("www.", "")
    return netloc or url


def get_scraper(url: str):
    """Return the best available scraper for a given URL."""
    domain = _domain(url)

    # Check built-in registry
    for known_domain, info in KNOWN_SITES.items():
        if known_domain in domain:
            try:
                mod = __import__(info["module"], fromlist=[info["class"]])
                cls = getattr(mod, info["class"])
                return cls()
            except Exception as e:
                logger.warning(f"Failed to load {info['class']}, falling back to generic: {e}")
                break

    # Check user-added sites in Redis
    stored = r.hget("site_registry", domain)
    if stored:
        data = json.loads(stored)
        base_url = data.get("base_url", f"https://{domain}")
        rpm = data.get("rate_limit_rpm", 6)
        logger.info(f"Using GenericScraper for registered site: {domain}")
        return GenericScraper(base_url, rpm)

    # Fallback: generic for completely unknown site
    logger.info(f"No specific scraper for {domain}, using GenericScraper")
    base_url = f"https://{domain}"
    return GenericScraper(base_url, rate_limit_rpm=6)


def register_site(url: str, rate_limit_rpm: int = 6, note: str = "") -> bool:
    """Register a new site so it gets included in clothing scans."""
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


def update_site_score(url: str, delta: float):
    """Adjust a site's score based on feedback (likes/dislikes on its results)."""
    domain = _domain(url)
    stored = r.hget("site_registry", domain)
    if stored:
        data = json.loads(stored)
        data["score"] = max(0.1, min(2.0, data.get("score", 1.0) + delta))
        r.hset("site_registry", domain, json.dumps(data))


def list_sites() -> list[dict]:
    """All registered user-added sites."""
    result = []
    for domain, raw in r.hgetall("site_registry").items():
        data = json.loads(raw)
        result.append({"domain": domain, **data})
    return sorted(result, key=lambda x: x.get("score", 1.0), reverse=True)


def get_all_search_sites() -> list:
    """Return scrapers for all active sites (built-in + registered)."""
    scrapers = []
    # Built-in
    for domain, info in KNOWN_SITES.items():
        try:
            mod = __import__(info["module"], fromlist=[info["class"]])
            cls = getattr(mod, info["class"])
            scrapers.append(cls())
        except Exception:
            pass
    # User-registered
    for domain, raw in r.hgetall("site_registry").items():
        data = json.loads(raw)
        scrapers.append(GenericScraper(data["base_url"], data.get("rate_limit_rpm", 6)))
    return scrapers
