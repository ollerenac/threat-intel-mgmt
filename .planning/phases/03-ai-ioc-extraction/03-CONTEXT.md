# Phase 3: AI IOC Extraction - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Build `intel-extractor` — a Python FastAPI service (port 8001) that accepts PDF files or URLs, parses and chunks the content, sends each chunk to Ollama (llama3.2:3b) for structured IOC extraction, maps extracted ATT&CK technique mentions to OpenCTI's pre-loaded attack-pattern objects, and creates STIX 2.1 `indicator` + `report` SDOs with relationship edges in OpenCTI via pycti.

**In scope:**
- `intel-extractor` FastAPI service at port 8001
- PDF ingestion (AIEX-01): parse with pypdf2/pdfplumber → text extraction → chunking
- URL ingestion (AIEX-02): scrape with trafilatura → text extraction → chunking
- Async job model: POST /extract → {job_id}, GET /jobs/{id} → status/results
- LLM extraction via Ollama llama3.2:3b (single-pass JSON schema, few-shot prompted)
- STIX output: `indicator` SDOs + one `report` SDO per extraction job
- ATT&CK mapping: LLM extracts technique keywords → Python queries OpenCTI → STIX relationship edges
- Chunking with overlap for documents exceeding ~6K tokens (AIEX-05)
- Docker Compose service entry with healthcheck, profile: [extract]

**Out of scope for Phase 3:**
- `malware`, `threat-actor`, `intrusion-set`, `campaign` SDOs (deferred from design doc — Phase 3 scope is indicator + report only)
- Full relationship graph beyond indicator→attack-pattern edges
- Streaming responses or SSE job progress
- Persistent job store (in-memory only — jobs lost on restart)
- Direct OpenCTI webhook integration (Phase 4 handles indexing)

</domain>

<decisions>
## Implementation Decisions

### LLM Extraction Prompt (D-01 through D-03)
- **D-01:** Single-pass JSON schema extraction. One Ollama call per chunk with a system prompt that instructs the model to return a JSON object with keys: `iocs` (list of `{type, value}` where type is ip, domain, hash_md5, hash_sha1, hash_sha256, url, email), `techniques` (list of `{name, description}`), `malware_families` (list of strings), `threat_actors` (list of strings). All IOC types extracted in one pass — no sequential per-type calls.
- **D-02:** Include one few-shot example in the system prompt. The example shows a short text snippet and the expected JSON output structure. Target ~200 tokens for the example. This dramatically improves formatting reliability for 3B models without excessive context overhead.
- **D-03:** On malformed/unparseable JSON response: retry once with a stripped-down fallback prompt ("List all IPs, domains, file hashes, and URLs from this text, one per line, format: TYPE:VALUE"). Parse the plain-text response with regex. If fallback also fails, skip the chunk and log a warning. Other chunks in the job continue processing.

### STIX Object Scope (D-04 through D-05)
- **D-04:** Per extraction job, create: (1) one `report` SDO with the document title/URL as the name, published date = extraction timestamp, and `object_refs` pointing to all indicator IDs created; (2) one `indicator` SDO per unique IOC (same pattern as Phase 2 — reuse `opencti_client.create_indicator()`). No `malware`, `threat-actor`, or `intrusion-set` SDOs in Phase 3.
- **D-05:** ATT&CK technique links: create a STIX `relationship` SDO with relationship_type="indicates" from each `indicator` to the matched `attack-pattern` OpenCTI object. This produces visible graph edges in OpenCTI's knowledge graph visualization — the demo-critical moment. Requires querying OpenCTI to get the `attack-pattern` object ID for each matched Txxxx technique.

### Job Processing Model (D-06 through D-07)
- **D-06:** Async job processing. `POST /extract` returns `{job_id, status: "queued"}` immediately. A FastAPI `BackgroundTasks` or asyncio task processes the document in the background. Job state stored in a module-level Python dict: `jobs: dict[str, JobState]`. `JobState` contains status, iocs_extracted count, techniques_found count, report_id (OpenCTI STIX ID), error (if failed), processing_time_s. Jobs are lost on container restart — acceptable for demo scope.
- **D-07:** `GET /jobs/{id}` returns: `{job_id, status (queued/processing/complete/failed), iocs_extracted, techniques_found, report_id, processing_time_s, error}`. Dashboard can display "Extracted N IOCs, M ATT&CK techniques" without needing to parse STIX.

### ATT&CK Technique Lookup (D-08 through D-09)
- **D-08:** LLM does NOT output Txxxx IDs directly (hallucination risk). Instead, the JSON schema's `techniques` field contains `{name, description}` as extracted by the LLM. Python code then queries OpenCTI's GraphQL API to search for attack-patterns whose name contains the extracted keyword. Uses pycti's `attack_pattern.list(search=keyword)` or equivalent. Returns canonical Txxxx ID and OpenCTI object ID for use in relationship creation.
- **D-09:** No-match handling: if OpenCTI returns zero attack-patterns for an extracted technique keyword, skip that technique (do not create a relationship, do not hallucinate a T-ID). Log: `[extractor] ATT&CK no match for: '{keyword}' — skipping`. The indicator still gets created without that technique link. Accuracy over completeness.

### Claude's Discretion
- Chunk size and overlap: ~1500 tokens per chunk with ~150 token overlap (10%) — prevents IOC loss at boundaries without excessive redundant processing. Claude calibrates this based on llama3.2:3b's ~8K context window.
- IOC deduplication across chunks: use a set of (type, value) tuples within a job to deduplicate before STIX creation. Phase 2's Redis dedup (`tim:ioc_seen:*`) handles cross-job deduplication for indicators already in OpenCTI.
- URL scraping: use `trafilatura` (as specified in design doc §4.3.1) for URL content extraction. Fall back to `requests` + BeautifulSoup if trafilatura returns empty content.
- PDF parsing: use `pypdf2` as primary (design doc spec). If pypdf2 fails to extract text (image-based PDF), log a warning and return a job error — OCR is out of scope.
- Healthcheck: `GET /health` returns `{status: "ok"}`. Docker Compose healthcheck: `CMD curl -f http://localhost:8001/health || exit 1` (port 8001 is exposed, curl available in python:3.12-slim base).
- LLM temperature: 0 for extraction (deterministic, reduce hallucination). Format: JSON (Ollama `format: "json"` parameter used alongside few-shot example for double enforcement).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Component Spec
- `docs/plans/2026-06-23-tim-system-design.md` §4.3.1 — intel-extractor component spec: pipeline, what the LLM extracts, chunking strategy, stack (Python + pypdf2/trafilatura + ollama SDK + stix2)
- `docs/plans/2026-06-23-tim-system-design.md` §6.3 — API contract for intel-extractor (POST /extract, GET /jobs/{id}, GET /health)
- `docs/plans/2026-06-23-tim-system-design.md` §5.1 — STIX SDO types; Phase 3 uses `indicator`, `report`, `relationship`
- `docs/plans/2026-06-23-tim-system-design.md` §5.3 — STIX relationship graph; Phase 3 creates indicator→attack-pattern edges
- `docs/plans/2026-06-23-tim-system-design.md` §5.6 — MITRE ATT&CK in the system: OpenCTI pre-loads ATT&CK, intel-extractor REFERENCES existing attack-pattern objects (does NOT create them)
- `docs/plans/2026-06-23-tim-system-design.md` §6.1 — Port 8001 for intel-extractor (browser + internal services accessible)
- `docs/plans/2026-06-23-tim-system-design.md` §7.1 — Directory: `services/intel-extractor/`

### Requirements
- `.planning/REQUIREMENTS.md` — AIEX-01 through AIEX-05 (the 5 AI extraction requirements this phase must satisfy)

### Phase 2 Patterns (reuse, don't reinvent)
- `services/feed-orchestrator/opencti_client.py` — pycti wrapper with 3× retry pattern; Phase 3 reuses `create_indicator()` and adds analogous `create_report()` and `create_relationship()` helpers
- `services/feed-orchestrator/config.py` — env var loading pattern; Phase 3 follows same module-level constant pattern for OPENCTI_URL, OPENCTI_TOKEN, OLLAMA_URL, OLLAMA_MODEL
- `services/feed-orchestrator/Dockerfile` — `python:3.12-slim` base; Phase 3 follows same structure
- `docker-compose.yml` (existing `intel-extractor` entry) — already scaffolded with profiles: [extract], ports: 8001:8001, OLLAMA_URL env var; needs healthcheck added

### Existing Infrastructure (build on, don't replace)
- `docker-compose.yml` — intel-extractor entry already present with correct env vars; add healthcheck only
- `.env` / `.env.example` — OPENCTI_ADMIN_TOKEN and OPENCTI_URL already defined; no new vars needed for Phase 3

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`services/feed-orchestrator/opencti_client.py`**: `build_pycti_client()` and `create_indicator()` are directly reusable. Phase 3 adds `create_report()` and `create_relationship()` using the same client and retry pattern (D-05 3× backoff from Phase 2).
- **`services/feed-orchestrator/config.py`**: Module-level env var pattern is the canonical pattern. `OPENCTI_URL`, `OPENCTI_TOKEN` already exist in `.env`. Phase 3 adds `OLLAMA_URL` (already in docker-compose.yml) and `OLLAMA_MODEL=llama3.2:3b`.
- **`services/feed-orchestrator/deduplicator.py`**: Redis-based dedup at `tim:ioc_seen:*` already handles cross-job IOC deduplication at the pycti level (pycti's `update=True` is the last-mile safety net). Phase 3 adds within-job dedup via a simple Python set.
- **`services/feed-orchestrator/Dockerfile`**: Identical base (`python:3.12-slim`). Phase 3 needs additional system deps: none expected (pypdf2 and trafilatura are pure Python).

### Established Patterns
- **Docker Compose service pattern**: profiles: [extract], depends_on opencti + ollama (both service_healthy), networks: [tim-network], restart: unless-stopped. The `intel-extractor` entry in docker-compose.yml already follows this — add healthcheck only.
- **No hardcoded secrets**: OPENCTI_TOKEN, OLLAMA_URL via env vars only. Already enforced in existing `.env` / docker-compose.yml.
- **Phase 2 profile isolation**: feed-orchestrator uses `--profile platform --profile feeds`. intel-extractor uses `--profile platform --profile extract` (profiles: [extract] already in compose).

### Integration Points
- **Ollama**: `http://ollama:11434` on `tim-network`. Use the `ollama` Python SDK (`import ollama; ollama.Client(host=OLLAMA_URL)`). Model `llama3.2:3b` already pulled via `scripts/init-models.sh` (Phase 1). Call `client.chat(model=OLLAMA_MODEL, messages=[...], format='json', options={'temperature': 0})`.
- **OpenCTI API**: `http://opencti:8080` via pycti. `attack_pattern.list(search=keyword)` for ATT&CK lookup (D-08). `report.create(...)` and `stix_relationship.create(...)` for STIX output (D-04, D-05).
- **Port 8001**: Already exposed in docker-compose.yml. Healthcheck uses this port. Dashboard (Phase 6) calls `POST http://intel-extractor:8001/extract` internally, or `http://localhost:8001/extract` from browser.

</code_context>

<specifics>
## Specific Ideas

- ATT&CK mapping is the demo's most impressive moment: a CISA advisory PDF goes in → T1566 (Phishing) appears as a graph edge in OpenCTI connecting the extracted IOC to the ATT&CK technique. The two-step lookup (LLM keyword → OpenCTI query) was chosen specifically to ensure this works reliably without hallucinated Txxxx IDs.
- The `report` SDO wraps all IOCs from a single extraction job, so a SOC analyst can see "CISA Advisory AA24-057A" as a report object in OpenCTI's knowledge graph with all its extracted indicators referenced from it.
- The design doc names `pypdf2` and `trafilatura` explicitly (§4.3.1) — these are the authoritative library choices. Do not swap for alternatives without a clear reason.
- The few-shot example in the system prompt (D-02) should use a fictional/generic threat report snippet, not real IOC data, to avoid any training data contamination concerns.

</specifics>

<deferred>
## Deferred Ideas

- **`malware` SDOs + `threat-actor` + `intrusion-set` + `campaign` SDOs**: The design doc §5.1 lists these as intel-extractor outputs. Deferred from Phase 3 scope to keep complexity manageable. The full relationship graph can be added in a Phase 3.5 or post-v1 enrichment pass.
- **OCR for image-based PDFs**: pypdf2 cannot extract text from scanned PDFs. Full OCR (tesseract) is out of scope for demo — these PDFs return an error with guidance to use a text-based PDF instead.
- **Streaming LLM response**: Ollama supports streaming. Not needed for Phase 3 — results are returned via job polling, not SSE.
- **Persistent job store (Redis)**: Async with Redis job store was offered as an option. Deferred — in-memory is sufficient for demo scope. Future: if intel-extractor needs horizontal scaling or job persistence across restarts, Redis is the obvious upgrade path (already running).

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 3-ai-ioc-extraction*
*Context gathered: 2026-06-25*
