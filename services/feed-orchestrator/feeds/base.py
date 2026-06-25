"""
feeds/base.py — Abstract base class for all feed implementations.

BaseFeed defines the contract that all 5 feed subclasses (urlhaus, malwarebazaar,
threatfox, feodo, otx) must implement: fetch() and normalize().

The run() method orchestrates the full feed cycle:
  1. Write status=running to Redis (D-02 fields, D-01 key namespace)
  2. _fetch_with_retry(): download with 3x backoff [30, 60, 120]s (D-04)
  3. normalize(): transform raw data to pycti create_indicator() kwargs dicts
  4. _insert_deduplicated(): dedup via Redis SETNX, insert via pycti (D-05 retry)
  5. Write status=ok or status=error to Redis

All Redis writes use hset(mapping={...}) — NOT hmset() (removed in redis-py 4.x).
"""
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from deduplicator import is_duplicate
from opencti_client import create_indicator

logger = logging.getLogger(__name__)


class BaseFeed(ABC):
    """Abstract base class for all threat intelligence feed implementations."""

    name: str        # Feed identifier used in Redis keys and log messages
    quality_weight: int   # D-09 confidence formula weight
    interval_hours: int   # Scheduled cadence for APScheduler

    @abstractmethod
    def fetch(self) -> list[dict]:
        """Download and parse raw feed data. Returns list of raw row dicts."""
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw: list[dict]) -> list[dict]:
        """
        Transform raw feed rows to pycti create_indicator() kwargs dicts.

        Each returned dict must contain keys:
          name, pattern, observable_type, confidence, labels, source_name
        Optional: valid_from (ISO-8601 string)

        Returns list of dicts — one per indicator to insert.
        """
        raise NotImplementedError

    def run(self, redis_client: Any, pycti_client: Any) -> None:
        """
        Execute a full feed cycle: status=running → fetch → normalize →
        insert → status=ok/error.

        Called by APScheduler on the configured interval, and once immediately
        on container startup (D-06).
        """
        redis_client.hset(
            f"tim:feed_status:{self.name}",
            mapping={
                "status": "running",
                "last_run": datetime.now(timezone.utc).isoformat(),
                "ioc_count": "0",
                "error_msg": "",
            },
        )
        try:
            raw = self._fetch_with_retry()
            indicators = self.normalize(raw)
            count = self._insert_deduplicated(indicators, redis_client, pycti_client)
            redis_client.hset(
                f"tim:feed_status:{self.name}",
                mapping={
                    "status": "ok",
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "ioc_count": str(count),
                    "error_msg": "",
                },
            )
            logger.info("[%s] run complete: %d indicators inserted", self.name, count)
        except Exception as exc:
            logger.error("[%s] run failed: %s", self.name, exc)
            redis_client.hset(
                f"tim:feed_status:{self.name}",
                mapping={
                    "status": "error",
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "ioc_count": "0",
                    "error_msg": str(exc)[:500],
                },
            )

    def _fetch_with_retry(self) -> list[dict]:
        """
        Call self.fetch() with D-04 retry: 3 attempts, delays [30, 60, 120]s.

        On each failure before the last attempt, logs a warning and sleeps.
        On final failure, re-raises the exception so run()'s except block
        can write status=error.
        """
        delays = [30, 60, 120]
        last_exc: Exception | None = None
        for attempt, delay in enumerate(delays):
            try:
                return self.fetch()
            except Exception as exc:
                last_exc = exc
                if attempt < len(delays) - 1:
                    logger.warning(
                        "[%s] fetch attempt %d failed, retrying in %ds: %s",
                        self.name,
                        attempt + 1,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
        raise last_exc  # type: ignore[misc]

    def _insert_deduplicated(
        self,
        indicators: list[dict],
        redis_client: Any,
        pycti_client: Any,
    ) -> int:
        """
        Insert indicators into OpenCTI, skipping duplicates via Redis SETNX.

        Loops over normalized indicator dicts. For each:
          - If is_duplicate() returns True: skip (already inserted this cycle)
          - Else: compute D-09 confidence, call create_indicator() with D-05 retry

        Returns count of indicators actually submitted to pycti (not skipped).
        """
        # Lazy import avoids circular-import risk at module load time
        from normalizer import compute_confidence, parse_first_seen

        count = 0
        for ind in indicators:
            pattern = ind.get("pattern", "")
            if not pattern:
                continue
            if is_duplicate(redis_client, pattern):
                continue
            first_seen_dt = parse_first_seen(ind.get("valid_from", ""))
            confidence = compute_confidence(self.name, first_seen_dt)
            ind["confidence"] = confidence
            result = create_indicator(
                client=pycti_client,
                name=ind.get("name", f"{self.name} indicator"),
                pattern=pattern,
                observable_type=ind.get("observable_type", ""),
                confidence=confidence,
                labels=ind.get("labels", []),
                source_name=ind.get("source_name", self.name),
                valid_from=first_seen_dt.isoformat(),  # ISO 8601 required by OpenCTI GraphQL
            )
            if result is not None:
                count += 1
        return count
