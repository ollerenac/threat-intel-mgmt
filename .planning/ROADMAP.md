# Roadmap: TIM — Threat Intelligence Management System

**Created:** 2026-06-23
**Granularity:** Standard
**Coverage:** 30/30 v1 requirements mapped

## Phases

- [x] **Phase 1: Platform Foundation** - OpenCTI stack deployed and operational with all backing services healthy
- [x] **Phase 2: Feed Ingestion Pipeline** - feed-orchestrator service ingesting, normalizing, and scoring IOCs from all 5+ sources (completed 2026-06-25)
- [x] **Phase 3: AI IOC Extraction** - intel-extractor service processing PDFs and URLs via local LLM into OpenCTI STIX objects (completed 2026-06-25)
- [ ] **Phase 4: Semantic Search Engine** - semantic-engine indexing all IOCs as vectors and serving natural-language queries
- [ ] **Phase 5: Briefing Generator** - briefing-generator producing and exporting executive summaries from live OpenCTI data
- [ ] **Phase 6: SOC Dashboard** - React frontend unifying all services into a demo-ready three-view interface

## Phase Details

### Phase 1: Platform Foundation

**Goal**: The full OpenCTI stack and deployment scaffolding are operational — analyst can open the platform, see MITRE ATT&CK pre-loaded, and confirm all services are healthy.

**Depends on**: Nothing (first phase)

**Requirements**: PLAT-01, PLAT-02, PLAT-03, PLAT-04, DEPL-01, DEPL-02, DEPL-03, DEPL-04

**Success Criteria** (what must be TRUE):

  1. `docker compose up -d` from project root starts the full stack with no manual steps beyond `.env` configuration
  2. OpenCTI is reachable at `localhost:8080` and MITRE ATT&CK framework objects (attack-patterns with Txxxx IDs) are visible in the knowledge graph
  3. `docker compose ps` shows all services (ES, Redis, RabbitMQ, MinIO, OpenCTI, connector-mitre) as healthy
  4. TAXII 2.1 endpoint returns a valid STIX bundle when queried (e.g. `GET /taxii2/root/collections/`)
  5. `.env.example` documents all required variables and `scripts/init-models.sh` successfully pulls Ollama models

**Status**: ✓ COMPLETE — verified 2026-06-25 (5/5 criteria, VERIFICATION.md passed)

**Plans**: 4/4 plans executed

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Pre-flight: .gitignore, .env.example permissions, nvidia-container-toolkit install
- [x] 01-02-PLAN.md — docker-compose.yml profile tags (all 13 services) + connector-mitre healthcheck

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-03-PLAN.md — scripts/setup-env.sh, scripts/verify-platform.sh, docs/SETUP.md

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-04-PLAN.md — Integration: compose up, init-models.sh, verify-platform.sh end-to-end

---

### Phase 2: Feed Ingestion Pipeline

**Goal**: The feed-orchestrator service automatically ingests IOCs from all configured structured feeds, normalizes them to STIX 2.1 with confidence scores, deduplicates them, and delivers them to OpenCTI on schedule.

**Depends on**: Phase 1

**Requirements**: FEED-01, FEED-02, FEED-03, FEED-04, FEED-05, FEED-06

**Success Criteria** (what must be TRUE):

  1. URLhaus, MalwareBazaar, ThreatFox, Feodo Tracker, and AlienVault OTX feeds all produce STIX `indicator` objects visible in OpenCTI after a single feed run
  2. Each indicator in OpenCTI carries a `confidence` field (0–100) computed from feed count, recency, and source quality
  3. Submitting the same IOC from two different feeds results in one deduplicated object in OpenCTI, not two
  4. Feeds run automatically on their configured cadences (no manual trigger required) — confirmed by checking OpenCTI for new IOCs after waiting one cycle

**Plans**: 8/8 plans complete

Plans:

**Wave 1** *(all parallel — no dependencies between 01, 02, 03)*

- [x] 02-01-PLAN.md — Test scaffold: pytest.ini, conftest.py, 7 RED-phase test files (FEED-01 through FEED-05)
- [x] 02-02-PLAN.md — Core service infrastructure: Dockerfile, requirements.txt, config.py, status.py, deduplicator.py, opencti_client.py, feeds/base.py
- [x] 02-03-PLAN.md — Docker/env config: docker-compose.yml healthcheck + env vars, .env.example MALWAREBAZAAR_AUTH_KEY + THREATFOX_AUTH_KEY

**Wave 2** *(blocked on Wave 1 02-01 + 02-02; 04/05/06 parallel with each other)*

- [x] 02-04-PLAN.md — CSV feeds: URLhausFeed + FeodoFeed (FEED-01, FEED-02)
- [x] 02-05-PLAN.md — JSON POST feeds: MalwareBazaarFeed + ThreatFoxFeed (FEED-02)
- [x] 02-06-PLAN.md — SDK feed: OTXFeed with modified_since time window (FEED-03)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-07-PLAN.md — Wiring: normalizer.py (D-09 confidence formula), scheduler.py, main.py entry point (FEED-05, FEED-06)

**Wave 4** *(blocked on Wave 3 + 02-03)*

- [x] 02-08-PLAN.md — Integration checkpoint: docker build, live IOC verification in OpenCTI, dedup + schedule confirmation

---

### Phase 3: AI IOC Extraction

**Goal**: An analyst can submit a PDF file or a URL to the intel-extractor service and receive extracted IOCs — mapped to MITRE ATT&CK techniques where mentioned — inserted into OpenCTI as STIX objects, processed entirely by the local LLM.

**Depends on**: Phase 1

**Requirements**: AIEX-01, AIEX-02, AIEX-03, AIEX-04, AIEX-05

**Success Criteria** (what must be TRUE):

  1. `POST /extract` with a multi-page PDF threat report returns extracted IOCs (IPs, domains, hashes) visible in OpenCTI within seconds of job completion
  2. `POST /extract` with a URL successfully scrapes and extracts IOCs from the page content
  3. IOCs extracted from documents that mention ATT&CK technique names appear in OpenCTI linked to the corresponding `attack-pattern` objects (e.g. T1566 for phishing references)
  4. A document longer than 8K tokens (LLM context limit) is processed completely — no IOCs are silently dropped at chunk boundaries

**Plans**: 6/6 plans complete

Plans:

**Wave 0**

- [x] 03-01-PLAN.md — Test scaffold: pytest.ini, conftest, 5 RED test files (AIEX-01 through AIEX-05)

**Wave 1** *(parallel — no file conflicts)*

- [x] 03-02-PLAN.md — config.py (env vars) + parser.py (PDF + URL extraction)
- [x] 03-03-PLAN.md — opencti_client.py: copy Phase 2 base + add lookup_attack_pattern, create_report, create_relationship

**Wave 2** *(blocked on Wave 1)*

- [x] 03-04-PLAN.md — extractor.py: chunk_text, call_llm (D-03 fallback), build_stix_pattern, run_extraction pipeline

**Wave 3** *(blocked on Wave 2)*

- [x] 03-05-PLAN.md — main.py (FastAPI endpoints) + requirements.txt + Dockerfile + docker-compose healthcheck

**Wave 4** *(blocked on Wave 3)*

- [x] 03-06-PLAN.md — Integration checkpoint: docker build, live IOC + ATT&CK verification in OpenCTI

---

### Phase 4: Semantic Search Engine

**Goal**: An analyst can submit a natural-language query and receive ranked IOC results from the semantic-engine, with similarity scores, linking back to OpenCTI — without needing exact IOC values.

**Depends on**: Phase 1, Phase 2

**Requirements**: AISEM-01, AISEM-02, AISEM-03, AISEM-04

**Success Criteria** (what must be TRUE):

  1. All indicators present in OpenCTI are indexed as 768-dimensional embedding vectors in ChromaDB (confirmed via `GET /health` and index count)
  2. A natural-language query such as "malware with DNS tunneling toward Russian infrastructure" returns relevant IOC results ranked by similarity
  3. Each result includes a similarity score between 0.0 and 1.0
  4. Each result includes a direct URL to the corresponding object in OpenCTI

**Plans**: TBD

---

### Phase 5: Briefing Generator

**Goal**: A briefing-generator service produces a 200–300 word executive summary from live OpenCTI data covering a configurable time window, exportable as PDF, triggerable on demand.

**Depends on**: Phase 1, Phase 2

**Requirements**: AIBR-01, AIBR-02, AIBR-03, AIBR-04

**Success Criteria** (what must be TRUE):

  1. `POST /generate` with `period_hours=24` returns a 200–300 word professional executive summary covering new IOCs, active actors, campaigns, top ATT&CK techniques, and affected sectors
  2. The same endpoint accepts `period_hours=72` and returns a summary scoped to that window
  3. `GET /briefings/{id}/pdf` returns a downloadable PDF containing the briefing text
  4. A briefing can be triggered and retrieved without any command-line interaction (API call only)

**Plans**: TBD

---

### Phase 6: SOC Dashboard

**Goal**: A React frontend at `localhost:3000` unifies OpenCTI data, semantic search, and briefings into three analyst-facing views — Overview, Threat Hunt, and Briefings — making the full system demonstrable to a SOC client without opening any other UI.

**Depends on**: Phase 1, Phase 2, Phase 4, Phase 5

**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06

**Success Criteria** (what must be TRUE):

  1. Overview view displays feed health (last update time, IOC count, and status) for each configured feed and total IOC count for the last 24h
  2. Overview view displays the top 5 MITRE ATT&CK techniques observed across current intelligence
  3. Threat Hunt view accepts a natural-language query, calls semantic-engine, and displays ranked results with similarity scores — clicking a result opens the object in OpenCTI
  4. Briefings view lists all generated briefings and provides a working PDF download for each
  5. The dashboard is accessible at `localhost:3000` with no additional setup after `docker compose up -d`

**Plans**: TBD
**UI hint**: yes

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Platform Foundation | 3/4 | In Progress|  |
| 2. Feed Ingestion Pipeline | 8/8 | Complete   | 2026-06-25 |
| 3. AI IOC Extraction | 6/6 | Complete   | 2026-06-25 |
| 4. Semantic Search Engine | 0/? | Not started | - |
| 5. Briefing Generator | 0/? | Not started | - |
| 6. SOC Dashboard | 0/? | Not started | - |

---
*Roadmap created: 2026-06-23*
