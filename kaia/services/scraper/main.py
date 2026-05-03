import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [scraper] %(message)s")
logger = logging.getLogger("scraper")

logger.info("Scraper starting up...")

while True:
    logger.info("Scraper alive")
    time.sleep(60)
