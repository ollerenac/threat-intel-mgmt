"""
main.py — FastAPI entry point for intel-extractor.

Endpoints:
  POST /extract  — submit PDF or URL for background extraction
  GET  /jobs/{id} — poll job status
  GET  /health   — liveness probe

D-06: job state stored in extractor.jobs (module-level dict, lost on restart).
T-03-05-01: file upload limited to 50 MB; returns 413 if exceeded.
"""
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile

import stats_store
from extractor import jobs, run_extraction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stats_store.init_db()
    yield


app = FastAPI(title="intel-extractor", version="1.0.0", lifespan=lifespan)

_MAX_UPLOAD_BYTES = 50_000_000  # T-03-05-01: 50 MB cap


@app.post("/extract")
async def submit_extract(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
):
    if not file and not url:
        raise HTTPException(status_code=400, detail="provide file or url")

    job_id = str(uuid.uuid4())
    # ponytail: init BEFORE add_task — task may read jobs[job_id] before this line runs otherwise
    jobs[job_id] = {
        "status": "queued",
        "iocs_extracted": 0,
        "techniques_found": 0,
        "report_id": None,
        "error": None,
        "processing_time_s": None,
    }

    if file:
        content = await file.read()
        # T-03-05-01: reject oversized uploads
        if len(content) > _MAX_UPLOAD_BYTES:
            del jobs[job_id]
            logger.warning("[main] upload rejected: %d bytes (limit %d)", len(content), _MAX_UPLOAD_BYTES)
            raise HTTPException(status_code=413, detail="file too large (max 50 MB)")
        background_tasks.add_task(run_extraction, job_id, "pdf", content, None)
    else:
        background_tasks.add_task(run_extraction, job_id, "url", None, url)

    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, **jobs[job_id]}


@app.get("/stats")
async def stats():
    row = stats_store.get_stats()
    last_run = row.get("last_run")
    return {
        "total_docs": row.get("total_docs", 0),
        "total_iocs": row.get("total_iocs", 0),
        "last_run": last_run,
        "status": "ok" if last_run else "never_run",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
