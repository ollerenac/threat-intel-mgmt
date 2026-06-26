---
phase: 5
slug: briefing-generator
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-26
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (matches prior services) |
| **Config file** | none — pytest.ini not used in prior services |
| **Quick run command** | `cd services/briefing-generator && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd services/briefing-generator && python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd services/briefing-generator && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd services/briefing-generator && python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 0 | AIBR-01–04 | — | N/A | scaffold | `python -m pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 5-02-01 | 02 | 1 | AIBR-01 | T-5-01 | `period_hours` Pydantic Field(ge=1, le=720) | unit | `pytest tests/test_generator.py::test_build_stats_block -x` | ❌ W0 | ⬜ pending |
| 5-02-02 | 02 | 1 | AIBR-01 | T-5-02 | `_call_ollama()` output truncated ≤ 320 words | unit (mock) | `pytest tests/test_generator.py::test_call_ollama_truncation -x` | ❌ W0 | ⬜ pending |
| 5-02-03 | 02 | 1 | AIBR-02 | — | time filter covers period_hours=72 | unit | `pytest tests/test_generator.py::test_updated_at_filter -x` | ❌ W0 | ⬜ pending |
| 5-03-01 | 03 | 1 | AIBR-03 | T-5-03 | PDF bytes start with `%PDF` | unit | `pytest tests/test_pdf_renderer.py::test_render_pdf_bytes -x` | ❌ W0 | ⬜ pending |
| 5-04-01 | 04 | 1 | AIBR-04 | — | POST /generate returns 200 + briefing_id immediately | integration (mock) | `pytest tests/test_generator.py::test_post_generate_returns_immediately -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/briefing-generator/tests/__init__.py` — empty, needed for pytest discovery
- [ ] `services/briefing-generator/tests/conftest.py` — `mock_pycti`, `mock_ollama` fixtures
- [ ] `services/briefing-generator/tests/test_generator.py` — stubs for AIBR-01, AIBR-02, AIBR-04
- [ ] `services/briefing-generator/tests/test_pdf_renderer.py` — stubs for AIBR-03
- [ ] `services/briefing-generator/fonts/DejaVuSans.ttf` — required for PDF renderer (not bundled in fpdf2)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Ollama returns 200–300 word prose for live OpenCTI data | AIBR-01 | Requires live Ollama + OpenCTI stack | `docker compose --profile platform --profile briefings up -d` then `curl -X POST localhost:8003/generate -d '{"period_hours":24}'` |
| PDF download contains briefing text | AIBR-03 | Requires live stack + binary response inspection | Retrieve PDF via `GET /briefings/{id}/pdf`, open and verify prose matches `GET /briefings/{id}` text |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
