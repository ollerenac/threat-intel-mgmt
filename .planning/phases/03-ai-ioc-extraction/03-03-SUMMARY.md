---
phase: 03-ai-ioc-extraction
plan: "03"
subsystem: intel-extractor
status: complete
tags: [pycti, opencti, stix, retry, tdd-green]
dependency_graph:
  requires: [03-01]
  provides: [opencti_client for extractor.py in Wave 2]
  affects: [services/intel-extractor/opencti_client.py]
tech_stack:
  added: []
  patterns: [D-05 3x retry, D-08 internal UUID return, D-09 ATT&CK no-match log]
key_files:
  created:
    - services/intel-extractor/opencti_client.py
  modified:
    - services/intel-extractor/tests/test_opencti_client.py
decisions:
  - report_types=["threat-report"] used (report_class= is deprecated in pycti 6.4.11)
  - lookup_attack_pattern returns results[0]["id"] (internal UUID), not x_mitre_id (D-08)
  - No retry on lookup_attack_pattern — read-only query, failures are harmless misses
metrics:
  duration: "~5m"
  completed: "2026-06-25"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 1
---

# Phase 3 Plan 03: OpenCTI Client (intel-extractor) Summary

**One-liner:** pycti wrapper with 5 functions — 2 copied verbatim from Phase 2, 3 new (lookup_attack_pattern, create_report, create_relationship) — all write functions use proven D-05 3x retry pattern.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | opencti_client.py — copy Phase 2 base + add 3 new functions | 1f2fe27 | services/intel-extractor/opencti_client.py, tests/test_opencti_client.py |

## What Was Built

`services/intel-extractor/opencti_client.py` with 5 public functions:

- **build_pycti_client()** — copied verbatim from feed-orchestrator; returns `OpenCTIApiClient(url, token, log_level="error")`
- **create_indicator()** — copied verbatim from feed-orchestrator; 3x retry with `_RETRY_DELAYS = [30, 60, 120]`, `update=True`, `objectLabel=` param
- **lookup_attack_pattern(client, keyword)** — read-only; calls `client.attack_pattern.list(search=keyword, first=5)`; returns `results[0]["id"]` (internal UUID per D-08) or None with INFO log per D-09
- **create_report(client, name, published, description, indicator_ids)** — 3x retry; `report_types=["threat-report"]` (not deprecated `report_class=`); `update=True`
- **create_relationship(client, from_id, to_id, relationship_type="indicates")** — 3x retry; `stix_core_relationship.create(fromId, toId, relationship_type, update=True)`

TDD GREEN phase: removed `pytest.fail("RED")` stubs from test_opencti_client.py; both tests now pass.

## Verification Results

```
pytest tests/test_opencti_client.py -x -q  →  2 passed
pytest tests/ -x -q                        →  5 passed, 3 skipped
grep -c "report_class"                      →  0
grep -c "report_types"                      →  1
grep -c "_RETRY_DELAYS"                     →  10
grep -c "update=True"                       →  4
imports OK
```

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints or auth paths introduced. `OPENCTI_TOKEN` read from env var only; logged as `bool()` per T-03-03-01 mitigation (same pattern as Phase 2).

## Self-Check: PASSED

- [x] `services/intel-extractor/opencti_client.py` exists
- [x] `services/intel-extractor/tests/test_opencti_client.py` updated
- [x] Commit 1f2fe27 exists in git log
- [x] 2 tests GREEN, 5 total passed
