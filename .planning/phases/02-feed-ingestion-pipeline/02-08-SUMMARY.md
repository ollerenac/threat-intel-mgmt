---
phase: 02-feed-ingestion-pipeline
plan: "08"
subsystem: infra
tags: [docker, pycti, redis, apscheduler, integration]

requires:
  - phase: 02-feed-ingestion-pipeline
    provides: All 7 plans (02-01 through 02-07) — complete feed-orchestrator service

provides:
  - Live feed-orchestrator container (healthy) inserting IOCs into OpenCTI
  - Human-verified integration: URLhaus + Feodo IOCs visible in OpenCTI
  - Deduplication confirmed (22,656 tim:ioc_seen: keys; restart does not duplicate)
  - APScheduler confirmed (5 jobs registered; URLhaus fired on 1h schedule)

affects: [02-feed-ingestion-pipeline]

tech-stack:
  added: []
  patterns: [integration verification, human gate checkpoint]

key-files:
  created: []
  modified:
    - services/feed-orchestrator/Dockerfile (libmagic1 system dep added)
    - services/feed-orchestrator/feeds/urlhaus.py (explicit fieldnames for headerless CSV)
    - services/feed-orchestrator/feeds/base.py (use parsed datetime for valid_from)
    - services/feed-orchestrator/opencti_client.py (removed externalReferences dict — pycti expects IDs)

key-decisions:
  - "Build command requires --profile platform --profile feeds (feed-orchestrator depends_on opencti which has profiles:[platform])"
  - "externalReferences omitted — pycti 6.4.11 expects ID strings not dicts; source tracked via labels"
  - "URLhaus CSV has no non-comment header row — DictReader needs explicit fieldnames"
  - "valid_from must be passed as first_seen_dt.isoformat(), not raw feed string (space-separated dates fail OpenCTI GraphQL DateTime)"

patterns-established:
  - "Cross-profile docker compose: always use --profile platform --profile feeds for feed-orchestrator"
  - "pycti 6.4.x: externalReferences takes IDs, not inline dicts"

requirements-completed: [FEED-01, FEED-02, FEED-03, FEED-04, FEED-05, FEED-06]

coverage:
  - id: D1
    description: "URLhaus and Feodo IOCs visible in OpenCTI Indicators view"
    requirement: FEED-01
    verification:
      - kind: manual_procedural
        ref: "Human verified at http://localhost:8080 Observations > Indicators"
        status: pass
    human_judgment: true
    rationale: "Requires live OpenCTI UI inspection — cannot be automated without a browser test harness"
  - id: D2
    description: "Confidence values (15-100) present on all indicators"
    requirement: FEED-05
    verification:
      - kind: manual_procedural
        ref: "Human verified confidence column in OpenCTI Indicators list"
        status: pass
    human_judgment: true
    rationale: "Requires UI inspection of confidence field rendered by OpenCTI"
  - id: D3
    description: "Deduplication: 22,656 tim:ioc_seen: keys in Redis; restart does not double indicator count"
    requirement: FEED-04
    verification:
      - kind: manual_procedural
        ref: "docker compose exec redis redis-cli KEYS 'tim:ioc_seen:*' | wc -l → 22656"
        status: pass
    human_judgment: false
  - id: D4
    description: "APScheduler registers 5 feed jobs and fires URLhaus on 1h schedule"
    requirement: FEED-06
    verification:
      - kind: manual_procedural
        ref: "Logs: 'Added job URLhausFeed.run' x5 + 'Scheduler started' + scheduled fire at 10:44 UTC"
        status: pass
    human_judgment: false

duration: 75min (includes 3 bug fix cycles + 1h scheduler wait for confirmation)
completed: "2026-06-25"
status: complete
---

# Plan 02-08: Integration Verification Summary

**feed-orchestrator live: URLhaus + Feodo IOCs in OpenCTI, 22,656 dedup keys, 5 APScheduler jobs confirmed — 3 integration bugs found and fixed**

## Performance

- **Duration:** ~75 min (3 Dockerfile/code fix cycles + scheduler verification)
- **Tasks:** 2/2 (Task 1 auto, Task 2 human-approved)

## Accomplishments

- `docker compose --profile platform --profile feeds up -d feed-orchestrator` starts healthy container
- URLhaus: 22,600+ IOCs inserted on initial run; 30 new IOCs on 1h scheduled re-run (dedup working)
- Feodo: 2 C2 IP indicators inserted with correct `ipv4-addr:value` STIX patterns
- MalwareBazaar, ThreatFox: `status=disabled` (no auth keys set — correct per D-07)
- OTX: `status=ok` (API key present from Phase 2 setup)
- All 5 APScheduler jobs registered; URLhaus scheduled run fired at exactly T+1h
- Human-verified: IOCs visible in OpenCTI, confidence values present, restart did not duplicate

## Bug Fixes During Integration

**1. Missing libmagic1 system dependency**
- pycti imports `python-magic` which wraps the C library `libmagic1`
- `python:3.12-slim` does not include it; container crashed at startup
- Fix: `apt-get install -y --no-install-recommends libmagic1` added to Dockerfile

**2. URLhaus CSV has no non-comment header row**
- After filtering `#` lines, `DictReader` used the first data row as column names
- `row.get("url")` returned `""` for all rows → 0 indicators every run
- Fix: explicit `fieldnames=_URLHAUS_FIELDS` in `DictReader` call

**3. Space-separated datetime rejected by OpenCTI GraphQL**
- Feodo CSV dates (`"2022-06-04 21:24:53"`) passed raw to `create_indicator()`
- OpenCTI DateTime requires ISO 8601 T separator: `"2022-06-04T21:24:53+00:00"`
- Fix: pass `first_seen_dt.isoformat()` (already parsed in `_insert_deduplicated`) instead of raw string

**4. externalReferences format mismatch**
- pycti 6.4.11 `indicator.create()` expects external reference IDs (strings), not `{"source_name": "..."}` dicts
- Fix: removed `externalReferences` parameter; source identity tracked via labels and indicator name

## Task Commits

1. **Build + Redis verify** — integrated directly (no new source files)
2. **Bug fixes** — `12e32de`, `9f88867`, `3d0cf88` (fix commits post-integration)
3. **Human gate approved** — all 4 Phase 2 success criteria confirmed

## Decisions Made

- Use `--profile platform --profile feeds` for all feed-orchestrator compose commands (cross-profile dependency)
- `externalReferences` deferred — pycti parameter interface requires pre-created IDs; not critical for Phase 2 scope

## Next Phase Readiness

Phase 2 complete. OpenCTI now has live threat intelligence from URLhaus and Feodo (and OTX if key configured). Phase 4 (Semantic Search) can now index IOCs from OpenCTI. Phase 5 (Briefings) has live data to query.
