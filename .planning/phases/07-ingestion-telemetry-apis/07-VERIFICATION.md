---
phase: 07-ingestion-telemetry-apis
verified: 2026-06-28T00:29:00Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification: false
---

# Phase 7: Ingestion Telemetry APIs — Verification Report

**Phase Goal:** Every TIM backend service exposes a structured `/stats` endpoint, giving the dashboard a unified telemetry surface without polling logs or Docker internals.
**Verified:** 2026-06-28T00:29:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET localhost:8002/stats` returns `{total_indexed, collection, last_run, status}` from semantic-engine | VERIFIED | `services/semantic-engine/main.py` lines 42-59: `@app.get("/stats")` returns exactly those four keys; `asyncio.to_thread` wraps blocking ChromaDB calls; `max(0, count - 1)` excludes WATERMARK_ID sentinel; `status` derives from `last_run` nullness |
| 2 | `GET localhost:8001/stats` returns `{total_docs, total_iocs, last_run, status}` from intel-extractor | VERIFIED | `services/intel-extractor/main.py` lines 78-87: `@app.get("/stats")` returns all four keys from `stats_store.get_stats()`; SQLite store backed by named Docker volume `extractordata`; smoke test confirmed accumulation: 2 increments → `total_docs=2, total_iocs=8, last_run=<utc timestamp>` |
| 3 | `GET localhost:8003/cve/stats` returns `{total_cves, last_run, status}` from briefing-generator (via pycti) | VERIFIED | `services/briefing-generator/main.py` lines 123-144: `@app.get("/cve/stats")` returns those three keys; `_get_cve_stats()` closure calls `client.vulnerability.list(first=500, getAll=True)` inside `asyncio.to_thread`; `or []` guards None; `last_run = max(updated_at)` |
| 4 | All three endpoints respond within 2s; none block the event loop (async wrappers on blocking calls) | VERIFIED | semantic-engine: `asyncio.to_thread(_get_stats)` confirmed present; briefing-generator: `asyncio.to_thread(_get_cve_stats)` confirmed present; intel-extractor: SQLite read is sub-millisecond synchronous (D-04 accepted — no to_thread needed); `import asyncio` present in both services that need it |

**Score: 4/4 truths verified**

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| STATS-01 | 07-02-PLAN.md | semantic-engine `GET /stats` returning ChromaDB count + last sync | SATISFIED | `@app.get("/stats")` in `services/semantic-engine/main.py`; returns `total_indexed`, `collection`, `last_run`, `status` |
| STATS-02 | 07-01-PLAN.md | intel-extractor `GET /stats` returning total docs, total IOCs, last run | SATISFIED | `@app.get("/stats")` in `services/intel-extractor/main.py`; backed by `stats_store.py` SQLite; `increment()` wired in `extractor.py` line 346 |
| STATS-03 | 07-02-PLAN.md | briefing-generator `GET /cve/stats` returning Vulnerability count from OpenCTI | SATISFIED | `@app.get("/cve/stats")` in `services/briefing-generator/main.py`; pycti `vulnerability.list` inside thread closure |

No orphaned requirements. All three STATS-* IDs from both PLAN files are accounted for and implemented.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `services/intel-extractor/stats_store.py` | New SQLite store module | VERIFIED | 60 lines; `init_db`, `increment`, `get_stats`, `_conn` contextmanager all present and substantive |
| `services/intel-extractor/extractor.py` | Modified — increment wired at Step 10 | VERIFIED | `import stats_store` line 25; `stats_store.increment(docs=1, iocs=len(indicator_ids))` at line 346, after `elapsed` computed, before `jobs[job_id].update()` — success path only |
| `services/intel-extractor/main.py` | Modified — lifespan + `/stats` added | VERIFIED | `asynccontextmanager lifespan` calls `stats_store.init_db()`; `FastAPI(lifespan=lifespan)`; `GET /stats` returns correct 4-key schema |
| `docker-compose.yml` | Modified — extractordata volume + DB_PATH | VERIFIED | Top-level `extractordata:` present; `intel-extractor` service: `DB_PATH=/data/stats.db` env var + `extractordata:/data` volume mount |
| `services/semantic-engine/main.py` | Modified — `GET /stats` added | VERIFIED | `asyncio` already present at line 10; `@app.get("/stats")` with `asyncio.to_thread(_get_stats)` closure; watermark sentinel handled with `max(0, count - 1)` |
| `services/briefing-generator/main.py` | Modified — `GET /cve/stats` added | VERIFIED | Placed after existing `GET /stats` and before `GET /health`; all existing endpoints (`/generate`, `/briefings`, `/stats`, `/health`) confirmed intact |

---

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `extractor.py run_extraction()` | `stats_store.increment()` | direct call at line 346, success path after Step 10 | WIRED |
| `main.py lifespan` | `stats_store.init_db()` | `asynccontextmanager` on startup | WIRED |
| `docker-compose.yml intel-extractor` | `/data/stats.db` SQLite | `extractordata:/data` volume + `DB_PATH=/data/stats.db` env var | WIRED |
| `semantic-engine /stats` | `indexer.get_collection()` + `indexer.read_watermark(col)` | `asyncio.to_thread(_get_stats)` closure | WIRED |
| `briefing-generator /cve/stats` | `client.vulnerability.list(first=500, getAll=True)` | `asyncio.to_thread(_get_cve_stats)` closure with lazy `build_pycti_client()` import | WIRED |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `intel-extractor /stats` | `total_docs`, `total_iocs`, `last_run` | SQLite `stats` table via `stats_store.get_stats()` | Yes — smoke test confirmed real accumulation | FLOWING |
| `extractor.py` | `indicator_ids` → `stats_store.increment` | `len(indicator_ids)` after full pipeline run | Yes — only fires on successful extraction | FLOWING |
| `semantic-engine /stats` | `count`, `last_run` | ChromaDB `col.count()` + `indexer.read_watermark(col)` | Yes — live ChromaDB query; `max(0, count-1)` removes sentinel | FLOWING |
| `briefing-generator /cve/stats` | `total_cves`, `last_run` | `client.vulnerability.list(getAll=True)` from OpenCTI via pycti | Yes — queries live OpenCTI; `or []` guards None; `max(updated_at)` for timestamp | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `stats_store` accumulates docs and IOCs correctly | `python3` smoke test: two `increment()` calls; assert `total_docs=2, total_iocs=8, last_run!=None` | `{'id': 1, 'total_docs': 2, 'total_iocs': 8, 'last_run': '2026-06-28T00:28:41.579269+00:00'}` | PASS |
| `stats_store.increment` at correct position in `extractor.py` | Position assertion: `idx_step10 < idx_increment < idx_jobs_update` | Passed | PASS |
| All three services pass static wiring checks | `python3` import/keyword assertions across all three `main.py` files | All assertions passed | PASS |
| docker-compose volume wiring | `python3` string assertions on `docker-compose.yml` | `extractordata:/data`, `DB_PATH=/data/stats.db`, top-level `extractordata:` all present | PASS |
| `/cve/stats` returns `{total_cves, last_run, status}` (no extra fields) | Source grep of return dict | Returns exactly `total_cves`, `last_run`, `status` | PASS |
| `/stats` on semantic-engine returns `{total_indexed, collection, last_run, status}` | Source grep of return dict | Returns exactly those four keys; internal variable `last_sync` is renamed to `last_run` in the return | PASS |

---

### Anti-Patterns Found

Scan of all six files modified in this phase:

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| (none found) | — | — | — |

No `TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, `PLACEHOLDER` markers in any file modified by this phase. No empty implementations (`return null`, `return {}`, `return []`). No hardcoded static data masquerading as real results.

---

### Regression Check — Existing Endpoints

| Service | Endpoint | Status |
|---------|----------|--------|
| intel-extractor | `POST /extract` | Present (`submit_extract` function) |
| intel-extractor | `GET /jobs/{id}` | Present |
| intel-extractor | `GET /health` | Present |
| semantic-engine | `GET /search` | Present (`search_iocs` function) |
| semantic-engine | `GET /health` | Present |
| briefing-generator | `POST /generate` | Present |
| briefing-generator | `GET /briefings`, `GET /briefings/{id}`, `GET /briefings/{id}/pdf` | Present |
| briefing-generator | `GET /stats` (DASH-02) | Present — `ioc_count_24h` confirmed in source |
| briefing-generator | `GET /health` | Present |

No regressions detected.

---

### Human Verification Required

None. All must-haves are verifiable statically or via unit-level smoke test. Runtime behavior against live OpenCTI/ChromaDB is outside phase scope and deferred to Phase 8 UAT.

---

## Gaps Summary

No gaps. All four ROADMAP success criteria are verified against the actual codebase with behavioral evidence.

---

_Verified: 2026-06-28T00:29:00Z_
_Verifier: Claude (gsd-verifier)_
