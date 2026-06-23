# STATE: TIM — Threat Intelligence Management System

**Last updated:** 2026-06-23
**Session:** Roadmap initialization

---

## Project Reference

**Core value:** An analyst can ingest any threat intelligence source — structured feed or unstructured PDF — and immediately search, correlate, and brief stakeholders on active threats, without a single IOC leaving the local network.

**Current focus:** Phase 1 — Platform Foundation

---

## Current Position

| Field | Value |
|-------|-------|
| Active phase | Phase 1: Platform Foundation |
| Active plan | None (planning not started) |
| Status | Not started |
| Phase progress | 0% |

**Progress bar:**
```
Phase 1 [          ] 0%
Phase 2 [          ] 0%
Phase 3 [          ] 0%
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
| Plans written | 0 |
| Plans complete | 0 |
| Phases complete | 0/6 |

---

## Accumulated Context

### Key Decisions Locked

| Decision | Rationale |
|----------|-----------|
| OpenCTI over MISP | Better graph visualization; STIX 2.1 native; more impressive to SOC buyers |
| Ollama (local LLM) over cloud APIs | Data sovereignty + competitive differentiation |
| ChromaDB for vector store | Lightweight, Docker-native, no external deps |
| Pull-based semantic indexing (5 min poll) | Simpler than OpenCTI webhooks for demo scope |
| React + Vite for dashboard | Fast dev; TanStack Query handles dual API sources cleanly |

### Architecture Constraints

- GPU VRAM: 4 GB — only one large model active at a time (llama3.2:3b OR nomic-embed-text, not both)
- Disk budget: 28 GB total for entire stack
- No external API calls — all IOC processing must remain local
- Single node deployment — all services on one Docker Compose stack

### Phase Dependencies

- Phase 3 (AI Extraction) depends on Phase 1 only (standalone service)
- Phase 4 (Semantic Search) depends on Phase 1 + Phase 2 (needs IOCs to index)
- Phase 5 (Briefings) depends on Phase 1 + Phase 2 (needs OpenCTI data)
- Phase 6 (Dashboard) depends on Phases 1, 2, 4, 5 (unifies all outputs)

### Todos

- [ ] Generate UUIDs for `OPENCTI_ADMIN_TOKEN` and `CONNECTOR_MITRE_ID` before Phase 1 start
- [ ] Obtain AlienVault OTX free API key before Phase 2 (FEED-03)
- [ ] Define seed data content for demo scenarios (post-implementation, Section 8 of design doc)

### Blockers

None.

---

## Session Continuity

**To resume work:**
1. Read `.planning/ROADMAP.md` for phase structure and success criteria
2. Read `.planning/REQUIREMENTS.md` for full requirement list and traceability
3. Read `docs/plans/2026-06-23-tim-system-design.md` for architecture details
4. Run `/gsd-plan-phase 1` to begin planning Phase 1

**Design document:** `docs/plans/2026-06-23-tim-system-design.md` — authoritative source for component specs, API contracts, docker-compose structure, and port assignments.

---
*State initialized: 2026-06-23 after roadmap creation*
