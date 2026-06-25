---
phase: 03-ai-ioc-extraction
plan: "05"
subsystem: intel-extractor
tags: [fastapi, docker, uvicorn, healthcheck]
status: complete

dependency_graph:
  requires: [03-04]
  provides: [intel-extractor-service-deployable]
  affects: [docker-compose.yml, 03-06]

tech_stack:
  added:
    - fastapi==0.115.14 (HTTP layer for intel-extractor)
    - uvicorn (ASGI server, CMD in Dockerfile)
    - python-multipart (FastAPI file upload support)
    - PyPDF2==3.0.1 (PDF parsing — via requirements.txt)
    - trafilatura (URL scraping — via requirements.txt)
    - beautifulsoup4 (URL fallback scraping)
  patterns:
    - BackgroundTasks for async job dispatch (plain def run_extraction in thread pool)
    - Module-level jobs dict shared between main.py and extractor.py (D-06)
    - 50 MB upload cap enforced before job init (T-03-05-01)

key_files:
  created:
    - services/intel-extractor/main.py
    - services/intel-extractor/requirements.txt
    - services/intel-extractor/Dockerfile
  modified:
    - docker-compose.yml (intel-extractor healthcheck block added)

decisions:
  - "D-06 enforced: jobs[job_id] initialized BEFORE add_task() to prevent race where background task reads dict before entry exists"
  - "T-03-05-01 mitigated: 50 MB file size cap returns 413 and cleans up job entry before it persists"
  - "Dockerfile has no libmagic1 apt install — PyPDF2 and trafilatura are pure Python"
  - "CMD uses uvicorn not python main.py — aligns with ASGI requirements"

metrics:
  duration: 2m
  completed: "2026-06-25"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 03 Plan 05: Wire intel-extractor FastAPI Service Summary

**One-liner:** FastAPI service with uvicorn CMD, pinned deps (pycti==6.4.11, fastapi==0.115.14, PyPDF2==3.0.1), and docker-compose healthcheck on port 8001.

---

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | main.py + requirements.txt + Dockerfile | 89ddd2d | services/intel-extractor/main.py, requirements.txt, Dockerfile |
| 2 | docker-compose.yml healthcheck | 21befe3 | docker-compose.yml |

---

## What Was Built

### Task 1: FastAPI service wired

**`services/intel-extractor/main.py`** — three endpoints:
- `POST /extract`: accepts `file=` (UploadFile) or `url=` (Form field); returns 400 if neither provided; initializes `jobs[job_id]` dict before dispatching `run_extraction` as a BackgroundTask; enforces 50 MB cap (413) per T-03-05-01.
- `GET /jobs/{job_id}`: returns full job state from the shared `extractor.jobs` dict; 404 for unknown IDs.
- `GET /health`: returns `{"status": "ok"}` for the Docker healthcheck probe.

**`services/intel-extractor/requirements.txt`** — pinned versions matching plan spec:
- fastapi==0.115.14, pycti==6.4.11, PyPDF2==3.0.1
- uvicorn, ollama, trafilatura, requests, python-multipart, beautifulsoup4, pytest, pytest-mock

**`services/intel-extractor/Dockerfile`** — 6-line file:
- `FROM python:3.12-slim` (matches feed-orchestrator base)
- No `apt-get libmagic1` line (pure Python deps only)
- `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]`
- Docker build verified: exit 0

### Task 2: docker-compose.yml healthcheck

Added to `intel-extractor` service stanza (after `restart: unless-stopped`, before `semantic-engine`):

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

`docker compose config` reports no errors.

---

## Deviations from Plan

### Auto-added security mitigations

**1. [Rule 2 - Security] T-03-05-01 file size cap applied**
- **Found during:** Task 1 implementation — threat model listed T-03-05-01 with `disposition: mitigate`
- **Issue:** Plan action described the endpoint but did not include the 50 MB guard explicitly in code steps
- **Fix:** After `content = await file.read()`, check `len(content) > 50_000_000`; return 413 and delete the pre-initialized job entry to avoid orphaned queued jobs
- **Files modified:** services/intel-extractor/main.py
- **Commit:** 89ddd2d

---

## Known Stubs

None — main.py delegates all processing to `extractor.run_extraction` (implemented in 03-04). No placeholder data flows to any output.

---

## Threat Flags

None — no new network endpoints, auth paths, or schema changes beyond what the plan's threat model covers.

---

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| services/intel-extractor/main.py | FOUND |
| services/intel-extractor/requirements.txt | FOUND |
| services/intel-extractor/Dockerfile | FOUND |
| Commit 89ddd2d (Task 1) | FOUND |
| Commit 21befe3 (Task 2) | FOUND |
| docker compose config errors | 0 |
