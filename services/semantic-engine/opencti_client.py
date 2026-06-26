"""
opencti_client.py — pycti wrapper for reading OpenCTI indicators in semantic-engine.

Provides:
  build_pycti_client()         — construct and return an OpenCTIApiClient
  list_all_indicators()        — fetch all indicators with getAll pagination
  list_indicators_since()      — fetch indicators updated after a timestamp,
                                 falling back to full fetch if the filter fails
                                 (D-04 / RESEARCH.md Open Question 1 / Assumption A1)
"""
import logging
import time
from typing import Optional

from pycti import OpenCTIApiClient

from config import OPENCTI_TOKEN, OPENCTI_URL

logger = logging.getLogger(__name__)

# D-05 retry delays: 30s → 60s → 120s (same as intel-extractor)
_RETRY_DELAYS = [30, 60, 120]


def build_pycti_client() -> OpenCTIApiClient:
    """Build and return an OpenCTIApiClient connected to OPENCTI_URL."""
    return OpenCTIApiClient(
        url=OPENCTI_URL,
        token=OPENCTI_TOKEN,
        log_level="error",  # suppress INFO spam from pycti internals
    )


def list_all_indicators(client: OpenCTIApiClient) -> list[dict]:
    """
    Fetch all indicators from OpenCTI.

    Uses getAll=True so pycti handles hasNextPage/endCursor pagination
    internally. first=500 sets the page size for each batch request.

    Returns:
        List of indicator dicts with pycti 6.4.11 field names.
    """
    return client.indicator.list(getAll=True, first=500)


def list_indicators_since(client: OpenCTIApiClient, since: str) -> list[dict]:
    """
    Fetch indicators updated after the given ISO-8601 timestamp.

    D-04: incremental watermark fetch. Constructs a FilterGroup dict
    with updated_at > since, then falls back to list_all_indicators()
    on any exception (RESEARCH.md Open Question 1 — updated_at filter
    support is version-dependent; fallback guarantees correctness).

    Args:
        client: OpenCTIApiClient instance from build_pycti_client()
        since:  ISO-8601 UTC timestamp string (e.g. "2026-06-25T00:00:00.000Z")

    Returns:
        List of indicator dicts, sorted by updated_at ascending.
    """
    filters = {
        "mode": "and",
        "filters": [{"key": "updated_at", "values": [since]}],
        "filterGroups": [],
    }
    try:
        return client.indicator.list(
            getAll=True,
            first=500,
            filters=filters,
            orderBy="updated_at",
            orderMode="asc",
        )
    except Exception:
        logger.warning(
            "[opencti_client] updated_at filter failed, falling back to full fetch"
        )
        return list_all_indicators(client)
