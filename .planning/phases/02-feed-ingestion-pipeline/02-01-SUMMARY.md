---
phase: 02-feed-ingestion-pipeline
plan: "01"
subsystem: feed-orchestrator test scaffold
tags: [tdd, testing, feed-ingestion, stix, redis, pytest]
status: complete

dependency_graph:
  requires: []
  provides:
    - services/feed-orchestrator/pytest.ini
    - services/feed-orchestrator/tests/conftest.py
    - services/feed-orchestrator/tests/test_urlhaus.py
    - services/feed-orchestrator/tests/test_malwarebazaar.py
    - services/feed-orchestrator/tests/test_threatfox.py
    - services/feed-orchestrator/tests/test_feodo.py
    - services/feed-orchestrator/tests/test_otx.py
    - services/feed-orchestrator/tests/test_deduplicator.py
    - services/feed-orchestrator/tests/test_normalizer.py
  affects: []

tech_stack:
  added:
    - pytest 9.1.1 (host-level, will be in requirements.txt in Plan 02)
    - pytest-mock (host-level)
  patterns:
    - RED-phase TDD test scaffold with ImportError on all production module imports
    - pytest fixtures in conftest.py (mock_redis, mock_pycti, 5 feed sample fixtures)
    - MagicMock with explicit return_value for Redis SETNX semantics

key_files:
  created:
    - services/feed-orchestrator/pytest.ini
    - services/feed-orchestrator/tests/__init__.py
    - services/feed-orchestrator/tests/conftest.py
    - services/feed-orchestrator/tests/test_urlhaus.py
    - services/feed-orchestrator/tests/test_malwarebazaar.py
    - services/feed-orchestrator/tests/test_threatfox.py
    - services/feed-orchestrator/tests/test_feodo.py
    - services/feed-orchestrator/tests/test_otx.py
    - services/feed-orchestrator/tests/test_deduplicator.py
    - services/feed-orchestrator/tests/test_normalizer.py
  modified: []

decisions:
  - key: RED-phase import strategy
    rationale: All 7 test files import from production modules that don't exist yet; ImportError is the correct RED state per TDD discipline
  - key: D-09 formula embedded as comments in test_normalizer.py
    rationale: Expected values (65, 53, 100, 40) calculated inline so Wave 3 executor can verify formula without re-reading RESEARCH.md
  - key: test_deduplicator.py tests nx+TTL kwargs explicitly
    rationale: Critical correctness requirement — SETNX without nx=True would silently overwrite existing keys, breaking dedup semantics

metrics:
  duration: "~3 minutes"
  completed: "2026-06-25"
  tasks_completed: 2
  files_created: 9
  files_modified: 0
---

# Phase 02 Plan 01: Test Scaffold (RED Phase) Summary

**One-liner:** pytest.ini + 7 RED-phase test files establishing STIX pattern contracts for all 5 feeds, deduplicator, and confidence scorer before any production code exists.

## What Was Built

Created the complete test infrastructure for the `feed-orchestrator` service as a TDD RED-phase scaffold. All 7 test files import from production modules that do not yet exist, producing `ImportError` on collection — this is the correct and expected state.

### Task 1: pytest.ini + conftest.py (commit 63ce7a8)

- `pytest.ini`: testpaths=tests, python_files=test_*.py, python_classes=Test*, python_functions=test_*
- `tests/__init__.py`: empty package marker
- `tests/conftest.py`: 7 shared fixtures:
  - `mock_redis`: MagicMock with `set.return_value=True` (SETNX new key), `hset.return_value=None`, `hgetall.return_value={}`
  - `mock_pycti`: MagicMock with `indicator.create.return_value={"id": "indicator--test-uuid"}`
  - `sample_urlhaus_rows`: 1 entry with url, url_status, dateadded, tags (comma-separated)
  - `sample_malwarebazaar_rows`: 1 entry with sha256_hash, first_seen, signature, tags (list)
  - `sample_threatfox_rows`: 5 entries covering domain, ip:port, url, md5_hash, sha256_hash ioc_types
  - `sample_feodo_rows`: 1 entry with first_seen_utc, dst_ip, dst_port, malware
  - `sample_otx_indicators`: 5 entries covering IPv4, domain, URL, FileHash-MD5, FileHash-SHA256

### Task 2: 7 RED-Phase Test Files (commit 902d230)

| File | Covers | Key Assertions |
|------|--------|----------------|
| test_urlhaus.py | FEED-01 | `[url:value = '...']` pattern, tags in labels, empty url skipped |
| test_malwarebazaar.py | FEED-02a | `[file:hashes.'SHA-256' = '...']` (Pitfall 3 — quoted property), malware family in labels |
| test_threatfox.py | FEED-02b | ip:port split → `[ipv4-addr:value = '185.220.101.47']` (Pitfall 2), domain/sha256/unknown skipped |
| test_feodo.py | FEED-02c | `[ipv4-addr:value = '185.220.101.47']`, "c2" label always present, malware family in labels |
| test_otx.py | FEED-03 | IPv4/SHA-256/SHA-1 type mappings, unknown type (email) skipped |
| test_deduplicator.py | FEED-04 | SETNX True=not-dup, None=dup, key prefix `tim:ioc_seen:`, nx=True+ex=86400 verified |
| test_normalizer.py | FEED-05 | D-09 formula: feodo-new=65, otx-7d=53, cap=100, urlhaus-11d=40 |

## Verification Results

All success criteria met:

- [x] pytest.ini present with testpaths=tests
- [x] tests/conftest.py present with 7 fixtures (mock_redis, mock_pycti, 5 feed samples)
- [x] All 7 test files present and syntactically valid (ast.parse passes all)
- [x] test_threatfox.py::test_normalize_ip_port_split exists (Pitfall 2 contract)
- [x] test_normalizer.py::test_confidence_feodo_new asserts result == 65
- [x] test_deduplicator.py::test_key_uses_sha256_of_pattern asserts `tim:ioc_seen:` prefix
- [x] RED state confirmed: pytest --collect-only shows ModuleNotFoundError for feeds.urlhaus, feeds.feodo, feeds.malwarebazaar, feeds.otx, feeds.threatfox, deduplicator, normalizer

## Deviations from Plan

### Additional Tests Added (Rule 2 — Missing Critical Functionality)

**test_deduplicator.py::test_uses_nx_and_ttl** — Added beyond the plan spec.

- **Found during:** Task 2 implementation
- **Issue:** Plan specified 3 test functions for deduplicator; a 4th test explicitly verifying `nx=True` and `ex=86400` kwargs catches a common implementation error where a developer writes `r.set(key, "1")` without the SETNX and TTL semantics (silently breaking dedup)
- **Fix:** Added `test_uses_nx_and_ttl` as the 4th deduplicator test
- **Files modified:** services/feed-orchestrator/tests/test_deduplicator.py

**test_normalizer.py::test_confidence_unknown_feed_uses_default_weight** — Added beyond the plan spec.

- **Found during:** Task 2 implementation
- **Issue:** Plan specified 4 normalizer tests; a 5th covering the unknown-feed default weight (10) catches the case where a future feed is added without updating QUALITY_WEIGHTS
- **Fix:** Added `test_confidence_unknown_feed_uses_default_weight` asserting result == 45

## Known Stubs

None. All test files are intentional RED-phase specs. The ImportErrors are the expected artifact — not stubs.

## Threat Flags

None. Test files contain only hardcoded dummy values (no real credentials, no network calls, no trust boundary crossings). Confirmed per T-02-01-01 threat register entry (conftest.py fixtures accepted as low risk).

## Self-Check: PASSED

All 10 files verified present on disk. Both task commits verified in git history:
- `63ce7a8` — pytest.ini, __init__.py, conftest.py
- `902d230` — 7 RED-phase test files
