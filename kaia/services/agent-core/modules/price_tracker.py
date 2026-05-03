import json
import logging
import os
import re

import httpx
import redis

from core.profile import load_profile, save_profile
from modules.base import BaseModule, ModuleResult

logger = logging.getLogger("module.price_tracker")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


class PriceTrackerModule(BaseModule):
    name = "price_tracker"
    schedule = "every day 12:00"
    catchup = True  # Check immediately on startup

    def run(self, profile: dict) -> ModuleResult:
        if not profile:
            profile = load_profile()

        products = profile.get("price_tracker", {}).get("products", [])
        if not products:
            return ModuleResult(success=True, message="")

        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        hits = []
        changed = False

        for product in products:
            link = product.get("link", "")
            target = float(product.get("target_price", 0))
            name = product.get("name", link)

            if not link:
                continue

            current = self._fetch_price(link)
            if current is None:
                logger.warning(f"Could not fetch price for {name}")
                continue

            old = float(product.get("current_price", 0))
            product["current_price"] = current
            changed = True

            if target > 0 and current <= target:
                hits.append({
                    "name": name,
                    "old": old,
                    "new": current,
                    "link": link,
                    "drop": round(old - current, 2) if old > 0 else 0,
                })
                logger.info(f"Price alert: {name} dropped to {current} TL (target {target} TL)")

        if changed:
            save_profile(profile)

        if not hits:
            return ModuleResult(success=True, message="")

        message = self._format_message(hits)
        r.rpush("queue:telegram:outbox", json.dumps({"text": message}))
        return ModuleResult(success=True, items=hits, message=message, proactive=True)

    def _fetch_price(self, url: str) -> float | None:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "tr-TR,tr;q=0.9",
            }
            resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
            resp.raise_for_status()

            # Try JSON-LD first
            matches = re.findall(
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                resp.text, re.DOTALL
            )
            for m in matches:
                try:
                    data = json.loads(m)
                    if isinstance(data, list):
                        data = data[0]
                    if data.get("@type") == "Product":
                        offers = data.get("offers", {})
                        if isinstance(offers, list):
                            offers = offers[0]
                        price = offers.get("price")
                        if price:
                            return float(str(price).replace(",", "."))
                except Exception:
                    continue

            # Fallback: heuristic regex for common price patterns
            patterns = [
                r'"price"\s*:\s*"?([\d.,]+)"?',
                r'data-price="([\d.,]+)"',
                r'class="[^"]*price[^"]*"[^>]*>([\d.,]+)',
            ]
            for pat in patterns:
                m = re.search(pat, resp.text)
                if m:
                    raw = m.group(1).replace(".", "").replace(",", ".")
                    return float(raw)

        except Exception as e:
            logger.debug(f"Price fetch error for {url}: {e}")
        return None

    def _format_message(self, hits: list) -> str:
        lines = ["💰 Fiyat alarmı!"]
        for h in hits:
            name = h["name"]
            old = h["old"]
            new = h["new"]
            link = h["link"]
            if old > 0:
                lines.append(f"📉 {name}: {old:.0f} TL → {new:.0f} TL (-{h['drop']:.0f} TL)\n   {link}")
            else:
                lines.append(f"✅ {name}: {new:.0f} TL (hedef fiyata ulaştı!)\n   {link}")
        return "\n".join(lines)
