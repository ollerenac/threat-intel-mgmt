---
phase: 4
slug: semantic-search-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `services/semantic-engine/pytest.ini` (Wave 0 gap — create from intel-extractor template) |
| **Quick run command** | `python -m pytest tests/ -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 0 | AISEM-01 | — | N/A | unit | `pytest tests/test_indexer.py -x -q` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 0 | AISEM-02 | — | N/A | unit | `pytest tests/test_searcher.py -x -q` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | AISEM-01 | — | embed text never excludes no-description IOCs (D-03) | unit | `pytest tests/test_indexer.py::test_build_embed_text -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 1 | AISEM-01 | — | upsert called with correct ids/embeddings/metadatas | unit | `pytest tests/test_indexer.py::test_run_index_calls_upsert -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | AISEM-02 | — | N/A | unit | `pytest tests/test_searcher.py::test_search_returns_ranked -x` | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 2 | AISEM-03 | — | score = 1 - distance (not raw distance) | unit | `pytest tests/test_searcher.py::test_score_conversion -x` | ❌ W0 | ⬜ pending |
| 04-03-03 | 03 | 2 | AISEM-03 | — | D-07 threshold filters low-similarity results | unit | `pytest tests/test_searcher.py::test_threshold_filters -x` | ❌ W0 | ⬜ pending |
| 04-03-04 | 03 | 2 | AISEM-04 | — | opencti_url contains indicator id | unit | `pytest tests/test_searcher.py::test_opencti_url_format -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/semantic-engine/pytest.ini` — `[pytest] testpaths = tests`
- [ ] `services/semantic-engine/tests/__init__.py` — empty init
- [ ] `services/semantic-engine/tests/conftest.py` — `mock_chroma`, `mock_ollama` (returns `MagicMock(embeddings=[[0.1]*768])`), `mock_pycti` fixtures
- [ ] `services/semantic-engine/tests/test_indexer.py` — stubs for AISEM-01: `test_build_embed_text`, `test_run_index_calls_upsert`
- [ ] `services/semantic-engine/tests/test_searcher.py` — stubs for AISEM-02/03/04: `test_search_returns_ranked`, `test_score_conversion`, `test_threshold_filters`, `test_opencti_url_format`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| All OpenCTI indicators indexed — count matches `GET /health` | AISEM-01 | Requires live OpenCTI + ChromaDB stack | `docker compose --profile platform --profile semantic up -d`, wait for index, `curl http://localhost:8002/health` — verify `indexed == total` |
| Natural-language query returns relevant IOCs | AISEM-02 | Subjective relevance of results | `curl "http://localhost:8002/search?q=malware+DNS+tunneling"` — inspect ranked results for semantic relevance |
| Similarity scores are between 0.0 and 1.0 | AISEM-03 | Requires live ChromaDB with real vectors | Inspect `score` field in search results from manual query above |
| OpenCTI deep-link opens the correct indicator | AISEM-04 | Requires browser + live OpenCTI | Click `opencti_url` from a search result — verify it opens the matching indicator in OpenCTI at `localhost:8080` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
