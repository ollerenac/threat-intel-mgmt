"""
opencti_client.py — pycti wrapper for OpenCTI indicator creation.

Provides:
  build_pycti_client()   — construct and return an OpenCTIApiClient
  create_indicator()     — submit a STIX indicator with D-05 retry (3x, 30/60/120s)

D-05: On pycti insertion failure, retry 3× with delays [30, 60, 120].
After all retries exhausted, log warning and return None (do not raise).
IOCs lost for that run; next scheduled run will re-download and retry.

Assumption A2: pycti.indicator.create() parameter name for labels is
'objectLabel' per RESEARCH.md Pattern 3 and docs.opencti.io.
Verify against pycti/entities/opencti_indicator.py in the installed package
(pycti==6.4.11) during first Docker build. If the parameter is 'labels'
instead of 'objectLabel', update the call below and remove this comment.

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
