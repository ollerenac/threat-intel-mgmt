---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 3 complete — intel-extractor integration checkpoint approved
last_updated: "2026-06-25T23:12:00.000Z"
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 18
  completed_plans: 18
  percent: 50
---

# STATE: TIM — Threat Intelligence Management System

**Last updated:** 2026-06-25
**Session:** Phase 3 Plan 06 complete — integration checkpoint approved, Phase 3 COMPLETE

---

## Project Reference

**Core value:** An analyst can ingest any threat intelligence source — structured feed or unstructured PDF — and immediately search, correlate, and brief stakeholders on active threats, without a single IOC leaving the local network.

**Current focus:** Phase 04 — semantic-search (next)

---

## Current Position

| Field | Value |
|-------|-------|
| Active phase | Phase 4: Semantic Search (ready to execute) |
| Status | Phase 3 complete |
| Phase progress | 3/6 phases complete (Phase 1 ✓, Phase 3 ✓, Phase 2 in progress) |

**Progress bar:**

```
Phase 1 [██████████] 100% ✓ COMPLETE
Phase 2 [██████████] 100% ✓ COMPLETE
Phase 3 [██████████] 100% ✓ COMPLETE
Phase 4 [          ] 0%
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

**Resume file:** .planning/phases/03-ai-ioc-extraction/03-CONTEXT.md

**Last session:** 2026-06-25T23:11:04.442Z
**Stopped at:** Phase 3 context gathered — 9 decisions locked, CONTEXT.md committed

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
