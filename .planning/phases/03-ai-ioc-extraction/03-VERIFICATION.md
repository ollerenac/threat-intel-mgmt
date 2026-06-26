---
phase: 03-ai-ioc-extraction
status: passed
verified_by: orchestrator-inline
date: 2026-06-25
must_haves_checked: 5
must_haves_passed: 5
gaps_found: false
human_needed: true
human_verification_items:
  - id: HV-01
    description: Submit a real threat-intel PDF and confirm IOC appears in OpenCTI Indicators tab with correct STIX pattern
    requirement: AIEX-01, AIEX-04
  - id: HV-02
    description: Submit a URL and confirm extraction completes and report object appears in OpenCTI Analysis → Reports
    requirement: AIEX-02, AIEX-04
---

# Phase 03: AI IOC Extraction — Verification Report

## Phase Goal

> An analyst can submit a PDF file or a URL to the intel-extractor service and receive extracted IOCs — mapped to MITRE ATT&CK techniques where mentioned — inserted into OpenCTI as STIX objects, processed entirely by the local LLM.

## Result: PASSED (with human verification items)

All 5 must-have requirements verified against the codebase and live integration tests from 03-06.

---

## Requirement Traceability

| Req ID | Description | Evidence | Status |
|--------|-------------|----------|--------|
| AIEX-01 | intel-extractor accepts PDF, extracts IOCs via local LLM | `parser.py:extract_pdf_text`, `extractor.py:run_extraction`, `main.py:POST /extract` (file upload path); 03-06 live test: job→complete, iocs_extracted>0 | ✓ PASS |
| AIEX-02 | intel-extractor accepts URL, extracts IOCs | `parser.py:extract_url_text` with SSRF guard, `main.py:POST /extract` (url path); 03-06 live test: URL job→complete | ✓ PASS |
| AIEX-03 | IOCs mapped to MITRE ATT&CK where mentioned | `extractor.py:lookup_attack_pattern` (line 31, 326); `create_relationship` links indicator→attack-pattern in OpenCTI | ✓ PASS |
| AIEX-04 | Extraction inserted into OpenCTI as STIX objects | `opencti_client.py:create_indicator`, `create_report`, `create_relationship` all with D-05 3× retry; 03-06 confirms IOC visible in OpenCTI Indicators tab, Report in Analysis tab | ✓ PASS |
| AIEX-05 | Long docs chunked without IOC loss at boundaries | `extractor.py:chunk_text(max_chars=6000, overlap_chars=600)`; unit test `test_parser.py#test_chunk_boundaries`; 600-char overlap prevents boundary splits | ✓ PASS |

---

## Security Checks

| Control | Implementation | Status |
|---------|---------------|--------|
| SSRF prevention | `parser.py:_is_private_ip` checks `not addr.is_global` covering loopback, link-local, private, reserved, multicast; http/https scheme-only guard; no embedded credentials | ✓ |
| Redirect bypass (trafilatura) | `trafilatura.fetch_url` dropped entirely (commit db3b2e2) — requests+bs4 used as sole fetch backbone with SSRF guard applied before any request | ✓ |
| Local LLM only | Ollama SDK calls `localhost` only via `config.py:OLLAMA_URL`; no external API calls | ✓ |

---

## Known Limitations (Acceptable)

- **D-06: In-memory job store** — `jobs` dict in `extractor.py` is lost on container restart. Documented in `main.py` header. Acceptable for Phase 3 scope; persistent store is Phase 4+ concern.
- **ATT&CK mapping coverage** — technique lookup depends on IOC text mentioning ATT&CK keywords; no-match case logs and skips (D-09), not an error. Expected false-negative rate is high for generic IOCs.
- **Single-model concurrency** — 4GB VRAM constraint enforced by design (one Ollama model at a time). Concurrent extraction jobs queue implicitly via FastAPI BackgroundTasks.

---

## Integration Test Evidence (from 03-06 live run)

- `docker compose ps intel-extractor` → `Up (healthy)` after b1c7647 healthcheck fix
- `POST /extract -F file=@report.pdf` → `status=complete`, `iocs_extracted=1`, IOC visible in OpenCTI Indicators tab
- `POST /extract -F url=https://www.cisa.gov/...` → `status=complete`
- `GET /health` → `{"status":"ok"}`
- `POST /extract` (no file/url) → `422 Unprocessable Entity`
- Report object created in OpenCTI Analysis → Reports

---

## Human Verification Items

These were verified procedurally during 03-06 but are flagged for analyst confirmation:

### HV-01: PDF IOC Extraction (AIEX-01, AIEX-04)
Submit a real threat-intel PDF to `POST http://localhost:8001/extract` and confirm:
- Job reaches `status=complete`
- `iocs_extracted > 0`
- IOC appears in OpenCTI Indicators tab with a valid STIX pattern (e.g. `[ipv4-addr:value = '...']`)

### HV-02: URL Extraction + Report Object (AIEX-02, AIEX-04)
Submit a threat-intel URL to `POST http://localhost:8001/extract?url=<url>` and confirm:
- Job reaches `status=complete`
- Report object appears in OpenCTI Analysis → Reports

---

## Plans Covered

| Plan | What it built |
|------|---------------|
| 03-01 | TDD test scaffold — pytest.ini, conftest, test skeletons |
| 03-02 | PDF + URL parser with SSRF hardening |
| 03-03 | OpenCTI client — STIX creation with D-05 retry |
| 03-04 | Core LLM pipeline — chunking, Ollama, STIX pattern building |
| 03-05 | FastAPI service + Docker wiring |
| 03-06 | Integration checkpoint — libmagic fix, healthcheck fix, live E2E validation |
