---
phase: 05-briefing-generator
plan: "02"
subsystem: briefing-generator
tags: [generator, ollama, pycti, asyncio, config]
status: complete

dependency_graph:
  requires: [05-01]
  provides: [generator.py, config.py, opencti_client.py]
  affects: [05-03, 05-04]

tech_stack:
  added: []
  patterns:
    - asyncio.to_thread for blocking pycti + ollama I/O (BC-03)
    - _safe_list() defensive wrapper with first=10 fallback (assumption A2)
    - bool(OPENCTI_TOKEN) logging — never token value (ASVS V14.2)
    - Module-level ollama.Client singleton with OLLAMA_TIMEOUT=60s

key_files:
  created:
    - services/briefing-generator/config.py
    - services/briefing-generator/opencti_client.py
    - services/briefing-generator/generator.py
  modified: []

decisions:
  - "OLLAMA_TIMEOUT=60 default — prose generation takes 30-45s on 4GB VRAM (Pitfall 3)"
  - "briefings dict is module-level — exported for Plan 04 main.py; acceptable for demo (D-10)"
  - "No format=json on ollama chat call — prose output, not structured JSON (anti-pattern from extractor.py)"
  - "_safe_list() defined inside _collect_threat_data as local function — no module pollution"

metrics:
  duration: "2m"
  completed: "2026-06-26T07:26:43Z"
  tasks_completed: 2
  files_created: 3
  files_modified: 0
---

# Phase 05 Plan 02: Config, OpenCTI Client, and Generator Summary

**One-liner:** Data collection and LLM generation layer — pycti entity reads via _safe_list, stats block aggregation, ollama prose call with word-count truncation, all blocking I/O in asyncio.to_thread sync helper.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | config.py + opencti_client.py | f299986 | config.py, opencti_client.py |
| 2 | generator.py | 976f7e5 | generator.py |

## What Was Built

### Task 1: config.py + opencti_client.py

`config.py` defines all five env vars (`OPENCTI_URL`, `OPENCTI_TOKEN`, `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`) with sane defaults. `OLLAMA_TIMEOUT` defaults to 60 seconds to handle 30-45s LLM prose generation on the 4GB VRAM machine. Logs `bool(OPENCTI_TOKEN)` only — never the token value (T-05-02-01, ASVS V14.2).

`opencti_client.py` provides only `build_pycti_client()` with `log_level="error"` to suppress pycti INFO spam. No write methods — briefing-generator is read-only.

### Task 2: generator.py

Implements the full generation pipeline:

- `_make_updated_at_filter(period_hours)` — pycti filter dict with ISO timestamp
- `_extract_sectors(indicators)` — label-based sector inference matching SECTOR_KEYWORDS
- `_safe_list(entity, **kwargs)` — defensive wrapper with first=10 fallback on exception (A2)
- `_collect_threat_data(client, period_hours)` — 5 entity types (indicator, threat_actor, malware, campaign, attack_pattern), D-04 confidence sort on IOCs
- `_build_stats_block(data, period_hours)` — human-readable stats string for LLM context
- `_call_ollama(stats_block)` — prose mode chat (no format="json"), truncates >320 words to 300+"..."
- `_run_generate_sync(briefing_id, period_hours)` — all blocking I/O in sync helper (BC-03)
- `run_generate(briefing_id, period_hours)` — async def wrapping asyncio.to_thread with error capture

`briefings: dict[str, dict]` exported at module level for Plan 04 main.py.

## Verification

```
pytest tests/test_generator.py::test_build_stats_block     PASSED
pytest tests/test_generator.py::test_updated_at_filter     PASSED
pytest tests/test_generator.py::test_call_ollama_truncation PASSED
```

`test_post_generate_returns_immediately` fails as expected — requires `main.py` (Plan 04).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All three files are complete implementations. `briefings` dict starts empty but is populated by `run_generate()` which is the intended runtime behavior.

## Threat Flags

No new security surface introduced beyond what the threat model (T-05-02-01 through T-05-02-05) already captures.

## Self-Check

### Files exist:
- [x] services/briefing-generator/config.py — FOUND
- [x] services/briefing-generator/opencti_client.py — FOUND
- [x] services/briefing-generator/generator.py — FOUND

### Commits exist:
- [x] f299986 — feat(05-02): add config.py and opencti_client.py
- [x] 976f7e5 — feat(05-02): implement generator.py

### Self-Check: PASSED
