# TIM — Threat Intelligence Management System

## What This Is

A local Threat Intelligence Management system that combines OpenCTI (industry-standard knowledge graph platform) with custom AI services powered by local LLMs. Built as a high-standard SOC demo that demonstrates both operational maturity and AI-augmented intelligence capabilities — with full data sovereignty (no IOC sent to external APIs).

## Core Value

An analyst can ingest any threat intelligence source — structured feed or unstructured PDF — and immediately search, correlate, and brief stakeholders on active threats, without a single IOC leaving the local network.

## Business Context

- **Customer**: SOC teams in enterprise organizations (financial, government, critical infrastructure)
- **Revenue model**: Professional services / product licensing
- **Success metric**: Demo convinces client of implementation value; differentiates from commodity TIM installs
- **Strategy notes**: Differentiator is local AI layer — IOC extraction from unstructured text + semantic search — which most consultants cannot deliver

## Requirements

### Validated

- [x] OpenCTI platform deployed and operational with MITRE ATT&CK pre-loaded — Validated in Phase 1
- [x] Structured feed ingestion from 3 active sources (URLhaus, Feodo Tracker, OTX); MalwareBazaar/ThreatFox pending auth keys — Validated in Phase 2
- [x] IOCs normalized to STIX 2.1 with confidence scoring (D-09 formula) — Validated in Phase 2
- [x] IOC extraction from unstructured documents (PDF, URL) via local LLM (llama3.2:3b) — Validated in Phase 3

### Active

- [ ] Semantic similarity search over IOCs via local embeddings
- [ ] Automated executive briefing generation from live OpenCTI data
- [ ] SOC Dashboard with Overview, Threat Hunt, and Briefings views
- [ ] Full Docker Compose deployment on single node

### Out of Scope

- External API enrichment (VirusTotal, AbuseIPDB) — data sovereignty requirement
- Multi-user authentication — demo runs on local network
- Production hardening (TLS, rate limiting, audit logs) — v2
- TheHive/Cortex case management — scope creep for v1 demo
- Paid threat feeds — free feeds sufficient for demo narrative
- Demo Scenarios (Section 8) content — defined post-implementation

## Context

- **Hardware**: 16 vCPUs, 31 GB RAM, 112 GB free disk, RTX 3050 4 GB VRAM, Ubuntu 22.04
- **Runtime**: Docker 29.5 + Compose v5
- **Design document**: `docs/plans/2026-06-23-tim-system-design.md` — complete architecture, component specs, data model, integration points, docker-compose
- **Purpose**: Demo for SOC client proposal — high standard, shows TIM domain knowledge + AI differentiation
- **AI stack**: Ollama with `llama3.2:3b` (extraction + briefings) and `nomic-embed-text` (embeddings), both run locally on GPU

## Constraints

- **Disk**: 28 GB allocated — must fit within budget
- **GPU VRAM**: 4 GB — only one large model active at a time
- **Data sovereignty**: No IOC may be sent to external APIs
- **Open source only**: All platform components must be free/open-source
- **Single node**: Entire stack runs on one machine

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| OpenCTI over MISP | Better graph visualization for demo; STIX 2.1 native; more impressive to SOC decision-makers | Validated in Phase 1 |
| Local LLM (Ollama) over cloud APIs | Data sovereignty + competitive differentiation | Validated in Phase 3 — llama3.2:3b extracts IOCs end-to-end |
| ChromaDB for vector store | Lightweight, Docker-native, no external deps | — Pending (Phase 4) |
| Pull-based semantic indexing (5 min poll) | Simpler than OpenCTI webhooks for demo scope | — Pending (Phase 4) |
| React + Vite for dashboard | Fast dev, TanStack Query handles dual API sources cleanly | — Pending (Phase 6) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

---
*Last updated: 2026-06-25 after Phase 3 (ai-ioc-extraction) completion*
