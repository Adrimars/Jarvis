import json
import os
import redis
from datetime import datetime

r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)


class ConversationMemory:
    def __init__(self, user_id: str, window_days: int = 3):
        self.key = f"conversation:{user_id}"
        self.ttl = window_days * 86400

    def add(self, role: str, content: str):
        msg = {"role": role, "content": content, "ts": datetime.now().isoformat()}
        r.rpush(self.key, json.dumps(msg))
        r.expire(self.key, self.ttl)

    def get_recent(self, last_n: int = 20) -> list:
        all_msgs = r.lrange(self.key, 0, -1)
        return [json.loads(m) for m in all_msgs[-last_n:]]

    def get_summary(self) -> str:
        from llm.client import ask_llm
        old = r.lrange(self.key, 0, -21)
        if not old:
            return ""
        text = "\n".join(json.loads(m)["content"] for m in old)
        return ask_llm(
            f"Summarize this conversation in 3 sentences:\n{text}",
            temperature=0.3,
        )

    def clear(self):
        r.delete(self.key)
