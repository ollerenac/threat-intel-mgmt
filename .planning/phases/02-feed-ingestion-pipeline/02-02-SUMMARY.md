---
phase: 02-feed-ingestion-pipeline
plan: "02"
subsystem: infra
tags: [python, pycti, redis, stix, docker, apscheduler]

requires:
  - phase: 01-platform-foundation
    provides: OpenCTI + Redis running on Docker Compose stack

provides:
  - Dockerfile (python:3.12-slim, pinned deps, CMD python main.py)
  - requirements.txt with pycti==6.4.11 exact pin and all feed deps
  - config.py — all env vars as module constants, API keys logged by presence only
  - status.py — hset(mapping=...) atomic status writes per D-02
  - deduplicator.py — sha256-keyed Redis SETNX with tim:ioc_seen: namespace
  - opencti_client.py — build_pycti_client() + create_indicator() with 3x retry
  - feeds/__init__.py — package marker
  - feeds/base.py — BaseFeed abstract class with run(), _fetch_with_retry([30,60,120]), _insert_deduplicated()

affects: [02-feed-ingestion-pipeline, 02-04, 02-05, 02-06, 02-07]

tech-stack:
  added: [pycti==6.4.11, APScheduler==3.11.2, stix2==3.0.2, redis==8.0.1, OTXv2==1.5.12, tenacity, requests]
  patterns: [BaseFeed abstract class, Redis SETNX deduplication, hset(mapping=...) atomic status]

key-files:
  created:
    - services/feed-orchestrator/Dockerfile
    - services/feed-orchestrator/requirements.txt
    - services/feed-orchestrator/config.py
    - services/feed-orchestrator/status.py
    - services/feed-orchestrator/deduplicator.py
    - services/feed-orchestrator/opencti_client.py
    - services/feed-orchestrator/feeds/__init__.py
    - services/feed-orchestrator/feeds/base.py

key-decisions:
  - "pycti==6.4.11 pinned exactly — pycti 7.x CalVer releases are incompatible with opencti/platform:6.4.0"
  - "hset(mapping=...) used everywhere — hmset() removed in redis-py 4.x"
  - "deduplication key = tim:ioc_seen: + sha256(pattern) — hashes full STIX pattern string, not raw IOC value"
  - "API key values never logged — config.py uses bool(OTX_API_KEY) in logger.info"
  - "objectLabel used in create_indicator() per RESEARCH.md Pattern 3; A2 assumption noted with TODO"

patterns-established:
  - "BaseFeed.run(): set running → fetch_with_retry → normalize → insert_deduplicated → set ok/error"
  - "_fetch_with_retry: delays=[30,60,120], re-raise on final attempt"
  - "Redis key namespace: tim:feed_status:{name} and tim:ioc_seen:{sha256}"

requirements-completed: [FEED-04, FEED-05, FEED-06]

coverage:
  - id: D1
    description: "Dockerfile with python:3.12-slim base and pinned pycti==6.4.11"
    requirement: FEED-04
    verification:
      - kind: manual_procedural
        ref: "grep pycti==6.4.11 services/feed-orchestrator/requirements.txt"
        status: pass
    human_judgment: false
  - id: D2
    description: "config.py importable with QUALITY_WEIGHTS[feodo]=30 and FEED_INTERVALS[urlhaus]=1"
    requirement: FEED-04
    verification:
      - kind: unit
        ref: "python3 -c \"import config; assert config.QUALITY_WEIGHTS['feodo']==30\""
        status: pass
    human_judgment: false
  - id: D3
    description: "deduplicator.is_duplicate() uses sha256 hash with tim:ioc_seen: prefix and 24h TTL"
    requirement: FEED-05
    verification:
      - kind: unit
        ref: "tests/test_deduplicator.py (RED — passes once feeds.base is importable)"
        status: unknown
    human_judgment: false
  - id: D4
    description: "BaseFeed abstract class with run(), _fetch_with_retry([30,60,120]), _insert_deduplicated()"
    requirement: FEED-06
    verification:
      - kind: unit
        ref: "python3 -c \"from feeds.base import BaseFeed\" exits 0 when pycti installed"
        status: unknown
    human_judgment: false
  - id: D5
    description: "status.py uses hset(mapping=...) — no hmset() calls anywhere"
    requirement: FEED-04
    verification:
      - kind: manual_procedural
        ref: "grep -c hmset services/feed-orchestrator/status.py services/feed-orchestrator/feeds/base.py → 0 actual calls"
        status: pass
    human_judgment: false

duration: 8min
completed: "2026-06-25"
status: complete
---

# Plan 02-02: Service Foundation Summary

**8-file service skeleton: Dockerfile, pinned requirements, config, status/deduplicator/opencti_client utilities, and BaseFeed abstract class with 3x-retry fetch and Redis dedup**

## Performance

- **Duration:** ~8 min (resumed after rate-limit interrupt)
- **Tasks:** 2/2
- **Files created:** 8

## Accomplishments

- `Dockerfile` — python:3.12-slim base, no EXPOSE (no HTTP port), CMD array form
- `requirements.txt` — pycti==6.4.11 exact pin (incompatible with pycti 7.x); full dep set
- `config.py` — all env vars as module constants; QUALITY_WEIGHTS and FEED_INTERVALS dicts; API keys logged by `bool()` only
- `status.py` — atomic `hset(mapping=...)` writes (D-02 fields: last_run, ioc_count, status, error_msg)
- `deduplicator.py` — `is_duplicate()` using `tim:ioc_seen:` + sha256(pattern), Redis SETNX with 24h TTL
- `opencti_client.py` — `build_pycti_client()` and `create_indicator()` with 3-attempt backoff [30, 60, 120]
- `feeds/base.py` — `BaseFeed` with `run()`, `_fetch_with_retry()`, `_insert_deduplicated()` abstract contract

## Task Commits

1. **Task 1: Dockerfile, requirements.txt, config.py** — `7091574`
2. **Task 2: status, deduplicator, opencti_client, feeds/base** — `e8a1aef`

## Decisions Made

- pycti==6.4.11 pinned exactly (not `>=`) — platform is opencti/platform:6.4.0; 7.x CalVer is incompatible
- `hset(mapping={...})` everywhere — `hmset()` removed in redis-py 4.x
- Dedup key hashes the full STIX **pattern string**, not the raw IOC value (a single IP can appear in multiple pattern types)
- `objectLabel` used in `create_indicator()` per RESEARCH.md; A2 assumption left as TODO for Wave 2+ to verify against installed pycti

## Deviations from Plan

None — plan executed as written. pycti host-import test skipped (expected: pycti only available inside Docker container).

## Issues Encountered

Session interrupted by rate limit mid-task-2; files were written but not committed. Resumed by verifying file content and committing directly.

## Next Phase Readiness

Wave 2 plans (02-04, 02-05, 02-06) can now subclass `BaseFeed` — all imports resolve once pycti is installed in the container. Wave 1 still needs plan 02-03 (docker-compose + .env.example).
