"""
main.py — FastAPI service entry point for semantic-engine.

Endpoints:
  GET /health  — immediate response with index progress (D-05, never blocks)
  GET /search  — natural-language IOC search with similarity scoring (AISEM-02/03/04)

Lifespan: fires indexer.run_index_loop() as asyncio background task on startup (D-05).
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import indexer
import searcher
from config import SIMILARITY_THRESHOLD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # D-05: fire-and-forget — does not block /health
    asyncio.create_task(indexer.run_index_loop())
    yield


app = FastAPI(title="semantic-engine", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Return index progress immediately. Never awaits indexer state (D-05)."""
    return {"status": "ok", **indexer.index_state}


@app.get("/search")
def search_iocs(q: str = "", n_results: int = 10):
    """
    Natural-language IOC search (AISEM-02/03/04).

    V5 input validation (T-04-04-01, T-04-04-03):
    - q empty → 400
    - q > 500 chars → 400 (DoS prevention before embed call)
    """
    if not q:
        raise HTTPException(status_code=400, detail="q parameter required")
    if len(q) > 500:
        raise HTTPException(status_code=400, detail="q too long (max 500 chars)")
    n_results = max(1, min(n_results, 100))

    results = searcher.search(
        indexer.get_collection(),
        q,
        n_results=n_results,
        threshold=SIMILARITY_THRESHOLD,
    )
    return {"query": q, "results": results, "count": len(results)}
