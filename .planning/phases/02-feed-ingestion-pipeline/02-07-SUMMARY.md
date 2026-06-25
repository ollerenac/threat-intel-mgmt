---
phase: 02-feed-ingestion-pipeline
plan: "07"
subsystem: feed-orchestrator-wiring
tags: [python, confidence-scoring, apscheduler, stix, normalizer]

requires:
  - phase: 02-feed-ingestion-pipeline
    plan: "02"
    provides: BaseFeed abstract class, config.py with QUALITY_WEIGHTS
  - phase: 02-feed-ingestion-pipeline
    plan: "04"
    provides: feeds/urlhaus.py, feeds/feodo.py
  - phase: 02-feed-ingestion-pipeline
    plan: "05"
    provides: feeds/malwarebazaar.py, feeds/threatfox.py
  - phase: 02-feed-ingestion-pipeline
    plan: "06"
    provides: feeds/otx.py

provides:
  - normalizer.py — D-09 confidence formula, parse_first_seen, OBSERVABLE_TYPE_MAP
  - scheduler.py — BackgroundScheduler with 1 job/feed, max_instances=1
  - main.py — service entry point, D-06 startup sequence
  - feeds/base.py (modified) — compute_confidence wired into _insert_deduplicated

affects: [02-feed-ingestion-pipeline, FEED-05, FEED-06]

tech-stack:
  added: []
  patterns:
    - D-09 confidence formula: seen_in_feeds*25 + recency_bonus + quality_weight, capped at 100
    - APScheduler BackgroundScheduler with threadpool executor, max_instances=1, coalesce=True
    - D-06 startup: all feeds run synchronously before scheduler.start()
    - Lazy import of compute_confidence in base.py avoids circular-import at module load

key-files:
  created:
    - services/feed-orchestrator/normalizer.py
    - services/feed-orchestrator/scheduler.py
    - services/feed-orchestrator/main.py
  modified:
    - services/feed-orchestrator/feeds/base.py

key-decisions:
  - "D-09 formula locked: min(100, seen_in_feeds*25 + max(0,10-days_old) + quality_weight)"
  - "Lazy import from normalizer in _insert_deduplicated avoids circular dependency at module load"
  - "D-06: immediate feed runs complete before scheduler.start() — T-02-07-02 mitigation"
  - "signal.pause() with threading.Event fallback for Windows portability"
  - "All 5 feeds returned from build_enabled_feeds(); disabled-if-no-key handled in each feed.run()"

metrics:
  duration: 8min
  completed: "2026-06-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 1

status: complete
---

# Phase 02 Plan 07: Normalizer, Scheduler, and Main Entry Point Summary

**D-09 confidence scoring formula wired end-to-end; APScheduler with immediate startup run; complete 5-feed service entry point**

## Performance

- **Duration:** ~8 min
- **Tasks:** 2/2
- **Files created:** 3
- **Files modified:** 1

## Accomplishments

### Task 1: normalizer.py (D-09 formula)

- `compute_confidence(feed_name, first_seen_dt, seen_in_feeds=1) -> int` — D-09 formula: `min(100, seen_in_feeds*25 + max(0, 10-days_old) + QUALITY_WEIGHTS.get(feed_name, 10))`
- `parse_first_seen(date_str) -> datetime` — handles ISO-8601 with Z suffix, +00:00 offset, bare YYYY-MM-DD, and empty strings (returns now UTC)
- `OBSERVABLE_TYPE_MAP` — `url→Url, domain-name→Domain-Name, ipv4-addr→IPv4-Addr, file→StixFile`
- All 5 `test_normalizer.py` tests GREEN: feodo-new=65, otx-7d=53, cap=100, floor-at-zero=40, unknown-feed=45

### Task 2: scheduler.py + main.py + base.py wiring

- `scheduler.py` — `build_scheduler(feeds, redis_client, pycti_client)`: BackgroundScheduler with threadpool(max_workers=5), job_defaults coalesce=True/max_instances=1/misfire_grace_time=60; one interval job per feed with jitter=60; listener logs ERROR|MISSED events; returns unconfigured scheduler (caller starts it)
- `main.py` — D-06 startup: `build_redis_client() → build_pycti_client() → build_enabled_feeds() → for feed in feeds: feed.run() → scheduler.start() → signal.pause()`; root logger configured with INFO level
- `feeds/base.py` — `_insert_deduplicated()` now uses lazy import `from normalizer import compute_confidence, parse_first_seen`; computes confidence per-indicator before create_indicator() call

## Task Commits

1. **Task 1: normalizer.py** — `e9eae79`
2. **Task 2: scheduler + main + base wiring** — `3224e81`

## Verification Results

```
services/feed-orchestrator $ python3 -m pytest tests/ -q
25 passed in 0.28s
```

Formula spot-checks:
- `compute_confidence("feodo", today, 1)` == 65 ✓
- `compute_confidence("otx", 7_days_ago, 1)` == 53 ✓
- `compute_confidence("feodo", today, 3)` == 100 (capped) ✓
- `scheduler.start()` line 68, after `feed.run()` loop line 65 ✓
- `grep -c "D-06" main.py` == 2 ✓
- `grep -c "max_instances" scheduler.py` == 2 ✓
- `grep -n "compute_confidence" feeds/base.py` lines 138, 148 ✓

## Threat Mitigations Applied

| Threat | Mitigation |
|--------|-----------|
| T-02-07-01 (DoS — 5 feeds simultaneous startup) | Sequential for-loop; max_instances=1 per scheduler job |
| T-02-07-02 (APScheduler concurrent run before immediate runs finish) | scheduler.start() called only after all feed.run() calls complete |
| T-02-07-03 (confidence formula reveals quality weights) | accepted — QUALITY_WEIGHTS are metadata, not secrets |

## Deviations from Plan

**Host-side APScheduler and redis install**

APScheduler==3.11.2 and redis==5.2.1 were not installed on host Python (only in Docker container per requirements.txt). Installed locally to run the verification import check. Not a new dependency.

## Known Stubs

None — all three modules are fully wired. The service is end-to-end complete.

## Self-Check: PASSED

- [x] `services/feed-orchestrator/normalizer.py` exists
- [x] `services/feed-orchestrator/scheduler.py` exists
- [x] `services/feed-orchestrator/main.py` exists
- [x] `feeds/base.py` contains `compute_confidence` on lines 138, 148
- [x] Commit `e9eae79` exists (normalizer)
- [x] Commit `3224e81` exists (scheduler + main + base)
- [x] 25/25 tests GREEN
