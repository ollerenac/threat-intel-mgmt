"""
main.py — Entry point for feed-orchestrator service.

Startup sequence (D-06):
  1. Build Redis and pycti clients
  2. Instantiate all 5 feed objects
  3. Run all feeds immediately (synchronously, before scheduler starts)
  4. Build and start the APScheduler background scheduler
  5. Block the main thread (signal.pause or threading.Event)
"""
import logging
import signal
import threading

from redis import from_url as redis_from_url

from config import REDIS_URL
from feeds.feodo import FeodoFeed
from feeds.malwarebazaar import MalwareBazaarFeed
from feeds.otx import OTXFeed
from feeds.threatfox import ThreatFoxFeed
from feeds.urlhaus import URLhausFeed
from opencti_client import build_pycti_client
from scheduler import build_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def build_redis_client():
    """Connect to Redis using REDIS_URL from config."""
    return redis_from_url(REDIS_URL, decode_responses=True)


def build_enabled_feeds() -> list:
    """
    Instantiate all 5 feed objects.

    All feeds are returned; each feed's run() handles the disabled-if-no-key
    check internally (D-07 pattern). main.py does not pre-filter.
    """
    return [
        URLhausFeed(),
        MalwareBazaarFeed(),
        ThreatFoxFeed(),
        FeodoFeed(),
        OTXFeed(),
    ]


def main() -> None:
    logger.info("feed-orchestrator starting")

    redis_client = build_redis_client()
    pycti_client = build_pycti_client()
    feeds = build_enabled_feeds()

    # D-06: run all feeds immediately BEFORE starting scheduler
    # T-02-07-02: sequential loop prevents concurrent OpenCTI writes on startup
    for feed in feeds:
        logger.info("[%s] initial run starting", feed.name)
        feed.run(redis_client, pycti_client)

    scheduler = build_scheduler(feeds, redis_client, pycti_client)
    scheduler.start()
    logger.info("Scheduler started — %d feed jobs registered", len(feeds))

    # Block main thread; scheduler runs in background threads
    try:
        signal.pause()
    except AttributeError:
        # signal.pause() not available on Windows
        threading.Event().wait()


if __name__ == "__main__":
    main()
