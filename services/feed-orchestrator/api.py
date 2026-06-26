"""
api.py — FastAPI application for feed-orchestrator HTTP endpoints.

Endpoints:
  GET /feeds/status — per-feed run history from Redis (DASH-01)
  GET /health       — liveness probe

CORS: allow_origins=["http://localhost:3000"] per T-06-01-01 (explicit origin, never "*").
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import from_url as redis_from_url

from config import REDIS_URL
from status import get_status

logger = logging.getLogger(__name__)

app = FastAPI(title="feed-orchestrator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Confirmed .name attribute values from each feed class (build_enabled_feeds order)
FEED_NAMES = ["urlhaus", "malwarebazaar", "threatfox", "feodo", "otx"]


@app.get("/feeds/status")
def feeds_status():
    """Return per-feed status from Redis. Missing keys return safe defaults."""
    r = redis_from_url(REDIS_URL, decode_responses=True)
    feeds = []
    for name in FEED_NAMES:
        h = get_status(r, name)
        feeds.append({
            "name": name,
            "last_run": h.get("last_run"),
            "ioc_count": int(h.get("ioc_count", 0)),
            "status": h.get("status", "never_run"),
        })
    return {"feeds": feeds}


@app.get("/health")
def health():
    return {"status": "ok"}
