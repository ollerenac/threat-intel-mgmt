"""
collector.py — RSS feed polling loop for intel-extractor.

Polls CISA, NCSC UK, and CERT-EU RSS feeds, discovers new document URLs,
fetches PDFs inline, dispatches new docs through run_extraction(), and persists
processed URLs to /data/collector_state.json (DOC-03).

D-01: poll immediately on startup, then every 3600s (each source checks its own interval).
D-02: per-source interval check via last_polled timestamp in collector_state.json.
D-03: bozo feed and per-entry errors are WARNING-logged, never crash the loop.
D-06: PDF URLs fetched via requests.get; HTML/other URLs dispatched as mode="url".
D-07: non-rss source types skipped with a WARNING log.
T-09-03: only yaml.safe_load is used — never the unsafe yaml.load variant.
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
import yaml

from extractor import jobs, run_extraction

logger = logging.getLogger(__name__)

STATE_PATH = Path(os.environ.get("STATE_PATH", "/data/collector_state.json"))
SOURCES_PATH = Path(__file__).parent / "sources.yaml"

# In-memory runtime state — reset on restart; disk state is authoritative for dedup
_collector_state: dict = {
    "sources_meta": {},  # name -> {new_found: int, errors: int}
    "last_run": None,
}


# ── Synchronous helpers (called from within asyncio.to_thread) ────────────────

def _load_sources() -> list[dict]:
    """Read sources.yaml. Uses yaml.safe_load to prevent arbitrary code execution (T-09-03)."""
    with open(SOURCES_PATH) as f:
        data = yaml.safe_load(f)
    return data["sources"]


def _load_state() -> dict:
    """Load persisted URL registry from disk. Returns empty registry when file absent."""
    if not STATE_PATH.exists():
        return {"processed_urls": [], "sources": {}}
    with open(STATE_PATH) as f:
        return json.load(f)


def _save_state(state: dict) -> None:
    """Persist URL registry to disk."""
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _is_source_due(name: str, state: dict, interval_hours: int) -> bool:
    """Return True if the source is due for polling (D-02: interval check by last_polled)."""
    last_polled = state.get("sources", {}).get(name, {}).get("last_polled")
    if last_polled is None:
        return True  # fresh deploy — never polled before
    last_dt = datetime.fromisoformat(last_polled)
    return datetime.now(timezone.utc) - last_dt >= timedelta(hours=interval_hours)


def _poll_source(source: dict, state: dict) -> list[tuple]:
    """
    Poll one RSS source. Returns list of (mode, content, url) pending-dispatch tuples.

    Saves processed URLs to disk immediately (optimistic — prevents re-dispatch on
    restart even if extraction ultimately fails, acceptable for demo scope).
    """
    name = source["name"]
    src_type = source.get("type", "")

    if src_type != "rss":
        # D-07: skip and warn on unsupported source types
        logger.warning("[collector] skipping source '%s' — type '%s' not supported", name, src_type)
        return []

    if not _is_source_due(name, state, source.get("poll_interval_hours", 24)):
        return []

    if name not in _collector_state["sources_meta"]:
        _collector_state["sources_meta"][name] = {"new_found": 0, "errors": 0}

    feed = feedparser.parse(source["url"])
    if feed.bozo and not feed.entries:
        # D-03: parse error with no recoverable entries — log and skip
        logger.warning(
            "[collector] feed '%s' parse error: %s",
            name,
            getattr(feed, "bozo_exception", "unknown"),
        )
        _collector_state["sources_meta"][name]["errors"] += 1
        return []

    processed_urls = set(state.get("processed_urls", []))
    pending: list[tuple] = []
    new_found = 0

    for entry in feed.entries:
        url = entry.get("link", "")
        if not url or url in processed_urls:
            continue

        try:
            if url.lower().endswith(".pdf"):
                # D-06: fetch PDF bytes synchronously (we're already inside a thread)
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                pending.append(("pdf", resp.content, None))
            else:
                # D-06: dispatch URL for web extraction
                pending.append(("url", None, url))

            # Optimistic persistence: persist before async extraction so restarts skip this URL
            processed_urls.add(url)
            state.setdefault("processed_urls", []).append(url)
            new_found += 1
            _save_state(state)

        except Exception as exc:
            # D-03/D-04: per-entry errors must not stop the loop
            logger.warning("[collector] error preparing '%s': %s", url, exc)
            _collector_state["sources_meta"][name]["errors"] += 1

    # Stamp last_polled in disk state regardless of how many new entries were found
    state.setdefault("sources", {}).setdefault(name, {})["last_polled"] = (
        datetime.now(timezone.utc).isoformat()
    )
    _save_state(state)

    _collector_state["sources_meta"][name]["new_found"] = new_found
    logger.info("[collector] source '%s': %d new doc(s) queued", name, new_found)
    return pending


def _run_poll_cycle() -> list[tuple]:
    """
    Run one full poll cycle across all configured sources.
    Returns combined (mode, content, url) list for run_collector_loop to dispatch.
    Blocking — always called via asyncio.to_thread(_run_poll_cycle).
    """
    state = _load_state()
    sources = _load_sources()
    pending: list[tuple] = []
    for source in sources:
        pending.extend(_poll_source(source, state))
    _collector_state["last_run"] = datetime.now(timezone.utc).isoformat()
    return pending


def get_status() -> dict:
    """Return collector status dict for the /collector/status endpoint (plan 09-02)."""
    state = _load_state()
    sources = _load_sources()
    return {
        "sources": [
            {
                "name": s["name"],
                "last_polled": state.get("sources", {}).get(s["name"], {}).get("last_polled"),
                "new_found": _collector_state["sources_meta"].get(s["name"], {}).get("new_found", 0),
                "errors": _collector_state["sources_meta"].get(s["name"], {}).get("errors", 0),
                "poll_interval_hours": s.get("poll_interval_hours", 24),
            }
            for s in sources
        ],
        "registry_size": len(state.get("processed_urls", [])),
        "last_run": _collector_state.get("last_run"),
    }


async def run_collector_loop() -> None:
    """
    Async poll coroutine started by main.py lifespan (D-01).

    Polls immediately on startup (no initial sleep). Runs _run_poll_cycle in a
    thread so feedparser.parse and requests.get don't block the event loop.
    Each discovered doc is dispatched via asyncio.to_thread(run_extraction, ...)
    so extraction also runs off-loop without blocking incoming requests.

    jobs[job_id] is pre-initialized immediately before each dispatch (KeyError
    landmine prevention — mirrors main.py lines 55-63 exactly).
    """
    while True:
        try:
            pending = await asyncio.to_thread(_run_poll_cycle)
            for mode, content, url in pending:
                job_id = str(uuid.uuid4())
                jobs[job_id] = {"status": "queued", "iocs_extracted": 0, "techniques_found": 0, "report_id": None, "error": None, "processing_time_s": None}  # noqa: E501
                asyncio.create_task(asyncio.to_thread(run_extraction, job_id, mode, content, url))
        except Exception as exc:
            logger.warning("[collector] poll cycle error: %s", exc)
        await asyncio.sleep(3600)  # hourly wakeup; each source checks its own interval
