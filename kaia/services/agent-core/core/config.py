import os
from pathlib import Path
import yaml

_CONFIG_PATHS = [
    Path("/data/kaia/kaia.config.yaml"),        # mounted in container
    Path("/app/kaia.config.yaml"),              # copied into image fallback
]


def _load() -> dict:
    for path in _CONFIG_PATHS:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}


_cfg = _load()


def get(key: str, default=None):
    """Dot-notation access: get('schedules.news') → '08:00'"""
    parts = key.split(".")
    node = _cfg
    for p in parts:
        if not isinstance(node, dict):
            return default
        node = node.get(p)
        if node is None:
            return default
    return node


def character_name() -> str:
    return get("character.name", "KAIA")


def character_personality() -> str:
    return get("character.personality", "")


def character_tone() -> str:
    return get("character.tone", "casual")


def schedule(module: str) -> str:
    return get(f"schedules.{module}", "")


def module_enabled(module: str) -> bool:
    return bool(get(f"modules.{module}", True))


def timezone() -> str:
    return get("timezone", "Europe/Istanbul")
