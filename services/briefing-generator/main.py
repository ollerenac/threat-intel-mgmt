"""
main.py — FastAPI entry point for briefing-generator.

Endpoints:
  POST /generate              — trigger async briefing generation
  GET  /briefings/{id}        — poll briefing status / fetch result
  GET  /briefings/{id}/pdf    — download briefing as PDF (status must be "done")
  GET  /briefings             — list all briefing summaries
  GET  /health                — liveness probe

D-10: briefing state stored in generator.briefings (module-level dict, lost on restart).
T-05-04-01: period_hours validated by Pydantic Field(ge=1, le=720) before any I/O.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from generator import briefings, run_generate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="briefing-generator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    period_hours: int = Field(default=24, ge=1, le=720)


@app.post("/generate")
async def generate(body: GenerateRequest, background_tasks: BackgroundTasks):
    briefing_id = str(uuid.uuid4())
    # ponytail: init BEFORE add_task — task reads briefings[briefing_id] before this line otherwise
    briefings[briefing_id] = {
        "status": "generating",
        "text": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "period_hours": body.period_hours,
        "error": None,
    }
    background_tasks.add_task(run_generate, briefing_id, body.period_hours)
    return {"briefing_id": briefing_id, "status": "generating"}


@app.get("/briefings/{briefing_id}")
async def get_briefing(briefing_id: str):
    if briefing_id not in briefings:
        raise HTTPException(status_code=404, detail="briefing not found")
    return {"briefing_id": briefing_id, **briefings[briefing_id]}


@app.get("/briefings/{briefing_id}/pdf")
async def get_briefing_pdf(briefing_id: str):
    if briefing_id not in briefings:
        raise HTTPException(status_code=404, detail="briefing not found")
    entry = briefings[briefing_id]
    if entry["status"] != "done":
        # Pitfall 5: never call render_pdf() when text is None
        raise HTTPException(status_code=404, detail="briefing not ready")
    from pdf_renderer import render_pdf  # lazy import — only needed on this path
    pdf_bytes = render_pdf(entry)
    return Response(content=pdf_bytes, media_type="application/pdf")


@app.get("/briefings")
async def list_briefings():
    return [
        {
            "briefing_id": bid,
            "created_at": v["created_at"],
            "period_hours": v["period_hours"],
            "status": v["status"],
        }
        for bid, v in briefings.items()
    ]


@app.get("/stats")
async def stats():
    """
    Return IOC count (last 24h) and top 5 ATT&CK techniques (DASH-02, D-05, D-06).

    Uses asyncio.to_thread to keep pycti I/O off the event loop (T-06-01-03).
    count=1 per technique — attack_patterns already ordered by pycti default.
    """
    from opencti_client import build_pycti_client
    from generator import _collect_threat_data
    client = build_pycti_client()
    data = await asyncio.to_thread(_collect_threat_data, client, 24)
    techniques = [
        {"id": p.get("x_mitre_id", ""), "name": p.get("name", ""), "count": 1}
        for p in data.get("attack_patterns", [])[:5]
    ]
    return {
        "ioc_count_24h": len(data.get("indicators", [])),
        "top_techniques": techniques,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
