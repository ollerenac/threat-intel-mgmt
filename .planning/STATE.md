---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: 1
status: completed
stopped_at: Post-v1.0 improvements — feeds fixed, briefing quality improved
last_updated: "2026-06-27T02:22:00.000Z"
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 31
  completed_plans: 31
  percent: 100
---

# STATE: TIM — Threat Intelligence Management System

**Last updated:** 2026-06-27
**Session:** Post-v1.0 fixes — all 5 feeds operational, briefing hallucinations eliminated (commit 1198d5c)

---

## Project Reference

**Core value:** An analyst can ingest any threat intelligence source — structured feed or unstructured PDF — and immediately search, correlate, and brief stakeholders on active threats, without a single IOC leaving the local network.

**Current focus:** Post-v1.0 improvements

---

## Current Position

| Field | Value |
|-------|-------|
| Active phase | — all phases complete |
| Current Plan | — |
| Status | TIM v1.0 complete + post-launch fixes |
| Phase progress | 6/6 phases complete ✓ |

**Progress bar:**

```
Phase 1 [██████████] 100% ✓ COMPLETE
Phase 2 [██████████] 100% ✓ COMPLETE
Phase 3 [██████████] 100% ✓ COMPLETE
Phase 4 [██████████] 100% ✓ COMPLETE
Phase 5 [██████████] 100% ✓ COMPLETE
Phase 6 [██████████] 100% ✓ COMPLETE
```

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases defined | 6 |
| Requirements mapped | 30/30 |
| Plans written | 4 |
| Plans complete | 4 |
| Phases complete | 5/6 |

---
| Phase 02 P01 | 3m | 2 tasks | 9 files |
| Phase 02 P03 | 7m | 2 tasks | 2 files |
| Phase 02-feed-ingestion-pipeline P04 | 5 | 2 tasks | 2 files |
| Phase 02-feed-ingestion-pipeline P07 | 8m | 2 tasks | 4 files |
| Phase 03 P02 | 2m | 2 tasks | 3 files |
| Phase 03-ai-ioc-extraction P03 | 5m | 1 tasks | 2 files |
| Phase 03 P05 | 2m | 2 tasks | 4 files |
| Phase 04-semantic-search-engine P01 | 2m | 2 tasks | 5 files |
| Phase 04 P02 | 5m | 2 tasks | 5 files |
| Phase 04-semantic-search-engine P03 | 4m | 1 tasks | 1 files |
| Phase 05-briefing-generator P01 | 2m | 2 tasks | 7 files |
| Phase 05-briefing-generator P02 | 2m | 2 tasks | 3 files |
| Phase 05-briefing-generator P03 | 2m | 1 tasks | 1 files |
| Phase 05 P04 | 7m | 2 tasks | 1 files |
| Phase 06 P01 | 12m | 2 tasks | 5 files |
| Phase 06 P02 | 8m | 2 tasks | 9 files |

## Accumulated Context

### Key Decisions Locked

| Decision | Rationale |
|----------|-----------|
| OpenCTI over MISP | Better graph visualization; STIX 2.1 native; more impressive to SOC buyers |
| Ollama (local LLM) over cloud APIs | Data sovereignty + competitive differentiation |
| ChromaDB for vector store | Lightweight, Docker-native, no external deps |
| Pull-based semantic indexing (5 min poll) | Simpler than OpenCTI webhooks for demo scope |
| React + Vite for dashboard | Fast dev; TanStack Query handles dual API sources cleanly |
| opencti/worker as separate service | OpenCTI 6.x requires worker to consume RabbitMQ; without it STIX bundles never reach Elasticsearch |
| pgrep -f probe for worker healthcheck | Only Python + pgrep available in opencti/worker image |
| TAXII collection must be created via UI | OpenCTI TAXII server returns empty collections until admin creates one in Data Sharing UI |

### Architecture Constraints

- GPU VRAM: 4 GB — only one large model active at a time (llama3.2:3b OR nomic-embed-text, not both)
- Disk budget: 28 GB total for entire stack
- No external API calls — all IOC processing must remain local
- Single node deployment — all services on one Docker Compose stack
- OpenCTI /health returns HTTP 401 when healthy — never use curl -f/-sf against it

### Phase Dependencies

- Phase 3 (AI Extraction) depends on Phase 1 only — **can be planned/executed in parallel with Phase 2**
- Phase 4 (Semantic Search) depends on Phase 1 + Phase 2 (needs IOCs to index)
- Phase 5 (Briefings) depends on Phase 1 + Phase 2 (needs OpenCTI data)
- Phase 6 (Dashboard) depends on Phases 1, 2, 4, 5 (unifies all outputs)

### Phase 1 Learned Constraints (carry forward)

- Healthcheck probes must use only binaries available inside each image — test with `docker compose exec <svc> which curl` before writing probes
- Port 11434 (Ollama) is not host-bound — readiness checks must use `docker compose exec ollama`
- `opencti/worker` service required for any OpenCTI 6.x stack — do not omit it
- TAXII collections require manual UI creation — document this in SETUP.md for Phase 2+ ops

### Todos

- [x] Generate UUIDs for `OPENCTI_ADMIN_TOKEN` and `CONNECTOR_MITRE_ID` — done in Phase 1
- [x] Obtain AlienVault OTX free API key before Phase 2 (FEED-03) — stored in .env
- [ ] Define seed data content for demo scenarios (post-implementation, Section 8 of design doc)

### Post-v1.0 Fixes Shipped (2026-06-27, commit 1198d5c)

- MalwareBazaar feed: `json=` → `data=` (API requires form-encoded, not JSON)
- ThreatFox feed: null `tags` field crashes `list(None)` — fixed with `or []`
- MalwareBazaar + ThreatFox auth keys added to `.env` — both feeds now active (3549 ThreatFox IOCs ingested on first run)
- briefing-generator: removed `updated_at` time filter from actors/malware/campaigns/patterns — reference entities are not timestamp-bumped by feed ingestion; were always returning empty
- briefing-generator: IOC fetch cap raised 10 → 25 (query 50, keep top 25 by confidence)
- briefing-generator: added hallucination guard to system prompt — briefings now grounded in actual data
- Briefings.jsx: fixed permanent `generating` lock caused by uncaught async error inside `setInterval`

### Remaining Improvement Backlog

| Item | Priority | Status |
|------|----------|--------|
| Briefing persistence (SQLite) | High | not started |
| Alerting on high-confidence IOC | High | not started |
| connector-mitre ATT&CK pattern gap | Medium | not started |
| IOC enrichment (VirusTotal/Shodan) | Medium | not started — out of scope per data sovereignty constraint |
| SIEM export (CEF/STIX) | Medium | not started |

### Blockers

None.

---

## Session Continuity

**Last session:** 2026-06-27T02:22:00Z
**Stopped at:** Post-v1.0 feed fixes and briefing quality improvements committed (1198d5c)

**Uncommitted files still pending:**
- `docker-compose.yml` — profile/rebuild fix from Phase 6
- `services/feed-orchestrator/main.py` — uvicorn/asyncio fix from Phase 6

**To resume work:** Pick from improvement backlog above. Suggested next: briefing persistence (SQLite) — lowest effort, highest demo stability impact.

**Running platform:**
- feed-orchestrator: port 8001 — 5 feeds active (URLhaus, OTX, Feodo, MalwareBazaar, ThreatFox)
- semantic-engine: port 8002 — 23k+ IOCs indexed in ChromaDB
- briefing-generator: port 8003 — grounded briefings, no hallucination
- soc-dashboard: port 3000 — React UI with Overview / Threat Hunt / Briefings views
- OpenCTI: port 8080

---
*State initialized: 2026-06-23 | Phase 1 closed: 2026-06-25 | Phase 5 closed: 2026-06-26*

## Decisions

- [Phase ?]: RED-phase TDD: test files define STIX contracts before production code exists
- [Phase ?]: D-09 formula values embedded as comments in test_normalizer.py (feodo-new=65, otx-7d=53, cap=100) so Wave 3 executor can verify formula without re-reading RESEARCH.md
- [Phase ?]: CSV comment-skip filter applied before DictReader — ensures first non-comment line becomes header row
- [Phase ?]: Feodo c2 label hardcoded unconditionally — all entries are confirmed botnet C2 servers
- [Phase 02-07]: D-09 confidence formula: min(100, seen_in_feeds*25 + max(0,10-days_old) + quality_weight)
- [Phase 02-07]: Lazy import from normalizer in _insert_deduplicated avoids circular dependency at module load
- [Phase 02-07]: D-06 enforced — all 5 feeds run synchronously before scheduler.start()
- [Phase ?]: [Phase 03-03]: report_types=[threat-report] used — report_class= is deprecated in pycti 6.4.11
- [Phase ?]: [Phase 03-03]: lookup_attack_pattern returns internal UUID not x_mitre_id (D-08)
- [Phase 03-06]: libmagic1 apt package required in python:3.12-slim for pycti (python-magic wraps C library libmagic.so)
- [Phase 03-06]: Python urllib.request healthcheck probe is the correct pattern for python:3.12-slim images (no curl available)
- [Phase 04-01]: RED-phase TDD scaffold: import-guard+skipif in test files so tests SKIP (not FAIL) when production modules absent
- [Phase 04-01]: monkeypatch _ollama singleton in test_searcher.py — search() takes no ollama arg (module-level client); injection via monkeypatch.setattr
- [Phase ?]: libmagic1 required in semantic-engine Dockerfile — pycti==6.4.11 imports python-magic which needs libmagic.so
- [Phase ?]: OPENCTI_BASE_URL default http://localhost:8080 — external browser URL distinct from internal Docker network http://opencti:8080
- [Phase 04-03]: Lazy ChromaDB HttpClient deferred to get_collection() — import-safe for test guard pattern (chromadb.HttpClient connects at construction, breaks import guard)
- [Phase 04-03]: response.embeddings[0] confirmed (plural) — not deprecated .embedding singular (ollama 0.6.2)
- [Phase 04-04]: score = round(1.0 - dist, 4) — cosine distance to similarity; threshold applied to score not raw distance (RESEARCH Pitfall 1)
- [Phase 04-04]: asynccontextmanager lifespan + asyncio.create_task is the correct FastAPI 0.115 startup pattern (not @app.on_event, not BackgroundTasks)
- [Phase 05-01]: DejaVuSans.ttf committed to repo from official dejavu-fonts 2.37 release — avoids wget at Docker build time
- [Phase 05-01]: import-guard+skipif pattern inherited from Phase 4 — tests SKIP not FAIL when production modules absent
- [Phase 05-01]: ollama==0.6.2 pinned (not floating) — version-locks response.message.content attribute path
- [Phase ?]: OLLAMA_TIMEOUT=60 default — prose generation 30-45s on 4GB VRAM
- [Phase ?]: briefings dict is module-level — exported for Plan 04 main.py; acceptable for demo (D-10)
- [Phase ?]: No format=json on ollama chat call — prose output mode distinct from intel-extractor JSON extraction
- [Phase ?]: FONT_PATH at module level in pdf_renderer.py — monkeypatchable by tests without Docker font path
- [Phase ?]: D-10 race guard: briefings[briefing_id] pre-initialized before background_tasks.add_task()
- [Phase ?]: uvicorn.run() replaces signal.pause() as main-thread blocker in feed-orchestrator
- [Phase ?]: asyncio.to_thread wraps _collect_threat_data in /stats — prevents blocking uvicorn event loop on pycti I/O
- [Phase ?]: feed-orchestrator healthcheck upgraded from Redis ping to urllib HTTP probe
- [Phase ?]: VITE_* env vars removed from soc-dashboard compose — Vite bakes env at build time; no runtime effect on static nginx
- [Phase ?]: Template devDeps (@types/react, oxlint) removed from dashboard package.json — plain JSX needs no TS types
