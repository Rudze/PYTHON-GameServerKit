"""The logger of the project: `from common.log import log`, then log.info / log.warning / log.error.
The level comes from LOG_LEVEL (DEBUG, INFO, WARNING, ERROR; INFO by default)."""
import logging
import os

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger("game")
