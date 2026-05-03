# modules/food.py
# On-demand module (disabled by default, enable with /module food on).
# Handles multi-turn recipe conversations: extracts ingredients from chat,
# suggests 3 recipes personalised to the user's favorites/dislikes/dietary needs,
# and refines based on follow-up messages ("make it light", "suggest another").
# Every like/dislike nudges the per-recipe preference scores in the profile.

import json
import logging
import os

import redis

from core.profile import load_profile, save_profile
from llm.client import ask_llm
from modules.base import BaseModule, ModuleResult

logger = logging.getLogger("module.food")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STATE_TTL = 3600  # conversation state lives 1 hour


def _r():
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def get_state(user_id: str) -> dict:
    raw = _r().get(f"food_state:{user_id}")
    return json.loads(raw) if raw else {}


def set_state(user_id: str, state: dict):
    _r().setex(f"food_state:{user_id}", STATE_TTL, json.dumps(state))


def clear_state(user_id: str):
    _r().delete(f"food_state:{user_id}")


def handle_food_conversation(user_id: str, message: str) -> str:
    """Multi-turn food conversation handler. Called from conversation_loop."""
    profile = load_profile()
    food_prefs = profile.get("food", {})
    state = get_state(user_id)

    # First message — ask for ingredients if not given
    if not state:
        # Check if ingredients are already in the message
        ingredients = _extract_ingredients(message)
        if ingredients:
            state = {"step": "suggest", "ingredients": ingredients, "modifiers": []}
            set_state(user_id, state)
            return _suggest_recipes(ingredients, [], food_prefs)
        else:
            set_state(user_id, {"step": "waiting_ingredients"})
            return "What do you have at home? Tell me the ingredients and I'll suggest a recipe."

    step = state.get("step")

    if step == "waiting_ingredients":
        ingredients = _extract_ingredients(message)
        if not ingredients:
            return "What ingredients do you have? (e.g. tomatoes, eggs, cheese)"
        state = {"step": "suggest", "ingredients": ingredients, "modifiers": []}
        set_state(user_id, state)
        return _suggest_recipes(ingredients, [], food_prefs)

    if step == "suggest":
        # User might be refining (e.g. "make it light", "suggest another")
        lower = message.lower()
        if any(w in lower for w in ["another", "different", "change", "no", "else", "other", "not that"]):
            modifiers = state.get("modifiers", [])
            return _suggest_recipes(state["ingredients"], modifiers, food_prefs, exclude=state.get("last_suggestions", []))
        else:
            # Treat as a modifier (e.g. "hafif olsun", "vejeteryan")
            modifiers = state.get("modifiers", []) + [message]
            state["modifiers"] = modifiers
            set_state(user_id, state)
            return _suggest_recipes(state["ingredients"], modifiers, food_prefs)

    clear_state(user_id)
    return "Want to try something else?"


def record_food_feedback(user_id: str, recipe_name: str, feedback: str):
    """Update food preference scores based on like/dislike."""
    profile = load_profile()
    scores = profile.setdefault("food", {}).setdefault("preference_scores", {})
    current = scores.get(recipe_name, 0.5)
    delta = 0.1 if feedback == "like" else -0.08
    scores[recipe_name] = round(max(0.0, min(1.0, current + delta)), 3)

    if feedback == "like" and recipe_name not in profile["food"].get("favorites", []):
        profile["food"].setdefault("favorites", []).append(recipe_name)
    elif feedback == "dislike" and recipe_name not in profile["food"].get("dislikes", []):
        profile["food"].setdefault("dislikes", []).append(recipe_name)

    save_profile(profile)


def _extract_ingredients(message: str) -> list[str]:
    """Use LLM to pull ingredient list from natural-language message."""
    result = ask_llm(
        f"Extract a list of ingredients from this message. Return only a JSON array, nothing else.\n"
        f"Example: [\"tomatoes\", \"eggs\", \"cheese\"]\n"
        f"If there are no ingredients, return an empty array: []\n\nMessage: {message}",
        temperature=0.1,
    )
    try:
        import re
        match = re.search(r'\[.*\]', result, re.DOTALL)
        if match:
            items = json.loads(match.group())
            return [str(i) for i in items if i]
    except Exception:
        pass
    return []


def _suggest_recipes(ingredients: list, modifiers: list, food_prefs: dict, exclude: list = None) -> str:
    favorites = food_prefs.get("favorites", [])
    dislikes = food_prefs.get("dislikes", [])
    cuisines = food_prefs.get("cuisines", [])
    dietary = food_prefs.get("dietary", [])
    scores = food_prefs.get("preference_scores", {})

    # Top liked recipes as context
    liked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    liked_str = ", ".join(r for r, _ in liked[:5]) if liked else ""

    prefs_block = ""
    if favorites:
        prefs_block += f"Favorites: {', '.join(favorites[:8])}. "
    if dislikes:
        prefs_block += f"Dislikes: {', '.join(dislikes[:8])}. "
    if cuisines:
        prefs_block += f"Preferred cuisines: {', '.join(cuisines)}. "
    if dietary:
        prefs_block += f"Dietary restrictions: {', '.join(dietary)}. "
    if liked_str:
        prefs_block += f"Top rated recipes: {liked_str}. "

    modifier_str = f"Extra requests: {', '.join(modifiers)}. " if modifiers else ""
    exclude_str = f"Do not suggest these: {', '.join(exclude)}. " if exclude else ""

    prompt = (
        f"Ingredients: {', '.join(ingredients)}.\n"
        f"{prefs_block}"
        f"{modifier_str}"
        f"{exclude_str}"
        f"Suggest 3 recipes that can be made with these ingredients. "
        f"For each: name, 1-sentence description, time (minutes). "
        f"Respect the user's preferences and restrictions. "
        f"Reply in English. Be concise."
    )

    return ask_llm(prompt, temperature=0.7)


class FoodModule(BaseModule):
    name = "food"
    schedule = ""  # on-demand only
    catchup = False

    @property
    def enabled(self) -> bool:
        profile = load_profile()
        return profile.get("modules", {}).get("food", False)

    def run(self, profile: dict) -> ModuleResult:
        return ModuleResult(success=True, message="Food module works through conversation.")
