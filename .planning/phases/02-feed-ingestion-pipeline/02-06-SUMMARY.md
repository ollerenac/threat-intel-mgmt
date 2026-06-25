---
phase: 02-feed-ingestion-pipeline
plan: "06"
subsystem: feed-parser
tags: [python, otx, stix, otxv2-sdk, threat-intel]

requires:
  - phase: 02-feed-ingestion-pipeline
    plan: "02"
    provides: BaseFeed abstract class, config.py with OTX_API_KEY and QUALITY_WEIGHTS

provides:
  - feeds/otx.py — OTXFeed subclass with time-bounded fetch, 7-type STIX mapping, disabled-if-no-key

affects: [02-feed-ingestion-pipeline, main.py build_enabled_feeds()]

tech-stack:
  added: []
  patterns:
    - OTXv2 SDK getall(modified_since=...) — always time-bounded (interval_hours+1)
    - OTX_TYPE_MAP module-level constant — 7 indicator type → STIX pattern mappings
    - disabled-if-no-key pattern (D-07) matching malwarebazaar.py

key-files:
  created:
    - services/feed-orchestrator/feeds/otx.py

key-decisions:
  - "modified_since window = interval_hours+1 hours — absorbs scheduler jitter (Pitfall 6)"
  - "OTX_TYPE_MAP is module-level, not a method — tests import it directly"
  - "Single quotes escaped in val_safe before STIX interpolation (T-02-06-02)"
  - "OTX_API_KEY passed directly to OTXv2() constructor, never stored on self"

metrics:
  duration: 5min
  completed: "2026-06-25"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0

status: complete
---

# Phase 02 Plan 06: OTX Feed Parser Summary

**OTXFeed with time-bounded pulse fetch (modified_since), 7-type STIX indicator mapping, single-quote hash escaping, and disabled-if-no-key pattern**

## Performance

- **Duration:** ~5 min
- **Tasks:** 1/1
- **Files created:** 1

## Accomplishments

- `feeds/otx.py` — OTXFeed subclass of BaseFeed
- `OTX_TYPE_MAP` — module-level dict with 7 entries: IPv4, domain, hostname, URL, FileHash-MD5, FileHash-SHA256, FileHash-SHA1
- `fetch()` — builds OTXv2 client, computes `modified_since = now - (interval_hours+1)h`, calls `otx.getall(modified_since=since_str)`, flattens pulses into indicators with `_pulse_name` tag
- `_parse_indicator()` — escapes single quotes in indicator values before STIX pattern interpolation; returns None for unmapped types
- `normalize()` — filters None results from `_parse_indicator`
- `run()` — returns early with `status=disabled` when `OTX_API_KEY` is empty (D-07 pattern, matches malwarebazaar.py exactly)
- All 4 tests in `test_otx.py` pass GREEN

## Task Commits

1. **Task 1: OTXFeed implementation** — `219f0e1`

## Threat Mitigations Applied

| Threat | Mitigation |
|--------|-----------|
| T-02-06-01 (DoS — unbounded getall) | `modified_since=interval_hours+1` always passed; no bare `getall()` call |
| T-02-06-02 (STIX pattern injection) | `val_safe = ind_value.replace("'", "\\'")` before interpolation |
| T-02-06-03 (API key disclosure) | Key passed to `OTXv2()` constructor only; never stored on `self`; log only presence check |

## Deviations from Plan

**Auto-install: OTXv2==1.5.12 on host Python**

The `test_otx.py` imports `from feeds.otx import OTXFeed` which triggers `from OTXv2 import OTXv2` at module level. OTXv2 was not installed on the host Python (only in the Docker container per requirements.txt). Installed it via `pip3 install OTXv2==1.5.12` to run the test suite locally. This matches the pinned version in requirements.txt and is not a new dependency.

**Plan verification check `grep -c "getall()"` returns 2 not 0**

Both matches are in comments (docstring + inline comment), not in executable code. The actual call is `otx.getall(modified_since=since_str)`. The unbounded-call guard is correctly implemented.

## Known Stubs

None — OTXFeed is fully wired. `valid_from` uses `ind.get("expiration", "")` which may be empty for many OTX indicators; this is expected (BaseFeed accepts empty valid_from).

## Self-Check: PASSED

- [x] `services/feed-orchestrator/feeds/otx.py` exists
- [x] Commit `219f0e1` exists in git log
- [x] `tests/test_otx.py`: 4/4 GREEN
