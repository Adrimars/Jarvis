import asyncio
import json
import logging
import os

import redis

from scraper.registry import get_all_search_sites, get_scraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [scraper] %(message)s")
logger = logging.getLogger("scraper")

# File logging — 30-day rotation
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
_log_dir = Path(os.getenv("KAIA_DATA_DIR", "/data/kaia")) / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
_fh = TimedRotatingFileHandler(_log_dir / "scraper.log", when="midnight", backupCount=30, encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s"))
logging.getLogger().addHandler(_fh)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

INBOX = "queue:scraper:inbox"


async def process_job(job: dict):
    job_id = job.get("job_id", "")
    query = job.get("query", "")
    sites = job.get("sites", [])  # list of base URLs; empty = all known sites
    max_items = job.get("max_items", 20)

    logger.info(f"Job {job_id}: query='{query}' sites={sites or 'all'}")

    scrapers = []
    if sites:
        for url in sites:
            scrapers.append(get_scraper(url))
    else:
        scrapers = get_all_search_sites()

    all_items = []
    for scraper in scrapers:
        try:
            items = await scraper.search(query, max_items=max_items)
            all_items.extend(items)
            logger.info(f"  {scraper.base_url}: {len(items)} items")
        except Exception as e:
            logger.error(f"  {scraper.base_url} failed: {e}")

    result_key = f"scraper:result:{job_id}"
    r.setex(result_key, 3600, json.dumps(all_items))
    logger.info(f"Job {job_id} done: {len(all_items)} total items → {result_key}")


async def main():
    logger.info("Scraper service ready — listening on queue:scraper:inbox")
    loop = asyncio.get_event_loop()

    while True:
        try:
            raw = await loop.run_in_executor(None, lambda: r.blpop(INBOX, timeout=5))
            if not raw:
                continue
            job = json.loads(raw[1])
            asyncio.create_task(process_job(job))
        except Exception as e:
            logger.error(f"Scraper loop error: {e}")
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
