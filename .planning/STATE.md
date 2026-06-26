---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 4 context gathered
last_updated: "2026-06-26T05:21:56.743Z"
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 23
  completed_plans: 21
  percent: 50
---

# STATE: TIM — Threat Intelligence Management System

**Last updated:** 2026-06-26
**Session:** Phase 4 Plan 03 complete — indexer.py implemented (4 tests passing, lazy ChromaDB init)

---

## Project Reference

**Core value:** An analyst can ingest any threat intelligence source — structured feed or unstructured PDF — and immediately search, correlate, and brief stakeholders on active threats, without a single IOC leaving the local network.

**Current focus:** Phase 04 — semantic-search-engine

---

## Current Position

| Field | Value |
|-------|-------|
| Active phase | Phase 4: Semantic Search (Plan 03 complete) |
| Current Plan | 3 / 5 |
| Status | Executing Phase 04 — Plan 03/5 done |
| Phase progress | 3/6 phases complete (Phase 1 ✓, Phase 2 ✓, Phase 3 ✓) |

**Progress bar:**

```
Phase 1 [██████████] 100% ✓ COMPLETE
Phase 2 [██████████] 100% ✓ COMPLETE
Phase 3 [██████████] 100% ✓ COMPLETE
Phase 4 [██████    ] 60% (3/5 plans)
Phase 5 [          ] 0%
Phase 6 [          ] 0%
```

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases defined | 6 |
| Requirements mapped | 30/30 |
| Plans written | 4 |
| Plans complete | 4 |
| Phases complete | 1/6 |

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

### Blockers

None.

---

## Session Continuity

**Resume file:** .planning/phases/04-semantic-search-engine/04-CONTEXT.md

**Last session:** 2026-06-26T05:21:56.738Z
**Stopped at:** Phase 4 context gathered

**To resume work:**

1. `/gsd-plan-phase 2` — Feed Ingestion Pipeline (feed-orchestrator service, 5+ sources)
2. `/gsd-plan-phase 3` — AI IOC Extraction (intel-extractor service, local LLM)
3. Phase 2 and Phase 3 can be planned and executed in parallel (no dependency between them)

**Design document:** `docs/plans/2026-06-23-tim-system-design.md` — authoritative source for component specs, API contracts, docker-compose structure, and port assignments.

**Running platform:** 9 services healthy at localhost:8080 — OpenCTI + 709 ATT&CK patterns + TAXII live.

---
*State initialized: 2026-06-23 | Phase 1 closed: 2026-06-25*

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
