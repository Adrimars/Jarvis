import logging
from playwright.async_api import async_playwright
from .base import BaseScraper

logger = logging.getLogger("scraper.hm")


class HMScraper(BaseScraper):
    def __init__(self):
        super().__init__("https://www2.hm.com/tr_tr", rate_limit_rpm=6)

    async def search(self, query: str, max_items: int = 20) -> list[dict]:
        search_url = f"{self.base_url}/search-results.html?q={query}"

        if not await self._check_robots(search_url):
            logger.warning("robots.txt disallows scraping this URL")
            return []

        items = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await self._new_page(browser)

            try:
                logger.info(f"H&M search: '{query}'")
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(".product-item", timeout=15000)

                cards = await page.query_selector_all(".product-item")
                logger.info(f"Found {len(cards)} cards, taking up to {max_items}")

                for card in cards[:max_items]:
                    await self._wait()
                    try:
                        name_el  = await card.query_selector(".item-heading")
                        price_el = await card.query_selector(".item-price")
                        link_el  = await card.query_selector("a")
                        img_el   = await card.query_selector("img")

                        title     = (await name_el.inner_text()).strip()  if name_el  else ""
                        price_raw = (await price_el.inner_text()).strip() if price_el else "0"
                        href      = await link_el.get_attribute("href")   if link_el  else ""
                        image_url = await img_el.get_attribute("src")     if img_el   else ""

                        price = _parse_price(price_raw)

                        if title:
                            items.append({
                                "title":     title,
                                "price":     price,
                                "link":      href,
                                "image_url": image_url,
                                "source":    "hm",
                            })
                    except Exception as e:
                        logger.debug(f"Card parse error: {e}")
                        continue

            except Exception as e:
                logger.error(f"H&M scrape failed: {e}")
            finally:
                await browser.close()

        logger.info(f"H&M returned {len(items)} items")
        return items


def _parse_price(raw: str) -> float:
    cleaned = raw.replace("TL", "").replace("₺", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
