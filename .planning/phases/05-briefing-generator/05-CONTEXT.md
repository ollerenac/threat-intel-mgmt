# Phase 5: Briefing Generator - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the `briefing-generator` service: a FastAPI service that (1) fetches a configurable time window of OpenCTI threat data, (2) generates a 200–300 word executive summary via local Ollama (llama3.2:3b), (3) stores briefings in memory, and (4) serves them via `POST /generate` + `GET /briefings/{id}` + `GET /briefings/{id}/pdf`.

The service stub already exists in `docker-compose.yml` (profile `briefings`, port 8003). Phase 5 delivers `services/briefing-generator/` from scratch, following the intel-extractor service as its primary analog.

</domain>

<decisions>
## Implementation Decisions

### Data Collection

- **D-01:** Pull the **full threat picture** from OpenCTI for the configured time window: new indicators, threat actors, malware families, campaigns, ATT&CK attack patterns, and affected sectors (inferred from indicator labels).
- **D-02:** Cap at **top-10 per entity type** within the window. Predictable context size (~800–1200 tokens of data), leaves room for prompt + LLM output within llama3.2:3b's ~4k context window.
- **D-03:** Entity types and pycti calls: `indicator.list()` (IOCs), `threat_actor.list()` (actors), `malware.list()` (malware families), `campaign.list()` (campaigns), `attack_pattern.list()` (ATT&CK techniques). Sectors inferred from indicator labels (e.g., `finance`, `critical-infrastructure`). All filtered by `updated_at` within the configured `period_hours`.
- **D-04:** Sort IOCs by confidence score descending (D-09 formula from Phase 2) to surface the top-10 highest-confidence indicators.

### LLM Prompt Design

- **D-05:** Data is sent as a **pre-aggregated stats block**, not raw JSON. Format:
  ```
  Period: last 24h (ending [ISO timestamp]).
  New IOCs: 847 (234 IPs, 312 domains, 301 URLs, top confidence: 0.91).
  Active threat actors: APT29, Lazarus Group.
  Active malware: QakBot, Emotet.
  Active campaigns: 2 identified.
  Top ATT&CK techniques: T1566 (Phishing), T1133 (External Remote Services), T1071 (Application Layer Protocol).
  Affected sectors: finance, critical-infrastructure.
  ```
  Predictable size (~250–350 tokens), allows LLM to focus on writing rather than parsing.

- **D-06:** System prompt targets **formal SOC-to-executive** tone:
  ```
  You are a senior threat intelligence analyst. Write a 200-300 word executive summary
  for C-suite leadership covering the threat landscape for the given period. Be factual,
  concise, and avoid technical jargon. Highlight business risk and strategic implications.
  Do not include lists, headers, or markdown — write in plain professional prose only.
  ```
  Output: plain prose, no markdown headers, no bullet lists.

- **D-07:** Use `asyncio.to_thread` for the Ollama HTTP call — mandatory pattern from Phase 4 (sync clients in async FastAPI starve the event loop). `temperature=0.3` for factual, consistent output.

### PDF Export

- **D-08:** Use `fpdf2` — pure Python, zero system deps, pip-installable. No apt packages needed beyond what `libmagic1` already requires.
- **D-09:** Minimal PDF layout: title line "Threat Intelligence Briefing", period date, generated-at timestamp, then body text via `FPDF.multi_cell()` for word-wrap. No logo, no border, no table. A4 page, DejaVu font (bundled with fpdf2) for Unicode safety (IOC values may contain non-ASCII).

### Briefing Storage

- **D-10:** In-memory dict — `briefings: dict[str, dict]` at module level. Consistent with intel-extractor's `jobs` dict pattern. Entry shape:
  ```python
  {
      "status": "generating" | "done" | "error",
      "text": str | None,
      "created_at": str,   # ISO
      "period_hours": int,
      "error": str | None,
  }
  ```
  Lost on container restart — acceptable for demo (trigger on demand, read immediately).

### API Shape

- **D-11:** Async generation pattern (consistent with intel-extractor BackgroundTasks):
  - `POST /generate` — body `{"period_hours": 24}` → returns `{"briefing_id": "...", "status": "generating"}` immediately
  - `GET /briefings/{id}` — polls for status + text
  - `GET /briefings/{id}/pdf` — returns `application/pdf` bytes when status is `done`; 404 while still generating or if not found
  - `GET /health` — returns `{"status": "ok"}`

### Claude's Discretion

- pycti field selection per entity type (which fields to request), exact `updated_at` filter syntax for pycti 6.4.x, Dockerfile structure and requirements.txt order — follow intel-extractor and semantic-engine patterns exactly.
- How to handle the LLM returning a briefing outside 200–300 words: truncate or re-prompt? Claude's call.

### Folded Todos

- **"Discuss and plan Phase 5 briefing-generator"** (`.planning/todos/pending/2026-06-26-discuss-and-plan-phase-5-briefing-generator.md`): This discussion session is the resolution. Decisions captured above. Mark pending todo as done after this context commit.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Service Stub (already wired)
- `docker-compose.yml` §briefing-generator (lines ~334–353) — service definition, env vars, profile (`briefings`), port (8003). Do NOT change port, profile name, or env var names (`OPENCTI_URL`, `OPENCTI_TOKEN`, `OLLAMA_URL`, `OLLAMA_MODEL`).

### Prior Service Analogs (build from these)
- `services/intel-extractor/main.py` — FastAPI + BackgroundTasks pattern; module-level `jobs` dict; POST/GET/health endpoints. **Primary analog for briefing-generator structure.**
- `services/intel-extractor/Dockerfile` — python:3.12-slim base, libmagic1 apt install, pip install -r requirements.txt, uvicorn CMD.
- `services/intel-extractor/opencti_client.py` — pycti auth/client init, retry pattern, OPENCTI_BASE_URL default.
- `services/semantic-engine/main.py` — asynccontextmanager lifespan + asyncio.create_task pattern; `asyncio.to_thread` usage. Read for the event-loop-safety pattern.

### Phase Requirements
- `.planning/REQUIREMENTS.md` §AIBR-01 through AIBR-04 — the 4 requirements this phase must satisfy.

### Architecture Constraints (from prior phases)
- **BC-01**: pycti 6.4.x: `report_types=["threat-report"]` (not deprecated `report_class=`). See Phase 3 decisions.
- **BC-02**: pycti 6.4.x rejects `externalReferences` as dicts — use ID strings only.
- **BC-03**: `asyncio.to_thread` is mandatory for any sync I/O (Ollama, pycti calls) inside async FastAPI endpoint handlers — Phase 4 hard lesson.
- **BC-04**: libmagic1 stays in Dockerfile regardless — pycti imports python-magic at module level.
- **BC-05**: `docker compose` needs `--profile platform --profile briefings` to start with the full stack.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `services/intel-extractor/main.py` — Copy the jobs-dict + BackgroundTasks skeleton verbatim; replace `jobs` with `briefings`, adapt endpoint names. The `job_id = str(uuid.uuid4())` + pre-init-before-add_task pattern must be preserved (race condition guard).
- `services/intel-extractor/opencti_client.py` — pycti client init + retry loop reusable as-is. For briefing-generator we call different pycti methods (indicator.list, threat_actor.list, etc.) but auth/retry is identical.
- `services/semantic-engine/main.py` lifespan block — shows `asyncio.create_task` vs `BackgroundTasks`. For briefing-generator, `BackgroundTasks` (per-request) is correct (not lifespan) since generation is request-scoped.

### Established Patterns
- FastAPI + uvicorn + python:3.12-slim Dockerfile (Phases 3, 4).
- Module-level state dict (lost on restart, acceptable for demo) — intel-extractor jobs.
- `asyncio.to_thread(sync_fn, *args)` wrapper for any blocking call — Phase 4 mandatory fix.
- Env vars for all config: `OPENCTI_URL`, `OPENCTI_TOKEN`, `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT` (suggest 60s default for LLM generation).

### Integration Points
- Ollama at `http://ollama:11434` — model `llama3.2:3b`. Must be loaded (init-models.sh). Use `ollama` Python SDK or direct HTTP POST to `/api/generate`.
- OpenCTI at `http://opencti:8080` — source of all threat data. pycti client with OPENCTI_TOKEN.
- Phase 6 (SOC dashboard) will call `POST http://briefing-generator:8003/generate` and then `GET /briefings/{id}/pdf` — keep the API stable.
- `VITE_BRIEFING_GENERATOR_URL=http://localhost:8003` already in soc-dashboard env (docker-compose.yml line ~373).

</code_context>

<specifics>
## Specific Ideas

- The stats block format (D-05) should mirror what an analyst would write in a morning handoff note — it's the ground truth the LLM narrative is built from. If it's well-structured, the LLM output will be accurate.
- `GET /briefings/{id}/pdf` returns 404 while status is `generating` — dashboard should poll `GET /briefings/{id}` first and only request PDF when `status == "done"`.
- Consider adding `GET /briefings` (list) returning `[{briefing_id, created_at, period_hours, status}]` — Phase 6 dashboard will want to list recent briefings without needing to know their IDs. Not a Phase 5 requirement but trivial to add alongside the other endpoints.

</specifics>

<deferred>
## Deferred Ideas

- Briefing persistence across restarts (SQLite or JSON on disk) — in-memory is sufficient for demo. Add in v2 if analysts need historical briefings.
- Configurable `period_hours` beyond 24/72 (e.g., 168h = 1 week) — AIBR-02 specifies 24h and 72h only. Accept any int via API but document 24/72 as tested.
- Sector breakdown as a separate PDF section or chart — text-only PDF is sufficient for demo.
- LLM re-prompt if output is outside 200–300 words — truncation is simpler and adequate.
- Multi-page PDF with table of top IOCs appended — deferred to Phase 6 or v2 styling pass.

</deferred>

---

*Phase: 5-Briefing Generator*
*Context gathered: 2026-06-26*
