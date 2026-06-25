---
phase: 03-ai-ioc-extraction
plan: "06"
subsystem: infra
tags: [docker, intel-extractor, fastapi, pycti, libmagic, healthcheck]

requires:
  - phase: 03-05
    provides: intel-extractor service wired into docker-compose with FastAPI + pycti

provides:
  - intel-extractor running healthy in Docker (localhost:8001)
  - PDF extraction returning job_id → status=complete, iocs_extracted > 0
  - IOCs visible in OpenCTI Indicators tab
  - URL extraction returning status=complete
  - Report object created in OpenCTI Analysis tab

affects: [04-semantic-search, 06-dashboard]

tech-stack:
  added: [libmagic1 (apt), python urllib healthcheck probe]
  patterns: [python stdlib healthcheck in python:3.12-slim images (no curl)]

key-files:
  created: []
  modified:
    - services/intel-extractor/Dockerfile
    - docker-compose.yml

key-decisions:
  - "libmagic1 system package required in python:3.12-slim — pycti depends on python-magic C library"
  - "Healthcheck uses python urllib.request not curl — curl absent from slim images (Phase 1 pattern applied)"
  - "ATT&CK relationship edges not triggered — no technique-mentioning document used; unit tests cover this path"
  - "Long-doc multi-chunk not tested live — covered by unit tests; accepted gap documented"

patterns-established:
  - "python:3.12-slim healthcheck: python -c 'import urllib.request; urllib.request.urlopen(url)'"
  - "Any python:3.12-slim service needing libmagic must install libmagic1 via apt before pip install"

requirements-completed:
  - AIEX-01
  - AIEX-02
  - AIEX-03
  - AIEX-04
  - AIEX-05

coverage:
  - id: D1
    description: "intel-extractor container starts healthy under --profile extract"
    requirement: AIEX-01
    verification:
      - kind: integration
        ref: "docker compose ps intel-extractor → Up (healthy)"
        status: pass
    human_judgment: false
  - id: D2
    description: "POST /extract PDF → job reaches status=complete, iocs_extracted > 0, IOC visible in OpenCTI"
    requirement: AIEX-01
    verification:
      - kind: manual_procedural
        ref: "curl POST /extract -F file=@report.pdf → polled to complete; OpenCTI Indicators confirmed"
        status: pass
    human_judgment: true
    rationale: "IOC visibility in OpenCTI UI requires human eyes to confirm correct indicator object created"
  - id: D3
    description: "POST /extract URL → job reaches status=complete"
    requirement: AIEX-02
    verification:
      - kind: manual_procedural
        ref: "curl POST /extract -F url=https://www.cisa.gov/... → polled to complete"
        status: pass
    human_judgment: false
  - id: D4
    description: "Report object created in OpenCTI Analysis → Reports"
    requirement: AIEX-04
    verification:
      - kind: manual_procedural
        ref: "OpenCTI Analysis → Reports tab shows report created today"
        status: pass
    human_judgment: true
    rationale: "object_refs population (Assumption A6) requires human to confirm indicators linked inside report"
  - id: D5
    description: "ATT&CK relationship edge (indicates → attack-pattern) in OpenCTI"
    requirement: AIEX-03
    verification:
      - kind: unit
        ref: "services/intel-extractor/tests/test_extractor.py#test_attack_pattern_lookup"
        status: pass
    human_judgment: true
    rationale: "Live edge not triggered — no technique-mentioning document used in session; unit test covers the code path"
  - id: D6
    description: "Long document processed without IOC loss at chunk boundaries"
    requirement: AIEX-05
    verification:
      - kind: unit
        ref: "services/intel-extractor/tests/test_parser.py#test_chunk_boundaries"
        status: pass
    human_judgment: true
    rationale: "Live 10+ page PDF not submitted; unit tests cover chunking logic; gap accepted"

duration: ~30min (Task 1 automation + human verification)
completed: "2026-06-25"
status: complete
---

# Phase 3 Plan 06: Integration Checkpoint Summary

**intel-extractor deployed healthy at localhost:8001; PDF extraction produces IOCs in OpenCTI; two Dockerfile bugs fixed (missing libmagic1, wrong healthcheck probe)**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-06-25T19:43:00Z
- **Completed:** 2026-06-25T23:10:00Z
- **Tasks:** 1 automated + 1 human checkpoint
- **Files modified:** 2

## Accomplishments

- Full stack (11 services) running healthy under `--profile platform --profile extract`
- PDF extraction: job completes, 1 IOC extracted, IOC confirmed visible in OpenCTI Indicators tab
- URL extraction: job completes without error
- Report object created in OpenCTI Analysis → Reports
- 400/404 error cases verified correct
- Two auto-fixes landed: `libmagic1` apt package + Python urllib healthcheck probe

## Task Commits

1. **Task 1: Start stack and verify intel-extractor health** - `b1c7647` (fix)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `services/intel-extractor/Dockerfile` — added `libmagic1` apt install (pycti/python-magic requires C library)
- `docker-compose.yml` — replaced `curl` healthcheck with `python -c urllib.request` probe

## Decisions Made

- `libmagic1` system package is required: `python-magic` (pulled by pycti 6.4.11) wraps the C library `libmagic.so` which is not bundled in `python:3.12-slim`. Any future slim-based service using pycti must include this apt install.
- Python stdlib healthcheck is the correct probe for `python:3.12-slim` images — curl is absent. Phase 1 established this pattern for other services; applied consistently here.
- ATT&CK relationship live test: not triggered (no technique-mentioning document submitted). Unit test `test_attack_pattern_lookup` covers the code path. Accepted gap.
- Long-doc chunk test: not run live (PDFs used had insufficient text). Unit tests cover boundary logic. Accepted gap.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing libmagic1 system package caused ImportError on startup**
- **Found during:** Task 1 (Start stack and verify intel-extractor health)
- **Issue:** `pycti/__init__.py` imports `python-magic` which calls `ctypes.util.find_library('magic')`. `libmagic.so` is not present in `python:3.12-slim`, causing `ImportError: failed to find libmagic. Check your installation` — container exits immediately.
- **Fix:** Added `RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 && rm -rf /var/lib/apt/lists/*` before pip install in Dockerfile
- **Files modified:** `services/intel-extractor/Dockerfile`
- **Verification:** Container rebuilt, uvicorn started cleanly, no Python traceback in logs
- **Committed in:** b1c7647

**2. [Rule 1 - Bug] Docker healthcheck used curl, not available in python:3.12-slim**
- **Found during:** Task 1 (health verification)
- **Issue:** `docker inspect` showed `"curl": executable file not found in $PATH` — healthcheck fired but curl absent; container stuck "unhealthy" despite service responding correctly on port 8001
- **Fix:** Replaced `["CMD", "curl", "-f", "http://localhost:8001/health"]` with `["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]`
- **Files modified:** `docker-compose.yml` (intel-extractor healthcheck block)
- **Verification:** Container flipped to "healthy" within one interval cycle; `curl -sf http://localhost:8001/health` returns `{"status":"ok"}`
- **Committed in:** b1c7647

---

**Total deviations:** 2 auto-fixed (both Rule 1 — runtime bugs blocking container startup and healthcheck)
**Impact on plan:** Both fixes necessary for the service to run at all. No scope creep.

## Issues Encountered

- Container initially failed to start due to missing C library (`libmagic1`) — not detectable from unit tests which mock pycti entirely. Fixed in same commit.
- Healthcheck probe pattern inconsistency: `docker-compose.yml` used curl for intel-extractor but Python-based probes for other slim services. Corrected to match established pattern.

## Known Gaps (accepted)

- ATT&CK relationship edges (AIEX-03): not triggered live. Unit test `test_attack_pattern_lookup` covers the pycti lookup and relationship creation path. Will be naturally tested during Phase 6 (dashboard) demo prep when real threat reports are submitted.
- Long-document chunking (AIEX-05): not tested live in this session. Unit tests cover `chunk_text()` boundary logic. Accepted for integration checkpoint scope.

## Next Phase Readiness

- intel-extractor is stable and demo-ready at localhost:8001
- All AIEX requirements confirmed or covered by unit tests
- Phase 3 complete — Phase 4 (semantic-engine/ChromaDB indexing) and Phase 6 (dashboard) can proceed
- No blockers

---

*Phase: 03-ai-ioc-extraction*
*Completed: 2026-06-25*

## Self-Check: PASSED

- `b1c7647` exists: confirmed (`git log --oneline -5` shows it)
- `services/intel-extractor/Dockerfile` modified: confirmed
- `docker-compose.yml` modified: confirmed
- intel-extractor healthy: confirmed (`{"status":"ok"}` from localhost:8001)
