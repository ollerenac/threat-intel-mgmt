---
phase: 05-briefing-generator
plan: "01"
subsystem: briefing-generator
tags: [wave-0, scaffold, test-harness, dockerfile, font-asset]
status: complete

dependency_graph:
  requires: []
  provides:
    - services/briefing-generator/fonts/DejaVuSans.ttf
    - services/briefing-generator/requirements.txt
    - services/briefing-generator/Dockerfile
    - services/briefing-generator/tests/
  affects:
    - Phase 05 plans 02–04 (all depend on this test harness)

tech_stack:
  added:
    - fpdf2==2.8.7 (PDF generation)
    - ollama==0.6.2 (LLM client)
    - DejaVuSans.ttf (committed binary font asset)
  patterns:
    - import-guard+skipif test pattern (from Phase 4)
    - asyncio.to_thread wrapping for pycti/ollama blocking calls (established pattern)

key_files:
  created:
    - services/briefing-generator/fonts/DejaVuSans.ttf
    - services/briefing-generator/requirements.txt
    - services/briefing-generator/Dockerfile
    - services/briefing-generator/tests/__init__.py
    - services/briefing-generator/tests/conftest.py
    - services/briefing-generator/tests/test_generator.py
    - services/briefing-generator/tests/test_pdf_renderer.py
  modified: []

decisions:
  - "DejaVuSans.ttf committed to repo from official dejavu-fonts 2.37 release (757 KB) — avoids wget at Docker build time (A3 risk avoided)"
  - "import-guard+skipif pattern inherited from Phase 4 — tests SKIP not FAIL when production modules absent (Nyquist compliance)"
  - "test_pdf_renderer.py monkeypatches FONT_PATH to repo-relative path for local runs outside Docker"
  - "ollama==0.6.2 pinned (not floating as in intel-extractor) — version-locks response.message.content attribute path"

metrics:
  duration: "2m"
  completed: "2026-06-26"
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 0
---

# Phase 05 Plan 01: Wave 0 Scaffold Summary

Wave 0 test harness and service infrastructure: Dockerfile with explicit font layer, pinned requirements, DejaVuSans.ttf committed as binary asset, and 5 import-guarded test stubs that skip cleanly when production modules are absent.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Font asset + Dockerfile + requirements.txt | 507a528 | fonts/DejaVuSans.ttf, Dockerfile, requirements.txt |
| 2 | Wave 0 test scaffold | 6b4a5da | tests/__init__.py, conftest.py, test_generator.py, test_pdf_renderer.py |

## Verification Results

```
python3 -m pytest tests/ -v
5 skipped in 0.01s   ← all stubs skip cleanly, none error
```

Font: 757,076 bytes (>100 KB requirement), starts with valid TTF bytes.
Dockerfile: port 8003, libmagic1 apt package, `COPY fonts/ /app/fonts/` before `COPY . .`.
requirements.txt: fastapi==0.115.14, pycti==6.4.11, ollama==0.6.2, fpdf2==2.8.7.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

All 5 test functions are intentional stubs: they skip when production modules (generator.py, pdf_renderer.py, main.py) are absent. These will be wired by Plans 02–04.

| File | Function | Reason |
|------|----------|--------|
| test_generator.py | test_build_stats_block | generator.py not yet implemented (Wave 1) |
| test_generator.py | test_call_ollama_truncation | generator.py not yet implemented (Wave 1) |
| test_generator.py | test_updated_at_filter | generator.py not yet implemented (Wave 1) |
| test_generator.py | test_post_generate_returns_immediately | main.py not yet implemented (Wave 1) |
| test_pdf_renderer.py | test_render_pdf_bytes | pdf_renderer.py not yet implemented (Wave 2) |

This is the explicit goal of Wave 0 (Nyquist compliance: test stubs precede production code).

## Threat Flags

None — this plan creates no network endpoints, auth paths, or trust boundary crossings. Font asset sourced from official GitHub release (T-05-01-02 mitigated by size check).

## Self-Check: PASSED

```
[ FOUND ] services/briefing-generator/fonts/DejaVuSans.ttf
[ FOUND ] services/briefing-generator/requirements.txt
[ FOUND ] services/briefing-generator/Dockerfile
[ FOUND ] services/briefing-generator/tests/__init__.py
[ FOUND ] services/briefing-generator/tests/conftest.py
[ FOUND ] services/briefing-generator/tests/test_generator.py
[ FOUND ] services/briefing-generator/tests/test_pdf_renderer.py
[ FOUND ] commit 507a528
[ FOUND ] commit 6b4a5da
```
