"""
opencti_client.py — pycti wrapper for OpenCTI indicator creation in intel-extractor.

Provides:
  build_pycti_client()       — construct and return an OpenCTIApiClient
  create_indicator()         — submit a STIX indicator with D-05 retry (3x, 30/60/120s)
  lookup_attack_pattern()    — query OpenCTI for ATT&CK pattern by keyword; returns internal UUID
  create_report()            — create a threat-report object with D-05 retry
  create_relationship()      — create a STIX relationship (indicates) with D-05 retry

D-05: On pycti write failure, retry 3× with delays [30, 60, 120].
After all retries exhausted, log warning and return None (do not raise).

D-08: lookup_attack_pattern returns internal OpenCTI UUID (results[0]["id"]), not x_mitre_id.
D-09: ATT&CK no-match logs at INFO level with prefix "[extractor]".

Assumption A2: pycti.indicator.create() parameter name for labels is
'objectLabel' per RESEARCH.md Pattern 3 and docs.opencti.io.
Assumption A4: 'confidence' and 'x_opencti_score' are independent fields.
Setting both to the same value is safe per RESEARCH.md Pattern 3.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from pycti import OpenCTIApiClient

from config import OPENCTI_TOKEN, OPENCTI_URL

logger = logging.getLogger(__name__)

# D-05 retry delays: 30s → 60s → 120s
_RETRY_DELAYS = [30, 60, 120]


def build_pycti_client() -> OpenCTIApiClient:
    """Build and return an OpenCTIApiClient connected to OPENCTI_URL."""
    return OpenCTIApiClient(
        url=OPENCTI_URL,
        token=OPENCTI_TOKEN,
        log_level="error",  # suppress INFO spam from pycti internals
    )


def create_indicator(
    client: OpenCTIApiClient,
    name: str,
    pattern: str,
    observable_type: str,
    confidence: int,
    labels: list,
    source_name: str,
    valid_from: Optional[str] = None,
) -> Optional[dict]:
    """
    Submit a STIX indicator to OpenCTI with idempotent upsert (update=True).

    Wraps client.indicator.create() in D-05 retry: 3x with [30, 60, 120]s delays.
    Logs a warning on each failure. Returns None after all retries exhausted.

    Args:
        client:           OpenCTIApiClient instance from build_pycti_client()
        name:             Human-readable indicator name
        pattern:          STIX 2.1 pattern string e.g. "[url:value = 'http://...']"
        observable_type:  x_opencti_main_observable_type value e.g. "IPv4-Addr"
        confidence:       0-100 confidence score (D-09 formula)
        labels:           List of label strings (malware families, tags)
        source_name:      Feed source name for externalReferences
        valid_from:       ISO-8601 UTC string; defaults to now if None

    Returns:
        dict with indicator data on success, None on failure after all retries.
    """
    if valid_from is None:
        valid_from = datetime.now(timezone.utc).isoformat()

    last_exc: Optional[Exception] = None
    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            return client.indicator.create(
                name=name,
                pattern_type="stix",
                pattern=pattern,
                x_opencti_main_observable_type=observable_type,
                valid_from=valid_from,
                confidence=confidence,
                x_opencti_score=confidence,  # A4: same value as confidence
                objectLabel=labels,           # A2: verify param name in pycti source
                indicator_types=["malicious-activity"],
                update=True,                 # idempotent upsert — safety net beyond Redis dedup
            )
        except Exception as exc:
            last_exc = exc
            if attempt < len(_RETRY_DELAYS) - 1:
                logger.warning(
                    "[opencti_client] indicator create attempt %d failed, retrying in %ds: %s",
                    attempt + 1,
                    delay,
                    exc,
                )
                time.sleep(delay)
            else:
                logger.warning(
                    "[opencti_client] indicator create failed after %d attempts, skipping: %s",
                    len(_RETRY_DELAYS),
                    exc,
                )

    return None


def lookup_attack_pattern(client: OpenCTIApiClient, keyword: str) -> Optional[str]:
    """
    Query OpenCTI for an ATT&CK pattern matching keyword.

    No retry — this is a read-only query. Returns the internal OpenCTI UUID
    (results[0]["id"]), NOT the x_mitre_id Txxxx string (D-08).

    Args:
        client:   OpenCTIApiClient instance
        keyword:  Technique name or keyword to search (e.g. "phishing")

    Returns:
        Internal OpenCTI UUID string on match, None if no match found (D-09).
    """
    results = client.attack_pattern.list(search=keyword, first=5)
    if not results:
        logger.info("[extractor] ATT&CK no match for: '%s' — skipping", keyword)
        return None
    return results[0]["id"]


def create_report(
    client: OpenCTIApiClient,
    name: str,
    published: str,
    description: str,
    indicator_ids: list[str],
    labels: list[str] = [],
) -> Optional[dict]:
    """
    Create a threat-report in OpenCTI with all indicator objects linked.

    Uses D-05 retry: 3x with [30, 60, 120]s delays. Call only after all
    create_indicator() calls are complete (Pitfall 1 — collect all IDs first).

    Args:
        client:         OpenCTIApiClient instance
        name:           Report title
        published:      ISO-8601 UTC string (e.g. "2026-06-25T00:00:00Z")
        description:    Report summary text
        indicator_ids:  List of internal OpenCTI indicator UUIDs to attach

    Returns:
        dict with report data on success, None on failure after all retries.
    """
    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            return client.report.create(
                name=name,
                published=published,
                description=description,
                objects=indicator_ids,
                report_types=["threat-report"],
                objectLabel=labels if labels else [],
                update=True,
            )
        except Exception as exc:
            if attempt < len(_RETRY_DELAYS) - 1:
                logger.warning(
                    "[opencti_client] report create attempt %d failed, retrying in %ds: %s",
                    attempt + 1,
                    delay,
                    exc,
                )
                time.sleep(delay)
            else:
                logger.warning(
                    "[opencti_client] report create failed after %d attempts, skipping: %s",
                    len(_RETRY_DELAYS),
                    exc,
                )

    return None


def create_relationship(
    client: OpenCTIApiClient,
    from_id: str,
    to_id: str,
    relationship_type: str = "indicates",
) -> Optional[dict]:
    """
    Create a STIX core relationship between two OpenCTI objects.

    Uses D-05 retry: 3x with [30, 60, 120]s delays. Typically links an
    indicator (from_id) to an attack-pattern (to_id) via "indicates".

    Args:
        client:            OpenCTIApiClient instance
        from_id:           Internal OpenCTI UUID of source object (indicator)
        to_id:             Internal OpenCTI UUID of target object (attack-pattern)
        relationship_type: STIX relationship type (default: "indicates")

    Returns:
        dict with relationship data on success, None on failure after all retries.
    """
    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            return client.stix_core_relationship.create(
                fromId=from_id,
                toId=to_id,
                relationship_type=relationship_type,
                update=True,
            )
        except Exception as exc:
            if attempt < len(_RETRY_DELAYS) - 1:
                logger.warning(
                    "[opencti_client] relationship create attempt %d failed, retrying in %ds: %s",
                    attempt + 1,
                    delay,
                    exc,
                )
                time.sleep(delay)
            else:
                logger.warning(
                    "[opencti_client] relationship create failed after %d attempts, skipping: %s",
                    len(_RETRY_DELAYS),
                    exc,
                )

    return None
