import asyncio
import logging
import random
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext

logger = logging.getLogger("scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]


class BaseScraper:
    def __init__(self, base_url: str, rate_limit_rpm: int = 10):
        self.base_url = base_url
        self.delay_min = 60 / rate_limit_rpm
        self.delay_max = self.delay_min * 2
        self._robots: RobotFileParser | None = None

    async def _wait(self):
        delay = random.uniform(self.delay_min, self.delay_max)
        logger.debug(f"Rate limit wait: {delay:.1f}s")
        await asyncio.sleep(delay)

    async def _check_robots(self, url: str) -> bool:
        if self._robots is None:
            parsed = urlparse(self.base_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(robots_url)
                    self._robots = RobotFileParser()
                    self._robots.parse(resp.text.splitlines())
            except Exception:
                return True  # If robots.txt unreachable, proceed
        return self._robots.can_fetch("*", url)

    async def _new_page(self, browser: Browser):
        context: BrowserContext = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800},
        )
        return await context.new_page()

    async def scrape(self, url: str) -> dict:
        raise NotImplementedError
