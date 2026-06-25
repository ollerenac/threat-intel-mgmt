# Phase 3: AI IOC Extraction - Pattern Map

**Mapped:** 2026-06-25
**Files analyzed:** 8 new files + 1 modified file
**Analogs found:** 8 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `services/intel-extractor/main.py` | controller | request-response | `services/feed-orchestrator/feeds/base.py` (partial) | partial — no FastAPI analog exists; use RESEARCH.md Pattern 1 |
| `services/intel-extractor/config.py` | config | — | `services/feed-orchestrator/config.py` | exact |
| `services/intel-extractor/opencti_client.py` | service | request-response | `services/feed-orchestrator/opencti_client.py` | exact (copy + extend) |
| `services/intel-extractor/extractor.py` | service | batch + transform | `services/feed-orchestrator/feeds/threatfox.py` (normalize pipeline) | role-match |
| `services/intel-extractor/parser.py` | utility | transform | `services/feed-orchestrator/feeds/threatfox.py` (fetch method) | partial |
| `services/intel-extractor/Dockerfile` | config | — | `services/feed-orchestrator/Dockerfile` | exact |
| `services/intel-extractor/requirements.txt` | config | — | `services/feed-orchestrator/requirements.txt` | exact |
| `services/intel-extractor/pytest.ini` | config | — | `services/feed-orchestrator/pytest.ini` | exact (copy verbatim) |
| `services/intel-extractor/tests/conftest.py` | test | — | `services/feed-orchestrator/tests/conftest.py` | role-match |
| `docker-compose.yml` (lines 274–292) | config | — | existing intel-extractor entry | exact (add healthcheck only) |

---

## Pattern Assignments

### `services/intel-extractor/config.py` (config)

**Analog:** `services/feed-orchestrator/config.py` (lines 1–47)

**Copy pattern exactly — remove Redis/feed vars, add Ollama vars:**

```python
# services/feed-orchestrator/config.py lines 1–16 (import + OpenCTI block)
import logging
import os

logger = logging.getLogger(__name__)

OPENCTI_URL   = os.environ.get("OPENCTI_URL", "http://opencti:8080")
OPENCTI_TOKEN = os.environ.get("OPENCTI_TOKEN", "")
```

**New vars to add (not in Phase 2):**
```python
OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
```

**Logging pattern** (feed-orchestrator/config.py line 44):
```python
logger.info("OPENCTI_TOKEN configured: %s", bool(OPENCTI_TOKEN))
```
Apply same pattern to OLLAMA_URL (log presence, not value).

**Omit:** REDIS_URL, OTX_API_KEY, MALWAREBAZAAR_AUTH_KEY, THREATFOX_AUTH_KEY, FEED_INTERVALS, QUALITY_WEIGHTS — none needed in Phase 3.

---

### `services/intel-extractor/opencti_client.py` (service, request-response)

**Analog:** `services/feed-orchestrator/opencti_client.py` (lines 1–109) — copy verbatim, then add three new functions below.

**Copy verbatim (lines 1–109):**
- `build_pycti_client()` — lines 36–42
- `create_indicator()` — lines 45–109 (includes D-05 3× retry with `_RETRY_DELAYS = [30, 60, 120]`)

**Retry pattern to replicate for new functions** (lines 78–108):
```python
last_exc: Optional[Exception] = None
for attempt, delay in enumerate(_RETRY_DELAYS):
    try:
        return client.<entity>.<method>(...)
    except Exception as exc:
        last_exc = exc
        if attempt < len(_RETRY_DELAYS) - 1:
            logger.warning(
                "[opencti_client] <entity> create attempt %d failed, retrying in %ds: %s",
                attempt + 1, delay, exc,
            )
            time.sleep(delay)
        else:
            logger.warning(
                "[opencti_client] <entity> create failed after %d attempts, skipping: %s",
                len(_RETRY_DELAYS), exc,
            )
return None
```

**New function `create_report()` — follow retry pattern above:**
```python
# pycti 6.4.11 source verified: report.create() accepts objects= kwarg
# report_types= (list), NOT report_class= (deprecated)
client.report.create(
    name=name,
    published=published,       # ISO-8601 UTC string
    description=description,
    objects=indicator_ids,     # list of OpenCTI internal IDs — collect ALL before calling
    report_types=["threat-report"],
    update=True,
)
```

**New function `create_relationship()` — follow retry pattern above:**
```python
# pycti 6.4.11 source verified: stix_core_relationship.create()
client.stix_core_relationship.create(
    fromId=from_id,            # indicator internal OpenCTI ID
    toId=to_id,                # attack-pattern internal OpenCTI ID
    relationship_type="indicates",
    update=True,
)
```

**New function `lookup_attack_pattern()` — no retry needed (read-only):**
```python
# pycti 6.4.11 source verified: attack_pattern.list(search=, first=)
results = client.attack_pattern.list(search=keyword, first=5)
if not results:
    logger.info("[extractor] ATT&CK no match for: '%s' — skipping", keyword)
    return None
return results[0]["id"]   # internal OpenCTI UUID for toId in relationship
# results[0]["x_mitre_id"] is the Txxxx string — use for logging only
```

---

### `services/intel-extractor/extractor.py` (service, batch + transform)

**Analog:** `services/feed-orchestrator/feeds/threatfox.py` (normalize pipeline, lines 76–96) — role-match for the IOC collection/dedup loop; RESEARCH.md Patterns 2, 6 for Ollama and chunking.

**STIX pattern builder — copy from threatfox.py lines 57–74, extend for email + sha1:**
```python
# threatfox.py lines 59–72 — proven escaping and STIX property quoting
v = ioc_value.replace("'", "\\'")
# SHA-256 uses single-quoted property name: [file:hashes.'SHA-256' = '...']
# SHA-1  uses single-quoted property name: [file:hashes.'SHA-1'   = '...']
```

Full mapping for intel-extractor (extends threatfox.py):
```python
IOC_TYPE_TO_STIX = {
    "ip":          ("[ipv4-addr:value = '{v}']",          "IPv4-Addr"),
    "domain":      ("[domain-name:value = '{v}']",        "Domain-Name"),
    "url":         ("[url:value = '{v}']",                "Url"),
    "hash_md5":    ("[file:hashes.MD5 = '{v}']",          "StixFile"),
    "hash_sha1":   ("[file:hashes.'SHA-1' = '{v}']",      "StixFile"),
    "hash_sha256": ("[file:hashes.'SHA-256' = '{v}']",    "StixFile"),
    "email":       ("[email-addr:value = '{v}']",         "Email-Addr"),
}
```

**IOC dedup pattern — within-job set before STIX creation (Claude's Discretion):**
```python
# threatfox.py normalize() collects into results list; Phase 3 uses a set first
seen: set[tuple[str, str]] = set()
unique_iocs = []
for ioc in raw_iocs:
    key = (ioc["type"], ioc["value"])
    if key not in seen:
        seen.add(key)
        unique_iocs.append(ioc)
```

**Ollama call pattern** (RESEARCH.md Pattern 2 — no codebase analog exists):
```python
# ollama.Client(host=) is the correct form for non-default host (Assumption A1)
_client = ollama.Client(host=OLLAMA_URL)

_client.chat(
    model=OLLAMA_MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": chunk_text},
    ],
    format="json",
    options={"temperature": 0, "num_ctx": 8192},  # num_ctx critical — default 2048 too small
)
# response.message.content is the attribute path (Assumption A2 — verify in Wave 0)
```

**D-03 fallback trigger** — wrap `json.loads()` in try/except; use `.get("iocs", [])` not `["iocs"]`:
```python
try:
    data = json.loads(resp.message.content)
    iocs = data.get("iocs", [])
except (json.JSONDecodeError, Exception):
    # trigger fallback prompt (RESEARCH.md Code Example)
```

**Background task must be `def` not `async def`** (Pitfall 5 — pycti uses requests/sync I/O):
```python
# FastAPI runs plain def background tasks in thread pool → isolates sync pycti calls
def run_extraction(job_id: str, mode: str, content, url) -> None:
    ...
```

**Job state dict pattern** (D-06):
```python
# Module-level — lost on restart, acceptable for demo scope
jobs: dict[str, dict] = {}

# JobState keys: status, iocs_extracted, techniques_found, report_id, error, processing_time_s
jobs[job_id] = {
    "status": "queued",
    "iocs_extracted": 0,
    "techniques_found": 0,
    "report_id": None,
    "error": None,
    "processing_time_s": None,
}
```

**Processing order** (Pitfall 1 — collect all indicator IDs BEFORE create_report):
1. Parse document → text
2. Chunk text
3. LLM extract per chunk → collect raw IOCs + technique keywords
4. Dedup IOCs with seen set
5. Create all indicators → collect indicator_ids list
6. ATT&CK lookup per technique keyword → create relationships
7. `create_report(objects=indicator_ids)` — only after step 5 is complete

---

### `services/intel-extractor/parser.py` (utility, transform)

**Analog:** `services/feed-orchestrator/feeds/threatfox.py` fetch() method (lines 39–54) — partial match for the "fetch external content, raise on failure" pattern.

**PDF extraction** (RESEARCH.md Pattern 7):
```python
from PyPDF2 import PdfReader   # NOT "from pypdf import" — different package (Pitfall 6)
import io

reader = PdfReader(io.BytesIO(pdf_bytes))
pages_text = [page.extract_text() for page in reader.pages]
full_text = "\n".join(t for t in pages_text if t)
if not full_text.strip():
    raise ValueError("PDF appears to be image-based — no extractable text found")
```

**URL extraction with fallback** (RESEARCH.md Pattern 8):
```python
from trafilatura import fetch_url, extract

downloaded = fetch_url(url)          # returns None on failure, does NOT raise (Pitfall 3)
if downloaded:
    result = extract(downloaded)
    if result:
        return result
# Fallback: requests + BeautifulSoup
resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
resp.raise_for_status()
soup = BeautifulSoup(resp.text, "html.parser")
return soup.get_text(separator="\n", strip=True)
```

**URL scheme validation** (security — SSRF mitigation per RESEARCH.md Security Domain):
```python
from urllib.parse import urlparse
parsed = urlparse(url)
if parsed.scheme not in ("http", "https"):
    raise ValueError(f"URL scheme '{parsed.scheme}' not allowed")
```

---

### `services/intel-extractor/main.py` (controller, request-response)

**No exact analog in codebase** — feed-orchestrator has no FastAPI. Use RESEARCH.md Pattern 1.

**FastAPI endpoint pattern** (RESEARCH.md Pattern 1):
```python
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException
from typing import Optional
import uuid

app = FastAPI()

@app.post("/extract")
async def submit_extract(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
):
    if not file and not url:
        raise HTTPException(status_code=400, detail="provide file or url")
    job_id = str(uuid.uuid4())
    jobs[job_id] = {...}   # initialize JobState before add_task (not after)
    if file:
        content = await file.read()
        background_tasks.add_task(run_extraction, job_id, "pdf", content, None)
    else:
        background_tasks.add_task(run_extraction, job_id, "url", None, url)
    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, **jobs[job_id]}

@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Logging setup** — follow feed-orchestrator/main.py convention (basicConfig at module level).

---

### `services/intel-extractor/Dockerfile` (config)

**Analog:** `services/feed-orchestrator/Dockerfile` (lines 1–7) — exact copy, two changes:

```dockerfile
FROM python:3.12-slim
# OMIT: RUN apt-get ... libmagic1  — not needed (PyPDF2 + trafilatura are pure Python)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
# CHANGED: CMD from "python main.py" to uvicorn (FastAPI requires ASGI server)
```

---

### `services/intel-extractor/tests/conftest.py` (test)

**Analog:** `services/feed-orchestrator/tests/conftest.py` (lines 1–36) — role-match; copy mock structure, replace fixtures.

**Mock structure to copy** (conftest.py lines 7–36):
```python
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_pycti():
    client = MagicMock()
    client.indicator.create.return_value = {"id": "indicator--test-uuid"}
    return client
```

**New fixtures to add for Phase 3:**
```python
@pytest.fixture
def mock_pycti():
    client = MagicMock()
    client.indicator.create.return_value = {"id": "indicator--test-uuid"}
    client.report.create.return_value = {"id": "report--test-uuid"}
    client.stix_core_relationship.create.return_value = {"id": "relationship--test-uuid"}
    client.attack_pattern.list.return_value = [
        {"id": "attack-pattern--test-uuid", "name": "Phishing", "x_mitre_id": "T1566"}
    ]
    return client

@pytest.fixture
def mock_ollama():
    client = MagicMock()
    msg = MagicMock()
    msg.content = '{"iocs":[{"type":"ip","value":"1.2.3.4"}],"techniques":[{"name":"phishing","description":"email lure"}],"malware_families":[],"threat_actors":[]}'
    client.chat.return_value.message = msg
    return client
```

**Drop:** sample_urlhaus_rows, sample_malwarebazaar_rows, sample_threatfox_rows, sample_feodo_rows, sample_otx_indicators, mock_redis — not needed in Phase 3.

---

### `docker-compose.yml` intel-extractor entry (lines 274–292)

**Existing entry** (lines 274–292) — add healthcheck only, touch nothing else:

```yaml
# ADD after line 292 (restart: unless-stopped), before the next service:
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

Note: `curl` is available in `python:3.12-slim` base image — no apt install needed.

---

## Shared Patterns

### Retry / error handling
**Source:** `services/feed-orchestrator/opencti_client.py` lines 33, 78–108
**Apply to:** All three new pycti write functions in `opencti_client.py` (`create_report`, `create_relationship`)
```python
_RETRY_DELAYS = [30, 60, 120]   # seconds; copy this constant verbatim

for attempt, delay in enumerate(_RETRY_DELAYS):
    try:
        return client.<entity>.create(...)
    except Exception as exc:
        if attempt < len(_RETRY_DELAYS) - 1:
            logger.warning("[opencti_client] ... retrying in %ds: %s", delay, exc)
            time.sleep(delay)
        else:
            logger.warning("[opencti_client] ... failed after %d attempts: %s", len(_RETRY_DELAYS), exc)
return None
```

### Logging convention
**Source:** `services/feed-orchestrator/opencti_client.py` lines 21–30, `config.py` lines 44–47
**Apply to:** All Phase 3 modules
- `logger = logging.getLogger(__name__)` at module level in every file
- Log format: `[module_name] message` prefix in all warning/info strings
- Never log secret values — `bool(OPENCTI_TOKEN)` only

### STIX single-quote escaping
**Source:** `services/feed-orchestrator/feeds/threatfox.py` line 59
**Apply to:** `extractor.py` `build_stix_pattern()`
```python
v = ioc_value.replace("'", "\\'")   # escape before interpolating into STIX pattern string
```

### `update=True` on all pycti writes
**Source:** `services/feed-orchestrator/opencti_client.py` line 90
**Apply to:** `create_indicator()`, `create_report()`, `create_relationship()` in opencti_client.py
Prevents duplicate-key errors on re-runs. Already proven in Phase 2.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `services/intel-extractor/main.py` | controller | request-response | No FastAPI service exists in codebase — use RESEARCH.md Pattern 1 verbatim |

---

## Metadata

**Analog search scope:** `services/feed-orchestrator/`, `docker-compose.yml`
**Files scanned:** 6 source files + docker-compose.yml
**Pattern extraction date:** 2026-06-25
