# Phase 3: AI IOC Extraction - Research

**Researched:** 2026-06-25
**Domain:** FastAPI async job service + Ollama LLM extraction + pycti STIX output
**Confidence:** MEDIUM (pycti signatures verified from installed source; Ollama/trafilatura/PyPDF2 from docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Single-pass JSON schema extraction. One Ollama call per chunk. JSON keys: `iocs` (list of `{type, value}`), `techniques` (list of `{name, description}`), `malware_families` (list of strings), `threat_actors` (list of strings). Types: ip, domain, hash_md5, hash_sha1, hash_sha256, url, email.
- **D-02:** One few-shot example in system prompt (~200 tokens). Fictional/generic snippet, not real IOC data.
- **D-03:** On malformed JSON: retry once with plain-text fallback prompt ("List all IPs, domains, file hashes, and URLs — one per line, format: TYPE:VALUE"). Parse with regex. If fallback fails, skip chunk, log warning. Other chunks continue.
- **D-04:** Per job: one `report` SDO (name = doc title/URL, published = extraction timestamp, object_refs = all indicator IDs), one `indicator` SDO per unique IOC. No malware/threat-actor/intrusion-set SDOs in Phase 3.
- **D-05:** ATT&CK links: STIX `relationship` with relationship_type="indicates" from each `indicator` to matched `attack-pattern` object. Requires querying OpenCTI for attack-pattern ID per matched technique.
- **D-06:** Async job model. `POST /extract` → `{job_id, status: "queued"}`. BackgroundTasks or asyncio task processes in background. Job state in module-level dict `jobs: dict[str, JobState]`. JobState fields: status, iocs_extracted, techniques_found, report_id, error, processing_time_s.
- **D-07:** `GET /jobs/{id}` → `{job_id, status (queued/processing/complete/failed), iocs_extracted, techniques_found, report_id, processing_time_s, error}`.
- **D-08:** LLM outputs technique names only (not Txxxx IDs). Python code queries `client.attack_pattern.list(search=keyword)` to resolve.
- **D-09:** No-match on attack-pattern lookup: skip, log `[extractor] ATT&CK no match for: '{keyword}' — skipping`. Indicator still created without that link.

### Claude's Discretion

- Chunk size: ~1500 tokens per chunk, ~150 token overlap (10%)
- Within-job IOC dedup: Python set of (type, value) tuples before STIX creation
- URL scraping: trafilatura primary, requests+BeautifulSoup fallback if trafilatura returns None
- PDF parsing: pypdf2 primary; if all pages return empty text, return job error (OCR out of scope)
- Healthcheck: `GET /health` → `{status: "ok"}`, Docker CMD: `curl -f http://localhost:8001/health || exit 1`
- LLM temperature: 0, format: "json"

### Deferred Ideas (OUT OF SCOPE)

- `malware`, `threat-actor`, `intrusion-set`, `campaign` SDOs
- OCR for image-based PDFs
- Streaming LLM response / SSE job progress
- Persistent job store (Redis)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AIEX-01 | intel-extractor accepts a PDF file and extracts IOCs via local LLM | PyPDF2 PdfReader API, Ollama client.chat JSON mode, chunking strategy |
| AIEX-02 | intel-extractor accepts a URL and extracts IOCs from scraped content | trafilatura fetch_url+extract API, fallback pattern |
| AIEX-03 | Extracted IOCs are mapped to MITRE ATT&CK techniques where mentioned | pycti attack_pattern.list(search=) verified from source; relationship_type="indicates" |
| AIEX-04 | Extraction result is inserted into OpenCTI as STIX objects | pycti report.create + stix_core_relationship.create + create_indicator verified from source |
| AIEX-05 | Long documents are chunked and processed without losing IOCs at boundaries | 1500-token chunks with 150-token overlap; per-job dedup set to collapse duplicates from overlap |
</phase_requirements>

---

## Summary

Phase 3 builds `intel-extractor`, a FastAPI service at port 8001. It is entirely new Python territory — no existing code in `services/intel-extractor/` yet. The service shares the same Python + Docker patterns as Phase 2's `feed-orchestrator` and reuses `opencti_client.py`'s `create_indicator()` directly. The new pycti calls (`report.create`, `stix_core_relationship.create`, `attack_pattern.list`) have been verified against the installed pycti 6.4.11 source at `/home/researcher/.local/lib/python3.10/site-packages/pycti/entities/`.

The core processing pipeline is: parse document (PDF bytes → PyPDF2 text, URL → trafilatura text) → chunk text into ~1500-token windows with 150-token overlap → call Ollama `llama3.2:3b` once per chunk in JSON mode → collect and deduplicate IOCs → write STIX to OpenCTI via pycti. ATT&CK technique lookup happens after all chunks are processed: for each unique technique keyword, call `client.attack_pattern.list(search=keyword)` and create a `indicates` relationship from each matched indicator to the returned attack-pattern object.

The job model is simple: a module-level `dict[str, JobState]` is sufficient for demo scope (D-06). FastAPI's `BackgroundTasks` runs the full extraction pipeline after returning `{job_id}` to the caller.

**Primary recommendation:** Reuse `create_indicator()` from Phase 2's `opencti_client.py` verbatim. Add `create_report()` and `create_relationship()` in the same file following the same 3× retry pattern already proven in Phase 2.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP API (POST /extract, GET /jobs, GET /health) | API / Backend (FastAPI) | — | Exposes service to dashboard and curl |
| PDF text extraction | API / Backend (Python) | — | CPU-bound, runs inside container |
| URL scraping | API / Backend (Python) | — | Network call, runs inside container |
| Text chunking | API / Backend (Python) | — | Pure in-process transform |
| LLM IOC extraction | AI Service (Ollama) | API Backend (orchestrates) | GPU inference on `tim-network` |
| STIX object creation | Database / Storage (OpenCTI) | API Backend (writes via pycti) | pycti GraphQL mutations |
| ATT&CK lookup | Database / Storage (OpenCTI) | API Backend (reads via pycti) | Existing attack-pattern objects in OpenCTI |
| Job state tracking | API / Backend (in-memory dict) | — | No persistence required for demo |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.115.x (pin to match existing) | HTTP API framework | Async-native, UploadFile built-in, BackgroundTasks built-in |
| uvicorn | latest | ASGI server for FastAPI | De-facto FastAPI runtime |
| pycti | 6.4.11 | OpenCTI GraphQL client | Must match platform 6.4.0 — ALREADY PINNED in feed-orchestrator |
| ollama | 0.4.x | Ollama Python SDK | Official SDK for Ollama server API |
| PyPDF2 | 3.0.1 | PDF text extraction | Design doc spec §4.3.1; pure Python, no system deps |
| trafilatura | 2.1.0 | URL content extraction | Design doc spec §4.3.1; main-content extraction handles nav/ads |
| requests | latest | HTTP fallback for URL scraping | Already in feed-orchestrator requirements.txt |
| python-multipart | latest | Required by FastAPI for file uploads | FastAPI dependency for UploadFile |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| beautifulsoup4 | latest | Fallback URL parsing | When trafilatura returns None |
| pytest | latest | Unit tests | All tests; same as Phase 2 |
| pytest-mock | latest | Mock pycti/ollama in tests | All tests; same as Phase 2 |

**Version verification:** [VERIFIED: pip index versions] — fastapi 0.138.0 latest (pin to stable 0.115.x matching Phase 2 era), ollama 0.6.2 latest, pycti 6.4.11 installed and matching platform, trafilatura 2.1.0 latest, PyPDF2 3.0.1 latest.

**Installation:**
```bash
pip install fastapi==0.115.14 uvicorn pycti==6.4.11 ollama PyPDF2==3.0.1 trafilatura requests python-multipart beautifulsoup4
```

**Critical version constraint:** `pycti==6.4.11` is non-negotiable. Platform is `opencti/platform:6.4.0`. Same constraint as Phase 2.

---

## Package Legitimacy Audit

> Legitimacy seam returned `SUS` for all packages due to PyPI download stats unavailable in the tool — not genuine suspicion. All packages are specified in the project design doc §4.3.1 or are direct analogs to Phase 2 packages. Manual verification below.

| Package | Registry | Age | Source Repo | Verdict | Disposition |
|---------|----------|-----|-------------|---------|-------------|
| fastapi | PyPI | 7+ yrs | github.com/fastapi/fastapi | OK | Approved — major framework, design doc spec |
| uvicorn | PyPI | 6+ yrs | github.com/encode/uvicorn | OK | Approved — fastapi standard runtime |
| pycti | PyPI | 5+ yrs | github.com/OpenCTI-Platform/client-python | OK | Approved — already pinned in Phase 2 |
| ollama | PyPI | 2+ yrs | github.com/ollama/ollama | OK | Approved — official Ollama SDK |
| PyPDF2 | PyPI | 10+ yrs | github.com/py-pdf/PyPDF2 | OK | Approved — design doc spec §4.3.1 |
| trafilatura | PyPI | 5+ yrs | github.com/adbar/trafilatura | OK | Approved — design doc spec §4.3.1 |
| requests | PyPI | 13+ yrs | github.com/psf/requests | OK | Approved — already in Phase 2 |
| python-multipart | PyPI | 10+ yrs | github.com/andrew-d/python-multipart | OK | Approved — FastAPI UploadFile requirement |
| beautifulsoup4 | PyPI | 10+ yrs | crummy.com/software/BeautifulSoup | OK | Approved — standard HTML parsing |

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious:** none

---

## Architecture Patterns

### System Architecture Diagram

```
  POST /extract (PDF bytes or URL string)
          │
          ▼
  [FastAPI endpoint]
     - reads UploadFile bytes / URL string
     - generates job_id (uuid4)
     - stores JobState(status="queued") in jobs dict
     - calls background_tasks.add_task(run_extraction, job_id, ...)
     - returns {job_id, status}
          │
          ▼ (background, after response sent)
  [run_extraction()]
     │
     ├── PDF: PyPDF2.PdfReader(io.BytesIO(bytes)) → join page.extract_text()
     │   URL: trafilatura.fetch_url(url) → trafilatura.extract(html)
     │         └─ fallback: requests.get(url) → BeautifulSoup.get_text()
     │
     ├── chunk_text(full_text, max_tokens=1500, overlap=150)
     │       returns list[str] of overlapping windows
     │
     ├── for each chunk:
     │       client.chat(model, messages, format='json', options={temperature:0})
     │       → parse JSON → collect {type,value} IOCs, technique keywords
     │       on parse failure: retry with fallback prompt → regex parse
     │
     ├── deduplicate: seen = set(); iocs = [(t,v) for t,v in raw if (t,v) not in seen]
     │
     ├── for each unique IOC:
     │       STIX pattern = build_pattern(type, value)
     │       indicator_id = create_indicator(client, ...)  ← reuse Phase 2
     │
     ├── for each unique technique keyword:
     │       results = opencti.attack_pattern.list(search=keyword, first=5)
     │       if results: create_relationship(indicator_ids, attack_pattern_id)
     │
     ├── report_id = create_report(name, published, objects=[all indicator_ids])
     │
     └── update jobs[job_id] → status=complete, iocs_extracted=N, report_id=...

  GET /jobs/{id}
          │
          └── return jobs[id] or 404
```

### Recommended Project Structure

```
services/intel-extractor/
├── Dockerfile
├── requirements.txt
├── pytest.ini
├── main.py              # FastAPI app, POST /extract, GET /jobs/{id}, GET /health
├── config.py            # OPENCTI_URL, OPENCTI_TOKEN, OLLAMA_URL, OLLAMA_MODEL
├── extractor.py         # run_extraction() background task, chunker, LLM call, IOC dedup
├── opencti_client.py    # create_indicator() (copy from Phase 2) + create_report() + create_relationship()
├── parser.py            # extract_pdf_text(), extract_url_text() — document parsing only
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_parser.py
    ├── test_extractor.py
    └── test_opencti_client.py
```

**File count rationale (ponytail):** `extractor.py` handles chunking + LLM + IOC dedup in one file (it's all one pipeline). `parser.py` isolates document parsing (testable independently). `opencti_client.py` extends Phase 2's version with two new functions.

### Pattern 1: FastAPI async job submission

**What:** POST endpoint reads file/URL, launches background task, returns job_id immediately.

**When to use:** Any operation that takes >1 second and caller should poll for results.

```python
# Source: FastAPI official docs https://fastapi.tiangolo.com/tutorial/background-tasks/
import uuid
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form
from typing import Optional

app = FastAPI()
jobs: dict[str, dict] = {}  # module-level — lost on restart (D-06)

@app.post("/extract")
async def submit_extract(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "iocs_extracted": 0,
                    "techniques_found": 0, "report_id": None, "error": None}
    if file:
        content = await file.read()
        background_tasks.add_task(run_extraction, job_id, "pdf", content, None)
    elif url:
        background_tasks.add_task(run_extraction, job_id, "url", None, url)
    else:
        return {"error": "provide file or url"}, 400
    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, **jobs[job_id]}
```

### Pattern 2: Ollama JSON-mode extraction

**What:** Single client.chat() call per chunk with system prompt enforcing JSON schema.

**When to use:** Every text chunk. temperature=0 + format='json' double-enforces structure.

```python
# Source: Ollama Python SDK docs https://github.com/ollama/ollama-python
import ollama
from config import OLLAMA_URL, OLLAMA_MODEL

_client = ollama.Client(host=OLLAMA_URL)

SYSTEM_PROMPT = """You are a threat intelligence analyst. Extract IOCs and techniques from the text.
Return ONLY valid JSON with this structure:
{
  "iocs": [{"type": "ip|domain|hash_md5|hash_sha1|hash_sha256|url|email", "value": "..."}],
  "techniques": [{"name": "...", "description": "..."}],
  "malware_families": ["..."],
  "threat_actors": ["..."]
}

Example input: "The actor used 192.168.1.1 and evil.example.com to distribute Emotet via phishing."
Example output: {"iocs":[{"type":"ip","value":"192.168.1.1"},{"type":"domain","value":"evil.example.com"}],"techniques":[{"name":"phishing","description":"email-based delivery"}],"malware_families":["Emotet"],"threat_actors":[]}
"""

def extract_chunk(text: str) -> dict:
    response = _client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        format="json",
        options={"temperature": 0, "num_ctx": 8192},
    )
    return json.loads(response.message.content)
```

### Pattern 3: pycti report.create() — verified from pycti 6.4.11 source

**What:** Creates a STIX report SDO in OpenCTI referencing all extracted indicators.

**When to use:** Once per extraction job, after all indicators are created.

```python
# Source: [VERIFIED: /home/researcher/.local/lib/python3.10/site-packages/pycti/entities/opencti_report.py]
def create_report(
    client: OpenCTIApiClient,
    name: str,
    published: str,          # ISO-8601 UTC string
    description: str,
    indicator_ids: list[str], # list of OpenCTI internal IDs (not STIX IDs)
) -> Optional[dict]:
    try:
        return client.report.create(
            name=name,
            published=published,
            description=description,
            objects=indicator_ids,   # "objects" param confirmed in pycti source line 699
            report_types=["threat-report"],
            update=True,
        )
    except Exception as exc:
        logger.warning("[opencti_client] report create failed: %s", exc)
        return None
```

### Pattern 4: pycti stix_core_relationship.create() — verified from pycti 6.4.11 source

**What:** Creates indicator→attack-pattern relationship edge in OpenCTI.

**When to use:** After attack_pattern.list() returns a match, for each (indicator, attack_pattern) pair.

```python
# Source: [VERIFIED: /home/researcher/.local/lib/python3.10/site-packages/pycti/entities/opencti_stix_core_relationship.py]
def create_relationship(
    client: OpenCTIApiClient,
    from_id: str,    # indicator internal OpenCTI ID (returned by indicator.create)
    to_id: str,      # attack-pattern internal OpenCTI ID (returned by attack_pattern.list)
    relationship_type: str = "indicates",
) -> Optional[dict]:
    try:
        return client.stix_core_relationship.create(
            fromId=from_id,
            toId=to_id,
            relationship_type=relationship_type,
            update=True,
        )
    except Exception as exc:
        logger.warning("[opencti_client] relationship create failed: %s", exc)
        return None
```

### Pattern 5: pycti attack_pattern.list() — verified from pycti 6.4.11 source

**What:** Searches OpenCTI's pre-loaded ATT&CK patterns by keyword.

**When to use:** For each unique technique name extracted by LLM.

```python
# Source: [VERIFIED: /home/researcher/.local/lib/python3.10/site-packages/pycti/entities/opencti_attack_pattern.py]
def lookup_attack_pattern(client: OpenCTIApiClient, keyword: str) -> Optional[str]:
    """Returns the internal OpenCTI ID of the best matching attack-pattern, or None."""
    results = client.attack_pattern.list(search=keyword, first=5)
    if not results:
        logger.info("[extractor] ATT&CK no match for: '%s' — skipping", keyword)
        return None
    # results[0] is best match; fields: id, name, x_mitre_id, standard_id
    return results[0]["id"]  # internal OpenCTI ID for relationship creation
```

**Key field:** `results[0]["id"]` is the internal OpenCTI UUID (use for `toId` in relationship creation). `results[0]["x_mitre_id"]` is the Txxxx string (for logging only).

### Pattern 6: Text chunking with overlap

**What:** Split text into fixed-size overlapping windows to prevent IOC loss at boundaries.

**When to use:** Any document whose full text exceeds ~6000 tokens (~24000 chars).

```python
# Source: [ASSUMED] — standard sliding-window chunking algorithm
def chunk_text(text: str, max_chars: int = 6000, overlap_chars: int = 600) -> list[str]:
    """
    Split text into overlapping windows.
    max_chars=6000 ≈ 1500 tokens at ~4 chars/token (leaves headroom for prompt+JSON).
    overlap_chars=600 ≈ 150 tokens (10% overlap per D-06 discretion).
    """
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        start = end - overlap_chars  # step = max_chars - overlap
    return chunks
```

**Token estimation:** llama3.2:3b tokenizes ~4 chars/token for English. 6000 chars ≈ 1500 tokens of content. System prompt + few-shot example ≈ 400 tokens. Total per call ≈ 1900 tokens, well within 8192 context.

### Pattern 7: PDF text extraction

**What:** Extract plain text from PDF bytes using PyPDF2.

```python
# Source: PyPDF2 3.0.x docs https://pypdf2.readthedocs.io/en/3.0.0/user/extract-text.html
import io
from PyPDF2 import PdfReader

def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text = [page.extract_text() for page in reader.pages]
    full_text = "\n".join(t for t in pages_text if t)
    if not full_text.strip():
        raise ValueError("PDF appears to be image-based — no extractable text found")
    return full_text
```

### Pattern 8: URL text extraction

**What:** Scrape URL and extract main content text.

```python
# Source: trafilatura docs https://trafilatura.readthedocs.io/en/latest/usage-python.html
from trafilatura import fetch_url, extract
import requests
from bs4 import BeautifulSoup

def extract_url_text(url: str) -> str:
    downloaded = fetch_url(url)
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

### Anti-Patterns to Avoid

- **Asking the LLM for Txxxx IDs directly:** The 3B model hallucinates technique IDs confidently. LLM outputs natural-language keyword → Python resolves via attack_pattern.list(). This was locked as D-08.
- **Creating attack-pattern objects:** OpenCTI pre-loads the full ATT&CK framework. Phase 3 only references existing objects — never creates new attack-pattern SDOs.
- **Using update=False on indicator creation:** Without `update=True`, inserting a duplicate IOC raises an error. Phase 2 already solved this with `update=True` in `create_indicator()`.
- **Calling `jobs[job_id]` directly in background task:** The background task runs after the response is sent — the dict is populated before `add_task()` so it's always present. But a missing job_id on GET should return 404, not KeyError.
- **Sequential calls to `attack_pattern.list()` for all technique keywords before any indicators are created:** ATT&CK lookup and indicator creation are independent — create indicators first, then do ATT&CK lookups and relationships in a second pass. This avoids blocking indicator creation on a slow/failed ATT&CK search.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | Custom PDF parser | PyPDF2 PdfReader | Handles PDF spec complexity (compression, encodings, cross-refs) |
| HTML main-content extraction | Strip HTML tags | trafilatura | Removes nav, ads, footers — critical for threat reports with heavy page chrome |
| JSON output enforcement | Prompt-only | `format='json'` in Ollama | Double-enforcement: model is constrained at tokenizer level, not just trained |
| IOC dedup across chunks | Complex set-merge | Python `set` of `(type, value)` tuples | Exact-match dedup is sufficient within one job |
| Cross-job IOC dedup | Redis SETNX in extractor | pycti `update=True` | Already handled — same indicator pattern → upsert, no duplicate in OpenCTI |
| ATT&CK keyword→Txxxx mapping | Maintain local ATT&CK lookup table | `attack_pattern.list(search=)` | OpenCTI already has 709+ patterns loaded; searching is free |

**Key insight:** OpenCTI's pre-loaded ATT&CK data makes the lookup table problem trivial. The entire technique-resolution problem is one `list(search=keyword)` call.

---

## Common Pitfalls

### Pitfall 1: `report.create(objects=...)` vs `add_stix_object_or_stix_relationship()`

**What goes wrong:** If indicator creation is slow, calling `report.create(objects=all_ids)` before all indicators are created silently skips missing IDs. Alternatively, creating the report with `objects=[]` first and then calling `add_stix_object_or_stix_relationship()` per indicator works but is N additional API calls.

**Why it happens:** OpenCTI silently ignores unknown object IDs in the `objects` list.

**How to avoid:** Collect all indicator IDs first (complete the indicator creation loop), then call `report.create(objects=all_ids)` in one call. This is the correct order.

**Warning signs:** Report appears in OpenCTI with zero object_refs.

### Pitfall 2: Ollama JSON mode still produces non-JSON

**What goes wrong:** `format='json'` prevents non-JSON tokens at the tokenizer level, but llama3.2:3b may still produce a JSON object with the wrong schema (e.g., missing keys, different field names).

**Why it happens:** 3B models are less instruction-following than 7B+. The few-shot example dramatically reduces this but doesn't eliminate it.

**How to avoid:** Parse with `json.loads()` inside a try/except. On `KeyError`/`json.JSONDecodeError`, trigger D-03 fallback prompt. Use `.get("iocs", [])` instead of `["iocs"]` when accessing parsed result.

**Warning signs:** `KeyError: 'iocs'` in logs — means JSON parsed but schema diverged.

### Pitfall 3: `trafilatura.fetch_url()` returns None silently

**What goes wrong:** `fetch_url()` returns `None` (not an exception) for many failure modes: timeout, 404, network unreachable, JavaScript-heavy page.

**Why it happens:** trafilatura is designed for crawling — quiet failures are by design.

**How to avoid:** Always check `if downloaded:` before passing to `extract()`. Implement the requests/BeautifulSoup fallback as specified in Claude's Discretion.

**Warning signs:** Extraction job completes with 0 IOCs from a URL that clearly has content.

### Pitfall 4: pycti `attack_pattern.list()` returns partial matches

**What goes wrong:** `search="lateral movement"` may return unrelated ATT&CK patterns whose description contains both words, not just T1021 (Remote Services).

**Why it happens:** OpenCTI GraphQL `search` does full-text search across all text fields.

**How to avoid:** Take only the first result (`results[0]`) and rely on OpenCTI's relevance ranking. For ambiguous keywords (e.g., "execution"), the first result is usually the most common technique. D-09 already accepts "accuracy over completeness".

**Warning signs:** Indicators linked to clearly wrong ATT&CK techniques in the OpenCTI graph.

### Pitfall 5: Background task runs in the same async event loop

**What goes wrong:** If `run_extraction()` is defined as `async def` and makes blocking calls (pycti is synchronous), it blocks the FastAPI event loop, preventing other requests from being handled.

**Why it happens:** FastAPI runs `async def` background tasks in the async event loop. pycti uses `requests` under the hood — synchronous I/O.

**How to avoid:** Define `run_extraction()` as a regular `def` (not `async def`). FastAPI runs `def` background tasks in a thread pool, which isolates them from the event loop. This matches Phase 2's pattern (pycti is always called from regular Python functions).

**Warning signs:** POST /extract returns immediately but GET /health starts timing out during extraction.

### Pitfall 6: PyPDF2 3.x renamed from `PyPDF2` import path

**What goes wrong:** PyPDF2 3.x changed the class path — some guides use `from pypdf import PdfReader` (the successor package).

**Why it happens:** `pypdf` (without "2") is the maintained fork. `PyPDF2` still works at 3.0.1 but is in maintenance mode.

**How to avoid:** Use `from PyPDF2 import PdfReader` with pinned `PyPDF2==3.0.1`. This is the design doc spec. Do not substitute `pypdf` without testing.

**Warning signs:** `ModuleNotFoundError: No module named 'pypdf'` — means wrong package name.

### Pitfall 7: `num_ctx` must be set explicitly for long chunks

**What goes wrong:** Ollama defaults `num_ctx` to 2048 for many models. A 6000-char chunk ≈ 1500 tokens plus ~400 token prompt exceeds the default, causing silent truncation.

**Why it happens:** llama3.2:3b supports 8K context but defaults to 2048 to save memory.

**How to avoid:** Always pass `options={"temperature": 0, "num_ctx": 8192}` in every `client.chat()` call.

**Warning signs:** IOCs near the end of chunks disappear from results — truncation at ~2048 tokens.

---

## Code Examples

### Complete LLM extraction call with fallback

```python
# Source: Ollama Python SDK + D-03 fallback pattern from CONTEXT.md
import json
import logging
import ollama

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a threat intelligence analyst. Extract all IOCs and techniques from the following text.
Return ONLY valid JSON matching this exact structure:
{"iocs":[{"type":"ip|domain|hash_md5|hash_sha1|hash_sha256|url|email","value":"..."}],"techniques":[{"name":"...","description":"..."}],"malware_families":["..."],"threat_actors":["..."]}

Example:
Input: "Actors distributed Emotet from 1.2.3.4 and evil.example.com using phishing lures."
Output: {"iocs":[{"type":"ip","value":"1.2.3.4"},{"type":"domain","value":"evil.example.com"}],"techniques":[{"name":"phishing","description":"email-based malware delivery"}],"malware_families":["Emotet"],"threat_actors":[]}
"""

FALLBACK_PROMPT = "List all IPs, domains, file hashes, and URLs from this text, one per line, format: TYPE:VALUE"

def call_llm(client: ollama.Client, model: str, text: str) -> dict:
    """Single-pass JSON extraction with D-03 fallback."""
    try:
        resp = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            format="json",
            options={"temperature": 0, "num_ctx": 8192},
        )
        return json.loads(resp.message.content)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("[extractor] LLM JSON parse failed, retrying with fallback: %s", exc)

    # D-03 fallback: plain-text extraction, regex parse
    try:
        resp = client.chat(
            model=model,
            messages=[
                {"role": "user", "content": f"{FALLBACK_PROMPT}\n\n{text}"},
            ],
            options={"temperature": 0},
        )
        return _parse_fallback_text(resp.message.content)
    except Exception as exc2:
        logger.warning("[extractor] fallback also failed, skipping chunk: %s", exc2)
        return {"iocs": [], "techniques": [], "malware_families": [], "threat_actors": []}


def _parse_fallback_text(text: str) -> dict:
    """Parse TYPE:VALUE lines from fallback LLM response."""
    import re
    iocs = []
    type_map = {
        "IP": "ip", "DOMAIN": "domain", "URL": "url",
        "MD5": "hash_md5", "SHA1": "hash_sha1", "SHA256": "hash_sha256",
        "HASH": "hash_sha256",  # generic hash — default to sha256
    }
    for line in text.strip().splitlines():
        m = re.match(r"^(\w+):(.+)$", line.strip())
        if m:
            typ = type_map.get(m.group(1).upper())
            if typ:
                iocs.append({"type": typ, "value": m.group(2).strip()})
    return {"iocs": iocs, "techniques": [], "malware_families": [], "threat_actors": []}
```

### STIX pattern builder — reusing Phase 2 normalizer patterns

```python
# Source: services/feed-orchestrator/feeds/threatfox.py + normalizer.py (Phase 2 patterns)
# These STIX patterns are already proven in Phase 2 — use verbatim.
IOC_TYPE_TO_STIX = {
    "ip":          ("[ipv4-addr:value = '{v}']", "IPv4-Addr"),
    "domain":      ("[domain-name:value = '{v}']", "Domain-Name"),
    "url":         ("[url:value = '{v}']", "Url"),
    "hash_md5":    ("[file:hashes.MD5 = '{v}']", "StixFile"),
    "hash_sha1":   ("[file:hashes.'SHA-1' = '{v}']", "StixFile"),   # quoted — hyphen in property name
    "hash_sha256": ("[file:hashes.'SHA-256' = '{v}']", "StixFile"), # quoted — hyphen in property name
    "email":       ("[email-addr:value = '{v}']", "Email-Addr"),
}

def build_stix_pattern(ioc_type: str, value: str) -> tuple[str, str] | None:
    """Returns (pattern_string, observable_type) or None if type unknown."""
    entry = IOC_TYPE_TO_STIX.get(ioc_type)
    if not entry:
        return None
    pattern = entry[0].replace("{v}", value.replace("'", "\\'"))
    return pattern, entry[1]
```

### Docker Compose healthcheck — matches intel-extractor entry

```yaml
# Source: docker-compose.yml intel-extractor entry (lines 274-292) — add healthcheck only
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

---

## Reusable Phase 2 Assets

This section maps what to copy vs. extend from Phase 2.

| Asset | Location | How Used in Phase 3 |
|-------|----------|----------------------|
| `create_indicator()` | `services/feed-orchestrator/opencti_client.py` | Copy verbatim into `services/intel-extractor/opencti_client.py` |
| `build_pycti_client()` | `services/feed-orchestrator/opencti_client.py` | Copy verbatim |
| `config.py` pattern | `services/feed-orchestrator/config.py` | New config.py adds `OLLAMA_URL`, `OLLAMA_MODEL`; remove Redis/feed-specific vars |
| `deduplicator.py` | `services/feed-orchestrator/deduplicator.py` | Use for cross-job dedup at pycti level (same pattern); within-job dedup is a plain Python set |
| `Dockerfile` | `services/feed-orchestrator/Dockerfile` | Copy and adjust CMD to `uvicorn main:app --host 0.0.0.0 --port 8001` |
| `pytest.ini` | `services/feed-orchestrator/pytest.ini` | Copy verbatim |
| STIX pattern strings | `services/feed-orchestrator/feeds/threatfox.py` | Reuse `IOC_TYPE_TO_STIX` mapping (verified working in Phase 2) |

**Note on Dockerfile:** Phase 2's Dockerfile installs `libmagic1` via apt. Intel-extractor needs no system-level deps (PyPDF2 and trafilatura are pure Python). The `libmagic1` line can be omitted.

### Phase 3 config.py (new vars)

```python
# Source: services/feed-orchestrator/config.py pattern
import os, logging
logger = logging.getLogger(__name__)

OPENCTI_URL   = os.environ.get("OPENCTI_URL", "http://opencti:8080")
OPENCTI_TOKEN = os.environ.get("OPENCTI_TOKEN", "")
OLLAMA_URL    = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL  = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

logger.info("OPENCTI_TOKEN configured: %s", bool(OPENCTI_TOKEN))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `format='json'` string only | JSON Schema object as `format=` parameter | ollama 0.5.0+ | Can enforce exact key names; for Phase 3 few-shot + `format='json'` string is sufficient for 3B model |
| `hmset()` for Redis | `hset(mapping={...})` | redis-py 4.x | Already applied in Phase 2 — no action |
| `pypdf` (old PyPDF2 fork) | PyPDF2 3.0.1 still maintained | 2022 | Project spec names `pypdf2` — use it as-is |
| Ollama default num_ctx=2048 | Must set num_ctx explicitly | llama3.2:3b config | Critical — 2048 is far too small for threat report chunks |

**Deprecated/outdated:**
- `report_class` parameter: older pycti examples use `report_class=` but pycti 6.4.11 source uses `report_types=` (list). Use `report_types=["threat-report"]`.
- `pypdf` (without "2"): is the maintained successor but requirements.txt should use `PyPDF2==3.0.1` per design doc spec.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| docker compose | Container build | ✓ | Docker 29.5 + Compose v5 | — |
| OpenCTI platform | pycti API calls | ✓ | 6.4.0 (9 services healthy) | — |
| Ollama + llama3.2:3b | LLM extraction | ✓ | pulled via init-models.sh in Phase 1 | — |
| Redis | Cross-job dedup (deduplicator.py) | ✓ | 7.2-alpine | — |
| python:3.12-slim | Docker base image | ✓ | available on registry | — |
| curl | Docker healthcheck | ✓ | in python:3.12-slim base | — |

**Missing dependencies with no fallback:** none

**Note:** intel-extractor does NOT depend on Redis directly (job state is in-memory). Redis dependency is only for `deduplicator.py`'s cross-job IOC dedup — and that module can be imported from Phase 2's feed-orchestrator or copied.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (same as Phase 2) |
| Config file | `services/intel-extractor/pytest.ini` (copy from feed-orchestrator) |
| Quick run command | `pytest services/intel-extractor/tests/ -x -q` |
| Full suite command | `pytest services/intel-extractor/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AIEX-01 | PDF bytes → text extraction → IOCs returned | unit | `pytest tests/test_parser.py::test_extract_pdf_text -x` | ❌ Wave 0 |
| AIEX-01 | LLM JSON response parsed to IOC list | unit | `pytest tests/test_extractor.py::test_call_llm_happy_path -x` | ❌ Wave 0 |
| AIEX-02 | URL → trafilatura text → IOCs returned | unit | `pytest tests/test_parser.py::test_extract_url_text -x` | ❌ Wave 0 |
| AIEX-02 | trafilatura None → fallback to requests | unit | `pytest tests/test_parser.py::test_extract_url_text_trafilatura_fallback -x` | ❌ Wave 0 |
| AIEX-03 | Technique keyword → attack_pattern.list → relationship created | unit | `pytest tests/test_opencti_client.py::test_lookup_attack_pattern -x` | ❌ Wave 0 |
| AIEX-04 | Indicators + report + relationships written to mock pycti | unit | `pytest tests/test_opencti_client.py::test_create_report -x` | ❌ Wave 0 |
| AIEX-05 | 20K char document splits into multiple chunks with overlap | unit | `pytest tests/test_extractor.py::test_chunk_text_overlap -x` | ❌ Wave 0 |
| AIEX-05 | IOC appearing in overlap region deduped to single indicator | unit | `pytest tests/test_extractor.py::test_ioc_dedup_across_chunks -x` | ❌ Wave 0 |

**Note on testing LLM extraction in CI:** Do NOT call Ollama in unit tests. Mock `call_llm()` to return a fixed dict. The chunking, parsing, dedup, and STIX-building logic is fully testable without a live LLM.

### Sampling Rate

- **Per task commit:** `pytest services/intel-extractor/tests/ -x -q`
- **Per wave merge:** `pytest services/intel-extractor/tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `services/intel-extractor/tests/__init__.py`
- [ ] `services/intel-extractor/tests/conftest.py` — mock_pycti_client, mock_ollama_client fixtures
- [ ] `services/intel-extractor/tests/test_parser.py` — AIEX-01, AIEX-02
- [ ] `services/intel-extractor/tests/test_extractor.py` — AIEX-01, AIEX-05
- [ ] `services/intel-extractor/tests/test_opencti_client.py` — AIEX-03, AIEX-04
- [ ] `services/intel-extractor/pytest.ini`
- [ ] Framework already installed (pytest in host env); Docker build installs in container

---

## Security Domain

> `security_enforcement: true`, ASVS level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user auth in demo scope |
| V3 Session Management | no | Stateless job IDs, no session tokens |
| V4 Access Control | no | No RBAC in demo scope |
| V5 Input Validation | yes | Validate PDF bytes are valid (PdfReader raises on corrupt), URL format validation |
| V6 Cryptography | no | No crypto operations |

### Known Threat Patterns for FastAPI + LLM pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious PDF with embedded JavaScript/macros | Tampering | PyPDF2 extracts text only — does not execute embedded content |
| SSRF via URL parameter | Spoofing | Validate URL scheme (http/https only), block internal IPs in production |
| Prompt injection via PDF content | Tampering | LLM output is validated against expected JSON schema; reject unexpected keys |
| Large file upload causing OOM | DoS | Limit UploadFile size in FastAPI (add `max_upload_size` guard or check `len(content)` after read) |
| Job ID enumeration | Information Disclosure | UUIDs are not sequential — low risk for demo; add auth in v2 |

**Security note on SSRF:** For demo scope (localhost network), SSRF is low risk. The URL scraping runs inside the Docker container on `tim-network` — only `tim-network` services are reachable. Still: validate URL scheme to reject `file://`, `ftp://`, and internal `http://` addresses pointing to OpenCTI/Redis/etc.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ollama.Client(host=).chat()` is the correct SDK call pattern (not `ollama.chat()` with env var) | Standard Stack, Pattern 2 | Service fails to connect to Ollama at `http://ollama:11434` |
| A2 | `response.message.content` is the attribute path for chat response content in ollama SDK 0.4.x+ | Pattern 2 | AttributeError — may need `response['message']['content']` for older versions |
| A3 | `trafilatura.fetch_url()` returns `None` (not raises) on network failure | Pattern 8, Pitfall 3 | Fallback logic not triggered; unhandled exception bubbles up |
| A4 | PyPDF2 3.0.1 `page.extract_text()` returns empty string `""` (not `None`) for image-only pages | Pattern 7 | `None` check instead of empty-string check — silent bug |
| A5 | `client.attack_pattern.list(search=keyword, first=5)` returns an empty list `[]` (not None) when no match | Pattern 5 | `if not results:` check works regardless — low risk |
| A6 | `report.create(objects=[...])` successfully sets `object_refs` in OpenCTI when IDs are passed at creation time | Pattern 3 | Report created with empty object_refs; fallback: call `add_stix_object_or_stix_relationship()` per indicator |

**Verify A1 and A2 in Wave 0:** Add a `test_ollama_connection.py` smoke test that mocks `ollama.Client` and confirms the call signature used in `extractor.py` matches what the mock expects.

**Verify A6 in Wave 1 integration:** After the first end-to-end test, check the created report in OpenCTI UI to confirm `object_refs` are populated. If empty, switch to the `add_stix_object_or_stix_relationship()` per-indicator loop approach.

---

## Open Questions

1. **`report.create(objects=[...])` vs. post-hoc `add_stix_object_or_stix_relationship()`**
   - What we know: pycti 6.4.11 source accepts `objects=` kwarg in `report.create()` and passes it to the GraphQL mutation as `"objects": objects`
   - What's unclear: Whether the OpenCTI 6.4.0 GraphQL schema actually populates `object_refs` from `objects=` at creation time, or whether it's silently ignored
   - Recommendation: Implement with `report.create(objects=ids)` first. If the report appears with empty object_refs in the UI, fall back to calling `add_stix_object_or_stix_relationship()` per indicator.

2. **Ollama SDK `response.message.content` vs `response['message']['content']`**
   - What we know: ollama SDK 0.4.x uses Pydantic models; `response.message` should be a `Message` object with `.content` attribute
   - What's unclear: exact attribute path in the installed version (0.6.2)
   - Recommendation: Wave 0 conftest should verify the attribute path with a real mock before implementing extractor.py

3. **Memory pressure with large PDFs + 1g mem_limit**
   - What we know: intel-extractor has `mem_limit: 1g` in docker-compose.yml; Ollama is separate
   - What's unclear: A 200-page PDF could produce 500KB+ of text; chunking and processing sequentially should be fine, but peak memory during PyPDF2 parsing is unknown
   - Recommendation: Accept for demo scope. Flag if OOM observed during testing; solution is streaming page-by-page rather than loading all pages at once.

---

## Sources

### Primary (MEDIUM confidence — verified from installed source)
- pycti 6.4.11 source at `/home/researcher/.local/lib/python3.10/site-packages/pycti/entities/` — `report.create()`, `stix_core_relationship.create()`, `attack_pattern.list()` signatures verified line-by-line
- `services/feed-orchestrator/opencti_client.py` — `create_indicator()` and `build_pycti_client()` verified from codebase

### Secondary (LOW confidence — from web search)
- FastAPI BackgroundTasks docs: https://fastapi.tiangolo.com/tutorial/background-tasks/
- Ollama Python SDK: https://github.com/ollama/ollama-python (structured outputs docs)
- trafilatura docs: https://trafilatura.readthedocs.io/en/latest/usage-python.html
- PyPDF2 3.x docs: https://pypdf2.readthedocs.io/en/3.0.0/user/extract-text.html
- pycti examples: https://github.com/OpenCTI-Platform/client-python/blob/master/examples/create_incident_with_ttps_and_indicators.py

### Tertiary (codebase — HIGH confidence for project conventions)
- `services/feed-orchestrator/config.py` — env var pattern
- `services/feed-orchestrator/feeds/base.py` — retry pattern, logging conventions
- `docker-compose.yml` lines 274–292 — intel-extractor service entry (already scaffolded)
- `docs/plans/2026-06-23-tim-system-design.md` §4.3.1, §5.1, §5.3, §5.6, §6.3, §7.1 — authoritative spec

---

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM — PyPI existence verified; API shapes from docs (not live tests against installed packages)
- pycti call signatures: MEDIUM — verified from installed 6.4.11 source (authoritative)
- Architecture: HIGH — consistent with Phase 2 patterns + design doc spec
- Pitfalls: MEDIUM — based on known library behaviors and Phase 2 learnings

**Research date:** 2026-06-25
**Valid until:** 2026-07-25 (30 days — stack is stable)
