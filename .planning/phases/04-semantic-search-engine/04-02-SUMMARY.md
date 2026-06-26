---
phase: 04-semantic-search-engine
plan: "02"
subsystem: semantic-engine
tags: [foundation, dockerfile, config, pycti, docker-compose]
dependency_graph:
  requires: [04-01]
  provides: [semantic-engine-foundation]
  affects: [04-03-indexer, 04-04-searcher, 04-05-main]
tech_stack:
  added: [pycti==6.4.11, chromadb==1.5.9, ollama==0.6.2]
  patterns: [env-var-config, token-never-logged, pycti-client-init, updated_at-filter-fallback]
key_files:
  created:
    - services/semantic-engine/Dockerfile
    - services/semantic-engine/requirements.txt
    - services/semantic-engine/config.py
    - services/semantic-engine/opencti_client.py
  modified:
    - docker-compose.yml
decisions:
  - libmagic1 apt package required in semantic-engine Dockerfile — pycti==6.4.11 imports python-magic which needs libmagic.so even in a read-only client
  - OPENCTI_BASE_URL default is http://localhost:8080 (external browser URL), not http://opencti:8080 (internal Docker network URL)
  - healthcheck start_period=60s for semantic-engine vs 30s for intel-extractor — initial indexing adds startup latency
metrics:
  duration: 5m
  completed: "2026-06-26"
  tasks: 2
  files: 5
status: complete
---

# Phase 04 Plan 02: Service Foundation Summary

**One-liner:** Dockerfile, requirements.txt, config.py, and opencti_client.py for semantic-engine, plus SIMILARITY_THRESHOLD/OPENCTI_BASE_URL/healthcheck added to docker-compose.yml semantic-engine block.

## What Was Built

**Task 1 — Four service foundation files:**

- **Dockerfile** — `python:3.12-slim` + `libmagic1` (see Deviations) + pip install + port 8002
- **requirements.txt** — `fastapi==0.115.14`, `uvicorn`, `chromadb==1.5.9`, `ollama==0.6.2`, `pycti==6.4.11`, `pytest`, `pytest-mock`
- **config.py** — 8 env-var constants at import time: `OPENCTI_URL`, `OPENCTI_TOKEN`, `OPENCTI_BASE_URL`, `OLLAMA_URL`, `OLLAMA_EMBED_MODEL`, `CHROMADB_URL`, `SIMILARITY_THRESHOLD` (float, default 0.3), `POLL_INTERVAL_SECONDS` (int, default 300). Token logged as `bool()` only.
- **opencti_client.py** — `build_pycti_client()`, `list_all_indicators()` (getAll=True, first=500), `list_indicators_since()` with try/except fallback to full fetch on filter failure

**Task 2 — docker-compose.yml semantic-engine block:**

- Added `SIMILARITY_THRESHOLD=0.3` and `OPENCTI_BASE_URL=http://localhost:8080` to environment list
- Added `healthcheck` block using `python urllib.request` probe on port 8002 (`start_period: 60s`)

## Verification

```
$ docker build -t semantic-engine-test ./services/semantic-engine → exit 0
$ docker run --rm semantic-engine-test python -c "from config import SIMILARITY_THRESHOLD, OPENCTI_BASE_URL; assert SIMILARITY_THRESHOLD == 0.3; assert OPENCTI_BASE_URL == 'http://localhost:8080'" → OK
$ docker run --rm semantic-engine-test python -c "from opencti_client import build_pycti_client, list_all_indicators, list_indicators_since" → OK
$ docker compose config --quiet → exit 0 (2 env var warnings only — expected)
```

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| `libmagic1` in Dockerfile | pycti==6.4.11 transitively imports python-magic which loads libmagic.so at import time. The plan said to remove the apt-get line but the container fails without it. Same as intel-extractor. |
| `OPENCTI_BASE_URL` default = `http://localhost:8080` | External browser URL for analyst deep-links (AISEM-04). Different from internal Docker network `OPENCTI_URL=http://opencti:8080`. |
| `start_period: 60s` for healthcheck | Semantic-engine startup involves connecting to ChromaDB + Ollama; more dependencies than intel-extractor which starts in ~5s. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] libmagic1 required by pycti==6.4.11 in semantic-engine**

- **Found during:** Task 1 acceptance check
- **Issue:** Plan specified removing `apt-get libmagic1` line since semantic-engine has no file parsing need. However `pycti==6.4.11` imports `python-magic` internally, which wraps the C library `libmagic.so`. Container failed with `ImportError: failed to find libmagic` when running `from opencti_client import ...`.
- **Fix:** Restored the `apt-get install libmagic1` line in Dockerfile. Added `ponytail:` comment explaining why.
- **Files modified:** `services/semantic-engine/Dockerfile`
- **Commit:** 1bc58d7

## Known Stubs

None — this plan creates infrastructure (Dockerfile, config, client) not user-facing rendering logic.

## Threat Flags

No new trust boundaries introduced beyond what the threat model covers. `OPENCTI_TOKEN` is logged only as `bool()` per T-04-02-01. All packages are pinned to audited versions per T-04-02-SC.

## Self-Check

- [x] `services/semantic-engine/Dockerfile` — exists
- [x] `services/semantic-engine/requirements.txt` — exists
- [x] `services/semantic-engine/config.py` — exists
- [x] `services/semantic-engine/opencti_client.py` — exists
- [x] `docker-compose.yml` — SIMILARITY_THRESHOLD, OPENCTI_BASE_URL, healthcheck present at lines 313-321
- [x] Commit 1bc58d7 (Task 1) present in git log
- [x] Commit 8bfd92d (Task 2) present in git log

## Self-Check: PASSED
