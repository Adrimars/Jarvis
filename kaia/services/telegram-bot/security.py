import logging
import os

logger = logging.getLogger("telegram-bot.security")

ALLOWED_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))


def is_allowed(update) -> bool:
    chat_id = update.effective_chat.id
    if chat_id == ALLOWED_CHAT_ID:
        return True
    logger.warning(f"Rejected message from unknown chat ID: {chat_id}")
    return False
