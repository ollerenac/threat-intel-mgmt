# Phase 1: Platform Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-23
**Phase:** 1-Platform Foundation
**Areas discussed:** Compose startup scope, Env setup automation, MITRE import verification

---

## Compose startup scope

**Context:** docker-compose.yml already has all 13 services. Custom service build directories (./services/X) don't exist yet — running docker compose up without a solution would fail.

| Option | Description | Selected |
|--------|-------------|----------|
| Docker Compose profiles | Tag platform services with `profiles: [platform]`. Phase 1 runs `docker compose --profile platform up -d`. Each phase adds its profile. | ✓ |
| Stub Dockerfiles now | Create minimal Dockerfiles for all 5 custom services. docker compose up always works without flags. | |
| Separate compose files | Split into docker-compose.platform.yml + docker-compose.full.yml. | |

**User's choice:** Docker Compose profiles

**Notes:** User also asked to understand what the 13 services are before deciding. Walkthrough provided: 6 platform services (ES/Redis/RabbitMQ/MinIO/OpenCTI/connector-mitre) + 2 AI infrastructure (Ollama/ChromaDB) + 5 custom-built services (one per Phase 2–6). User confirmed progressive build-up via profiles is exactly the right pattern.

---

## Ollama/ChromaDB profile placement

| Option | Description | Selected |
|--------|-------------|----------|
| Include in `platform` profile | Ollama + ChromaDB start with Phase 1. init-models.sh runs immediately after Phase 1. | ✓ |
| Separate `ai` profile | Deferred to Phase 3 when first used. Saves ~2GB RAM in early phases. | |

**User's choice:** Include in `platform` profile

---

## Env setup automation

**Context:** Before any docker compose up, .env must exist with generated UUIDs for OPENCTI_ADMIN_TOKEN and CONNECTOR_MITRE_ID.

| Option | Description | Selected |
|--------|-------------|----------|
| scripts/setup-env.sh auto-generator | Script auto-generates UUIDs + passwords, copies .env.example, idempotent | ✓ |
| Makefile with make setup | Makefile target wraps generation | |
| Document manual steps only | 4-step manual process in README | |

**User's choice:** scripts/setup-env.sh auto-generator

**Notes:** User also chose to auto-generate RabbitMQ and MinIO passwords alongside UUIDs (full automation, not just UUIDs).

---

## MITRE import verification

**Context:** connector-mitre imports ~600+ ATT&CK objects on first run, takes 3–10 min. Success criteria require attack-patterns visible in OpenCTI.

| Option | Description | Selected |
|--------|-------------|----------|
| Polling verify script | scripts/verify-platform.sh polls GraphQL API for attack-pattern count + TAXII check | ✓ |
| Manual UI check | README documents: open OpenCTI, check Knowledge → Attack Patterns | |
| Document the wait, no verification | README says "wait 10 minutes" — no script | |

**User's choice:** Polling verify script

**Notes:** User chose to also check TAXII 2.1 endpoint in the same script (covers PLAT-04). Script output format agreed: progress lines `[N/10] OpenCTI up, ATT&CK objects: {count}` → `Platform ready. {N} ATT&CK patterns imported.` + `TAXII endpoint: OK` + `Phase 1 complete.`

---

## Claude's Discretion

- Script language: bash preferred, Python fallback acceptable for UUID generation
- OpenCTI GraphQL auth in verify script: read admin token from .env
- Error message formatting: clear, human-readable, actionable

## Deferred Ideas

None — discussion stayed within phase scope.
