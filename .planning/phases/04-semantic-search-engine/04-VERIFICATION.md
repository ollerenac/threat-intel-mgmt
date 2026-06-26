---
phase: 04-semantic-search-engine
verified: 2026-06-26T06:00:52Z
status: passed
score: 7/7
behavior_unverified: 0
overrides_applied: 0
re_verification: false
---

# Phase 4: Semantic Search Engine Verification Report

**Phase Goal:** Build a semantic search engine that lets analysts find IOCs using natural-language queries
**Verified:** 2026-06-26T06:00:52Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | AISEM-01: semantic-engine indexes all indicators from OpenCTI as embedding vectors | VERIFIED | `run_index_loop()` calls `list_all_indicators()`/`list_indicators_since()`, embeds via `_embed_with_retry()`, upserts into ChromaDB. Human checkpoint confirmed `total=23067` live. |
| 2 | AISEM-02: analyst can search with natural-language query and receive ranked IOC results | VERIFIED | `GET /search?q=` wired through `searcher.search()` → ChromaDB query. Results ordered by cosine distance ascending (score descending). `test_search_returns_ranked` PASSES. Human confirmed 10 results for "malware botnet C2 server". |
| 3 | AISEM-03: each result includes a similarity score (0.0–1.0) | VERIFIED | `score = round(1.0 - dist, 4)` in `searcher.py:51`. `test_score_conversion` PASSES: distances [0.2, 0.8] → scores [0.8, 0.2]. Human confirmed scores 0.57–0.60 live. |
| 4 | AISEM-04: result links back to the corresponding object in OpenCTI | VERIFIED | `opencti_url` constructed as `{OPENCTI_BASE_URL}/dashboard/observations/indicators/{indicator['id']}` in `indexer.py:171`. `OPENCTI_BASE_URL=http://localhost:8080` in docker-compose.yml. Human verified deep-link opens correct indicator in browser. |
| 5 | /health returns 200 immediately with status/index_status/indexed/total (D-05, never blocks) | VERIFIED | `health()` returns `{"status": "ok", **indexer.index_state}` synchronously. `asyncio.to_thread` offloads blocking index cycle so event loop stays free during indexing. Human confirmed /health responds during indexing. |
| 6 | /search validates q (non-empty → 400, >500 chars → 400) and clamps n_results [1,100] | VERIFIED | `main.py:49-53` — empty q raises 400, `len(q) > 500` raises 400, `n_results = max(1, min(n_results, 100))` at line 53. Commits dd143a3 (clamp) and 3055e36 (validation) both in git log. |
| 7 | Test suite: 8 unit tests pass (4 indexer + 4 searcher) | VERIFIED | `python3 -m pytest tests/ -v` — 8 passed in 2.27s, 0 failed, 0 skipped. Confirmed live on host with system Python 3.10. |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Status | Evidence |
|----------|--------|---------|
| `services/semantic-engine/pytest.ini` | VERIFIED | Exists; `testpaths = tests` confirmed (pytest discovered tests from this config). |
| `services/semantic-engine/tests/__init__.py` | VERIFIED | Exists (empty package marker). |
| `services/semantic-engine/tests/conftest.py` | VERIFIED | Exists; `mock_ollama.embed.return_value.embeddings` is list-of-lists, 768 elements; `mock_chroma.query.return_value["distances"][0] == [0.2, 0.8]`. |
| `services/semantic-engine/tests/test_indexer.py` | VERIFIED | Exists; 4 tests, all PASS with import guard pattern. |
| `services/semantic-engine/tests/test_searcher.py` | VERIFIED | Exists; 4 tests, all PASS with monkeypatch pattern for `_ollama` singleton. |
| `services/semantic-engine/Dockerfile` | VERIFIED | Exists; `CMD` uses port 8002; `libmagic1` present (required by pycti==6.4.11 transitively). |
| `services/semantic-engine/requirements.txt` | VERIFIED | `pycti==6.4.11` and `chromadb==1.5.9` exactly pinned. |
| `services/semantic-engine/config.py` | VERIFIED | All 8 env vars: `OPENCTI_URL`, `OPENCTI_TOKEN`, `OPENCTI_BASE_URL`, `OLLAMA_URL`, `OLLAMA_EMBED_MODEL`, `CHROMADB_URL`, `SIMILARITY_THRESHOLD` (float, default 0.3), `POLL_INTERVAL_SECONDS` (int, default 300). Token logged as `bool()` only. |
| `services/semantic-engine/opencti_client.py` | VERIFIED | `list_all_indicators()` uses `getAll=True, first=500`; `list_indicators_since()` has try/except fallback to full fetch. |
| `services/semantic-engine/indexer.py` | VERIFIED | `index_state` exported at module level; `get_collection()` uses `configuration={"hnsw":{"space":"cosine"}}`; `run_index_loop()` is `async def`; `_embed_with_retry` accesses `response.embeddings[0]` (plural); `WATERMARK_ID="_watermark_"` sentinel; `asyncio.to_thread` wraps blocking cycle. |
| `services/semantic-engine/searcher.py` | VERIFIED | `score = round(1.0 - dist, 4)`; threshold filter on `score < threshold` (not `dist >`); result shape includes `ioc_type, value, score, opencti_url, embedded_text`. |
| `services/semantic-engine/main.py` | VERIFIED | `asynccontextmanager` lifespan with `asyncio.create_task(indexer.run_index_loop())`; `/health` spreads `index_state`; `/search` validates q and clamps n_results; no `BackgroundTasks`. |

---

### Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|-----|--------|---------|
| `main.py` lifespan | `indexer.run_index_loop()` | `asyncio.create_task()` | WIRED | `main.py:27` — `asyncio.create_task(indexer.run_index_loop())` |
| `main.py /health` | `indexer.index_state` | `**indexer.index_state` spread | WIRED | `main.py:37` — `{"status": "ok", **indexer.index_state}` |
| `main.py /search` | `indexer.get_collection()` | direct call | WIRED | `main.py:56` — `searcher.search(indexer.get_collection(), ...)` |
| `main.py /search` | `searcher.search()` | direct call with `SIMILARITY_THRESHOLD` from config | WIRED | `main.py:55-59` — passes `threshold=SIMILARITY_THRESHOLD` |
| `indexer._index_batch` | `OPENCTI_BASE_URL` | f-string URL construction | WIRED | `indexer.py:171` — `f"{OPENCTI_BASE_URL}/dashboard/observations/indicators/{indicator['id']}"` |
| `searcher.search()` | `embed_query()` | internal call with optional `ollama_client` injection | WIRED | `searcher.py:42` — `query_vec = embed_query(query, ollama_client)` |
| `indexer.run_index_loop()` | `asyncio.to_thread(_run_index_cycle, ...)` | thread offload | WIRED | `indexer.py:224` — prevents event-loop starvation during 23k-IOC index |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `main.py /health` | `index_state` | `indexer.index_state` dict mutated by `_run_index_cycle` | Yes — `index_state["total"] = len(indicators)` populated from live pycti response | FLOWING |
| `main.py /search` | `results` | `searcher.search()` → ChromaDB `collection.query()` → distance/metadata from real vectors | Yes — query vector from Ollama embed, distances from ChromaDB cosine index | FLOWING |
| `indexer._index_batch` | `opencti_url` in metadata | `OPENCTI_BASE_URL` env var + indicator `id` | Yes — constructed per indicator from pycti response `id` field | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 8 unit tests pass | `python3 -m pytest tests/ -v` (run on host) | 8 passed in 2.27s | PASS |
| `test_score_conversion`: distance→score conversion and threshold filter | named test within suite | PASSED | PASS |
| `test_search_returns_ranked`: descending score order | named test within suite | PASSED | PASS |
| `test_opencti_url_format`: opencti_url contains indicator ID, embedded_text present | named test within suite | PASSED | PASS |
| Live /health returning index progress | Human checkpoint (04-05) | `index_status` progressed from "starting" → "indexing" with `total=23067` | PASS (human-confirmed) |
| Live /search?q=malware+botnet+C2+server | Human checkpoint (04-05) | 10 results, scores 0.57–0.60, opencti_url correct, embedded_text present | PASS (human-confirmed) |
| Deep-link to OpenCTI | Human checkpoint (04-05) | Browser opened correct indicator at localhost:8080 | PASS (human-confirmed) |

---

### Requirements Coverage

| Requirement | Plans | Description | Status | Evidence |
|-------------|-------|-------------|--------|---------|
| AISEM-01 | 01, 02, 03, 05 | semantic-engine indexes all indicators from OpenCTI as embedding vectors | SATISFIED | `run_index_loop()` full+incremental fetch, `_index_batch()` embeds+upserts all indicators including no-description IOCs (D-03). Live: `total=23067`. |
| AISEM-02 | 01, 04, 05 | Analyst can search with natural language query and receive ranked IOC results | SATISFIED | `GET /search?q=` → `searcher.search()` → ChromaDB cosine query → ranked results. `test_search_returns_ranked` PASSES. Live: 10 results for botnet C2 query. |
| AISEM-03 | 01, 04, 05 | Each result includes a similarity score (0.0–1.0) | SATISFIED | `score = round(1.0 - dist, 4)` in `searcher.py:51`. `test_score_conversion` PASSES. Live: scores 0.57–0.60. |
| AISEM-04 | 01, 04, 05 | Result links back to the corresponding object in OpenCTI | SATISFIED | `opencti_url` = `{OPENCTI_BASE_URL}/dashboard/observations/indicators/{id}`. `OPENCTI_BASE_URL=http://localhost:8080` in docker-compose. `test_opencti_url_format` PASSES. Live: deep-link verified in browser. |

No orphaned requirements: all four AISEM IDs claimed by plans match REQUIREMENTS.md exactly. REQUIREMENTS.md traceability table marks all four as Complete, Phase 4.

---

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|-----------|
| None | — | — | No `TBD`, `FIXME`, or `XXX` markers found in any phase-4 source file. No stub returns (empty arrays/nulls) in production paths. No TODO/PLACEHOLDER text. |

The only `ponytail:` comments present are intentional design notes (lazy ChromaDB init, monkeypatch injection point) — these are correctly marked and not unresolved debt.

---

### Human Verification Required

None. All programmatic checks passed. Live integration was human-verified at the 04-05 checkpoint gate (blocking, required human approval before phase closure). The integration checkpoint covered all four AISEM requirements observably:

- AISEM-01: `/health` showed `total=23067`, indexed count progressing
- AISEM-02: 10 semantically relevant results returned for natural-language query
- AISEM-03: all scores in [0.0, 1.0] range (observed 0.57–0.60)
- AISEM-04: deep-link opened correct indicator in OpenCTI browser

---

### Notable Deviations from Plans (Accepted)

| Deviation | Plan | Resolution | Impact |
|-----------|------|------------|--------|
| `libmagic1` in Dockerfile | 04-02 said remove it | pycti==6.4.11 transitively requires `libmagic.so`; restored with `ponytail:` comment | None — correct fix |
| monkeypatch `_ollama` singleton in test_searcher.py instead of positional arg injection | 04-01 suggested positional arg | `search()` signature uses module-level singleton per PATTERNS.md; monkeypatch is correct injection point | None — plan authorized adaptation |
| `asyncio.to_thread` wrapping `_run_index_cycle` | Not in original 04-03/04 plans | Discovered during integration: event-loop starvation on 23k-IOC initial index; fix committed as a656489 | Positive — improves /health responsiveness during indexing |
| `n_results` clamped to [1, 100] | Not in original 04-04 plan | Discovered during integration: unbounded n_results could cause ChromaDB OOM; fix committed as dd143a3 | Positive — security hardening |

---

_Verified: 2026-06-26T06:00:52Z_
_Verifier: Claude (gsd-verifier)_
