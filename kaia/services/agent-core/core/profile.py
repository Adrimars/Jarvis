import os
import yaml
from pathlib import Path

PROFILE_PATH = Path(os.getenv("KAIA_DATA_DIR", "/data/kaia")) / "user_profile.yaml"

PROFILE_TEMPLATE = {
    "location": "Izmir",
    "clothing": {
        "style": "",
        "budget": {"min": 0, "max": 0},
        "reference_photos": [],
    },
    "interests": [],
    "reading": {
        "morning": "short_news",
        "evening": "deep_article",
        "max_minutes": 20,
    },
    "events": {
        "categories": ["theater", "cinema", "concert"],
        "min_interest_score": 0.75,
    },
    "price_tracker": {"products": []},
    "modules": {"food": False},
}


def profile_exists() -> bool:
    return PROFILE_PATH.exists()


def load_profile() -> dict:
    if not profile_exists():
        return dict(PROFILE_TEMPLATE)
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or dict(PROFILE_TEMPLATE)


def save_profile(profile: dict):
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)


def parse_profile(yaml_text: str) -> dict:
    data = yaml.safe_load(yaml_text)
    if not isinstance(data, dict):
        raise ValueError("Invalid profile format")
    return data


def get_template_yaml() -> str:
    return yaml.dump(PROFILE_TEMPLATE, allow_unicode=True, default_flow_style=False)
