# Phase 1: Platform Foundation - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Bring up the OpenCTI platform stack using Docker Compose profiles so the platform services start cleanly while later-phase custom services don't exist yet. Phase 1 delivers: all 8 infrastructure services healthy, MITRE ATT&CK framework fully imported, TAXII 2.1 endpoint responding, and a verified first-run experience via two helper scripts. No application code (Python services, React) is written in this phase.

Services in scope for Phase 1: `elasticsearch`, `redis`, `rabbitmq`, `minio`, `opencti`, `connector-mitre`, `ollama`, `chromadb` — all tagged `profiles: [platform]`.

</domain>

<decisions>
## Implementation Decisions

### D-1: Docker Compose Profiles (Compose startup scope)

- **D-01:** Use Docker Compose `profiles` to isolate service groups. Phase 1 only starts `profiles: [platform]` services — no stubs, no separate files.
- **D-02:** Profile map is fixed:
  - `platform` → elasticsearch, redis, rabbitmq, minio, opencti, connector-mitre, ollama, chromadb
  - `feeds` → feed-orchestrator (Phase 2)
  - `extract` → intel-extractor (Phase 3)
  - `semantic` → semantic-engine (Phase 4)
  - `briefings` → briefing-generator (Phase 5)
  - `dashboard` → soc-dashboard (Phase 6)
- **D-03:** Phase 1 startup command: `docker compose --profile platform up -d`. Full stack (all phases complete): `docker compose up -d`.
- **D-04:** Ollama and ChromaDB are included in the `platform` profile (not a separate `ai` profile) so `scripts/init-models.sh` can run immediately after Phase 1 completes.

### D-2: Environment Setup Automation

- **D-05:** Phase 1 delivers `scripts/setup-env.sh` — an auto-generator that:
  1. Checks if `.env` already exists (idempotent — exits early if so)
  2. Copies `.env.example` as base
  3. Generates UUIDs for `OPENCTI_ADMIN_TOKEN` and `CONNECTOR_MITRE_ID` using `uuidgen` (fallback: `python3 -c "import uuid; print(uuid.uuid4())"`)
  4. Auto-generates random passwords for `RABBITMQ_PASSWORD` and `MINIO_SECRET_KEY`
  5. Prints a summary of what was generated
- **D-06:** First-run sequence: `./scripts/setup-env.sh && docker compose --profile platform up -d`
- **D-07:** Script is idempotent — safe to run twice; will not overwrite an existing `.env`.

### D-3: Platform Verification

- **D-08:** Phase 1 delivers `scripts/verify-platform.sh` — a polling script that:
  1. Waits for OpenCTI to be reachable at `localhost:8080/health`
  2. Polls OpenCTI GraphQL API (`/graphql`) for `attackPatterns` count every 30s
  3. Exits success (0) when count > 100 attack-patterns
  4. Also verifies TAXII 2.1 endpoint: `GET localhost:8080/taxii2/root/collections/` returns a valid response
  5. Times out after 15 minutes with a non-zero exit and actionable error message
- **D-09:** Script covers all Phase 1 success criteria in one run (PLAT-01–04, DEPL-01).
- **D-10:** Script is human-run once after `docker compose --profile platform up -d` — not an automated health check.

### Claude's Discretion

- Script language for setup-env.sh and verify-platform.sh: bash is preferred for portability, but Python is acceptable for the UUID fallback.
- OpenCTI GraphQL authentication method for verify-platform.sh: use the admin token from `.env` (read it from the file in the script).
- Error message formatting in scripts: clear, human-readable, actionable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Design
- `docs/plans/2026-06-23-tim-system-design.md` — Full system design: component specs, API contracts, docker-compose structure, port assignments, and service descriptions. Section 7 covers deployment specifics.

### Planning Artifacts
- `.planning/ROADMAP.md` — Phase 1 success criteria (5 criteria), requirement list (PLAT-01–04, DEPL-01–04), phase dependencies
- `.planning/REQUIREMENTS.md` — Full requirement definitions for PLAT-01, PLAT-02, PLAT-03, PLAT-04, DEPL-01, DEPL-02, DEPL-03, DEPL-04

### Existing Deployment Files
- `docker-compose.yml` — Current state: all 13 services defined, **needs profile tags added** per D-02. Service dependencies and health-gate chain are already correct.
- `.env.example` — All required environment variables documented. `scripts/setup-env.sh` reads this as its template.
- `scripts/init-models.sh` — Existing script for pulling Ollama models (`llama3.2:3b` + `nomic-embed-text`). Runs after Phase 1 completes.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docker-compose.yml` — Health-gate dependency chain is already correct (ES → Redis/RabbitMQ/MinIO → OpenCTI → connector-mitre). Phase 1 only needs to add `profiles:` tags to services and add the two new scripts.
- `scripts/init-models.sh` — Existing Ollama model pull script. No changes needed in Phase 1.
- `.env.example` — Complete variable template. `setup-env.sh` reads it as its source.

### Established Patterns
- Health checks: all existing services already have `healthcheck:` blocks with appropriate intervals and start_periods. The new scripts should respect these (poll `/health` before querying GraphQL).
- Service restarts: all services use `restart: unless-stopped` — consistent.
- Memory limits: all services have `mem_limit` set — do not add services without one.

### Integration Points
- `connector-mitre` depends on `opencti: condition: service_healthy` — the verify script must wait for OpenCTI healthy before checking ATT&CK count.
- GPU: `ollama` uses `deploy.resources.reservations.devices` with `driver: nvidia`. If nvidia-container-toolkit is not installed, `docker compose --profile platform up -d` will fail on the ollama service. The verify script should detect this and give a clear error.

</code_context>

<specifics>
## Specific Ideas

- The `verify-platform.sh` output format the user approved: `[N/10] OpenCTI up, ATT&CK objects: {count}` progress lines, then `Platform ready. {N} ATT&CK patterns imported.` + `TAXII endpoint: OK` + `Phase 1 complete.`
- The `setup-env.sh` output format: print generated values summary after creation so the user can see what was set.
- Profile naming convention: lowercase, single-word profile names (`platform`, `feeds`, `extract`, `semantic`, `briefings`, `dashboard`).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Platform Foundation*
*Context gathered: 2026-06-23*
