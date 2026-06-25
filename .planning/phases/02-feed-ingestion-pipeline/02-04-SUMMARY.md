---
phase: 02-feed-ingestion-pipeline
plan: "04"
subsystem: feed-orchestrator
tags: [python, csv, stix, urlhaus, feodo, tdd, security]

dependency_graph:
  requires:
    - phase: 02-feed-ingestion-pipeline
      plan: "02"
      provides: BaseFeed abstract class, config.py QUALITY_WEIGHTS/FEED_INTERVALS
  provides:
    - services/feed-orchestrator/feeds/urlhaus.py (URLhausFeed — FEED-01)
    - services/feed-orchestrator/feeds/feodo.py (FeodoFeed — FEED-02c)
  affects:
    - 02-07 (main.py build_enabled_feeds() registers both parsers)
    - 02-08 (integration test runs both feeds end-to-end)

tech-stack:
  added: []
  patterns:
    - CSV comment-skip filter before DictReader: [l for l in text.splitlines() if not l.startswith("#")]
    - STIX pattern injection guard: value.replace("'", "\\'") before f-string interpolation
    - BaseFeed subclass with only fetch() + normalize() overridden (run() inherited)

key-files:
  created:
    - services/feed-orchestrator/feeds/urlhaus.py
    - services/feed-orchestrator/feeds/feodo.py
  modified: []

key-decisions:
  - "CSV comment-skip applied before DictReader — not inside DictReader — to avoid header row misparse"
  - "Feodo 'c2' label hardcoded unconditionally — all Feodo entries are confirmed botnet C2 servers per feed design"
  - "valid_from passes raw string to opencti_client — create_indicator() handles None/empty per Plan 02 contract"
  - "name field in normalized dict set to escaped IOC value (reuses pattern value) — sufficient for OpenCTI indicator name"

requirements-completed: [FEED-01, FEED-02]

metrics:
  duration: "~5 min"
  completed: "2026-06-25"
  tasks_completed: 2
  files_created: 2
  files_modified: 0

status: complete
---

# Phase 02 Plan 04: CSV Feed Parsers (URLhaus + Feodo) Summary

**One-liner:** URLhausFeed and FeodoFeed — two CSV-based threat parsers inheriting BaseFeed, normalizing to STIX patterns with single-quote injection guards, both fully GREEN under pytest.

## Performance

- **Duration:** ~5 min
- **Tasks:** 2/2
- **Files created:** 2

## Accomplishments

### Task 1: URLhausFeed (commit 25c4a46)

- `feeds/urlhaus.py` — URLhausFeed(BaseFeed) with:
  - `fetch()`: GET `https://urlhaus.abuse.ch/downloads/csv_recent/` with timeout=30, skip `#` comment lines, parse with csv.DictReader
  - `normalize()`: maps `url` → `[url:value = '...']` STIX pattern, splits comma-separated `tags` into labels, skips empty-url rows
  - `name="urlhaus"`, `quality_weight=15`, `interval_hours=1`
  - Single-quote escape: `url.replace("'", "\\'")` applied before pattern interpolation

### Task 2: FeodoFeed (commit ebb8df1)

- `feeds/feodo.py` — FeodoFeed(BaseFeed) with:
  - `fetch()`: GET `https://feodotracker.abuse.ch/downloads/ipblocklist.csv` with timeout=30, same comment-skip pattern
  - `normalize()`: maps `dst_ip` → `[ipv4-addr:value = '...']` STIX pattern, always includes `"c2"` label, appends malware family if present, skips empty-ip rows
  - `name="feodo"`, `quality_weight=30` (highest — manually curated C2 blocklist), `interval_hours=4`
  - Single-quote escape: `dst_ip.replace("'", "\\'")` applied before pattern interpolation

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement URLhausFeed | 25c4a46 | feeds/urlhaus.py |
| 2 | Implement FeodoFeed | ebb8df1 | feeds/feodo.py |

## Verification Results

All success criteria met:

- [x] `test_urlhaus.py`: 3/3 tests GREEN
- [x] `test_feodo.py`: 3/3 tests GREEN
- [x] `URLhausFeed.name == "urlhaus"`, `quality_weight == 15`
- [x] `FeodoFeed.name == "feodo"`, `quality_weight == 30`
- [x] Both `fetch()` methods skip `#` comment lines
- [x] Both `normalize()` methods escape single quotes (`grep -c "replace.*\\'" *.py` → 1 each)
- [x] `"c2"` label hardcoded in FeodoFeed (`grep -c '"c2"' feeds/feodo.py` → 2: assignment + comment)
- [x] `from feeds.urlhaus import URLhausFeed; from feeds.feodo import FeodoFeed` both import cleanly

## Decisions Made

- CSV comment-skip applied as a list comprehension before csv.DictReader — ensures the first non-comment line becomes the header row for field mapping
- `"c2"` label always first in the labels list — Feodo exclusively tracks botnet C2 infrastructure; this is not optional
- `valid_from` passed as raw string from CSV — `create_indicator()` in opencti_client.py handles empty/None gracefully

## Deviations from Plan

None — plan executed exactly as written. Both feeds implement fetch() and normalize() only; run() is fully inherited from BaseFeed.

## Threat Surface Scan

Both files implement T-02-04-01 mitigation (STIX pattern injection) via `.replace("'", "\\'")` on all IOC values before string interpolation. T-02-04-02 (timeout=30 on requests.get) and T-02-04-03 (comment-line filter) are also implemented. No new threat surface introduced beyond what the plan's threat model covers.

## Known Stubs

None.

## Self-Check: PASSED

Files verified on disk:
- `services/feed-orchestrator/feeds/urlhaus.py` — FOUND
- `services/feed-orchestrator/feeds/feodo.py` — FOUND

Commits verified in git log:
- `25c4a46` — URLhausFeed
- `ebb8df1` — FeodoFeed
