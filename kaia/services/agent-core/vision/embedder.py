import logging
from functools import lru_cache
from pathlib import Path

import httpx
import numpy as np

logger = logging.getLogger("vision.embedder")

_MODEL_NAME = "clip-ViT-B-32"
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading CLIP model {_MODEL_NAME} (first load may take a moment)...")
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info("CLIP model loaded.")
    return _model


def embed_image_file(path: str) -> np.ndarray:
    from PIL import Image
    model = _get_model()
    img = Image.open(path).convert("RGB")
    return model.encode(img)


def embed_image_url(url: str) -> np.ndarray | None:
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        return _get_model().encode(img)
    except Exception as e:
        logger.debug(f"embed_image_url failed for {url}: {e}")
        return None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def mean_similarity(embedding: np.ndarray, references: list[np.ndarray]) -> float:
    if not references:
        return 0.0
    return float(np.mean([cosine_similarity(embedding, r) for r in references]))
