"""
indexer.py — Core indexing engine for semantic-engine.

Fetches OpenCTI indicators, embeds them via Ollama nomic-embed-text,
and upserts them into ChromaDB with a watermark sentinel for incremental
restarts (D-04).

Exports at module level for main.py:
  index_state       — progress dict spread into /health response (D-05)
  get_collection()  — returns the ChromaDB collection (called by searcher)
  run_index_loop()  — async coroutine launched by lifespan (D-05)
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import chromadb
import ollama

from config import (
    CHROMADB_URL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_URL,
    OPENCTI_BASE_URL,
    POLL_INTERVAL_SECONDS,
)
from opencti_client import build_pycti_client, list_all_indicators, list_indicators_since

logger = logging.getLogger(__name__)

# ── Module-level state dict exported for main.py /health (D-05) ─────────────
index_state: dict = {"status": "starting", "indexed": 0, "total": 0}

# ── ChromaDB — lazy singleton (defer connect to avoid import-time network call) ──
# ponytail: lazy init so test_indexer.py import guard works without a live ChromaDB
COLLECTION_NAME = "ioc_embeddings"
_chroma: Optional[chromadb.HttpClient] = None  # type: ignore[type-arg]


def _get_chroma() -> chromadb.HttpClient:  # type: ignore[type-arg]
    global _chroma
    if _chroma is None:
        parsed = urlparse(CHROMADB_URL)
        _chroma = chromadb.HttpClient(host=parsed.hostname, port=parsed.port or 8000)
    return _chroma


# ── Ollama singleton ─────────────────────────────────────────────────────────
_ollama = ollama.Client(host=OLLAMA_URL)

# ── Retry delays: same pattern as intel-extractor ───────────────────────────
_RETRY_DELAYS = [30, 60, 120]

# ── Watermark sentinel (D-04) ────────────────────────────────────────────────
WATERMARK_ID = "_watermark_"


def get_collection():
    """
    Get or create the ChromaDB IOC collection with cosine distance.

    MUST use configuration= key (not metadata=) and cosine space — default
    is L2 which produces poor text similarity results (RESEARCH Pitfall 2).
    Safe to call on every startup (get_or_create is idempotent).
    """
    return _get_chroma().get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
    )


def read_watermark(collection) -> Optional[str]:
    """Return last_indexed_at from the watermark sentinel, or None if absent."""
    try:
        result = collection.get(ids=[WATERMARK_ID], include=["metadatas"])
        if result["ids"]:
            return result["metadatas"][0].get("last_indexed_at")
    except Exception:
        pass
    return None


def write_watermark(collection, timestamp: str) -> None:
    """Upsert the watermark sentinel with the given ISO-8601 timestamp."""
    collection.upsert(
        ids=[WATERMARK_ID],
        embeddings=[[0.0] * 768],  # dummy vector — never queried
        documents=["watermark"],
        metadatas=[{"last_indexed_at": timestamp}],
    )


def build_embed_text(indicator: dict) -> str:
    """
    Build the text that will be embedded for a given indicator.

    D-01: With description → "{type}: {value} — {description} {labels}"
    D-03: Without description → "{type}: {value} [{labels}]"

    The em dash (—) is U+2014. Never skip no-description IOCs.
    """
    ioc_type = indicator.get("x_opencti_main_observable_type", "Unknown")
    value = indicator.get("name", "")
    description = indicator.get("description") or ""
    labels = [lbl["value"] for lbl in (indicator.get("objectLabel") or [])]
    label_str = " ".join(labels)

    if description:
        return f"{ioc_type}: {value} — {description} {label_str}".strip()
    else:
        return f"{ioc_type}: {value} [{label_str}]".strip()  # ponytail: D-03 bracket format


def _embed_with_retry(text: str) -> Optional[list]:
    """
    Embed text via Ollama with retry on failure (RESEARCH Pitfall 6).

    Returns response.embeddings[0] (plural — not .embedding singular).
    Returns None after all retries exhausted; caller must skip None vectors.
    """
    vector = None
    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            response = _ollama.embed(model=OLLAMA_EMBED_MODEL, input=text)
            vector = response.embeddings[0]  # embeddings[0] — not .embedding (deprecated)
            break
        except Exception as exc:
            if attempt < len(_RETRY_DELAYS) - 1:
                logger.warning(
                    "[indexer] embed failed attempt %d, retrying in %ds: %s",
                    attempt + 1, delay, exc,
                )
                time.sleep(delay)
            else:
                logger.warning(
                    "[indexer] embed failed after %d attempts, skipping IOC: %s",
                    len(_RETRY_DELAYS), exc,
                )
    return vector


def _index_batch(collection, indicators: list[dict]) -> int:
    """
    Embed and upsert a batch of indicators into ChromaDB.

    Skips any indicator where embedding fails. Never indexes the watermark
    sentinel ID. Returns count of successfully indexed items.
    """
    count = 0
    for indicator in indicators:
        # Guard: never index the watermark sentinel as an IOC
        if indicator.get("id") == WATERMARK_ID:
            continue

        embed_text = build_embed_text(indicator)
        vector = _embed_with_retry(embed_text)
        if vector is None:
            continue

        collection.upsert(
            ids=[indicator["id"]],
            embeddings=[vector],
            documents=[embed_text],
            metadatas=[{
                "ioc_type": indicator["x_opencti_main_observable_type"],
                "value": indicator["name"],
                "opencti_url": (
                    f"{OPENCTI_BASE_URL}/dashboard/observations/indicators/{indicator['id']}"
                ),
                "embedded_text": embed_text,  # D-08: analyst sees WHY this matched
            }],
        )
        count += 1
    return count


def _run_index_cycle(watermark: Optional[str]) -> tuple:
    """Sync helper — one full index cycle. Runs in a thread via asyncio.to_thread.

    All blocking I/O (pycti, ollama, chromadb) is safe to do here because the
    caller awaits this in a threadpool — the event loop stays free to serve /health
    and /search while indexing is in progress (fixes event-loop starvation on startup).
    """
    client = build_pycti_client()
    collection = get_collection()

    if watermark is None:
        watermark = read_watermark(collection)

    if watermark is None:
        logger.info("[indexer] No watermark found — running full index")
        indicators = list_all_indicators(client)
    else:
        logger.info("[indexer] Watermark %s — running incremental index", watermark)
        indicators = list_indicators_since(client, watermark)

    index_state["status"] = "indexing"
    index_state["total"] = len(indicators)
    index_state["indexed"] = 0

    indexed = _index_batch(collection, indicators)
    index_state["indexed"] = indexed

    new_watermark = datetime.utcnow().isoformat() + "Z"
    write_watermark(collection, new_watermark)
    index_state["status"] = "ready"
    logger.info("[indexer] Cycle complete: %d/%d indexed", indexed, len(indicators))
    return indexed, new_watermark


async def run_index_loop() -> None:
    """Async coroutine — offloads each blocking index cycle to a thread (D-05).

    asyncio.to_thread releases the event loop during sync I/O so /health responds
    immediately even while indexing is in progress.
    """
    watermark: Optional[str] = None

    while True:
        try:
            _, watermark = await asyncio.to_thread(_run_index_cycle, watermark)
        except Exception as exc:
            logger.error("[indexer] Cycle failed: %s", exc)
            index_state["status"] = "error"

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
