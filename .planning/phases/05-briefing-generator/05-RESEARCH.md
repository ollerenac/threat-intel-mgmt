# Phase 05: Briefing Generator - Research

**Researched:** 2026-06-26
**Domain:** FastAPI + pycti read queries + Ollama chat + fpdf2 PDF export
**Confidence:** HIGH (all critical patterns verified from live codebase)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Pull full threat picture from OpenCTI for the configured time window: new indicators, threat actors, malware families, campaigns, ATT&CK attack patterns, and affected sectors (inferred from indicator labels).
- **D-02:** Cap at top-10 per entity type within the window.
- **D-03:** Entity types and pycti calls: `indicator.list()`, `threat_actor.list()`, `malware.list()`, `campaign.list()`, `attack_pattern.list()`. Sectors inferred from indicator labels.
- **D-04:** Sort IOCs by confidence score descending (D-09 formula from Phase 2) to surface top-10 highest-confidence indicators.
- **D-05:** Data sent as pre-aggregated stats block (not raw JSON). ~250–350 tokens.
- **D-06:** System prompt targets formal SOC-to-executive tone. Output: plain prose, no markdown, no bullets.
- **D-07:** `asyncio.to_thread` for all Ollama and pycti calls. `temperature=0.3`.
- **D-08:** Use `fpdf2` — pure Python, no system deps beyond libmagic1. A4, DejaVu font for Unicode safety.
- **D-09:** Minimal PDF layout: title, period date, generated-at timestamp, body via `FPDF.multi_cell()`.
- **D-10:** In-memory dict `briefings: dict[str, dict]` at module level. Lost on restart — acceptable for demo.
- **D-11:** API: `POST /generate` → `{"briefing_id": "...", "status": "generating"}` immediately; `GET /briefings/{id}` polls; `GET /briefings/{id}/pdf` returns PDF bytes when done; `GET /health`.

### Claude's Discretion
- pycti field selection per entity type (which fields to request).
- Exact `updated_at` filter syntax for pycti 6.4.x — follow semantic-engine pattern exactly.
- Dockerfile structure and requirements.txt order — follow intel-extractor and semantic-engine patterns exactly.
- How to handle LLM returning briefing outside 200–300 words: truncate or re-prompt — truncate is simpler (deferred decision from CONTEXT.md).

### Deferred Ideas (OUT OF SCOPE)
- Briefing persistence across restarts (SQLite or JSON on disk).
- Sector breakdown as a separate PDF section or chart.
- LLM re-prompt if output is outside 200–300 words (truncate only).
- Multi-page PDF with table of top IOCs.
- `period_hours` beyond 24/72 (accept any int, document 24/72 as tested).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AIBR-01 | briefing-generator produces a 200–300 word executive summary from OpenCTI data | D-05 stats block → D-06 system prompt → `client.chat()` → prose text. Truncate to ~1800 chars if over limit. |
| AIBR-02 | Briefing covers last 24h or 72h period (configurable) | `period_hours` param on `POST /generate`; `updated_at` filter with `gt` operator applied to all pycti list calls. |
| AIBR-03 | Briefing available in dashboard and exportable as PDF | `GET /briefings/{id}/pdf` returns `application/pdf` bytes built by fpdf2. DejaVu TTF must be baked into Docker image. |
| AIBR-04 | Briefing can be triggered manually from the dashboard | `POST /generate` is stateless HTTP — no CLI, no shell access needed. Phase 6 dashboard calls this endpoint directly. |
</phase_requirements>

---

## Summary

Phase 5 builds `services/briefing-generator/` — a FastAPI service that reads OpenCTI threat data for a configurable time window, aggregates it into a stats block, sends it to Ollama (llama3.2:3b) for executive-prose generation, and exposes the result as JSON and PDF. The service follows the intel-extractor pattern (BackgroundTasks, module-level state dict, pre-init race guard) with the semantic-engine's `asyncio.to_thread` pattern for all blocking I/O.

The primary new dependency is `fpdf2` for PDF generation. The critical finding here is that **DejaVu fonts are NOT bundled with fpdf2** — they must be downloaded and baked into the Docker image at build time. This is the only meaningful addition to the established Dockerfile pattern.

All other patterns are directly reusable from prior phases: pycti client init from intel-extractor, the `updated_at` filter shape from semantic-engine's `list_indicators_since()`, the `ollama.Client.chat()` call from intel-extractor's `call_llm()`, and the `asyncio.to_thread` wrapper from semantic-engine's `run_index_loop()`.

**Primary recommendation:** Copy intel-extractor as the skeleton, replace `jobs` with `briefings`, implement a `_collect_threat_data()` sync function (pycti reads), a `_generate_briefing()` sync function (ollama chat), combine them in one `_run_generate()` sync helper, wrap with `asyncio.to_thread` inside a BackgroundTask, and add fpdf2 PDF rendering. DejaVu TTF must be `COPY`-ed into the image — download it in Dockerfile or commit the TTF to the service directory.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Threat data aggregation | API / Backend (briefing-generator) | — | pycti read queries run server-side; client never touches OpenCTI directly |
| LLM summary generation | API / Backend (briefing-generator) | — | Ollama is internal Docker service; blocking I/O offloaded via asyncio.to_thread |
| PDF rendering | API / Backend (briefing-generator) | — | fpdf2 runs in-process; PDF bytes returned as HTTP response body |
| Briefing storage | API / Backend (in-memory dict) | — | Module-level dict, request-scoped, lost on restart (D-10) |
| Briefing trigger | API / Backend (HTTP POST) | Browser (Phase 6 dashboard) | Dashboard calls POST /generate; no CLI interaction required (AIBR-04) |
| PDF download | API / Backend (HTTP GET) | Browser | GET /briefings/{id}/pdf streams bytes; browser handles file save |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.115.14 | HTTP API framework | Pinned across all prior phases — do not change [VERIFIED: codebase grep] |
| uvicorn | (unpinned) | ASGI server | Consistent with all prior services [VERIFIED: codebase grep] |
| pycti | 6.4.11 | OpenCTI GraphQL client | Pinned across Phases 3 and 4 — BC-01/BC-02 apply [VERIFIED: codebase grep] |
| ollama | 0.6.2 | Local LLM client | `ollama.Client` + `.chat()` already used in intel-extractor and semantic-engine [VERIFIED: codebase grep] |
| fpdf2 | 2.8.7 | PDF generation | Current release; pure Python; no system deps [VERIFIED: pip index versions] |
| pytest | (unpinned) | Test framework | Consistent with all prior services [VERIFIED: codebase grep] |
| pytest-mock | (unpinned) | Mocking for tests | Consistent with all prior services [VERIFIED: codebase grep] |

### No New System Dependencies
`libmagic1` is already required by pycti (BC-04). No additional apt packages. DejaVu TTF is fetched at Docker build time (see Dockerfile pattern below).

**Installation (requirements.txt — follows intel-extractor order):**
```
fastapi==0.115.14
uvicorn
pycti==6.4.11
ollama==0.6.2
fpdf2==2.8.7
pytest
pytest-mock
```

**Version verification:** [VERIFIED: pip index versions fpdf2 → 2.8.7 current]

---

## Package Legitimacy Audit

The seam tool lacks PyPI download count data (returns `unknown-downloads` for all packages). All packages except fpdf2 are already in production in Phases 3 and 4. fpdf2 is verified via official GitHub repo and PyPI.

| Package | Registry | Source Repo | Verdict | Disposition |
|---------|----------|-------------|---------|-------------|
| fastapi | PyPI | github.com/fastapi/fastapi | SUS (unknown-downloads) | Approved — production in Phases 3 & 4 |
| uvicorn | PyPI | github.com/Kludex/uvicorn | SUS (unknown-downloads) | Approved — production in Phases 3 & 4 |
| pycti | PyPI | github.com/OpenCTI-Platform/opencti | SUS (too-new, unknown-downloads) | Approved — production in Phases 3 & 4 |
| ollama | PyPI | (no repo URL in registry) | SUS (unknown-downloads) | Approved — production in Phases 3 & 4; `ollama.Client` confirmed working at 0.6.2 |
| fpdf2 | PyPI | github.com/py-pdf/fpdf2 | SUS (unknown-downloads) | Approved — well-known pure-Python PDF lib; official GitHub py-pdf org; LGPL-3.0 [CITED: pypi.org/project/fpdf2] |

**Packages removed (SLOP verdict):** none
**Packages flagged SUS:** all — but the seam returns SUS for every PyPI package due to missing download data. Prior-phase packages are proven in production. fpdf2 is confirmed via official py-pdf GitHub org.

---

## Architecture Patterns

### System Architecture Diagram

```
POST /generate
    │
    ▼
main.py — pre-init briefings[id] = {status: "generating"}
    │
    ├─► background_tasks.add_task(run_generate, briefing_id, period_hours)
    │       │
    │       ▼
    │   asyncio.to_thread(_run_generate_sync, briefing_id, period_hours)
    │       │
    │       ├─► _collect_threat_data(client, period_hours)
    │       │       │
    │       │       ├─► client.indicator.list(filters=updated_at_filter, first=10)
    │       │       ├─► client.threat_actor.list(filters=updated_at_filter, first=10)
    │       │       ├─► client.malware.list(filters=updated_at_filter, first=10)
    │       │       ├─► client.campaign.list(filters=updated_at_filter, first=10)
    │       │       └─► client.attack_pattern.list(filters=updated_at_filter, first=10)
    │       │
    │       ├─► _build_stats_block(data, period_hours)  → ~300-token text
    │       │
    │       ├─► _call_ollama(stats_block) → prose text
    │       │       └─► ollama_client.chat(model, messages=[system+user], options={temperature:0.3})
    │       │
    │       └─► briefings[id] = {status: "done", text: prose, ...}
    │
    └─► returns {"briefing_id": id, "status": "generating"}

GET /briefings/{id}    → dict from briefings[id]
GET /briefings/{id}/pdf → fpdf2 renders text → bytes → StreamingResponse
GET /health            → {"status": "ok"}
```

### Recommended Project Structure
```
services/briefing-generator/
├── main.py            # FastAPI app, endpoints, BackgroundTasks wiring
├── generator.py       # briefings dict, run_generate(), _collect_*, _build_stats_block(), _call_ollama()
├── opencti_client.py  # build_pycti_client() — copied from intel-extractor, read-only queries added
├── pdf_renderer.py    # render_pdf(briefing: dict) -> bytes using fpdf2
├── config.py          # env vars: OPENCTI_URL, OPENCTI_TOKEN, OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
├── Dockerfile         # python:3.12-slim, libmagic1, DejaVu TTF download, pip install
├── requirements.txt   # see Standard Stack above
└── tests/
    ├── __init__.py
    ├── conftest.py    # mock_pycti, mock_ollama fixtures
    ├── test_generator.py   # unit tests for stats block, data collection
    └── test_pdf_renderer.py # unit test for render_pdf output
```

### Pattern 1: BackgroundTasks + pre-init race guard (from intel-extractor)

[VERIFIED: services/intel-extractor/main.py lines 38-58]

```python
# main.py
briefing_id = str(uuid.uuid4())
# ponytail: init BEFORE add_task — task reads briefings[briefing_id] before this line otherwise
briefings[briefing_id] = {
    "status": "generating",
    "text": None,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "period_hours": body.period_hours,
    "error": None,
}
background_tasks.add_task(run_generate, briefing_id, body.period_hours)
return {"briefing_id": briefing_id, "status": "generating"}
```

### Pattern 2: asyncio.to_thread for blocking sync I/O (from semantic-engine)

[VERIFIED: services/semantic-engine/indexer.py lines 214-229]

```python
# generator.py — async wrapper called by BackgroundTasks
async def run_generate(briefing_id: str, period_hours: int) -> None:
    try:
        await asyncio.to_thread(_run_generate_sync, briefing_id, period_hours)
    except Exception as exc:
        logger.error("[generator] generation failed: %s", exc)
        briefings[briefing_id]["status"] = "error"
        briefings[briefing_id]["error"] = str(exc)

def _run_generate_sync(briefing_id: str, period_hours: int) -> None:
    """All blocking I/O here — pycti + ollama are sync clients."""
    client = build_pycti_client()
    data = _collect_threat_data(client, period_hours)
    stats_block = _build_stats_block(data, period_hours)
    text = _call_ollama(stats_block)
    briefings[briefing_id]["text"] = text
    briefings[briefing_id]["status"] = "done"
```

### Pattern 3: pycti updated_at filter shape (from semantic-engine)

[VERIFIED: services/semantic-engine/opencti_client.py lines 63-80]

```python
from datetime import datetime, timezone, timedelta

def _make_updated_at_filter(period_hours: int) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(hours=period_hours)).isoformat()
    return {
        "mode": "and",
        "filters": [{"key": "updated_at", "values": [since]}],
        "filterGroups": [],
    }

# Usage — same shape works for all entity types:
filters = _make_updated_at_filter(period_hours)
indicators  = client.indicator.list(filters=filters, first=10, orderBy="updated_at", orderMode="desc")
actors      = client.threat_actor.list(filters=filters, first=10)
malware     = client.malware.list(filters=filters, first=10)
campaigns   = client.campaign.list(filters=filters, first=10)
patterns    = client.attack_pattern.list(filters=filters, first=10)
```

The filter uses `gt` semantics (OpenCTI interprets a single value as "greater than"). The semantic-engine wraps this in a try/except and falls back to full fetch on failure — the same defensive pattern applies here.

### Pattern 4: ollama.Client.chat() for prose generation (from intel-extractor)

[VERIFIED: services/intel-extractor/extractor.py lines 178-186]

```python
import ollama

_ollama = ollama.Client(host=OLLAMA_URL)  # module-level singleton

def _call_ollama(stats_block: str) -> str:
    response = _ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": stats_block},
        ],
        options={"temperature": 0.3},
        # NOTE: NO format="json" — we want plain prose output
    )
    text = response.message.content.strip()
    # Truncate to ~300 words if LLM overshoots (D-deferred: no re-prompt)
    words = text.split()
    if len(words) > 320:
        text = " ".join(words[:300]) + "..."
    return text
```

### Pattern 5: fpdf2 PDF rendering (DejaVu NOT bundled — must be in image)

[CITED: py-pdf/fpdf2 GitHub repo, pypi.org/project/fpdf2]

```python
from fpdf import FPDF

def render_pdf(briefing: dict) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    # DejaVu TTF path must match COPY destination in Dockerfile
    pdf.add_font("DejaVu", fname="/app/fonts/DejaVuSans.ttf")
    pdf.set_font("DejaVu", size=16)
    pdf.cell(text="Threat Intelligence Briefing", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", size=11)
    pdf.cell(text=f"Period: last {briefing['period_hours']}h | Generated: {briefing['created_at']}")
    pdf.ln(8)
    pdf.set_font("DejaVu", size=11)
    pdf.multi_cell(w=0, text=briefing["text"])  # word-wraps to page width
    return bytes(pdf.output())
```

**Critical: `multi_cell(w=0, ...)` uses full page width. `w=0` is the idiomatic fpdf2 pattern.**

### Pattern 6: Dockerfile with DejaVu font download

[ASSUMED — standard pattern; fpdf2 non-bundling VERIFIED from GitHub repo inspection]

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 wget \
    && wget -q -O /tmp/dejavu.zip \
       "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip" \
    && mkdir -p /app/fonts \
    && unzip -j /tmp/dejavu.zip "*/DejaVuSans.ttf" -d /app/fonts \
    && rm /tmp/dejavu.zip \
    && apt-get remove -y wget unzip && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
```

**Alternative (simpler, avoids wget):** Commit `DejaVuSans.ttf` directly into `services/briefing-generator/fonts/` and `COPY fonts/ /app/fonts/`. No wget needed. Preferred if the font file size (~757 KB) is acceptable in git.

### Pattern 7: config.py (follows intel-extractor exactly)

[VERIFIED: services/intel-extractor/config.py]

```python
import os, logging
logger = logging.getLogger(__name__)

OPENCTI_URL   = os.environ.get("OPENCTI_URL", "http://opencti:8080")
OPENCTI_TOKEN = os.environ.get("OPENCTI_TOKEN", "")
OLLAMA_URL    = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL  = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "60"))  # LLM generation can take 30-45s

logger.info("OPENCTI_TOKEN configured: %s", bool(OPENCTI_TOKEN))
```

`OLLAMA_TIMEOUT` is NOT in the docker-compose.yml env block — pass it via `options` or a client timeout parameter if needed, or accept the default.

### Anti-Patterns to Avoid

- **`asyncio.to_thread` inside a non-async function:** `run_generate()` must be `async def`. BackgroundTasks calls it as a coroutine. If declared `def`, `await asyncio.to_thread(...)` will raise.
- **Calling pycti or ollama directly in the async endpoint handler:** Starves the event loop. All blocking I/O must be inside `_run_generate_sync()`, called via `asyncio.to_thread`.
- **`format="json"` on the ollama chat call:** intel-extractor uses it for structured extraction. Briefing generator wants prose — omit `format="json"` or the LLM will emit JSON wrapping around the text.
- **`response.embedding` (singular):** Deprecated. The codebase uses `response.embeddings[0]` (plural) for embed calls. For chat, `response.message.content` is correct.
- **DejaVu assumed bundled:** fpdf2 does NOT bundle DejaVu. Missing font file at runtime raises `FileNotFoundError` inside the background task, setting `status: "error"`. Must be in the Docker image.
- **`report_class=` in pycti:** BC-01: use `report_types=["threat-report"]`. Not relevant to read queries but keep in mind for any write calls.
- **`externalReferences` as dicts in pycti:** BC-02. Not used in briefing-generator (read-only service) but noted.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF word-wrap | Manual line-break calculation | `FPDF.multi_cell(w=0, text=...)` | fpdf2 handles pagination, margins, line breaks |
| HTTP pagination through pycti results | Manual cursor loop | `getAll=True, first=N` | pycti handles `hasNextPage`/`endCursor` internally |
| Blocking-in-async | Threads manually | `asyncio.to_thread(sync_fn, *args)` | BC-03: event loop starvation otherwise |
| Word count truncation | Byte counting, char counting | `text.split()` → slice to 300 words | Split on whitespace is sufficient for prose |
| IOC type counting | Regex on raw data | Count `x_opencti_main_observable_type` values in list results | pycti returns typed dicts |

---

## Common Pitfalls

### Pitfall 1: DejaVu font not in Docker image
**What goes wrong:** `render_pdf()` raises `FileNotFoundError` at runtime inside the BackgroundTask. `briefings[id]["status"]` becomes `"error"`. PDF endpoint returns 404.
**Why it happens:** fpdf2 does not bundle any TTF fonts. `add_font(fname="/app/fonts/DejaVuSans.ttf")` looks for an absolute path.
**How to avoid:** Either (a) commit `DejaVuSans.ttf` to the repo under `services/briefing-generator/fonts/` and `COPY fonts/ /app/fonts/` in Dockerfile, or (b) wget it during Docker build. Option (a) is simpler.
**Warning signs:** Container starts fine but all generate requests end in `status: "error"`.

### Pitfall 2: asyncio.to_thread wrapper declared as def instead of async def
**What goes wrong:** `await asyncio.to_thread(...)` inside a `def` function raises `SyntaxError`. If declared `def` at the BackgroundTasks level, FastAPI runs it synchronously in the request thread, blocking the event loop.
**Why it happens:** `BackgroundTasks.add_task()` accepts both sync and async callables. The intent is async — must be `async def`.
**How to avoid:** Declare `run_generate()` as `async def`. The sync work goes inside `_run_generate_sync()` called via `asyncio.to_thread`.

### Pitfall 3: ollama timeout not set for LLM generation
**What goes wrong:** `llama3.2:3b` generating 200–300 words of prose can take 30–45 seconds on a 4 GB VRAM machine. Default ollama client timeout may be shorter. Request hangs or errors with connection reset.
**Why it happens:** intel-extractor's `call_llm()` worked because it sends short structured prompts. The briefing prompt + stats block is larger and output is longer.
**How to avoid:** Pass `OLLAMA_TIMEOUT=60` as an env var. Construct `ollama.Client(host=OLLAMA_URL, timeout=OLLAMA_TIMEOUT)`.

### Pitfall 4: pycti updated_at filter returns empty list (no data in window)
**What goes wrong:** `indicator.list(filters=...)` returns `[]` for a 24h window if no new data was ingested recently. Stats block shows "New IOCs: 0". LLM generates a valid but content-free briefing.
**Why it happens:** Demo environment may not have live feed ingestion running continuously.
**How to avoid:** Emit the stats block regardless of zero counts. The LLM handles "nothing new in this period" gracefully. Do NOT raise an error on empty data — return a valid briefing.

### Pitfall 5: PDF endpoint called before status == "done"
**What goes wrong:** `GET /briefings/{id}/pdf` is called while `status == "generating"`. `briefings[id]["text"]` is `None`. `render_pdf()` receives `None` and crashes.
**Why it happens:** Client doesn't poll `GET /briefings/{id}` first.
**How to avoid:** In the PDF endpoint, check `briefings[id]["status"] == "done"` before calling `render_pdf()`. Return 404 with detail `"briefing not ready"` if status is still `"generating"`. This is documented in D-11 and CONTEXT.md.

### Pitfall 6: pycti entity types — field names differ per entity type
**What goes wrong:** `client.threat_actor.list()` returns `name` at the top level. `client.malware.list()` also returns `name`. `client.attack_pattern.list()` returns `name` AND `x_mitre_id`. Accessing a missing field with `["key"]` raises `KeyError` in `_build_stats_block()`.
**Why it happens:** pycti returns different field subsets per entity type, and not all fields are present on all objects.
**How to avoid:** Use `.get("name", "Unknown")` and `.get("x_mitre_id", "")` throughout `_build_stats_block()`. Confirmed pattern from intel-extractor `call_llm()` line 190.

---

## Code Examples

### Confidence score sort for IOC top-10 (D-04)
```python
# x_opencti_score is the D-09 formula field stored in OpenCTI
indicators_sorted = sorted(
    indicators,
    key=lambda x: x.get("x_opencti_score", 0),
    reverse=True
)[:10]
```

### Stats block construction (D-05)
```python
from datetime import datetime, timezone

def _build_stats_block(data: dict, period_hours: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    iocs = data["indicators"]
    ioc_types = {}
    for ind in iocs:
        t = ind.get("x_opencti_main_observable_type", "Unknown")
        ioc_types[t] = ioc_types.get(t, 0) + 1

    top_conf = max((i.get("x_opencti_score", 0) for i in iocs), default=0) / 100

    actor_names   = [a.get("name", "Unknown") for a in data["actors"]]
    malware_names = [m.get("name", "Unknown") for m in data["malware"]]
    campaigns     = data["campaigns"]
    patterns      = data["attack_patterns"]
    pattern_strs  = [
        f"{p.get('x_mitre_id', '')} ({p.get('name', '')})"
        for p in patterns
    ]
    sectors = data.get("sectors", [])

    return (
        f"Period: last {period_hours}h (ending {now}).\n"
        f"New IOCs: {len(iocs)} ({', '.join(f'{c} {t}' for t,c in ioc_types.items()) or 'none'})"
        + (f", top confidence: {top_conf:.2f}" if iocs else "") + ".\n"
        f"Active threat actors: {', '.join(actor_names) or 'none identified'}.\n"
        f"Active malware: {', '.join(malware_names) or 'none identified'}.\n"
        f"Active campaigns: {len(campaigns)} identified.\n"
        f"Top ATT&CK techniques: {', '.join(pattern_strs[:3]) or 'none'}.\n"
        f"Affected sectors: {', '.join(sectors) or 'none identified'}.\n"
    )
```

### Sector inference from indicator labels
```python
# Sectors are inferred from objectLabel values (D-01, D-03)
SECTOR_KEYWORDS = {"finance", "critical-infrastructure", "healthcare", "energy", "government"}

def _extract_sectors(indicators: list[dict]) -> list[str]:
    found = set()
    for ind in indicators:
        for label in ind.get("objectLabel", []):
            v = label.get("value", "").lower()
            if v in SECTOR_KEYWORDS:
                found.add(v)
    return sorted(found)
```

### POST /generate endpoint with validation
```python
from pydantic import BaseModel, Field

class GenerateRequest(BaseModel):
    period_hours: int = Field(default=24, ge=1, le=720)  # 1h–30d; 24/72 are tested values
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| OpenCTI | pycti reads (AIBR-01/02) | ✓ (Phase 1) | 6.x | — |
| Ollama + llama3.2:3b | LLM generation (AIBR-01) | ✓ (Phase 3/4) | 0.6.2 | — |
| fpdf2 | PDF export (AIBR-03) | ✓ (pip installable, 2.8.7) | 2.8.7 | — |
| DejaVu TTF | fpdf2 Unicode rendering | ✗ (not bundled) | 2.37 | No fallback — must be in image |
| Docker profile `briefings` | Service startup | ✓ (stub in compose) | — | `--profile briefings` alongside `--profile platform` |

**Missing dependencies with no fallback:**
- DejaVu TTF font file — must be added to the Docker image at build time (commit to repo or wget in Dockerfile).

---

## Validation Architecture

`nyquist_validation: true` — section required.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (unpinned, matches prior services) |
| Config file | none — pytest.ini not used in prior services; run from service dir |
| Quick run command | `cd services/briefing-generator && python -m pytest tests/ -x -q` |
| Full suite command | `cd services/briefing-generator && python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AIBR-01 | `_build_stats_block()` produces correct format | unit | `pytest tests/test_generator.py::test_build_stats_block -x` | ❌ Wave 0 |
| AIBR-01 | `_call_ollama()` returns truncated prose ≤ 320 words | unit (mock) | `pytest tests/test_generator.py::test_call_ollama_truncation -x` | ❌ Wave 0 |
| AIBR-02 | `_make_updated_at_filter(72)` produces correct filter dict | unit | `pytest tests/test_generator.py::test_updated_at_filter -x` | ❌ Wave 0 |
| AIBR-03 | `render_pdf()` returns bytes starting with `%PDF` | unit | `pytest tests/test_pdf_renderer.py::test_render_pdf_bytes -x` | ❌ Wave 0 |
| AIBR-04 | `POST /generate` returns 200 + `briefing_id` immediately | integration (mock) | `pytest tests/test_generator.py::test_post_generate_returns_immediately -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd services/briefing-generator && python -m pytest tests/ -x -q`
- **Per wave merge:** same (small service, full suite is fast)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` — empty, needed for pytest discovery
- [ ] `tests/conftest.py` — `mock_pycti`, `mock_ollama` fixtures (copy from intel-extractor pattern)
- [ ] `tests/test_generator.py` — import-guard + _skip pattern (copy from intel-extractor)
- [ ] `tests/test_pdf_renderer.py` — import-guard + render_pdf bytes check
- [ ] `fonts/DejaVuSans.ttf` — must exist for `test_pdf_renderer.py` to pass without mocking font path

---

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Service is internal Docker network only; no auth required at demo scope |
| V3 Session Management | no | Stateless HTTP; no sessions |
| V4 Access Control | no | Internal network only |
| V5 Input Validation | yes | `period_hours`: Pydantic `Field(ge=1, le=720)` on `GenerateRequest`. `briefing_id` is UUID — validate with `uuid.UUID(briefing_id)` guard or check against dict keys. |
| V6 Cryptography | no | No crypto operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| `period_hours` overflow / negative value | Tampering | Pydantic `Field(ge=1, le=720)` rejects invalid values with 422 |
| `briefing_id` path traversal (non-UUID string) | Tampering | Dict key lookup — if not in `briefings`, raises 404. No filesystem access. |
| LLM output injection (malicious prompt in OpenCTI data) | Tampering | Stats block is aggregated counts + names, not raw user input. Risk is low — brief C-suite prose from structured data, not reflected to a shell. |
| OOM from large pycti result set | DoS | `first=10` cap on all list calls (D-02). |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `updated_at` filter with single value uses `gt` semantics in pycti 6.4.11 (inferred from semantic-engine fallback pattern) | Pattern 3 | If filter is `gte` or `eq`, time window may include stale data. Fallback to full fetch (same as semantic-engine) is the mitigation. |
| A2 | `client.threat_actor.list()`, `client.malware.list()`, `client.campaign.list()` accept the same `filters` dict as `client.indicator.list()` | Pattern 3 | Different entity types may have different filter API shapes. Guard with try/except, fall back to `first=10` without filter. |
| A3 | DejaVu TTF downloadable from `github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/` | Dockerfile pattern | URL may change. Safer to commit TTF to repo under `services/briefing-generator/fonts/`. |
| A4 | `ollama.Client(host=..., timeout=60)` is a valid constructor kwarg at ollama 0.6.2 | Pattern 4, Pitfall 3 | If `timeout` is not a valid kwarg, pass it via `options={"timeout": 60}` or accept default. |

---

## Open Questions (RESOLVED)

1. **Does `client.threat_actor.list()` support the `filters` dict?**
   - What we know: `client.indicator.list()` with `filters` dict works (Phase 4 production). `attack_pattern.list(search=keyword)` works (Phase 3 production).
   - What's unclear: Whether all entity types expose the same `filters` kwarg in pycti 6.4.11.
   - RESOLVED: Plan 02 implements `_safe_list()` — each entity list call wrapped in try/except; falls back to `first=10` without `filters` on exception with logged warning.

2. **`OLLAMA_TIMEOUT` env var — is it wired in docker-compose.yml?**
   - What we know: The docker-compose.yml briefing-generator env block does NOT include `OLLAMA_TIMEOUT`. The CONTEXT.md suggests adding it as a config default (60s).
   - What's unclear: Whether the `ollama.Client` constructor accepts a `timeout` kwarg.
   - RESOLVED: Plan 02 adds `OLLAMA_TIMEOUT=60` default in `config.py`; passed to `ollama.Client(timeout=OLLAMA_TIMEOUT)`. If SDK rejects it, fallback is accepted default timeout.

---

## Sources

### Primary (HIGH confidence — verified from live codebase)
- `services/intel-extractor/main.py` — BackgroundTasks + pre-init race guard (lines 38-58)
- `services/intel-extractor/extractor.py` — `ollama.Client.chat()` call signature (lines 178-186)
- `services/intel-extractor/config.py` — config.py pattern (all lines)
- `services/semantic-engine/opencti_client.py` — `updated_at` filter dict shape (lines 63-80)
- `services/semantic-engine/indexer.py` — `asyncio.to_thread(_run_sync, ...)` pattern (lines 214-229)
- `services/intel-extractor/requirements.txt` — confirmed `ollama` (unpinned) is the Python package name
- `services/semantic-engine/requirements.txt` — confirmed `ollama==0.6.2`
- `docker-compose.yml` lines 334-352 — briefing-generator stub (env vars, port, profiles, depends_on)

### Secondary (MEDIUM confidence — verified via official source)
- [pypi.org/project/fpdf2](https://pypi.org/project/fpdf2/) — version 2.8.7 current; LGPL-3.0; depends on Pillow/defusedxml/fontTools
- [github.com/py-pdf/fpdf2](https://github.com/py-pdf/fpdf2) — no fonts bundled in `fpdf/data/` directory; DejaVu must be provided externally
- `pip index versions fpdf2` — confirmed 2.8.7 is current release

### Tertiary (LOW confidence — documentation lookup)
- fpdf2 `multi_cell(w=0, text=...)` API shape — from fpdf2 Unicode documentation [ASSUMED syntax; confirm against installed fpdf2 2.8.7 API]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pinned versions from live codebase; fpdf2 version from pip registry
- Architecture: HIGH — BackgroundTasks + asyncio.to_thread pattern verified in two prior services
- pycti filter syntax: HIGH — exact working code from semantic-engine production
- fpdf2 patterns: MEDIUM — API documented, DejaVu non-bundling confirmed via GitHub; exact `multi_cell` kwargs need runtime verification
- Pitfalls: HIGH — sourced from prior phase BC-01–05 constraints and direct code reading

**Research date:** 2026-06-26
**Valid until:** 2026-07-26 (pycti and fpdf2 are stable; ollama SDK moves faster — re-verify if ollama bumped past 0.6.x)
