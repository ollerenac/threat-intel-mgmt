# Phase 4: Semantic Search Engine - Pattern Map

**Mapped:** 2026-06-25
**Files analyzed:** 10 (7 source + 3 test)
**Analogs found:** 9 / 10 (chromadb/ollama integration is net-new)

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `services/semantic-engine/config.py` | config | — | `services/intel-extractor/config.py` | exact |
| `services/semantic-engine/opencti_client.py` | service | request-response | `services/intel-extractor/opencti_client.py` | role-match (read vs write) |
| `services/semantic-engine/indexer.py` | service | batch + event-driven | `services/intel-extractor/extractor.py` (background job) | role-match |
| `services/semantic-engine/searcher.py` | service | request-response | `services/intel-extractor/extractor.py` (transform) | partial |
| `services/semantic-engine/main.py` | controller | request-response | `services/intel-extractor/main.py` | exact |
| `services/semantic-engine/Dockerfile` | config | — | `services/intel-extractor/Dockerfile` | exact |
| `services/semantic-engine/requirements.txt` | config | — | `services/intel-extractor/requirements.txt` | exact |
| `services/semantic-engine/pytest.ini` | config | — | *(none in intel-extractor; use testpaths convention)* | none |
| `services/semantic-engine/tests/conftest.py` | test | — | `services/intel-extractor/tests/conftest.py` | exact |
| `services/semantic-engine/tests/test_indexer.py` | test | — | `services/intel-extractor/tests/test_opencti_client.py` | role-match |
| `services/semantic-engine/tests/test_searcher.py` | test | — | `services/intel-extractor/tests/test_opencti_client.py` | role-match |

---

## Pattern Assignments

### `services/semantic-engine/config.py` (config)

**Analog:** `services/intel-extractor/config.py`

**Full pattern** (lines 1–22):
```python
"""
config.py — Environment variable configuration for semantic-engine.

All env vars are read at import time and exposed as module-level constants.
Security: token values are NEVER logged. Only presence is logged via bool().
"""
import logging
import os

logger = logging.getLogger(__name__)

OPENCTI_URL        = os.environ.get("OPENCTI_URL", "http://opencti:8080")
OPENCTI_TOKEN      = os.environ.get("OPENCTI_TOKEN", "")
OPENCTI_BASE_URL   = os.environ.get("OPENCTI_BASE_URL", "http://localhost:8080")
OLLAMA_URL         = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
CHROMADB_URL       = os.environ.get("CHROMADB_URL", "http://chromadb:8000")
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.3"))
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))

# D-07: token presence only — never log values
logger.info("OPENCTI_TOKEN configured: %s", bool(OPENCTI_TOKEN))
```

---

### `services/semantic-engine/opencti_client.py` (service, request-response)

**Analog:** `services/intel-extractor/opencti_client.py`

**Imports + client init pattern** (lines 1–43):
```python
import logging
import time
from typing import Optional

from pycti import OpenCTIApiClient

from config import OPENCTI_TOKEN, OPENCTI_URL

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [30, 60, 120]  # same as intel-extractor D-05

def build_pycti_client() -> OpenCTIApiClient:
    return OpenCTIApiClient(
        url=OPENCTI_URL,
        token=OPENCTI_TOKEN,
        log_level="error",  # suppress INFO spam from pycti internals
    )
```

**Read-all-indicators pattern** (new, no write analog — from RESEARCH.md Pattern 3):
```python
def list_all_indicators(client: OpenCTIApiClient) -> list[dict]:
    # getAll=True handles hasNextPage/endCursor pagination internally
    return client.indicator.list(getAll=True, first=500)

def list_indicators_since(client: OpenCTIApiClient, since: str) -> list[dict]:
    # D-04: incremental watermark fetch — falls back to getAll if updated_at filter fails
    filters = {
        "mode": "and",
        "filters": [{"key": "updated_at", "values": [since]}],
        "filterGroups": [],
    }
    try:
        return client.indicator.list(
            getAll=True, first=500, filters=filters,
            orderBy="updated_at", orderMode="asc",
        )
    except Exception:
        logger.warning("[opencti_client] updated_at filter failed, falling back to full fetch")
        return list_all_indicators(client)
```

---

### `services/semantic-engine/indexer.py` (service, batch)

**Analog:** `services/intel-extractor/extractor.py` (background jobs dict pattern)

**Module-level state pattern** — copy from `main.py` lines 40–47 jobs init:
```python
# Module-level state — same pattern as intel-extractor jobs{}
# Lost on restart (acceptable per D-04: watermark handles re-index)
index_state: dict = {"status": "starting", "indexed": 0, "total": 0}
```

**ChromaDB collection setup** (RESEARCH.md Pattern 1):
```python
import chromadb
from urllib.parse import urlparse
from config import CHROMADB_URL

_parsed = urlparse(CHROMADB_URL)
_chroma = chromadb.HttpClient(host=_parsed.hostname, port=_parsed.port or 8000)
COLLECTION_NAME = "ioc_embeddings"

def get_or_create_collection():
    # MUST set cosine — default is l2, wrong for text embeddings
    return _chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
    )
```

**Watermark pattern** (RESEARCH.md Pattern 6):
```python
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

**Embed text builder** (D-01/D-02/D-03 from RESEARCH.md):
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

**Retry pattern for embed failures** — copy from `opencti_client.py` lines 79–109:
```python
# Wrap ollama embed() calls in try/except + retry (Pitfall 6 — model not ready)
for attempt, delay in enumerate(_RETRY_DELAYS):
    try:
        vector = _ollama.embed(model=OLLAMA_EMBED_MODEL, input=text).embeddings[0]
        break
    except Exception as exc:
        if attempt < len(_RETRY_DELAYS) - 1:
            logger.warning("[indexer] embed failed attempt %d, retrying in %ds: %s", attempt+1, delay, exc)
            time.sleep(delay)
        else:
            logger.warning("[indexer] embed failed after %d attempts, skipping IOC: %s", len(_RETRY_DELAYS), exc)
            vector = None
```

**ChromaDB upsert** (RESEARCH.md Pattern 4):
```python
collection.upsert(
    ids=[indicator["id"]],
    embeddings=[vector],
    documents=[embed_text],
    metadatas=[{
        "ioc_type": indicator["x_opencti_main_observable_type"],
        "value": indicator["name"],
        "opencti_url": f"{OPENCTI_BASE_URL}/dashboard/observations/indicators/{indicator['id']}",
        "embedded_text": embed_text,  # D-08
    }],
)
```

---

### `services/semantic-engine/searcher.py` (service, request-response)

**No direct analog** — net-new ChromaDB query logic; use RESEARCH.md Pattern 5.

**Ollama embed singleton** (RESEARCH.md Pattern 2):
```python
import ollama
from config import OLLAMA_URL, OLLAMA_EMBED_MODEL

_ollama = ollama.Client(host=OLLAMA_URL)

def embed_query(text: str) -> list[float]:
    # DO NOT use client.embeddings() — deprecated, wrong attribute shape
    return _ollama.embed(model=OLLAMA_EMBED_MODEL, input=text).embeddings[0]
```

**Search + score conversion** (RESEARCH.md Pattern 5):
```python
def search(collection, query: str, n_results: int = 10, threshold: float = 0.3) -> list[dict]:
    query_vec = embed_query(query)
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=n_results,
        include=["distances", "metadatas", "documents"],
    )
    output = []
    for dist, meta in zip(results["distances"][0], results["metadatas"][0]):
        score = round(1.0 - dist, 4)  # cosine distance → similarity (RESEARCH Pitfall 1)
        if score < threshold:          # D-07: filter on score, NOT on dist
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

---

### `services/semantic-engine/main.py` (controller, request-response)

**Analog:** `services/intel-extractor/main.py` — exact pattern, swap BackgroundTasks for lifespan asyncio.create_task.

**Imports + app init** (analog lines 1–24):
```python
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

import indexer
import searcher
from config import SIMILARITY_THRESHOLD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

**Lifespan + background task** (RESEARCH.md Pattern 7 — replaces intel-extractor BackgroundTasks):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(indexer.run_index_loop())  # D-05: fire-and-forget, non-blocking
    yield

app = FastAPI(title="semantic-engine", version="1.0.0", lifespan=lifespan)
```

**Health endpoint** (analog lines 70–72, extended with index_state per D-05):
```python
@app.get("/health")
async def health():
    # D-05: never blocks; returns progress so `docker compose ps` shows useful status
    return {"status": "ok", **indexer.index_state}
```

**Search endpoint** (analog lines 29–60 pattern, adapted):
```python
@app.get("/search")
async def search(q: str, n_results: int = 10):
    if not q:
        raise HTTPException(status_code=400, detail="q parameter required")
    if len(q) > 500:  # V5 input validation — truncate DoS vector
        raise HTTPException(status_code=400, detail="q too long (max 500 chars)")
    results = searcher.search(indexer.get_collection(), q, n_results=n_results, threshold=SIMILARITY_THRESHOLD)
    return {"query": q, "results": results, "count": len(results)}
```

---

### `services/semantic-engine/Dockerfile` (config)

**Analog:** `services/intel-extractor/Dockerfile` lines 1–7 — exact copy, two changes:

```dockerfile
FROM python:3.12-slim
# No libmagic — semantic-engine has no file parsing
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
```

Changes from analog: remove `apt-get libmagic1` line; port `8001` → `8002`.

---

### `services/semantic-engine/requirements.txt` (config)

**Analog:** `services/intel-extractor/requirements.txt` — same structure, different deps:

```
fastapi==0.115.14
uvicorn
chromadb==1.5.9
ollama==0.6.2
pycti==6.4.11
pytest
pytest-mock
```

Pin logic: `fastapi` and `pycti` must be pinned (BC-02, Pitfall 5). `chromadb` pinned to 1.x API. `ollama` pinned to 0.6.2 (verified `embed()` API).

---

### `services/semantic-engine/tests/conftest.py` (test)

**Analog:** `services/intel-extractor/tests/conftest.py` lines 1–27 — exact structure.

```python
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_pycti():
    client = MagicMock()
    # list() returns indicator dicts matching pycti 6.4.11 field names
    client.indicator.list.return_value = [
        {
            "id": "indicator--test-uuid-1234",
            "name": "1.2.3.4",
            "x_opencti_main_observable_type": "IPv4-Addr",
            "description": "C2 server",
            "objectLabel": [{"value": "botnet-cc"}],
            "updated_at": "2026-06-25T00:00:00.000Z",
        }
    ]
    return client

@pytest.fixture
def mock_ollama():
    # Validates embed() API shape: response.embeddings[0] (Pitfall 4)
    client = MagicMock()
    client.embed.return_value = MagicMock(embeddings=[[0.1] * 768])
    return client

@pytest.fixture
def mock_chroma():
    collection = MagicMock()
    collection.get.return_value = {"ids": [], "metadatas": []}
    collection.query.return_value = {
        "distances": [[0.2, 0.8]],
        "metadatas": [[
            {"ioc_type": "IPv4-Addr", "value": "1.2.3.4", "opencti_url": "http://opencti/...", "embedded_text": "IPv4-Addr: 1.2.3.4 [botnet-cc]"},
            {"ioc_type": "Domain-Name", "value": "evil.com", "opencti_url": "http://opencti/...", "embedded_text": "Domain-Name: evil.com"},
        ]],
        "documents": [["doc1", "doc2"]],
    }
    return collection
```

---

### `services/semantic-engine/tests/test_indexer.py` (test)

**Analog:** `services/intel-extractor/tests/test_opencti_client.py` — import-guard + skipif pattern (lines 1–10):

```python
import pytest

try:
    from indexer import build_embed_text
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

_skip = pytest.mark.skipif(not _IMPORT_OK, reason="indexer not yet implemented")

@_skip
def test_build_embed_text_with_description():
    ind = {"x_opencti_main_observable_type": "IPv4-Addr", "name": "1.2.3.4",
           "description": "C2 server", "objectLabel": [{"value": "botnet-cc"}]}
    assert build_embed_text(ind) == "IPv4-Addr: 1.2.3.4 — C2 server botnet-cc"

@_skip
def test_build_embed_text_no_description():
    ind = {"x_opencti_main_observable_type": "IPv4-Addr", "name": "1.2.3.4",
           "description": None, "objectLabel": [{"value": "malware-distribution"}]}
    assert build_embed_text(ind) == "IPv4-Addr: 1.2.3.4 [malware-distribution]"
```

---

### `services/semantic-engine/tests/test_searcher.py` (test)

**Analog:** same import-guard pattern; covers AISEM-02/03/04.

```python
# Key test: score = 1 - distance (RESEARCH Pitfall 1 — HIGH IMPACT)
@_skip
def test_score_conversion(mock_chroma, mock_ollama):
    # mock_chroma returns distances [0.2, 0.8]
    # score[0] = 0.8 (above threshold 0.3) → included
    # score[1] = 0.2 (below threshold 0.3) → filtered out
    results = search(mock_chroma, "Russian malware", threshold=0.3)
    assert len(results) == 1
    assert results[0]["score"] == 0.8
    assert "opencti_url" in results[0]
    assert "embedded_text" in results[0]
```

---

## Shared Patterns

### pycti Client Init
**Source:** `services/intel-extractor/opencti_client.py` lines 37–43
**Apply to:** `opencti_client.py`
```python
return OpenCTIApiClient(url=OPENCTI_URL, token=OPENCTI_TOKEN, log_level="error")
```

### Retry with Delays
**Source:** `services/intel-extractor/opencti_client.py` lines 33–34, 79–109
**Apply to:** `indexer.py` (embed failures, Pitfall 6)
```python
_RETRY_DELAYS = [30, 60, 120]
for attempt, delay in enumerate(_RETRY_DELAYS):
    try:
        ...
        break
    except Exception as exc:
        if attempt < len(_RETRY_DELAYS) - 1:
            logger.warning("[module] attempt %d failed, retrying in %ds: %s", attempt+1, delay, exc)
            time.sleep(delay)
        else:
            logger.warning("[module] failed after %d attempts: %s", len(_RETRY_DELAYS), exc)
```

### Module-Level State Dict
**Source:** `services/intel-extractor/main.py` lines 40–47
**Apply to:** `indexer.py` (`index_state`), `main.py` (reference `indexer.index_state`)
```python
jobs[job_id] = {"status": "queued", ...}  # pattern; semantic-engine uses single index_state dict
```

### Import Guard + skipif in Tests
**Source:** `services/intel-extractor/tests/test_opencti_client.py` lines 1–10
**Apply to:** all test files in `tests/`
```python
try:
    from module import func
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

_skip = pytest.mark.skipif(not _IMPORT_OK, reason="module not yet implemented")
```

### Token Never Logged
**Source:** `services/intel-extractor/config.py` line 21
**Apply to:** `config.py`
```python
logger.info("OPENCTI_TOKEN configured: %s", bool(OPENCTI_TOKEN))
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `searcher.py` (ChromaDB query + score conversion) | service | request-response | No vector store queries exist in codebase; use RESEARCH.md Pattern 5 verbatim |
| `indexer.py` (ChromaDB upsert + watermark) | service | batch | No ChromaDB writes exist; use RESEARCH.md Patterns 1, 4, 6 |
| `pytest.ini` | config | — | No pytest.ini in intel-extractor; create `[pytest]\ntestpaths = tests` |

---

## Critical Implementation Notes (for Planner)

1. **Cosine distance ≠ similarity** (RESEARCH Pitfall 1, HIGH): `score = 1 - distance`. D-07 threshold applies to `score`, not `distance`. Unit test in `test_searcher.py` must assert this.
2. **ChromaDB collection must set cosine space** (RESEARCH Pitfall 2): `configuration={"hnsw": {"space": "cosine"}}` in `get_or_create_collection()`. Cannot change post-creation.
3. **Ollama API**: use `client.embed(input=text).embeddings[0]` — NOT `.embeddings()` and NOT `.embedding` (singular).
4. **pycti pin**: `pycti==6.4.11` in requirements.txt — unversioned installs 7.x which breaks OpenCTI 6.4.0.
5. **ChromaDB volume mismatch** (RESEARCH Pitfall 3): data lost on restart → watermark also lost → full re-index on restart. This is expected, not a bug in Phase 4. Document in plan notes, do not fix.

---

## Metadata

**Analog search scope:** `services/intel-extractor/`
**Files scanned:** 7 source files + 4 test files
**Pattern extraction date:** 2026-06-25
