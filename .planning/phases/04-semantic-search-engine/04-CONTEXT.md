# Phase 4: Semantic Search Engine - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the `semantic-engine` service: a FastAPI service that (1) indexes all OpenCTI indicator objects as embedding vectors in ChromaDB, and (2) serves natural-language queries returning ranked IOC results with similarity scores and OpenCTI deep-links.

The service stub already exists in `docker-compose.yml` (profile `semantic`, port 8002). Phase 4 delivers `services/semantic-engine/` from scratch.

</domain>

<decisions>
## Implementation Decisions

### Embedding Content
- **D-01:** Embed enriched context per IOC: `"{indicator_type}: {value} — {description} {labels}"` — not raw value alone. This makes semantic search work for queries like "Russian infrastructure malware" even without exact IOC values.
- **D-02:** Pull enrichment from OpenCTI indicator fields only (name, description, labels). No graph traversal to linked reports — one API call per indicator, fast enough for 22k+ IOC corpus.
- **D-03:** For indicators with no description (most feed-sourced IOCs from URLhaus/Feodo), embed `"{type}: {value} [{labels}]"` — skip blank description silently, use labels (e.g., `malware-distribution`, `botnet-cc`) as the signal. Never exclude no-description IOCs — they represent the bulk of the corpus.

### Indexing Startup
- **D-04:** Use incremental watermark indexing: store `last_indexed_at` timestamp in ChromaDB metadata. On restart, fetch only indicators with `updated_at > last_indexed_at`. ChromaDB handles upserts for changed IOCs. Fast restarts after initial index.
- **D-05:** On first startup (ChromaDB empty), run full index in background — do NOT block `/health`. Service responds immediately with `{"status": "ok", "indexed": N, "total": M}` so progress is visible. Same background-task pattern as `intel-extractor` jobs.

### Search Result Shape
- **D-06:** Return top 10 results, fixed. (Planner may add optional `?limit=` param but 10 is the default and all callers should use it.)
- **D-07:** Apply similarity threshold of 0.3 — drop results scoring below this to avoid returning obviously-unrelated IOCs. Expose as env var `SIMILARITY_THRESHOLD=0.3` so it can be tuned without rebuild.
- **D-08:** Each result includes: `ioc_type`, `value`, `score` (0.0–1.0), `opencti_url`, `embedded_text` (the text that was vectorized). `embedded_text` lets the analyst see WHY the IOC matched — critical for demo credibility. ChromaDB stores this as metadata alongside the vector (no extra DB call).

### Claude's Discretion
- ChromaDB collection strategy (single vs. per-type), exact pycti query approach for indicator pagination, Dockerfile and requirements.txt structure — follow `intel-extractor` patterns.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Service Stub (already wired)
- `docker-compose.yml` §semantic-engine — service definition, env vars, profiles, depends_on. Do NOT change port (8002), profile name (`semantic`), or env var names.

### Prior Service Pattern (analog to build from)
- `services/intel-extractor/main.py` — FastAPI + BackgroundTasks pattern; background job state in module-level dict; `/health`, `/extract`, `/jobs/{id}` endpoints
- `services/intel-extractor/Dockerfile` — `python:3.12-slim` base, `apt-get libmagic1`, `pip install -r requirements.txt`, `CMD ["uvicorn", ...]`
- `services/intel-extractor/opencti_client.py` — pycti usage pattern, D-05 retry logic, how to authenticate to OpenCTI

### Phase Requirements
- `.planning/REQUIREMENTS.md` §AISEM-01 through AISEM-04 — the 4 requirements this phase must satisfy

### BC Constraints (from Phase 2/3)
- **BC-01**: `docker compose` always needs `--profile platform --profile semantic` (not just `--profile semantic`) — ChromaDB is in the `platform` profile
- **BC-02**: pycti 6.4.x rejects `externalReferences` as dicts — use ID strings only

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `services/intel-extractor/main.py` — Copy FastAPI app skeleton, `/health` pattern, background task dispatch. The `jobs` dict pattern works for tracking index progress too.
- `services/intel-extractor/opencti_client.py` — `create_indicator` shows the pycti auth/client init pattern. For semantic-engine, we need `client.indicator.list()` with pagination instead of create.
- `docker-compose.yml` chromadb block — Already defines `chromadata` volume, port 8000, healthcheck. Just use `CHROMADB_URL=http://chromadb:8000`.

### Established Patterns
- FastAPI + uvicorn + python:3.12-slim Dockerfile (Phases 3)
- Background task for long-running work; `/health` returns immediately with progress info
- Env vars for all config (OPENCTI_URL, OPENCTI_TOKEN, OLLAMA_URL already in docker-compose stub)
- `pytest` + `pytest-skipif` import guard for optional deps (Phase 3 test scaffold)

### Integration Points
- ChromaDB at `http://chromadb:8000` (already in platform profile, `chromadb/chroma:latest`)
- Ollama at `http://ollama:11434` — model `nomic-embed-text` (768-dim vectors). Must be pulled before indexing (already handled by `scripts/init-models.sh`)
- OpenCTI at `http://opencti:8080` — source of all indicator objects
- Phase 6 (dashboard) will call `GET http://semantic-engine:8002/search?q=...` — keep the API simple and stable

</code_context>

<specifics>
## Specific Ideas

- The `/health` endpoint should expose index progress (`indexed`, `total`) so `docker compose ps` gives useful status during initial index — not just a boolean healthy/unhealthy
- `SIMILARITY_THRESHOLD` as env var enables tuning without rebuild — important for demo prep where the right threshold depends on corpus composition
- `embedded_text` in results is a demo differentiator: analyst can see "this IP matched because it was tagged botnet-cc" rather than just getting a score

</specifics>

<deferred>
## Deferred Ideas

- Filtering results by IOC type (e.g., only domains) — Phase 6 (dashboard) concern, not the engine
- Graph-traversal enrichment (pulling linked report titles) — deferred as too slow for 22k corpus; revisit if search quality is poor after Phase 4 ships
- Configurable `?limit=` param — planner may add if needed, not a Phase 4 requirement
- Semantic search over non-indicator objects (threat actors, malware families) — out of scope for Phase 4 (AISEM-01 says "indicators"); Phase 6 dashboard decides what surface area to expose

</deferred>

---

*Phase: 4-Semantic Search Engine*
*Context gathered: 2026-06-25*
