import asyncio
import json
import logging
import os

import redis

from core.profile import profile_exists, load_profile, save_profile, parse_profile, get_template_yaml
from core.conversation_loop import handle_message
from core.catchup import CatchUpService
from core.module_loader import load_all_modules
from scraper.registry import register_site, list_sites

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [agent-core] %(message)s",
)
logger = logging.getLogger("agent-core")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

INBOX = "queue:agent:inbox"
OUTBOX_TELEGRAM = "queue:telegram:outbox"


def push_to_telegram(text: str, buttons: list = None):
    payload = {"text": text}
    if buttons:
        payload["buttons"] = buttons
    r.rpush(OUTBOX_TELEGRAM, json.dumps(payload))


async def dispatch(user_id: str, text: str) -> str:
    """Route special internal commands, then hand off to conversation loop."""

    if text == "__start__":
        if not profile_exists():
            template = get_template_yaml()
            r.set("pending_onboarding", "1")
            push_to_telegram(
                "Hello! Fill out this template and send it back so I can get to know you.",
                buttons=None,
            )
            # Signal bot to send the YAML as a file (handled separately)
            r.set("send_profile_template", template)
            return "Sending profile template..."
        return "Hey, I'm already set up! What's up?"

    if text.startswith("__yaml__:"):
        yaml_text = text[len("__yaml__:"):]
        try:
            profile = parse_profile(yaml_text)
            save_profile(profile)
            return "Profile saved! I'm ready now. Say hello 👋"
        except Exception as e:
            return f"Couldn't parse the profile: {e}"

    if text.startswith("__addsite__:"):
        url = text[len("__addsite__:"):]
        register_site(url)
        return f"Site registered: {url}\nI'll include it in clothing scans."

    if text == "__listsites__":
        sites = list_sites()
        if not sites:
            return "No custom sites registered yet. Use /addsite <url> to add one."
        lines = [f"• {s['domain']} (score: {s.get('score', 1.0):.1f})" for s in sites]
        return "Registered sites:\n" + "\n".join(lines)

    if text.startswith("__module__:"):
        _, name, state = text.split(":")
        profile = load_profile()
        profile.setdefault("modules", {})[name] = (state == "on")
        save_profile(profile)
        return f"Module '{name}' {'enabled' if state == 'on' else 'disabled'}."

    if text.startswith("__feedback__:"):
        _, sentiment, item_id = text.split(":", 2)
        from core.learning import LearningEngine
        LearningEngine().process_feedback(item_id, sentiment, load_profile())
        return ""

    if text.startswith("__approved__:"):
        action_id = text[len("__approved__:"):]
        logger.info(f"Action approved: {action_id}")
        return "Action confirmed."

    if text.startswith("__photo__:"):
        path = text[len("__photo__:"):]
        return await _handle_photo(user_id, path)

    # Normal conversation
    return await handle_message(user_id, text)


async def _handle_photo(user_id: str, path: str) -> str:
    profile = load_profile()
    photos = profile.setdefault("clothing", {}).setdefault("reference_photos", [])
    photos.append({"path": path, "embedding": None})
    save_profile(profile)
    count = len(photos)
    return f"Reference photo added ({count}/5). {'Ready for Friday scan!' if count >= 5 else 'Send more if you want.'}"


async def message_loop():
    logger.info("Agent Core ready — listening for messages")

    # Run catch-up on startup
    try:
        modules = load_all_modules()
        CatchUpService().run(modules)
    except Exception as e:
        logger.error(f"Catch-up error: {e}")

    while True:
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: r.blpop(INBOX, timeout=5)
        )
        if not result:
            continue

        try:
            msg = json.loads(result[1])
            user_id    = msg["user_id"]
            request_id = msg["request_id"]
            text       = msg["text"]

            logger.info(f"← {user_id}: {text[:80]}")
            response = await dispatch(user_id, text)
            logger.info(f"→ {user_id}: {response[:80]}")

            r.setex(f"response:{request_id}", 120, json.dumps({"text": response}))
        except Exception as e:
            logger.error(f"Dispatch error: {e}")


if __name__ == "__main__":
    asyncio.run(message_loop())
