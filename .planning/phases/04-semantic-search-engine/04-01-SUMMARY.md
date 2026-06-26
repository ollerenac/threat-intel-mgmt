---
phase: 04-semantic-search-engine
plan: "01"
subsystem: semantic-engine
tags: [tdd, testing, pytest, red-phase]
dependency_graph:
  requires: []
  provides: [test-scaffold-semantic-engine]
  affects: [04-02-indexer, 04-03-searcher]
tech_stack:
  added: [pytest, pytest-mock]
  patterns: [import-guard-skipif, monkeypatch-singleton]
key_files:
  created:
    - services/semantic-engine/pytest.ini
    - services/semantic-engine/tests/__init__.py
    - services/semantic-engine/tests/conftest.py
    - services/semantic-engine/tests/test_indexer.py
    - services/semantic-engine/tests/test_searcher.py
  modified: []
decisions:
  - import-guard + skipif in test files so tests SKIP (not FAIL) when production modules absent
  - monkeypatch _ollama module-level singleton in test_searcher.py — aligns with PATTERNS.md search() signature that takes no ollama arg
  - mock_chroma uses full localhost:8080 opencti URLs (not http://opencti) — test_opencti_url_format asserts indicator--test-uuid-1234 in url
metrics:
  duration: 2m
  completed: "2026-06-26"
  tasks: 2
  files: 5
status: complete
---

# Phase 04 Plan 01: RED-Phase Test Scaffold for Semantic Engine Summary

**One-liner:** pytest infrastructure and 8 import-guarded test stubs that skip cleanly until indexer.py and searcher.py are implemented.

## What Was Built

Five files establishing the TDD RED-phase contract for the semantic-engine service:

- **pytest.ini** — discovered by pytest, `testpaths = tests`, standard conventions matching intel-extractor
- **tests/__init__.py** — empty package marker
- **tests/conftest.py** — three fixtures: `mock_pycti` (indicator list), `mock_ollama` (embed returns `embeddings=[[0.1]*768]`), `mock_chroma` (query returns distances `[0.2, 0.8]` with full opencti URLs)
- **tests/test_indexer.py** — 4 tests for `build_embed_text`: D-01 em-dash format, D-03 bracket format, empty labels, strip trailing space
- **tests/test_searcher.py** — 4 tests for `search`: score conversion (1-dist), threshold filtering, ranked order, opencti_url/embedded_text/score field presence

## Verification

```
$ cd services/semantic-engine && python3 -m pytest tests/ -v
8 skipped in 0.01s   (exit 0)
```

All 8 tests show SKIPPED with reasons "indexer not yet implemented" / "searcher not yet implemented".

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| `monkeypatch` `_ollama` singleton in test_searcher.py | PATTERNS.md `search()` signature is `(collection, query, n_results, threshold)` — no ollama arg. Monkeypatching the module-level `_ollama` is the correct injection point. |
| Full `localhost:8080` URL in mock_chroma | `test_opencti_url_format` asserts `"indicator--test-uuid-1234" in results[0]["opencti_url"]` — URL must contain the ID string. |
| Scores sorted descending in mock_chroma return | Distances `[0.2, 0.8]` → scores `[0.8, 0.2]` — first result has higher score, satisfying AISEM-02 ranking test without sorting in searcher. |

## Deviations from Plan

**1. [Rule 1 - Adaptation] test_searcher.py uses monkeypatch instead of mock_ollama parameter**

- **Found during:** Task 2
- **Issue:** Plan task description called `search(mock_chroma, "Russian malware", mock_ollama, threshold=0.3)` passing ollama as positional arg, but PATTERNS.md `search()` signature has no ollama parameter (uses module-level `_ollama`).
- **Fix:** Used `monkeypatch.setattr(searcher, "_ollama", mock_ollama)` before calling `search(mock_chroma, query, threshold=...)`. Fixtures still injected via pytest; plan's "adapt to actual signature" note authorizes this.
- **Files modified:** `tests/test_searcher.py`
- **Commit:** 77ff4dc

## Self-Check

- [x] `services/semantic-engine/pytest.ini` — exists
- [x] `services/semantic-engine/tests/__init__.py` — exists
- [x] `services/semantic-engine/tests/conftest.py` — exists
- [x] `services/semantic-engine/tests/test_indexer.py` — exists
- [x] `services/semantic-engine/tests/test_searcher.py` — exists
- [x] Commits fbdbd2e (Task 1) and 77ff4dc (Task 2) present in git log
- [x] `python3 -m pytest tests/ -q` exits 0, 8 skipped, 0 failed

## Self-Check: PASSED
