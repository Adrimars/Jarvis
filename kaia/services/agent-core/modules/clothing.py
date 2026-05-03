import json
import logging
import os
import time
import uuid

import numpy as np
import redis

from core.profile import load_profile
from llm.client import ask_llm
from modules.base import BaseModule, ModuleResult

logger = logging.getLogger("module.clothing")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SCRAPER_TIMEOUT = 300  # seconds to wait for scraper results


class ClothingModule(BaseModule):
    name = "clothing"
    schedule = "every tuesday,friday 10:00"
    catchup = False

    def run(self, profile: dict) -> ModuleResult:
        if not profile:
            profile = load_profile()

        clothing = profile.get("clothing", {})
        ref_photos = clothing.get("reference_photos", [])
        budget = clothing.get("budget", {})
        budget_min = budget.get("min", 0)
        budget_max = budget.get("max", 2000)
        style = clothing.get("style", "casual")

        # Build reference embeddings from saved photos
        refs = self._load_reference_embeddings(ref_photos)
        use_visual = len(refs) > 0

        if not use_visual:
            logger.info("No reference photos — using style-based text search")

        # Dispatch scrape job to scraper service via Redis
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        job_id = str(uuid.uuid4())
        query = style if not use_visual else ""
        job = {
            "job_id": job_id,
            "query": query,
            "sites": [],  # empty = all known sites
            "max_items": 50,
        }
        r.rpush("queue:scraper:inbox", json.dumps(job))
        logger.info(f"Dispatched scraper job {job_id}")

        # Wait for results
        items = self._wait_for_results(r, job_id)
        if not items:
            return ModuleResult(success=False, message="Kıyafet taraması sonuç döndürmedi.")

        # Filter by budget
        items = [i for i in items if budget_min <= i.get("price", 0) <= budget_max]

        # Score items visually or by LLM
        if use_visual:
            scored = self._score_visual(items, refs)
        else:
            scored = self._score_llm(items, style, budget_min, budget_max)

        scored = sorted(scored, key=lambda x: x["score"], reverse=True)[:8]
        if not scored:
            return ModuleResult(success=False, message="Bütçe ve stile uygun ürün bulunamadı.")

        # Cache items for feedback later
        for item in scored:
            item_id = item.get("id", str(uuid.uuid4()))
            item["id"] = item_id
            r.setex(f"item:{item_id}", 3600 * 48, json.dumps(item))

        message = self._format_message(scored)
        buttons = self._build_buttons(scored)

        return ModuleResult(
            success=True,
            items=scored,
            message=message,
            proactive=True,
        )

    def _load_reference_embeddings(self, ref_photos: list) -> list:
        refs = []
        for photo in ref_photos:
            emb = photo.get("embedding")
            if emb:
                refs.append(np.array(emb, dtype=np.float32))
            elif photo.get("path"):
                try:
                    from vision.embedder import embed_image_file
                    vec = embed_image_file(photo["path"])
                    refs.append(vec)
                except Exception as e:
                    logger.warning(f"Could not embed reference photo {photo['path']}: {e}")
        return refs

    def _wait_for_results(self, r: redis.Redis, job_id: str) -> list:
        result_key = f"scraper:result:{job_id}"
        deadline = time.time() + SCRAPER_TIMEOUT
        while time.time() < deadline:
            raw = r.get(result_key)
            if raw:
                r.delete(result_key)
                return json.loads(raw)
            time.sleep(3)
        logger.warning(f"Scraper job {job_id} timed out after {SCRAPER_TIMEOUT}s")
        return []

    def _score_visual(self, items: list, refs: list) -> list:
        from vision.embedder import embed_image_url, mean_similarity
        scored = []
        for item in items:
            image_url = item.get("image_url", "")
            if not image_url:
                continue
            emb = embed_image_url(image_url)
            if emb is None:
                continue
            score = mean_similarity(emb, refs)
            if score > 0.70:
                scored.append({**item, "score": score})
        return scored

    def _score_llm(self, items: list, style: str, budget_min: float, budget_max: float) -> list:
        if not items:
            return []
        sample = items[:20]
        listing = "\n".join(
            f"{i+1}. {it.get('title','')} — {it.get('price',0):.0f} TL ({it.get('source','')})"
            for i, it in enumerate(sample)
        )
        prompt = (
            f"Kullanıcının stili: {style}. Bütçe: {budget_min:.0f}–{budget_max:.0f} TL.\n"
            f"Aşağıdaki kıyafetleri stiline uygunluğuna göre 0.0–1.0 arasında puanla.\n"
            f"Sadece JSON dizisi döndür: [{{\"index\": 1, \"score\": 0.85}}, ...]\n\n"
            f"{listing}"
        )
        try:
            raw = ask_llm(prompt, temperature=0.1)
            import re
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                scores = json.loads(match.group())
                scored = []
                for s in scores:
                    idx = s.get("index", 0) - 1
                    if 0 <= idx < len(sample):
                        scored.append({**sample[idx], "score": float(s.get("score", 0))})
                return scored
        except Exception as e:
            logger.error(f"LLM scoring failed: {e}")
        # Fallback: return all with neutral score
        return [{**it, "score": 0.5} for it in sample]

    def _format_message(self, items: list) -> str:
        lines = ["👕 Kıyafet önerileri:"]
        for i, item in enumerate(items, 1):
            score_pct = int(item.get("score", 0) * 100)
            price = item.get("price", 0)
            title = item.get("title", "")[:50]
            source = item.get("source", "")
            link = item.get("link", "")
            line = f"{i}. {title} — {price:.0f} TL, {source} (%{score_pct} eşleşme)"
            if link:
                line += f"\n   {link}"
            lines.append(line)
        return "\n".join(lines)

    def _build_buttons(self, items: list) -> list:
        buttons = []
        for item in items[:4]:
            item_id = item["id"]
            title = item.get("title", "")[:20]
            buttons.append([
                {"label": f"❤️ {title}", "data": f"feedback_like_{item_id}"},
                {"label": "👎", "data": f"feedback_dislike_{item_id}"},
            ])
        return buttons

    def on_feedback(self, item_id: str, feedback: str):
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        raw = r.get(f"item:{item_id}")
        if not raw:
            return
        item = json.loads(raw)
        source_url = item.get("link", "")

        from core.learning import LearningEngine
        from core.profile import load_profile
        profile = load_profile()
        LearningEngine().process_feedback(item_id, feedback, profile)

        if source_url and feedback in ("like", "dislike"):
            try:
                from scraper.registry import update_site_score
                delta = 0.1 if feedback == "like" else -0.1
                update_site_score(source_url, delta)
            except Exception:
                pass
