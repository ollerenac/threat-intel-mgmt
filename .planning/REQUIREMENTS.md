# Requirements: TIM — Threat Intelligence Management System

**Defined:** 2026-06-23
**Core Value:** Ingest any threat source, search and correlate locally, brief stakeholders — no IOC leaves the network.

## v1 Requirements

### Platform

- [ ] **PLAT-01**: OpenCTI platform is deployed and reachable at localhost:8080
- [ ] **PLAT-02**: MITRE ATT&CK framework is pre-loaded in OpenCTI on first run
- [ ] **PLAT-03**: All platform services (ES, Redis, RabbitMQ, MinIO) start healthy via docker compose up
- [ ] **PLAT-04**: TAXII 2.1 endpoint is accessible and returns valid STIX bundles

### Feed Ingestion

- [x] **FEED-01**: Feed orchestrator downloads URLhaus feed and normalizes IOCs to STIX 2.1
- [x] **FEED-02**: Feed orchestrator downloads MalwareBazaar, ThreatFox, Feodo Tracker feeds
- [x] **FEED-03**: Feed orchestrator downloads AlienVault OTX feed (with API key)
- [x] **FEED-04**: IOCs from all feeds are deduplicated before insertion into OpenCTI
- [x] **FEED-05**: Each IOC has a confidence score (0-100) based on feed count, recency, and quality
- [x] **FEED-06**: Feeds run on schedule automatically (no manual trigger required)

### AI — IOC Extraction

- [ ] **AIEX-01**: intel-extractor accepts a PDF file and extracts IOCs via local LLM
- [ ] **AIEX-02**: intel-extractor accepts a URL and extracts IOCs from scraped content
- [ ] **AIEX-03**: Extracted IOCs are mapped to MITRE ATT&CK techniques where mentioned
- [ ] **AIEX-04**: Extraction result is inserted into OpenCTI as STIX objects
- [ ] **AIEX-05**: Long documents are chunked and processed without losing IOCs at boundaries

### AI — Semantic Search

- [ ] **AISEM-01**: semantic-engine indexes all indicators from OpenCTI as embedding vectors
- [ ] **AISEM-02**: Analyst can search with natural language query and receive ranked IOC results
- [ ] **AISEM-03**: Each result includes a similarity score (0.0–1.0)
- [ ] **AISEM-04**: Result links back to the corresponding object in OpenCTI

### AI — Briefings

- [ ] **AIBR-01**: briefing-generator produces a 200-300 word executive summary from OpenCTI data
- [ ] **AIBR-02**: Briefing covers last 24h or 72h period (configurable)
- [ ] **AIBR-03**: Briefing is available in the dashboard and exportable as PDF
- [ ] **AIBR-04**: Briefing can be triggered manually from the dashboard

### SOC Dashboard

- [ ] **DASH-01**: Overview view shows feed health (last update, IOC count, status per feed)
- [ ] **DASH-02**: Overview shows IOC count for last 24h and top 5 ATT&CK techniques
- [ ] **DASH-03**: Threat Hunt view accepts natural language query and displays semantic results
- [ ] **DASH-04**: Threat Hunt results link to OpenCTI object on click
- [ ] **DASH-05**: Briefings view lists generated briefings and allows PDF download
- [ ] **DASH-06**: Dashboard is accessible at localhost:3000

### Deployment

- [ ] **DEPL-01**: Full stack starts with `docker compose up -d` from project root
- [ ] **DEPL-02**: `.env.example` documents all required environment variables
- [ ] **DEPL-03**: `scripts/init-models.sh` downloads Ollama models after first start
- [ ] **DEPL-04**: All services have health checks; unhealthy services are visible in `docker compose ps`

## v2 Requirements

### Enrichment

- **ENRCH-01**: Optional local enrichment from offline threat DB (no external call)
- **ENRCH-02**: Geolocation lookup from local MaxMind database

### Case Management

- **CASE-01**: TheHive integration for incident case management
- **CASE-02**: Cortex analyzers for observable enrichment

### Production Hardening

- **HARD-01**: TLS termination for all exposed services
- **HARD-02**: Role-based access control in dashboard
- **HARD-03**: Audit logging for all analyst actions

## Out of Scope

| Feature | Reason |
|---------|--------|
| External enrichment APIs (VirusTotal, AbuseIPDB) | Data sovereignty — no IOC leaves network |
| Multi-user authentication | Demo on local network; v2 |
| TheHive/Cortex | Scope creep for v1 demo |
| Paid threat feeds | Free feeds sufficient for demo |
| Mobile/responsive dashboard | Demo on desktop |
| Demo scenario seed data (Section 8) | Post-implementation content |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLAT-01 | Phase 1 | Pending |
| PLAT-02 | Phase 1 | Pending |
| PLAT-03 | Phase 1 | Pending |
| PLAT-04 | Phase 1 | Pending |
| FEED-01 | Phase 2 | Complete |
| FEED-02 | Phase 2 | Complete |
| FEED-03 | Phase 2 | Complete |
| FEED-04 | Phase 2 | Complete |
| FEED-05 | Phase 2 | Complete |
| FEED-06 | Phase 2 | Complete |
| AIEX-01 | Phase 3 | Pending |
| AIEX-02 | Phase 3 | Pending |
| AIEX-03 | Phase 3 | Pending |
| AIEX-04 | Phase 3 | Pending |
| AIEX-05 | Phase 3 | Pending |
| AISEM-01 | Phase 4 | Pending |
| AISEM-02 | Phase 4 | Pending |
| AISEM-03 | Phase 4 | Pending |
| AISEM-04 | Phase 4 | Pending |
| AIBR-01 | Phase 5 | Pending |
| AIBR-02 | Phase 5 | Pending |
| AIBR-03 | Phase 5 | Pending |
| AIBR-04 | Phase 5 | Pending |
| DASH-01 | Phase 6 | Pending |
| DASH-02 | Phase 6 | Pending |
| DASH-03 | Phase 6 | Pending |
| DASH-04 | Phase 6 | Pending |
| DASH-05 | Phase 6 | Pending |
| DASH-06 | Phase 6 | Pending |
| DEPL-01 | Phase 1 | Pending |
| DEPL-02 | Phase 1 | Pending |
| DEPL-03 | Phase 1 | Pending |
| DEPL-04 | Phase 1 | Pending |

**Coverage:**

- v1 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-23*
*Last updated: 2026-06-23 after initial definition*
