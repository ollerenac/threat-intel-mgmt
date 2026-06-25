---
phase: 03-ai-ioc-extraction
plan: "02"
subsystem: intel-extractor
tags: [config, parser, pdf, url-extraction, ssrf, tdd, green-phase, wave-1]
dependency_graph:
  requires: [03-01]
  provides: [config-constants, pdf-extraction, url-extraction]
  affects: [03-03, 03-04, 03-05, 03-06]
tech_stack:
  added: [PyPDF2, trafilatura, beautifulsoup4, requests]
  patterns: [env-var-constants, ssrf-scheme-guard, trafilatura-none-check, requests-bs4-fallback]
key_files:
  created:
    - services/intel-extractor/config.py
    - services/intel-extractor/parser.py
  modified:
    - services/intel-extractor/tests/test_parser.py
decisions:
  - "PyPDF2 exceptions wrapped in ValueError so all unreadable PDF cases (empty bytes, malformed, image-based) surface uniformly as ValueError"
  - "test_parser.py updated with minimal valid PDF fixture — original stub bytes were a malformed PDF fragment that PdfReader could not parse"
  - "OLLAMA_URL presence-logged via bool() (not value) matching OPENCTI_TOKEN logging convention"
metrics:
  duration: 2m
  completed: "2026-06-25"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
status: complete
---

# Phase 03 Plan 02: config.py + parser.py Summary

**One-liner:** OPENCTI+OLLAMA env-var constants and PDF/URL text extraction with SSRF guard and trafilatura→requests fallback.

---

## What Was Built

**config.py** — 4 module-level constants read at import time: `OPENCTI_URL`, `OPENCTI_TOKEN`, `OLLAMA_URL`, `OLLAMA_MODEL`. No Redis, no feed vars. Logs token/URL presence via `bool()` only.

**parser.py** — Two public functions:
- `extract_pdf_text(pdf_bytes: bytes) -> str`: PyPDF2 reader with ValueError on any unreadable or image-based PDF (empty extracted text).
- `extract_url_text(url: str) -> str`: SSRF scheme guard (http/https only), trafilatura primary path with None-check, requests+BeautifulSoup fallback on None result.

**tests/test_parser.py** updated — replaced non-parseable PDF stub bytes with a minimal valid PDF fixture containing "Hello World"; removed `pytest.fail("RED")` calls to turn all 3 tests GREEN.

---

## Verification

```
pytest services/intel-extractor/tests/test_parser.py -x -q
# 3 passed, 2 warnings in 1.10s

pytest services/intel-extractor/tests/ -q
# 3 passed, 5 skipped — test_extractor + test_opencti_client still RED as expected
```

---

## Decisions Made

1. **PyPDF2 exceptions wrapped in ValueError**: `PdfReader` raises `EmptyFileError`, `PdfReadError`, etc. for bad input. Wrapping all in `ValueError` matches the plan acceptance criterion and gives callers a single exception type to handle for all "unreadable PDF" cases.

2. **Minimal valid PDF fixture in test_parser.py**: The original RED stub used `b"%PDF-1.4 1 0 obj..."` — a truncated fragment that `PdfReader` raises `PdfReadError: EOF marker not found` on. Updated to a complete 7-object PDF with a single page containing "Hello World" in a Type1 font stream.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test PDF bytes unparseable by PyPDF2**
- **Found during:** Task 2 verification
- **Issue:** Original test used `b"%PDF-1.4 1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj"` — a truncated PDF fragment. PyPDF2's `PdfReader` raises `PdfReadError: EOF marker not found`, so `extract_pdf_text` would never return text and the test could never pass GREEN.
- **Fix:** Replaced with a minimal 7-object valid PDF containing extractable "Hello World" text. Also wrapped all `PdfReader` exceptions in `ValueError` to satisfy the `extract_pdf_text(b'')` → `ValueError` acceptance criterion.
- **Files modified:** `tests/test_parser.py`, `parser.py`
- **Commit:** 350ac0b

---

## Commits

| Hash | Message |
|------|---------|
| 675a844 | feat(03-02): config.py — OPENCTI + OLLAMA env var constants |
| 350ac0b | feat(03-02): parser.py — PDF + URL text extraction (GREEN) |

---

## Known Stubs

None — both production files are fully implemented.

---

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: SSRF | parser.py | extract_url_text validates URL scheme before network call — mitigates T-03-02-01 |

## Self-Check: PASSED
