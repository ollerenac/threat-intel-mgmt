---
phase: 04-semantic-search-engine
plan: "03"
subsystem: semantic-engine
tags: [indexer, chromadb, ollama, embeddings, watermark, tdd-green]
status: complete

dependency_graph:
  requires: [04-02]
  provides: [indexer.py, index_state, get_collection, run_index_loop]
  affects: [04-04-main.py, 04-05-searcher.py]

tech_stack:
  added: []
  patterns:
    - lazy ChromaDB HttpClient init (deferred to first get_collection call)
    - cosine HNSW collection via configuration= key (ChromaDB 1.x API)
    - Ollama embed via client.embed(input=).embeddings[0]
    - D-04 watermark sentinel (_watermark_ ID in ChromaDB)
    - D-01/D-03 embed text format (em-dash with desc, brackets without)

key_files:
  created:
    - services/semantic-engine/indexer.py
  modified: []

decisions:
  - "[04-03] Lazy ChromaDB HttpClient: deferred _chroma init to get_collection() call to keep module import side-effect free — test import guard works without live ChromaDB"
  - "[04-03] configuration={hnsw:{space:cosine}} — NOT metadata= key (ChromaDB 1.x API)"
  - "[04-03] response.embeddings[0] confirmed (not deprecated .embedding singular)"

metrics:
  duration: 4m
  completed: "2026-06-26"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 4 Plan 03: Indexer Implementation Summary

**One-liner:** ChromaDB cosine-space indexer with Ollama nomic-embed-text embeddings, D-04 watermark sentinel, and D-01/D-03 embed text formatting.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | indexer.py — build_embed_text, ChromaDB collection, watermark, run_index_loop | 09e90b5 | services/semantic-engine/indexer.py |

---

## What Was Built

`services/semantic-engine/indexer.py` — the core indexing engine. Provides:

- **`build_embed_text(indicator)`** — D-01: `"{type}: {value} — {description} {labels}"` when description present (em dash U+2014); D-03: `"{type}: {value} [{labels}]"` when absent. Strips trailing whitespace.
- **`get_collection()`** — idempotent `get_or_create_collection` with `configuration={"hnsw": {"space": "cosine"}}`. Called by main.py search endpoint to pass to searcher.
- **`read_watermark(collection)`** / **`write_watermark(collection, ts)`** — D-04 sentinel pattern using `WATERMARK_ID = "_watermark_"`. Stored as ChromaDB metadata, never appears in query results.
- **`_embed_with_retry(text)`** — wraps `_ollama.embed(model=..., input=text)`, accesses `response.embeddings[0]` (plural). Retries with `_RETRY_DELAYS = [30, 60, 120]`, returns `None` on exhaustion.
- **`_index_batch(collection, indicators)`** — embeds and upserts each indicator; skips None vectors; stores `ioc_type`, `value`, `opencti_url`, `embedded_text` as metadata (D-08).
- **`run_index_loop()`** — `async def` coroutine. Full fetch on no watermark; incremental via `list_indicators_since` when watermark present. Updates `index_state` throughout. Cycle failures are caught and logged; loop continues after sleep.
- **`index_state`** — module-level dict `{"status": "starting", "indexed": 0, "total": 0}` exported for main.py `/health` spread.

---

## Verification

```
python3 -m pytest tests/test_indexer.py -v
  PASSED test_build_embed_text_with_description
  PASSED test_build_embed_text_no_description
  PASSED test_build_embed_text_no_description_no_labels
  PASSED test_build_embed_text_empty_labels_ignored

python3 -m pytest tests/ -v
  4 passed (test_indexer), 4 skipped (test_searcher — searcher.py not yet written)
```

All acceptance criteria confirmed:
- 4 `test_build_embed_text_*` tests PASSED
- `from indexer import index_state, get_collection, build_embed_text, run_index_loop` exits 0
- `cosine` confirmed in `get_collection` source
- `embeddings[0]` confirmed in `_embed_with_retry` source

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lazy ChromaDB HttpClient to fix import-time connection error**
- **Found during:** Task 1 verification — `python3 -c "from indexer import build_embed_text"` raised `ValueError: Could not connect to a Chroma server`
- **Issue:** `chromadb.HttpClient(...)` at module level attempts a network connection immediately on import. With no ChromaDB reachable from host (Docker internal network), this crashes the import. The test import guard catches it as ImportError, causing all 4 tests to skip.
- **Fix:** Moved `chromadb.HttpClient(...)` call into a lazy `_get_chroma()` helper called only from `get_collection()`. Module-level `_chroma` starts as `None`. No connection attempted at import time.
- **Files modified:** `services/semantic-engine/indexer.py`
- **Commit:** 09e90b5

---

## Known Stubs

None — `indexer.py` is fully implemented. `index_state`, `get_collection`, `build_embed_text`, `run_index_loop`, `read_watermark`, `write_watermark`, `_embed_with_retry`, `_index_batch` are all production-ready.

---

## Threat Surface Scan

No new network endpoints introduced. `indexer.py` is an internal background worker:
- Reads from OpenCTI via pycti (internal Docker network, token from env, log_level="error")
- Writes to ChromaDB (internal Docker network, no auth surface)
- Embeds via Ollama (internal Docker network, no user data escapes)
- `OPENCTI_TOKEN` is never logged per config.py pattern

No threat flags beyond the plan's T-04-03-01 and T-04-03-02 (already accepted/mitigated).

---

## Self-Check: PASSED

- [x] `services/semantic-engine/indexer.py` exists
- [x] Commit 09e90b5 exists in git log
- [x] 4 tests PASSED, 4 tests skipped (correct — searcher.py not yet written)
