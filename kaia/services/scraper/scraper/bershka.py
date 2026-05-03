import logging
from playwright.async_api import async_playwright
from .base import BaseScraper
from .generic import _parse_price

logger = logging.getLogger("scraper.bershka")


class BershkaScraper(BaseScraper):
    def __init__(self):
        super().__init__("https://www.bershka.com/tr", rate_limit_rpm=6)

    async def search(self, query: str, max_items: int = 20) -> list[dict]:
        search_url = f"{self.base_url}/tr/search?term={query}"
        if not await self._check_robots(search_url):
            return []

        items = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await self._new_page(browser)
            try:
                logger.info(f"Bershka search: '{query}'")
                await page.goto(search_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_selector(".grid-item, [class*='product']", timeout=15000)

                cards = await page.query_selector_all(".grid-item, [class*='product-card']")
                for card in cards[:max_items]:
                    await self._wait()
                    try:
                        name_el  = await card.query_selector("[class*='name'], [class*='title'], h3")
                        price_el = await card.query_selector("[class*='price']")
                        link_el  = await card.query_selector("a")
                        img_el   = await card.query_selector("img")

                        title     = (await name_el.inner_text()).strip()  if name_el  else ""
                        price_raw = (await price_el.inner_text()).strip() if price_el else "0"
                        href      = await link_el.get_attribute("href")   if link_el  else ""
                        image_url = await img_el.get_attribute("src")     if img_el   else ""

                        if href and not href.startswith("http"):
                            href = f"https://www.bershka.com{href}"

                        if title:
                            items.append({"title": title, "price": _parse_price(price_raw),
                                          "link": href, "image_url": image_url, "source": "bershka"})
                    except Exception as e:
                        logger.debug(f"Card error: {e}")
            except Exception as e:
                logger.error(f"Bershka failed: {e}")
            finally:
                await browser.close()

        logger.info(f"Bershka returned {len(items)} items")
        return items
