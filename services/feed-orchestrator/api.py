"""
api.py — FastAPI application for feed-orchestrator HTTP endpoints.

Endpoints:
  GET /feeds/status — per-feed run history from Redis (DASH-01)
  GET /health       — liveness probe

CORS: allow_origins=["http://localhost:3000"] per T-06-01-01 (explicit origin, never "*").
"""
import json
import logging
import uuid

import requests
import stix2
from dateutil.parser import parse as parse_dt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from redis import from_url as redis_from_url

from config import ALERT_THRESHOLD, ES_URL, REDIS_URL
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


@app.get("/feeds/alerts")
def feeds_alerts():
    """Return the 100 most recent high-confidence IOC alerts from Redis."""
    r = redis_from_url(REDIS_URL, decode_responses=True)
    raw = r.lrange("tim:alerts", 0, -1)
    alerts = [json.loads(e) for e in raw]
    return {"threshold": ALERT_THRESHOLD, "alerts": list(reversed(alerts))}


@app.get("/feeds/export/stix")
def export_stix():
    """Return a STIX 2.1 bundle of all high-confidence IOCs indexed in Elasticsearch."""
    try:
        resp = requests.get(
            f"{ES_URL}/tim-iocs/_search",
            json={"size": 1000, "sort": [{"ts": {"order": "desc"}}]},
            timeout=10,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ES unavailable: {exc}")

    indicators = []
    for hit in hits:
        src = hit["_source"]
        indicators.append(stix2.Indicator(
            id=src.get("stix_id", f"indicator--{uuid.uuid4()}"),
            name=src["value"],
            pattern=src["pattern"],
            pattern_type="stix",
            valid_from=parse_dt(src["ts"]),
            confidence=src["confidence"],
            labels=[src["feed"]],
        ))

    bundle = stix2.Bundle(*indicators, allow_custom=True)
    return Response(content=bundle.serialize(), media_type="application/stix+json")


@app.get("/health")
def health():
    return {"status": "ok"}
