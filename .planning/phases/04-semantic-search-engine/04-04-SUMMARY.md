---
phase: 04-semantic-search-engine
plan: "04"
subsystem: semantic-engine
tags: [fastapi, chromadb, ollama, semantic-search, embeddings]
status: complete

dependency_graph:
  requires: [04-03]
  provides: [04-05]
  affects: [services/semantic-engine]

tech_stack:
  added: []
  patterns:
    - asynccontextmanager lifespan for startup background tasks (FastAPI 0.115)
    - cosine distance → similarity conversion (score = 1 - distance)
    - similarity threshold filter applied to score (not raw distance)
    - module-level Ollama singleton with optional client injection for tests

key_files:
  created:
    - services/semantic-engine/searcher.py
    - services/semantic-engine/main.py
  modified: []

decisions:
  - "D-05: lifespan asyncio.create_task fires run_index_loop() without blocking /health"
  - "D-06: n_results=10 default in /search endpoint"
  - "D-07: SIMILARITY_THRESHOLD=0.3 applied to score (1-distance), not raw distance"
  - "D-08: embedded_text key returned in each search result so analyst sees why IOC matched"
  - "score = round(1.0 - dist, 4) — cosine distance converted to similarity (RESEARCH Pitfall 1)"

metrics:
  duration: "2m"
  completed: "2026-06-26"
  tasks_completed: 2
  files_created: 2
---

# Phase 4 Plan 4: Searcher + FastAPI App Summary

FastAPI semantic-engine service completed: searcher.py converts ChromaDB cosine distances to similarity scores with threshold filtering; main.py wires lifespan startup indexing, /health, and /search with input validation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | searcher.py — embed_query + search with score conversion | 9ef57fe | services/semantic-engine/searcher.py |
| 2 | main.py — FastAPI app with lifespan, /health, /search | 3055e36 | services/semantic-engine/main.py |

## What Was Built

### searcher.py
- `embed_query(text, ollama_client=None)`: embeds query text via Ollama; uses `response.embeddings[0]` (plural, not deprecated `.embedding` singular)
- `search(collection, query, ollama_client=None, n_results=10, threshold=0.3)`: queries ChromaDB, converts distance to similarity score (`round(1.0 - dist, 4)`), filters on `score < threshold` (not `dist >`), returns list of dicts with `ioc_type`, `value`, `score`, `opencti_url`, `embedded_text`
- ChromaDB returns results ordered by distance ascending → output is already ranked by score descending

### main.py
- `asynccontextmanager` lifespan fires `asyncio.create_task(indexer.run_index_loop())` — non-blocking startup
- `GET /health`: spreads `indexer.index_state` dict immediately (never awaits indexer)
- `GET /search?q=<query>`: validates `q` non-empty (400) and `len(q) <= 500` (400 DoS guard), calls `searcher.search()` with `SIMILARITY_THRESHOLD` from config, returns `{query, results, count}`

## Verification

```
python3 -m pytest tests/ -v
8 passed in 1.92s (4 test_indexer + 4 test_searcher)
```

Source invariants confirmed:
- `1.0 - dist` present in searcher.search() source
- `dist >` not present in searcher.search() source (filter is on score)
- `asynccontextmanager` and `asyncio.create_task` in main.py
- `status_code=400` and `len(q) > 500` in main.py
- `BackgroundTasks` absent from main.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring mentioned `dist > threshold` pattern**
- **Found during:** Task 1 acceptance criteria check (`assert 'dist >' not in src`)
- **Issue:** The function docstring in `search()` contained the text "not dist > threshold" as a negative example, causing the source-level assertion to fail
- **Fix:** Rephrased to "not on raw distance" — removes the `dist >` text while preserving the intent
- **Files modified:** services/semantic-engine/searcher.py
- **Commit:** 9ef57fe (same commit, fixed before commit)

## Known Stubs

None — both modules are fully wired. `searcher.search()` calls a real ChromaDB collection and Ollama client. `main.py` calls `indexer.get_collection()` and `searcher.search()` with live config values.

## Threat Flags

No new trust boundaries introduced beyond what the threat model covers. Input validation for T-04-04-01 (non-empty q) and T-04-04-03 (500-char cap) implemented before any Ollama call.

## Self-Check: PASSED

Files exist:
- services/semantic-engine/searcher.py ✓
- services/semantic-engine/main.py ✓

Commits exist:
- 9ef57fe (searcher.py) ✓
- 3055e36 (main.py) ✓

8/8 tests pass ✓
