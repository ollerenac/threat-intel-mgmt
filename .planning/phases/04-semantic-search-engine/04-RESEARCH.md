# Phase 4: Semantic Search Engine - Research

**Researched:** 2026-06-25
**Domain:** FastAPI + ChromaDB (HTTP client) + Ollama embeddings + pycti indicator pagination
**Confidence:** MEDIUM

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Embed enriched context per IOC: `"{indicator_type}: {value} — {description} {labels}"` — not raw value alone.
- **D-02:** Pull enrichment from OpenCTI indicator fields only (name, description, labels). No graph traversal. One API call per indicator.
- **D-03:** For indicators with no description, embed `"{type}: {value} [{labels}]"`. Never exclude no-description IOCs.
- **D-04:** Incremental watermark indexing: store `last_indexed_at` timestamp in ChromaDB metadata. On restart, fetch only `updated_at > last_indexed_at`. ChromaDB handles upserts.
- **D-05:** On first startup (ChromaDB empty), run full index in background — do NOT block `/health`. Service responds immediately with `{"status": "ok", "indexed": N, "total": M}`.
- **D-06:** Return top 10 results, fixed.
- **D-07:** Similarity threshold 0.3 — drop results scoring below this. Expose as env var `SIMILARITY_THRESHOLD=0.3`.
- **D-08:** Each result includes: `ioc_type`, `value`, `score` (0.0–1.0), `opencti_url`, `embedded_text`. Store `embedded_text` as ChromaDB metadata alongside the vector.

### Claude's Discretion

- ChromaDB collection strategy (single vs. per-type), exact pycti query approach for indicator pagination, Dockerfile and requirements.txt structure — follow `intel-extractor` patterns.

### Deferred Ideas (OUT OF SCOPE)

- Filtering results by IOC type
- Graph-traversal enrichment (linked report titles)
- Configurable `?limit=` param
- Semantic search over non-indicator objects
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AISEM-01 | semantic-engine indexes all indicators from OpenCTI as embedding vectors | pycti `indicator.list(getAll=True)` retrieves all; ChromaDB `collection.upsert()` indexes them |
| AISEM-02 | Analyst can search with natural language query and receive ranked IOC results | `collection.query(query_embeddings=[...], n_results=10)` returns ranked results |
| AISEM-03 | Each result includes a similarity score (0.0–1.0) | ChromaDB returns cosine distance; convert: `score = 1 - distance` |
| AISEM-04 | Result links back to the corresponding object in OpenCTI | Construct `{OPENCTI_URL}/dashboard/observations/indicators/{indicator_id}` and store as metadata |
</phase_requirements>

---

## Summary

The semantic-engine is a FastAPI service that mirrors the intel-extractor pattern (background tasks, module-level state dict, `/health` returning progress). It adds ChromaDB as a vector store and Ollama's `nomic-embed-text` model for 768-dimensional embeddings. The entire pycti + ChromaDB + Ollama integration is new territory not yet in the codebase.

The three critical API facts that must not be assumed from training data:

1. ChromaDB's `query()` returns cosine **distance** (0 = identical), not similarity. Convert via `score = 1 - distance`. D-07's threshold of 0.3 (similarity) means filtering where `distance > 0.7`.
2. The current Ollama Python client uses `client.embed(model=..., input=...)` (not the deprecated `client.embeddings(model=..., prompt=...)`). Response is `response.embeddings[0]` (list of lists).
3. pycti 6.4.11's `indicator.list(getAll=True)` auto-paginates through all results using the `hasNextPage`/`endCursor` loop internally — no manual cursor loop needed.

The docker-compose stub already wires the service at port 8002 in the `semantic` profile with `OPENCTI_URL`, `OPENCTI_TOKEN`, `OLLAMA_URL`, `OLLAMA_EMBED_MODEL`, `CHROMADB_URL`, and `POLL_INTERVAL_SECONDS` env vars. No docker-compose changes are needed.

**Primary recommendation:** Build `services/semantic-engine/` from scratch following the `intel-extractor` file layout (config.py → opencti_client.py → indexer.py → searcher.py → main.py). The indexer is the hardest part — get the ChromaDB cosine distance / similarity conversion right and the D-04 watermark correct.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Embedding generation | API / Backend (semantic-engine) | — | CPU/GPU work stays server-side; nomic-embed-text is an Ollama model |
| Vector storage & similarity search | Database / Storage (ChromaDB) | — | ChromaDB owns HNSW index; semantic-engine calls it |
| Indicator retrieval | API / Backend (semantic-engine → OpenCTI) | — | Fetch-on-startup, poll-on-interval |
| Natural-language query endpoint | API / Backend (semantic-engine) | — | Phase 6 dashboard will call GET /search?q= |
| OpenCTI deep-link construction | API / Backend (semantic-engine) | — | URL built from OPENCTI_URL env var + indicator id |
| Progress visibility | API / Backend (semantic-engine /health) | — | Module-level dict, same pattern as intel-extractor |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | 0.115.14 (pinned, matches intel-extractor) | HTTP API | Already in use; pin matches |
| `uvicorn` | latest | ASGI server | Same Dockerfile pattern |
| `chromadb` | 1.5.9 (latest) | Vector store HTTP client | Official Python client; connects to ChromaDB 1.4.4 container |
| `ollama` | 0.6.2 (installed) | Embedding generation | Already in use in intel-extractor; `embed()` API |
| `pycti` | 6.4.11 (pinned) | OpenCTI indicator fetch | Must match OpenCTI 6.4.0; do not upgrade |
| `pytest` | latest | Unit tests | Established project pattern |
| `pytest-mock` | latest | Mock ChromaDB/Ollama | Established project pattern |

[VERIFIED: pip index versions] — chromadb 1.5.9, ollama 0.6.2, pycti latest is 7.x but pinned to 6.4.11 to match OpenCTI 6.4.0.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `requests` | latest | Optional health probes | Already in intel-extractor; reuse if needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `chromadb` Python client | Raw HTTP requests to ChromaDB API | Python client handles auth, serialization, retry. Use the SDK. |
| `ollama.embed()` | Direct HTTP POST to Ollama `/api/embed` | SDK call is cleaner; consistent with intel-extractor pattern |
| `getAll=True` in pycti | Manual cursor loop | `getAll=True` handles pagination internally — no custom loop needed |

**Installation:**

```bash
pip install fastapi==0.115.14 uvicorn chromadb==1.5.9 ollama==0.6.2 pycti==6.4.11 pytest pytest-mock
```

**Version verification:** [VERIFIED: pip index versions chromadb → 1.5.9; pip show ollama → 0.6.2; pip show pycti → 6.4.11 installed (7.x latest on PyPI — MUST stay pinned)]

---

## Package Legitimacy Audit

> All packages are established libraries already confirmed in this project's codebase or the Python ecosystem. PyPI's download stats are unavailable via the legitimacy seam (returns `unknown-downloads` for all PyPI packages), so verdicts show SUS due to the missing metric — not due to actual legitimacy concerns.

| Package | Registry | Age | Source Repo | Verdict | Disposition |
|---------|----------|-----|-------------|---------|-------------|
| `chromadb` | PyPI | 3+ yrs (0.x era), 1.x since 2025 | github.com/chroma-core/chroma | SUS (unknown downloads) | Approved — official chroma-core org, widely used |
| `ollama` | PyPI | 2+ yrs | github.com/ollama/ollama-python | SUS (unknown downloads) | Approved — official Ollama project |
| `pycti` | PyPI | 5+ yrs | github.com/OpenCTI-Platform/opencti | SUS (too-new + unknown downloads) | Approved — official OpenCTI project, already pinned and in use |
| `fastapi` | PyPI | 5+ yrs | github.com/fastapi/fastapi | SUS (unknown downloads) | Approved — already in use in intel-extractor |
| `uvicorn` | PyPI | 5+ yrs | github.com/Kludex/uvicorn | SUS (unknown downloads) | Approved — already in use in intel-extractor |

**Packages removed due to [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** all listed above, but all are established libraries already in use in this project or with official org GitHub repos. PyPI download metric unavailable — not a legitimacy signal.

---

## Architecture Patterns

### System Architecture Diagram

```
OpenCTI (8080)
     │
     │ pycti indicator.list(getAll=True)
     │ [on startup + every POLL_INTERVAL_SECONDS]
     ▼
semantic-engine (8002)
  [indexer.py]
     │ build_embed_text(indicator)  →  "{type}: {value} — {desc} {labels}"
     │
     │ ollama.Client.embed(model='nomic-embed-text', input=text)
     │                                  ▼
     │                         Ollama (11434)
     │                         nomic-embed-text → 768-dim vector
     │
     │ collection.upsert(ids, embeddings, documents, metadatas)
     ▼
ChromaDB (8000) [cosine HNSW index]
     ▲
     │ collection.query(query_embeddings=[...], n_results=10)
     │
  [searcher.py]
     ▲
     │ GET /search?q=<natural language query>
     │
Phase 6 Dashboard / curl
```

### Recommended Project Structure

```
services/semantic-engine/
├── Dockerfile          # python:3.12-slim, no apt extras needed (no libmagic)
├── requirements.txt    # fastapi + uvicorn + chromadb + ollama + pycti + pytest
├── config.py           # env var reads (OPENCTI_URL, OPENCTI_TOKEN, OLLAMA_URL,
│                       # OLLAMA_EMBED_MODEL, CHROMADB_URL, SIMILARITY_THRESHOLD,
│                       # POLL_INTERVAL_SECONDS, OPENCTI_BASE_URL)
├── opencti_client.py   # build_pycti_client(), list_all_indicators()
├── indexer.py          # build_embed_text(), index_state dict, run_index(),
│                       # get_or_create_collection(), watermark read/write
├── searcher.py         # embed_query(), search_collection(), score conversion
├── main.py             # FastAPI app, /health, /search, startup event → run_index()
├── pytest.ini          # testpaths = tests
└── tests/
    ├── __init__.py
    ├── conftest.py     # mock_chroma, mock_ollama, mock_pycti fixtures
    ├── test_indexer.py # build_embed_text, score conversion, watermark logic
    └── test_searcher.py # search result shaping, threshold filtering
```

### Pattern 1: ChromaDB HTTP Client Setup + Cosine Collection

```python
# Source: cookbook.chromadb.dev/core/collections/ + docs.trychroma.com/docs/collections/configure
import chromadb
from config import CHROMADB_URL  # "http://chromadb:8000"

# Parse host/port from URL
from urllib.parse import urlparse
parsed = urlparse(CHROMADB_URL)
_chroma = chromadb.HttpClient(host=parsed.hostname, port=parsed.port or 8000)

COLLECTION_NAME = "ioc_embeddings"

def get_or_create_collection():
    return _chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},  # MUST set — default is l2
    )
```

[CITED: docs.trychroma.com/docs/collections/configure]

### Pattern 2: Ollama Embedding Call

```python
# Source: github.com/ollama/ollama-python/_types.py (inspected in session)
import ollama
from config import OLLAMA_URL, OLLAMA_EMBED_MODEL

_ollama = ollama.Client(host=OLLAMA_URL)  # same singleton pattern as intel-extractor

def embed_text(text: str) -> list[float]:
    response = _ollama.embed(model=OLLAMA_EMBED_MODEL, input=text)
    return response.embeddings[0]  # embeddings (plural) → first item = 768-dim vector
    # DO NOT use: client.embeddings(model=..., prompt=...) — that API is deprecated
    # Deprecated returns response.embedding (singular) — wrong attribute name
```

[VERIFIED: codebase — inspected ollama 0.6.2 source at runtime]

### Pattern 3: pycti Bulk Indicator Fetch

```python
# Source: inspected pycti 6.4.11 Indicator.list() source at runtime
def list_all_indicators(client) -> list[dict]:
    # getAll=True handles hasNextPage/endCursor pagination internally
    # first=500 sets page size for each internal request
    return client.indicator.list(getAll=True, first=500)

# Each indicator dict contains:
# indicator["id"]                         — OpenCTI internal UUID (for ChromaDB id + URL)
# indicator["name"]                        — indicator value (IP, domain, hash, etc.)
# indicator["x_opencti_main_observable_type"] — "IPv4-Addr", "Domain-Name", etc.
# indicator["description"]                 — may be None for feed-sourced IOCs
# indicator["objectLabel"]                 — list of {"id": ..., "value": "malware-distribution", ...}
# indicator["updated_at"]                  — ISO-8601 UTC string

# For watermark filter (incremental indexing):
filters = {
    "mode": "and",
    "filters": [{"key": "updated_at", "values": [last_indexed_at]}],
    "filterGroups": [],
}
# Then: client.indicator.list(getAll=True, first=500, filters=filters, orderBy="updated_at", orderMode="asc")
```

[VERIFIED: codebase — inspected pycti 6.4.11 Indicator.list() and INDICATOR_PROPERTIES at runtime]

### Pattern 4: ChromaDB Upsert

```python
# Source: docs.trychroma.com/docs/collections/update-data
collection.upsert(
    ids=[indicator["id"]],           # OpenCTI UUID — stable, idempotent key
    embeddings=[vector],              # 768-dim float list from nomic-embed-text
    documents=[embed_text],          # the text that was vectorized (for debugging)
    metadatas=[{
        "ioc_type": indicator["x_opencti_main_observable_type"],
        "value": indicator["name"],
        "opencti_url": f"{OPENCTI_BASE_URL}/dashboard/observations/indicators/{indicator['id']}",
        "embedded_text": embed_text,  # D-08: analyst sees WHY this matched
    }],
)
```

[CITED: docs.trychroma.com/docs/collections/update-data]

### Pattern 5: Search with Similarity Score Conversion

```python
# Source: cookbook.chromadb.dev/core/collections/ + cosine distance confirmed
def search(query: str, n_results: int = 10) -> list[dict]:
    query_vec = embed_text(query)
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=n_results,
        include=["distances", "metadatas", "documents"],
    )
    # results["distances"][0]  → list of cosine DISTANCES (0=identical, 2=opposite)
    # results["metadatas"][0]  → list of metadata dicts
    # Convert distance to similarity: score = 1 - distance
    threshold = float(os.environ.get("SIMILARITY_THRESHOLD", "0.3"))
    output = []
    for dist, meta in zip(results["distances"][0], results["metadatas"][0]):
        score = round(1.0 - dist, 4)  # D-07: cosine distance → similarity score
        if score < threshold:
            continue
        output.append({
            "ioc_type": meta["ioc_type"],
            "value": meta["value"],
            "score": score,
            "opencti_url": meta["opencti_url"],
            "embedded_text": meta["embedded_text"],
        })
    return output
```

[VERIFIED: confirmed cosine distance semantics via docs.trychroma.com and cookbook.chromadb.dev]

### Pattern 6: Watermark Storage in ChromaDB Metadata

```python
# D-04: store last_indexed_at as a sentinel document in ChromaDB
WATERMARK_ID = "_watermark_"

def read_watermark(collection) -> Optional[str]:
    try:
        result = collection.get(ids=[WATERMARK_ID], include=["metadatas"])
        if result["ids"]:
            return result["metadatas"][0].get("last_indexed_at")
    except Exception:
        pass
    return None

def write_watermark(collection, timestamp: str):
    collection.upsert(
        ids=[WATERMARK_ID],
        embeddings=[[0.0] * 768],  # dummy vector — never queried
        documents=["watermark"],
        metadatas=[{"last_indexed_at": timestamp}],
    )
```

### Pattern 7: Startup Background Indexing (Non-blocking /health)

```python
# Source: intel-extractor main.py pattern + FastAPI lifespan
import asyncio
from contextlib import asynccontextmanager

# Module-level state (same pattern as intel-extractor's jobs{})
index_state = {"status": "starting", "indexed": 0, "total": 0}

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(run_index_loop())  # fire-and-forget
    yield

app = FastAPI(title="semantic-engine", version="1.0.0", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok", **index_state}  # D-05: never blocks, always returns
```

### Anti-Patterns to Avoid

- **Using `client.embeddings()` (deprecated):** Returns `response.embedding` (singular). Use `client.embed()` → `response.embeddings[0]`.
- **Not setting `configuration={"hnsw": {"space": "cosine"}}`:** Default metric is L2. Cosine is required for text embeddings. Cannot change after collection creation.
- **Treating ChromaDB distances as similarity scores:** `distances[0][0] = 0.1` means 90% similar (score = 0.9), not 10% similar.
- **Applying D-07 threshold to the raw distance:** Filter on `score >= threshold` (where `score = 1 - distance`), not `distance >= threshold`.
- **Using `metadata={"hnsw:space": "cosine"}` (old API):** This is the pre-1.0 syntax. ChromaDB 1.x uses `configuration={"hnsw": {"space": "cosine"}}`.
- **Calling `pycti.indicator.list()` without `getAll=True`:** Returns only first 500 indicators. Use `getAll=True` for full corpus.
- **Blocking `/health` during initial indexing:** Use `asyncio.create_task()` in lifespan, not blocking startup code. Same pattern as intel-extractor.
- **Pinning `pycti` to 7.x:** The repo uses OpenCTI 6.4.0 which requires pycti 6.4.11. pycti 7.x breaks against 6.x OpenCTI.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HNSW vector indexing | Custom nearest-neighbor search | ChromaDB `collection.query()` | HNSW with cosine space handles 22k+ vectors efficiently |
| Pagination through OpenCTI indicators | Manual cursor while-loop | `indicator.list(getAll=True)` | Built-in; handles `hasNextPage`/`endCursor` internally |
| Embedding generation | numpy/scipy vector math | `ollama.Client.embed()` | nomic-embed-text is already pulled and optimized |
| Distance-to-similarity conversion | Custom formula research | `score = 1 - distance` | Standard for cosine space in ChromaDB |
| Collection creation idempotency | Check-then-create | `get_or_create_collection()` | Atomic; safe to call on every startup |

**Key insight:** ChromaDB's `get_or_create_collection()` + `upsert()` handles all the hard parts of incremental indexing — idempotency, deduplication by ID, update detection.

---

## Common Pitfalls

### Pitfall 1: ChromaDB Distance ≠ Similarity (HIGH IMPACT)

**What goes wrong:** Threshold filtering passes all results (or blocks all results) because raw distance values are used instead of converted similarity scores.

**Why it happens:** ChromaDB's `query()` returns `distances` field with cosine **distance** values (0–2 range), not cosine similarity (0–1 range). Training data and examples often conflate the two.

**How to avoid:** Always convert: `score = 1 - distance`. Apply D-07 threshold as `if score < SIMILARITY_THRESHOLD: continue`. Write a unit test that asserts `score = 1 - distance` for a known distance value.

**Warning signs:** All queries return 10 results even with very low threshold; or queries for exact IOC names return 0 results with a threshold of 0.3.

### Pitfall 2: ChromaDB Default Distance Metric is L2, Not Cosine

**What goes wrong:** Collection is created without `configuration={"hnsw": {"space": "cosine"}}`. Semantic search works poorly for text because L2 is sensitive to vector magnitude, not just direction.

**Why it happens:** `get_or_create_collection(name)` silently uses L2 default. No error is raised.

**How to avoid:** Always pass `configuration={"hnsw": {"space": "cosine"}}`. This cannot be changed after collection creation — if wrong, must delete collection and re-index.

**Warning signs:** Queries for clearly related concepts return low similarity; unrelated IOCs score higher than related ones.

### Pitfall 3: ChromaDB Volume Mount Mismatch (EXISTING INFRASTRUCTURE)

**What goes wrong:** On container restart, ChromaDB starts empty even though the volume is mounted. All indexed data is lost.

**Why it happens:** `docker-compose.yml` mounts `chromadata:/chroma/chroma` but ChromaDB 1.4.4 (confirmed in running container) writes its data to `/data` (the 1.x default). The `/chroma/chroma` volume exists but ChromaDB ignores it.

**Impact on Phase 4:** On restart, the watermark will also be gone, so `run_index()` starts fresh. D-04 incremental indexing still works — the full re-index takes time but is correct.

**How to avoid in this phase:** Document in the plan that D-04 watermark reset on restart is expected given the volume issue. Do NOT try to fix the volume mount in Phase 4 — it is pre-existing infrastructure and risks breaking the running platform. Flag as a deployment note.

**Long-term fix (out of scope for Phase 4):** Add `IS_DOCKER=1 CHROMA_DATA_DIR=/chroma/chroma` env var to the chromadb service OR update the volume mount to `/data`.

### Pitfall 4: Using Deprecated `ollama.embeddings()` Instead of `ollama.embed()`

**What goes wrong:** `response.embedding` (singular) vs `response.embeddings[0]` (plural). AttributeError at runtime.

**Why it happens:** Many code examples use the old `/api/embeddings` endpoint. ollama 0.6.2 marks it deprecated but doesn't remove it.

**How to avoid:** Use `client.embed(model=OLLAMA_EMBED_MODEL, input=text)` → `response.embeddings[0]`. Write a conftest mock that returns `MagicMock(embeddings=[[0.1]*768])` to validate the attribute path.

### Pitfall 5: pycti Version Drift

**What goes wrong:** If requirements.txt uses `pycti` (unversioned), pip installs 7.x which breaks against OpenCTI 6.4.0.

**Why it happens:** pycti moved to date-based versioning (7.260624.0 etc.) — `pip install pycti` now installs 7.x.

**How to avoid:** Pin `pycti==6.4.11` in requirements.txt, identical to intel-extractor.

### Pitfall 6: Ollama Model Not Ready During Startup

**What goes wrong:** `embed()` call fails on first startup if nomic-embed-text is still loading.

**Why it happens:** Ollama healthcheck uses `ollama list` (passes immediately) but model is not loaded into memory until first call.

**How to avoid:** Wrap `embed()` calls in try/except and retry with backoff. The background indexer should retry on embed failure rather than crashing. Use the same `try/except` + logging pattern as intel-extractor's retry logic.

---

## Code Examples

### Build Embed Text (D-01, D-02, D-03)

```python
def build_embed_text(indicator: dict) -> str:
    ioc_type = indicator.get("x_opencti_main_observable_type", "Unknown")
    value = indicator.get("name", "")
    description = indicator.get("description") or ""
    labels = [lbl["value"] for lbl in (indicator.get("objectLabel") or [])]
    label_str = " ".join(labels)

    if description:
        return f"{ioc_type}: {value} — {description} {label_str}".strip()
    else:
        return f"{ioc_type}: {value} [{label_str}]".strip()  # D-03
```

### /health Endpoint with Progress

```python
@app.get("/health")
async def health():
    # D-05: never blocks; returns immediately with indexing progress
    return {
        "status": "ok",
        "index_status": index_state["status"],  # "starting" | "indexing" | "ready"
        "indexed": index_state["indexed"],
        "total": index_state["total"],
    }
```

### /search Endpoint

```python
@app.get("/search")
async def search(q: str, n_results: int = 10):  # D-06: default 10
    if not q:
        raise HTTPException(status_code=400, detail="q parameter required")
    results = searcher.search(q, n_results=n_results)
    return {"query": q, "results": results, "count": len(results)}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ollama.embeddings(prompt=...)` | `ollama.embed(input=...)` | ollama 0.4.x | Return type changed: `embedding` → `embeddings[0]` |
| `metadata={"hnsw:space": "cosine"}` | `configuration={"hnsw": {"space": "cosine"}}` | ChromaDB 1.0 | Old metadata syntax deprecated; config dict required |
| ChromaDB data in `/chroma/chroma` | ChromaDB 1.x data in `/data` | ChromaDB 1.0 | Volume mount in docker-compose.yml targets wrong path |
| `pycti==6.x` | `pycti==7.x` (date-based) on PyPI | 2026 | Must stay pinned to 6.4.11 for OpenCTI 6.4.0 compat |

**Deprecated/outdated:**

- `ollama.Client.embeddings()`: deprecated in ollama 0.4+, still works but returns wrong attribute shape
- `metadata={"hnsw:space": "cosine"}` in ChromaDB collection creation: pre-1.0 API, may still work but `configuration=` is the documented 1.x path

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | pycti `updated_at` is a valid filter key for the GraphQL `indicators` query | Pattern 3, Pitfall, D-04 | Incremental watermark indexing falls back to full re-index on every restart — slower but correct |
| A2 | The OpenCTI URL pattern for indicators is `/dashboard/observations/indicators/{id}` | Pattern 4, AISEM-04 | Deep-links 404; analyst cannot navigate from result to OpenCTI |
| A3 | ChromaDB 1.4.4 in the container accepts `configuration={"hnsw": {"space": "cosine"}}` (1.x API) | Pattern 1 | Collection creation fails; must fall back to `metadata={"hnsw:space": "cosine"}` (0.x API) |

---

## Open Questions

1. **Updated_at filter key in pycti GraphQL**
   - What we know: FilterGroup `{"key": "created_day", "values": [...]}` is used in pycti feedback entity. `updated_at` appears in INDICATOR_PROPERTIES returned fields.
   - What's unclear: Whether `updated_at` is a valid `IndicatorsOrdering` / filter key in the GraphQL schema for OpenCTI 6.4.0.
   - Recommendation: Implement D-04 with `orderBy="updated_at"` and filter; if it fails at runtime, fall back to `getAll=True` without filter (full re-index each poll is safe but slower).

2. **OpenCTI indicator deep-link URL pattern**
   - What we know: OpenCTI is at `OPENCTI_BASE_URL`. STIX indicators appear under "Observations" in the UI.
   - What's unclear: Exact URL path — could be `/observations/indicators/` or `/dashboard/observations/indicators/`.
   - Recommendation: Verify by navigating to one indicator in the running OpenCTI at localhost:8080 before hardcoding. Store as `OPENCTI_BASE_URL + "/dashboard/observations/indicators/" + id` initially.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| ChromaDB | Vector store | ✓ (healthy) | 1.4.4 (confirmed via `chroma --version` in container) | — |
| Ollama | Embedding generation | ✓ (healthy) | latest | — |
| nomic-embed-text model | AISEM-01 | ✓ pulled | 274 MB | — |
| OpenCTI | Indicator source | ✓ (healthy) | 6.4.0 | — |
| pycti 6.4.11 | Indicator fetch | ✓ installed | 6.4.11 | — |
| Python 3.12-slim (Docker) | Service runtime | ✓ (used by intel-extractor) | 3.12 | — |

[VERIFIED: docker compose ps — all 9 platform services healthy; docker exec ollama ollama list — nomic-embed-text present]

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:** none — all dependencies confirmed available.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (matches intel-extractor) |
| Config file | `services/semantic-engine/pytest.ini` (Wave 0 gap — create from intel-extractor template) |
| Quick run command | `python -m pytest tests/ -q` (inside container or with deps installed) |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AISEM-01 | `build_embed_text()` produces correct string for IOC with/without description/labels | unit | `pytest tests/test_indexer.py::test_build_embed_text -x` | ❌ Wave 0 |
| AISEM-01 | `run_index()` calls `collection.upsert()` with correct ids/embeddings/metadatas | unit | `pytest tests/test_indexer.py::test_run_index_calls_upsert -x` | ❌ Wave 0 |
| AISEM-02 | `search()` returns ranked results for a natural-language query | unit | `pytest tests/test_searcher.py::test_search_returns_ranked -x` | ❌ Wave 0 |
| AISEM-03 | Score conversion: `score = 1 - distance` applied correctly | unit | `pytest tests/test_searcher.py::test_score_conversion -x` | ❌ Wave 0 |
| AISEM-03 | D-07 threshold filters out low-similarity results | unit | `pytest tests/test_searcher.py::test_threshold_filters -x` | ❌ Wave 0 |
| AISEM-04 | Result `opencti_url` contains indicator id | unit | `pytest tests/test_searcher.py::test_opencti_url_format -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/ -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/__init__.py` — empty init
- [ ] `tests/conftest.py` — `mock_chroma`, `mock_ollama`, `mock_pycti` fixtures (mock `response.embeddings = [[0.1]*768]`)
- [ ] `tests/test_indexer.py` — covers AISEM-01
- [ ] `tests/test_searcher.py` — covers AISEM-02, AISEM-03, AISEM-04
- [ ] `pytest.ini` — `[pytest] testpaths = tests`

---

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1` in config.json.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | semantic-engine is internal-only (no exposed auth surface in Phase 4) |
| V3 Session Management | no | stateless HTTP API |
| V4 Access Control | no | service is on internal Docker network, not exposed externally |
| V5 Input Validation | yes | `q` query parameter — validate non-empty, truncate to reasonable max length (e.g., 500 chars) before embedding |
| V6 Cryptography | no | no user credentials or sensitive secrets encrypted in this service |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via `q` parameter | Tampering | Validate max length; the query is only embedded (not sent to an LLM), so injection risk is low but length cap prevents DoS |
| ChromaDB collection poisoning | Tampering | ChromaDB is internal-only; OpenCTI token scoped to read-only listing |
| OPENCTI_TOKEN exposure | Information Disclosure | Token read from env var, never logged. Use `log_level="error"` on pycti client (same as intel-extractor) |
| Uncaught exception leaking stack traces | Information Disclosure | FastAPI returns 500 with generic message; suppress tracebacks in responses |

---

## Sources

### Primary (MEDIUM confidence)

- ChromaDB 1.x docs: `docs.trychroma.com/docs/collections/configure` — cosine distance configuration
- ChromaDB cookbook: `cookbook.chromadb.dev/core/collections/` — query, upsert, distance conversion
- ollama 0.6.2 source: `github.com/ollama/ollama-python/blob/main/ollama/_types.py` — `EmbedResponse.embeddings` vs deprecated `EmbeddingsResponse.embedding`
- pycti 6.4.11: inspected `Indicator.list()` source at runtime — `getAll=True`, FilterGroup format, returned fields

### Secondary (MEDIUM confidence)

- ChromaDB migration guide: `docs.trychroma.com/docs/overview/migration` — 1.x breaking changes (data dir moved, auth removed)
- WebSearch: ChromaDB `HttpClient(host=, port=)` constructor confirmed via `cookbook.chromadb.dev/core/clients/`

### Tertiary (LOW confidence)

- [ASSUMED] A1: `updated_at` as pycti filter key — inferred from GraphQL field presence, not confirmed against running OpenCTI schema
- [ASSUMED] A2: OpenCTI deep-link URL pattern `/dashboard/observations/indicators/{id}` — needs runtime verification

---

## Metadata

**Confidence breakdown:**

- Standard stack: MEDIUM — package versions confirmed via `pip index versions` + runtime inspection
- Architecture: MEDIUM — ChromaDB and ollama APIs verified via source inspection and official docs; pycti pagination verified via source
- Pitfalls: HIGH for ChromaDB distance/similarity (confirmed via docs and WebSearch); MEDIUM for volume mount issue (confirmed via `docker exec`); MEDIUM for pycti version drift (confirmed via `pip index versions`)

**Research date:** 2026-06-25
**Valid until:** 2026-07-25 (ChromaDB 1.x stable; ollama API stable; pycti pinned)
