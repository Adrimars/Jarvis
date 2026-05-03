import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [agent-core] %(message)s")
logger = logging.getLogger("agent-core")

logger.info("Agent Core starting up...")

while True:
    logger.info("Agent Core alive")
    time.sleep(60)
