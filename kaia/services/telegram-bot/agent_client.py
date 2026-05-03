"""
Thin client — forwards messages to Agent Core via Redis queue
and reads responses back.
"""
import json
import os
import uuid
import redis

r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)

INBOX  = "queue:agent:inbox"
OUTBOX = "queue:agent:outbox:{user_id}"


def send_message(user_id: str, text: str) -> str:
    """Push message to agent inbox, block until response (max 90s)."""
    request_id = str(uuid.uuid4())
    payload = json.dumps({"request_id": request_id, "user_id": user_id, "text": text})
    r.rpush(INBOX, payload)

    response_key = f"response:{request_id}"
    result = r.blpop(response_key, timeout=90)
    if result:
        return json.loads(result[1])["text"]
    return "Sorry, I didn't get a response in time."
