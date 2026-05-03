"""
Universal scraper — works on any e-commerce site.
Strategy (in order):
  1. JSON-LD structured data (Product schema)
  2. Open Graph meta tags
  3. Common CSS selector heuristics
  4. LLM-based extraction (last resort)
"""
import json
import logging
import re
from urllib.parse import urljoin

import httpx
from playwright.async_api import async_playwright

from .base import BaseScraper

logger = logging.getLogger("scraper.generic")

# Selector patterns tried in order — covers most e-commerce frameworks
PRODUCT_CARD_SELECTORS = [
    "[data-testid*='product']",
    "[class*='product-card']",
    "[class*='productCard']",
    "[class*='product-item']",
    "[class*='productItem']",
    "[class*='product_card']",
    "[class*='item-card']",
    "[class*='card-product']",
    "article[class*='product']",
    "li[class*='product']",
    "div[class*='product']",
]

PRICE_SELECTORS = [
    "[class*='price']",
    "[class*='Price']",
    "[itemprop='price']",
    "[data-price]",
    "span[class*='amount']",
    "span[class*='cost']",
]

TITLE_SELECTORS = [
    "[class*='product-name']",
    "[class*='productName']",
    "[class*='product-title']",
    "[class*='item-title']",
    "[itemprop='name']",
    "h2", "h3",
]


class GenericScraper(BaseScraper):
    def __init__(self, base_url: str, rate_limit_rpm: int = 8):
        super().__init__(base_url, rate_limit_rpm)

    async def search(self, query: str, max_items: int = 20) -> list[dict]:
        search_url = self._build_search_url(query)
        if not await self._check_robots(search_url):
            logger.warning(f"robots.txt disallows: {search_url}")
            return []

        items = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await self._new_page(browser)
            try:
                logger.info(f"Generic scrape: {search_url}")
                await page.goto(search_url, wait_until="networkidle", timeout=30000)

                # Try JSON-LD first (fastest, most reliable)
                items = await self._extract_jsonld(page, search_url)
                if items:
                    logger.info(f"JSON-LD extracted {len(items)} products")
                    await browser.close()
                    return items[:max_items]

                # Try CSS heuristics
                items = await self._extract_css(page, search_url, max_items)
                if items:
                    logger.info(f"CSS heuristics extracted {len(items)} products")
                    await browser.close()
                    return items[:max_items]

                # LLM fallback
                items = await self._extract_llm(page, search_url, max_items)
                logger.info(f"LLM extracted {len(items)} products")

            except Exception as e:
                logger.error(f"Generic scrape failed for {self.base_url}: {e}")
            finally:
                await browser.close()

        return items[:max_items]

    def _build_search_url(self, query: str) -> str:
        encoded = query.replace(" ", "+")
        # Common search URL patterns — override in subclasses for known sites
        for pattern in ["/search?q=", "/ara?q=", "/search?query=", "/sr?q="]:
            return f"{self.base_url}{pattern}{encoded}"
        return f"{self.base_url}/search?q={encoded}"

    async def _extract_jsonld(self, page, base_url: str) -> list[dict]:
        scripts = await page.query_selector_all("script[type='application/ld+json']")
        items = []
        for script in scripts:
            try:
                content = await script.inner_text()
                data = json.loads(content)
                products = []
                if isinstance(data, list):
                    products = [d for d in data if d.get("@type") in ("Product", "ItemList")]
                elif data.get("@type") == "Product":
                    products = [data]
                elif data.get("@type") == "ItemList":
                    products = data.get("itemListElement", [])

                for p in products:
                    item = p.get("item", p)
                    offer = item.get("offers", {})
                    if isinstance(offer, list):
                        offer = offer[0] if offer else {}
                    price = offer.get("price", 0)
                    items.append({
                        "title": item.get("name", ""),
                        "price": float(price) if price else 0.0,
                        "link": item.get("url", base_url),
                        "image_url": item.get("image", ""),
                        "source": self._domain(),
                    })
            except Exception:
                continue
        return [i for i in items if i["title"]]

    async def _extract_css(self, page, base_url: str, max_items: int) -> list[dict]:
        for selector in PRODUCT_CARD_SELECTORS:
            try:
                cards = await page.query_selector_all(selector)
                if len(cards) < 3:
                    continue

                items = []
                for card in cards[:max_items]:
                    await self._wait()
                    title = await self._first_text(card, TITLE_SELECTORS)
                    price = await self._first_text(card, PRICE_SELECTORS)
                    link_el = await card.query_selector("a")
                    img_el = await card.query_selector("img")

                    href = await link_el.get_attribute("href") if link_el else ""
                    if href and not href.startswith("http"):
                        href = urljoin(base_url, href)

                    image_url = ""
                    if img_el:
                        image_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src") or ""

                    if title:
                        items.append({
                            "title": title.strip(),
                            "price": _parse_price(price),
                            "link": href,
                            "image_url": image_url,
                            "source": self._domain(),
                        })

                if items:
                    return items
            except Exception:
                continue
        return []

    async def _extract_llm(self, page, base_url: str, max_items: int) -> list[dict]:
        try:
            # Grab visible text, truncated for context window
            body_text = await page.inner_text("body")
            body_text = body_text[:4000]

            from llm.client import ask_llm
            prompt = f"""
Extract product listings from this e-commerce page text.
Return a JSON array with objects: {{"title": "", "price": 0.0, "link": ""}}
Maximum {max_items} products. Only return the JSON array, nothing else.

Page URL: {base_url}
Page text:
{body_text}
"""
            result = ask_llm(prompt, temperature=0.1)
            # Find JSON array in response
            match = re.search(r'\[.*\]', result, re.DOTALL)
            if match:
                raw = json.loads(match.group())
                return [
                    {**item, "source": self._domain(), "image_url": ""}
                    for item in raw if isinstance(item, dict) and item.get("title")
                ]
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
        return []

    async def _first_text(self, parent, selectors: list) -> str:
        for sel in selectors:
            try:
                el = await parent.query_selector(sel)
                if el:
                    text = await el.inner_text()
                    if text.strip():
                        return text.strip()
            except Exception:
                continue
        return ""

    def _domain(self) -> str:
        from urllib.parse import urlparse
        return urlparse(self.base_url).netloc.replace("www.", "")


def _parse_price(raw: str) -> float:
    if not raw:
        return 0.0
    cleaned = re.sub(r"[^\d,.]", "", raw).replace(",", ".")
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
