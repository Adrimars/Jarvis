import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [telegram-bot] %(message)s")
logger = logging.getLogger("telegram-bot")

logger.info("Telegram Bot starting up...")

while True:
    logger.info("Telegram Bot alive")
    time.sleep(60)
