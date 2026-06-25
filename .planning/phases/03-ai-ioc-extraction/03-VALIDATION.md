---
phase: 03
slug: ai-ioc-extraction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (same as Phase 2) |
| **Config file** | `services/intel-extractor/pytest.ini` (copy pattern from feed-orchestrator) |
| **Quick run command** | `pytest services/intel-extractor/tests/ -x -q` |
| **Full suite command** | `pytest services/intel-extractor/tests/ -v` |
| **Estimated runtime** | ~15 seconds (all mocked, no live Ollama/pycti calls) |

---

## Sampling Rate

- **After every task commit:** Run `pytest services/intel-extractor/tests/ -x -q`
- **After every plan wave:** Run `pytest services/intel-extractor/tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0 | AIEX-01 | — | N/A | unit | `pytest tests/test_parser.py::test_extract_pdf_text -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 0 | AIEX-01 | — | N/A | unit | `pytest tests/test_extractor.py::test_call_llm_happy_path -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 0 | AIEX-02 | — | N/A | unit | `pytest tests/test_parser.py::test_extract_url_text -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 0 | AIEX-02 | — | N/A | unit | `pytest tests/test_parser.py::test_extract_url_text_trafilatura_fallback -x` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 0 | AIEX-05 | — | N/A | unit | `pytest tests/test_extractor.py::test_chunk_text_overlap -x` | ❌ W0 | ⬜ pending |
| 03-01-06 | 01 | 0 | AIEX-05 | — | N/A | unit | `pytest tests/test_extractor.py::test_ioc_dedup_across_chunks -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | AIEX-03 | — | N/A | unit | `pytest tests/test_opencti_client.py::test_lookup_attack_pattern -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | AIEX-04 | — | N/A | unit | `pytest tests/test_opencti_client.py::test_create_report -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/intel-extractor/tests/__init__.py` — package marker
- [ ] `services/intel-extractor/tests/conftest.py` — `mock_pycti_client`, `mock_ollama_client` fixtures; verify ollama SDK attribute path (`response.message.content` vs dict access)
- [ ] `services/intel-extractor/tests/test_parser.py` — stubs for AIEX-01, AIEX-02
- [ ] `services/intel-extractor/tests/test_extractor.py` — stubs for AIEX-01, AIEX-05
- [ ] `services/intel-extractor/tests/test_opencti_client.py` — stubs for AIEX-03, AIEX-04
- [ ] `services/intel-extractor/pytest.ini` — copy from services/feed-orchestrator/pytest.ini

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| IOCs appear in OpenCTI UI after full E2E POST /extract | AIEX-01, AIEX-04 | Requires live Docker stack | Run `docker compose up`, POST a PDF, check OpenCTI Indicators tab |
| `report.create(objects=...)` populates object_refs (A6) | AIEX-04 | OpenCTI GraphQL schema behavior at runtime | After Wave 1, check created report in OpenCTI UI for populated object_refs |
| ATT&CK links visible on indicator in OpenCTI | AIEX-03 | Requires live OpenCTI + attack-pattern seed data | POST report mentioning "phishing", check indicator in OpenCTI for linked attack-pattern |
| Chunk boundary: no IOCs silently dropped across chunks | AIEX-05 | Requires live LLM | POST 20+ page PDF, compare extracted IOC count against manual review of PDF |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
