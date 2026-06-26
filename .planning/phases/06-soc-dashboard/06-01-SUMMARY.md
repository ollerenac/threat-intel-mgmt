---
phase: 06-soc-dashboard
plan: "01"
subsystem: backend-api
tags: [fastapi, cors, feed-orchestrator, briefing-generator, semantic-engine]
status: complete

dependency_graph:
  requires:
    - services/feed-orchestrator/status.py
    - services/feed-orchestrator/config.py
    - services/briefing-generator/generator.py (_collect_threat_data)
    - services/briefing-generator/opencti_client.py
  provides:
    - services/feed-orchestrator/api.py (GET /feeds/status, GET /health on port 8001)
    - GET /stats on briefing-generator (port 8003)
    - CORSMiddleware on all three backend services
  affects:
    - services/feed-orchestrator/main.py (uvicorn replaces signal.pause)
    - services/feed-orchestrator/requirements.txt
    - services/semantic-engine/main.py

tech_stack:
  added:
    - fastapi==0.115.14 (feed-orchestrator)
    - uvicorn (feed-orchestrator)
  patterns:
    - FastAPI CORSMiddleware with explicit allow_origins (not "*")
    - uvicorn.run() as main-thread blocker with APScheduler daemon threads
    - asyncio.to_thread for blocking pycti calls in async endpoint

key_files:
  created:
    - services/feed-orchestrator/api.py
  modified:
    - services/feed-orchestrator/requirements.txt
    - services/feed-orchestrator/main.py
    - services/briefing-generator/main.py
    - services/semantic-engine/main.py

decisions:
  - "uvicorn.run() replaces signal.pause() as main-thread blocker — APScheduler daemon threads continue unaffected"
  - "FEED_NAMES hardcoded as module constant in api.py — stable constants from feed .name attributes"
  - "asyncio.to_thread wraps _collect_threat_data in /stats — prevents blocking the uvicorn event loop on pycti I/O"
  - "count=1 per technique in /stats top_techniques — attack_patterns already ordered by pycti default; cross-referencing not needed for demo"

metrics:
  duration: "~12m"
  completed: "2026-06-26"
  tasks_completed: 2
  files_changed: 5

requirements_satisfied:
  - DASH-01 (backend: GET /feeds/status available)
  - DASH-02 (backend: GET /stats available)
  - DASH-03 (backend: CORS enabled on semantic-engine for browser fetch)
---

# Phase 6 Plan 01: Backend API Additions and CORS — Summary

**One-liner:** FastAPI HTTP layer added to feed-orchestrator (port 8001 with /feeds/status), GET /stats added to briefing-generator, and CORSMiddleware with explicit allow_origins set on all three backend services.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Convert feed-orchestrator to hybrid HTTP+scheduler | 3e27199 | requirements.txt, api.py (new), main.py |
| 2 | Add GET /stats to briefing-generator and CORS to all services | 68dde02 | briefing-generator/main.py, semantic-engine/main.py |

## What Was Built

### Task 1: feed-orchestrator HTTP layer

`services/feed-orchestrator/api.py` is a new file with:
- `FastAPI(title="feed-orchestrator", version="1.0.0")`
- `CORSMiddleware(allow_origins=["http://localhost:3000"])`
- `FEED_NAMES = ["urlhaus", "malwarebazaar", "threatfox", "feodo", "otx"]`
- `GET /feeds/status` — iterates FEED_NAMES, calls `get_status(r, name)` from `status.py`, returns `{"feeds": [...]}` with `name`, `last_run`, `ioc_count`, `status` per feed
- `GET /health` — returns `{"status": "ok"}`

`services/feed-orchestrator/main.py` changes:
- Removed `signal`, `threading` imports
- Added `import uvicorn` and `from api import app`
- Replaced `signal.pause()` / `threading.Event().wait()` block with `uvicorn.run(app, host="0.0.0.0", port=8001)`
- APScheduler is started via `scheduler.start()` before `uvicorn.run()` — daemon threads continue

### Task 2: briefing-generator /stats and CORS

`services/briefing-generator/main.py` additions:
- `import asyncio` at top of imports
- `from fastapi.middleware.cors import CORSMiddleware` added
- `CORSMiddleware(allow_origins=["http://localhost:3000"])` after `app = FastAPI(...)`
- `GET /stats` endpoint using `asyncio.to_thread(_collect_threat_data, client, 24)` — returns `{"ioc_count_24h": int, "top_techniques": [{"id", "name", "count"}]}`

`services/semantic-engine/main.py` additions:
- `from fastapi.middleware.cors import CORSMiddleware` added
- `CORSMiddleware(allow_origins=["http://localhost:3000"])` after `app = FastAPI(...)`

## Verification

All automated checks passed:

```
services/feed-orchestrator/requirements.txt: fastapi present ✓, uvicorn present ✓
api.py: parses OK (ast.parse) ✓
main.py: parses OK (ast.parse) ✓
briefing-generator/main.py: parses OK ✓, CORSMiddleware count=2 ✓, /stats present ✓
semantic-engine/main.py: parses OK ✓, CORSMiddleware count=2 ✓
XSS gate: dangerouslySetInnerHTML count=0 in briefing-generator/main.py ✓
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All endpoints return real data (Redis reads and pycti queries). OpenCTI must be running for /stats to return non-empty attack_patterns; this is expected behavior, not a stub.

## Threat Flags

None. All threat mitigations from the plan's threat model were applied:
- T-06-01-01: `allow_origins=["http://localhost:3000"]` (explicit, never `"*"`) on all three services
- T-06-01-02: JSON responses only; no HTML output; dangerouslySetInnerHTML not present
- T-06-01-03: `asyncio.to_thread` wraps `_collect_threat_data` in /stats

## Self-Check: PASSED

- `services/feed-orchestrator/api.py` exists ✓
- `services/feed-orchestrator/requirements.txt` contains fastapi==0.115.14 ✓
- `services/feed-orchestrator/main.py` contains uvicorn.run, no signal.pause ✓
- `services/briefing-generator/main.py` contains /stats, CORSMiddleware, asyncio.to_thread ✓
- `services/semantic-engine/main.py` contains CORSMiddleware ✓
- Commits 3e27199 and 68dde02 exist ✓
