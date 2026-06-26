---
phase: 03-ai-ioc-extraction
plan: "04"
subsystem: intel-extractor
status: complete
tags: [extractor, llm, ollama, stix, ioc, pipeline]

dependency_graph:
  requires:
    - 03-02  # config.py + opencti_client.py
    - 03-03  # parser.py
  provides:
    - extractor.py with chunk_text, call_llm, build_stix_pattern, run_extraction
  affects:
    - 03-05  # main.py imports run_extraction + jobs from extractor.py

tech_stack:
  added:
    - ollama Python SDK 0.6.2 (installed to host env for test execution)
  patterns:
    - Sliding-window chunker with configurable overlap (6000 chars / 600 overlap)
    - D-03 double-prompt fallback: JSON-mode primary, regex TYPE:VALUE secondary
    - IOC dedup via set of (type, value) tuples within-job
    - STIX single-quoted property names for SHA-1/SHA-256 (proven in threatfox.py)
    - Plain def background task — FastAPI thread pool isolates sync pycti (Pitfall 5)

key_files:
  created:
    - services/intel-extractor/extractor.py
  modified:
    - services/intel-extractor/tests/test_extractor.py  # removed pytest.fail("RED") stubs

decisions:
  - "chunk_text stops at len(text) end (min(start+max_chars, len(text))) to avoid a tiny trailing chunk that duplicates overlap content"
  - "call_llm catches Exception broadly for primary call, falls to D-03 fallback, then returns empty dict on double failure"
  - "IOC_TYPE_TO_STIX.get() returns None for unknown types — silently skipped, consistent with D-09 no-match principle"

metrics:
  duration: "~15 minutes"
  completed: "2026-06-25"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 2
---

# Phase 3 Plan 4: extractor.py Core Pipeline Summary

Implemented `extractor.py` — the LLM extraction core of intel-extractor. Turns all 3 RED stubs in `test_extractor.py` GREEN. Full test suite is 8/8 GREEN.

## What Was Built

`services/intel-extractor/extractor.py` with:

- **`chunk_text(text, max_chars=6000, overlap_chars=600)`** — sliding window chunker. Uses `min(start+max_chars, len(text))` as the end index so the final chunk always reaches the text boundary without emitting a tiny trailing chunk that duplicates the overlap content.

- **`build_stix_pattern(ioc_type, value)`** — maps 7 IOC types to STIX 2.1 patterns. SHA-1 and SHA-256 use single-quoted property names (`[file:hashes.'SHA-1' = '...']`) per the pattern proven in `services/feed-orchestrator/feeds/threatfox.py`. Returns `None` for unknown types (silent skip, consistent with D-09).

- **`call_llm(client, model, text)`** — primary JSON-mode Ollama call with `format="json"` and `num_ctx=8192` (Pitfall 7). On `JSONDecodeError` or `KeyError`, falls back to D-03 plain-text `FALLBACK_PROMPT` with `_parse_fallback_text()` regex parser. Double failure returns empty dict with 4 empty list keys.

- **`run_extraction(job_id, mode, content, url)`** — plain `def` (not `async def`) so FastAPI runs it in a thread pool (Pitfall 5). 10-step pipeline in correct processing order: parse → chunk → LLM → dedup → pycti client → create indicators → ATT&CK lookup + relationships → `create_report` (only after all indicator IDs collected — Pitfall 1) → update job state.

- **`SYSTEM_PROMPT`** — D-01 JSON schema with D-02 few-shot example (~200 tokens, fictional Emotet scenario).

- **`FALLBACK_PROMPT`** — D-03 stripped fallback: "List all IPs, domains, file hashes, and URLs, one per line, format: TYPE:VALUE".

- **`IOC_TYPE_TO_STIX`** — 7-entry dict mapping `ip`, `domain`, `url`, `hash_md5`, `hash_sha1`, `hash_sha256`, `email` to `(pattern, observable_type)` tuples.

- **`jobs: dict[str, dict]`** — module-level job state store (D-06). `_ollama_client` singleton at module level.

## Test Results

```
services/intel-extractor/tests/ — 8/8 PASSED
  test_parser.py         3 passed
  test_opencti_client.py 2 passed
  test_extractor.py      3 passed
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `chunk_text` with `min()` end index instead of raw slice**
- **Found during:** Task 1 implementation verification
- **Issue:** Plan's described algorithm (`text[start:end]` where `end=start+max_chars`) with step advance produces 3 chunks for 12000-char input with 6000/600 settings. The test asserts `>= 2` (passes regardless), but the plan's acceptance criteria note says "length 2". Using `min(start+max_chars, len(text))` as end index causes the final chunk to extend to the text boundary, eliminating the tiny tail chunk.
- **Fix:** `end = min(start + max_chars, len(text))` and break when `end >= len(text)`.
- **Files modified:** `services/intel-extractor/extractor.py`
- **Commit:** c39c599

**2. [Rule 3 - Blocking] `ollama` package not installed in host environment**
- **Found during:** Task 1 — `python3 -c "from extractor import ..."` failed with `ModuleNotFoundError: No module named 'ollama'`
- **Fix:** `pip3 install ollama` (0.6.2). Package is legitimate — `ollama.com/blog/python-library`.
- **Impact:** `requirements.txt` does not yet exist; package needed in host env for test execution. Wave 3 (main.py) will create `requirements.txt` with this dependency.

**3. [Rule 1 - Bug] Removed `pytest.fail("RED")` stubs from test file**
- **Found during:** Task 1 — stubs were written to force RED even if logic passes; must be removed for GREEN.
- **Fix:** Removed the 3 `pytest.fail("RED")` calls; preserved all assertions unchanged.
- **Files modified:** `services/intel-extractor/tests/test_extractor.py`
- **Commit:** c39c599 (same commit)

## Threat Model Compliance

- **T-03-04-01** (LLM output schema validation): Implemented — `json.loads` in `try/except`, `.get()` on all key access, D-03 fallback, unknown IOC types rejected by `IOC_TYPE_TO_STIX.get()`.
- **T-03-04-04** (IOC values in logs): Compliant — logs IOC counts and types only; individual values not logged at INFO. `logger.info("[extractor] job %s: %d unique IOC types after dedup", ...)`.

## Self-Check

Files exist:
- `services/intel-extractor/extractor.py` — FOUND
- `services/intel-extractor/tests/test_extractor.py` — FOUND (modified)

Commits exist:
- `c39c599` — FOUND (`feat(03-04): implement extractor.py — LLM pipeline GREEN`)

## Self-Check: PASSED
