import os
import redis

r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)

INSTRUCTIONS = {
    "casual":       "Speak casually and in a friendly way. Can be informal.",
    "serious":      "Be serious and professional. Not cold.",
    "professional": "Use formal language. Be brief and precise.",
}

TONE_KEYWORDS = {
    "serious":      ["serious", "professional", "formal"],
    "professional": ["professional", "formal", "strict"],
    "casual":       ["casual", "relax", "chill", "normal", "default", "friendly"],
}


class ToneManager:
    def __init__(self, user_id: str):
        self.key = f"tone:{user_id}"

    def get(self) -> str:
        return r.hget(self.key, "current") or "casual"

    def set(self, tone: str):
        if tone in INSTRUCTIONS:
            r.hset(self.key, mapping={"current": tone})

    def instruction(self) -> str:
        return INSTRUCTIONS.get(self.get(), INSTRUCTIONS["casual"])


def extract_tone_from_message(message: str) -> str:
    msg_lower = message.lower()
    for tone, keywords in TONE_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            return tone
    return "casual"
