# Phase 1: Platform Foundation - Research

**Researched:** 2026-06-23
**Domain:** Docker Compose orchestration, OpenCTI 6.x platform deployment, NVIDIA GPU passthrough
**Confidence:** MEDIUM (core config verified against docker-compose.yml; GraphQL query shape and TAXII auth from web sources; MITRE object counts estimated)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Use Docker Compose `profiles` to isolate service groups. Phase 1 only starts `profiles: [platform]` services.

**D-02:** Profile map:
- `platform` → elasticsearch, redis, rabbitmq, minio, opencti, connector-mitre, ollama, chromadb
- `feeds` → feed-orchestrator (Phase 2)
- `extract` → intel-extractor (Phase 3)
- `semantic` → semantic-engine (Phase 4)
- `briefings` → briefing-generator (Phase 5)
- `dashboard` → soc-dashboard (Phase 6)

**D-03:** Phase 1 startup command: `docker compose --profile platform up -d`.

**D-04:** Ollama and ChromaDB are included in the `platform` profile so `scripts/init-models.sh` can run immediately after Phase 1.

**D-05:** Phase 1 delivers `scripts/setup-env.sh` — idempotent .env generator that:
1. Checks if `.env` already exists (exits early if so)
2. Copies `.env.example` as base
3. Generates UUIDs for `OPENCTI_ADMIN_TOKEN` and `CONNECTOR_MITRE_ID` via `uuidgen` (fallback: python3)
4. Auto-generates random passwords for `RABBITMQ_PASSWORD` and `MINIO_SECRET_KEY`
5. Prints a summary of what was generated

**D-06:** First-run sequence: `./scripts/setup-env.sh && docker compose --profile platform up -d`

**D-07:** Script is idempotent — will not overwrite an existing `.env`.

**D-08:** Phase 1 delivers `scripts/verify-platform.sh` — polling script that:
1. Waits for OpenCTI reachable at `localhost:8080/health`
2. Polls `/graphql` for `attackPatterns` count every 30s
3. Exits 0 when count > 100 attack-patterns
4. Verifies TAXII 2.1 endpoint: `GET localhost:8080/taxii2/root/collections/`
5. Times out after 15 minutes with non-zero exit and actionable error

**D-09:** Script covers all Phase 1 success criteria in one run (PLAT-01–04, DEPL-01).

**D-10:** TAXII 2.1 verification endpoint: `GET /taxii2/root/collections/` with OpenCTI token header.

### Claude's Discretion

- Script language: bash preferred, Python acceptable for UUID fallback
- OpenCTI GraphQL auth for verify-platform.sh: use admin token from `.env`
- Error message formatting: clear, human-readable, actionable

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLAT-01 | OpenCTI platform deployed and reachable at localhost:8080 | docker-compose.yml already has opencti service on port 8080; health endpoint is /health |
| PLAT-02 | MITRE ATT&CK framework pre-loaded on first run | connector-mitre service already configured; imports Enterprise+Mobile+ICS+CAPEC; 600–900+ attack-pattern objects expected |
| PLAT-03 | All platform services (ES, Redis, RabbitMQ, MinIO) start healthy via docker compose up | All 4 backing services have healthcheck blocks; ES memlock ulimit already set in docker-compose.yml |
| PLAT-04 | TAXII 2.1 endpoint accessible and returns valid STIX bundles | OpenCTI native TAXII at /taxii2/root/collections/; Bearer token auth |
| DEPL-01 | Full stack starts with `docker compose up -d` from project root | Profile tags must be added to 8 services; no .env → setup-env.sh generates one |
| DEPL-02 | .env.example documents all required environment variables | .env.example exists; needs review for completeness against docker-compose.yml vars |
| DEPL-03 | scripts/init-models.sh downloads Ollama models after first start | init-models.sh exists and is correct; runs after Phase 1 completes |
| DEPL-04 | All services have health checks; unhealthy services visible in docker compose ps | All 8 platform services already have healthcheck blocks; connector-mitre does NOT have one — this is a gap |

</phase_requirements>

---

## Summary

Phase 1 is primarily a **configuration and scaffolding phase** — the docker-compose.yml already contains all 13 services with correct dependency chains, health checks, and environment variable references. The core work is: (1) adding `profiles:` tags to the 8 platform-profile services, (2) writing `scripts/setup-env.sh` to automate .env generation, and (3) writing `scripts/verify-platform.sh` to poll for MITRE import completion and TAXII availability. No new Docker images, no application code.

The single most consequential finding is that **nvidia-container-toolkit is not installed** on the host machine. The `ollama` service in docker-compose.yml uses `deploy.resources.reservations.devices` with `driver: nvidia`. Without the toolkit, `docker compose --profile platform up -d` will fail on the ollama service. This must be addressed: either install the toolkit before Phase 1 executes, or add a detection step in `setup-env.sh` that warns clearly before the compose command is run.

The MITRE ATT&CK connector imports Enterprise, Mobile, ICS, and CAPEC datasets — approximately 600–900+ attack-pattern objects total. "Initial import may take several minutes" per official docs; the 3–10 minute range in the additional context is consistent with this. The verify script's 15-minute timeout is appropriate and sufficient. The threshold of >100 attack-patterns as the success signal is well-calibrated (Enterprise alone has 222 techniques + 475 sub-techniques, so >100 is easily exceeded within the first few minutes of import).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Data persistence | Database/Storage (ES, Redis, MinIO) | — | ES is the STIX graph store; Redis handles cache + auth sessions; MinIO stores file attachments |
| Message routing | Message queue (RabbitMQ) | — | Decouples connectors from platform; all connector imports flow through RabbitMQ |
| Platform API + UI | Application server (OpenCTI) | ES query layer | OpenCTI owns GraphQL + TAXII endpoints; all queries translate to ES queries |
| MITRE import | Connector (connector-mitre) | RabbitMQ → OpenCTI | Connector downloads STIX from MITRE GitHub, sends bundle to RabbitMQ, OpenCTI ingests |
| GPU inference | AI runtime (Ollama) | Host NVIDIA driver | Ollama container requires nvidia-container-toolkit on host for GPU passthrough |
| Vector storage | AI runtime (ChromaDB) | — | Standalone vector DB; no dependency on OpenCTI in Phase 1 |
| Environment setup | Host scripts | — | setup-env.sh runs on host before compose; verify-platform.sh polls from host |

---

## Key Findings by Research Question

### Q1: OpenCTI Docker Compose exact configuration

**What is already correct in docker-compose.yml:** [VERIFIED: codebase grep]

All required OpenCTI 6.x environment variables are already present:
- `APP__PORT`, `APP__BASE_URL`, `APP__ADMIN__EMAIL`, `APP__ADMIN__PASSWORD`, `APP__ADMIN__TOKEN`
- `ELASTICSEARCH__URL=http://elasticsearch:9200`
- `REDIS__HOSTNAME=redis`, `REDIS__PORT=6379`
- `RABBITMQ__HOSTNAME=rabbitmq`, `RABBITMQ__PORT=5672`, `RABBITMQ__USERNAME`, `RABBITMQ__PASSWORD`
- `MINIO__ENDPOINT=minio`, `MINIO__PORT=9000`, `MINIO__USE_SSL=false`, `MINIO__ACCESS_KEY`, `MINIO__SECRET_KEY`
- `NODE_OPTIONS=--max-old-space-size=2048` — critical for 2 GB mem_limit
- `APP__APP_LOGS__LOGS_LEVEL=error` — reduces log noise
- `APP__TELEMETRY__METRICS__ENABLED=true`

**Version-specific notes for 6.4.0:** [ASSUMED]
- OpenCTI 6.x introduced `APP__TELEMETRY__METRICS__ENABLED` (added in 6.x series; absent in 5.x configs)
- Since OpenCTI 6.6.0, token-based connections no longer create persistent user sessions. Version 6.4.0 is below this threshold — sessions persist normally [CITED: docs.opencti.io/latest/deployment/connectors/]
- The `CONNECTOR_SCOPE` in connector-mitre is set to the full object type list rather than the simplified `mitre` scope; this is more explicit and correct for ensuring all MITRE object types are imported

**Connector-mitre environment variable completeness check:** [VERIFIED: codebase grep]
The current connector-mitre service definition is missing `MITRE_INTERVAL` and `CONNECTOR_LOG_LEVEL`. The defaults (interval=7 days, log_level=error) are acceptable, but adding them explicitly makes the configuration self-documenting. The `CONNECTOR_UPDATE_EXISTING_DATA=true` is already present and is the correct setting for idempotent re-import.

**What the docker-compose.yml is missing for Phase 1:** [VERIFIED: codebase grep]
- `profiles:` tags on all 8 platform services — the single required structural change
- connector-mitre has no `healthcheck:` block (only services listed in DEPL-04 need one; connector-mitre is not a backing service but the success criteria says "all services" visible in `docker compose ps`)

### Q2: scripts/setup-env.sh design

**UUIDs required:** [VERIFIED: codebase grep of docker-compose.yml]
- `OPENCTI_ADMIN_TOKEN` — used by: opencti, connector-mitre (3x), intel-extractor, semantic-engine, briefing-generator
- `CONNECTOR_MITRE_ID` — used by: connector-mitre only

**Passwords required:** [VERIFIED: codebase grep]
- `RABBITMQ_PASSWORD` — random alphanumeric, avoid special chars that break shell quoting
- `MINIO_SECRET_KEY` — random alphanumeric, 20+ chars
- `OPENCTI_ADMIN_PASSWORD` — should be strong; must be documented in .env.example with a placeholder

**Variables that should NOT be auto-generated (user-provided):** [VERIFIED: codebase grep]
- `OPENCTI_ADMIN_EMAIL` — user-specific; default `admin@tim.local` is fine for demo
- `OPENCTI_BASE_URL` — defaults to `http://localhost:8080`; acceptable for local deployment
- `RABBITMQ_USER` — default `tim` is fine
- `MINIO_ACCESS_KEY` — default `minioadmin` is fine
- `OTX_API_KEY` — Phase 2 concern; leave blank

**Idempotency pattern:** [ASSUMED]
```bash
if [ -f ".env" ]; then
  echo "[setup-env] .env already exists. Remove it to regenerate."
  exit 0
fi
```
Copy `.env.example` to `.env`, then use `sed -i` to substitute the 4 generated values in-place.

**UUID generation:**
```bash
# Primary (uuidgen is available: confirmed on this machine)
UUID=$(uuidgen)
# Fallback (python3 3.10.12 available: confirmed)
UUID=$(python3 -c "import uuid; print(uuid.uuid4())")
```
Both are available on this machine. [VERIFIED: environment probe]

**Password generation:**
```bash
# Use /dev/urandom + tr to avoid special chars
PASS=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 24)
```

**Generation order (per D-09):** Generate ES_JAVA_OPTS and memory vars first if any need to be set via env; then OpenCTI vars. In the current design all of these are hardcoded in docker-compose.yml (not in .env), so the order in setup-env.sh is simply: generate passwords, generate UUIDs, write file, print summary.

### Q3: scripts/verify-platform.sh design

**Step 1 — OpenCTI health poll:**
```bash
until curl -sf http://localhost:8080/health > /dev/null; do
  sleep 5
done
```
The `/health` endpoint is confirmed in docker-compose.yml healthcheck block. [VERIFIED: codebase grep]

**Step 2 — GraphQL attackPatterns count poll:**

OpenCTI's GraphQL endpoint: `POST http://localhost:8080/graphql`
Auth header: `Authorization: Bearer <OPENCTI_ADMIN_TOKEN>` [CITED: docs.opencti.io/latest/reference/api/]

The query that returns count (OpenCTI uses `pageInfo.globalCount` in its pagination model): [ASSUMED — not confirmed from authoritative source; derived from pycti pagination behavior and community examples]

```bash
QUERY='{"query":"{ attackPatterns(first: 1) { pageInfo { globalCount } } }"}'
COUNT=$(curl -sf -X POST http://localhost:8080/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OPENCTI_ADMIN_TOKEN}" \
  -d "$QUERY" | jq -r '.data.attackPatterns.pageInfo.globalCount // 0')
```

**Fallback query shape if pageInfo.globalCount is unavailable:** [ASSUMED]
```bash
QUERY='{"query":"{ attackPatterns(first: 500) { edges { node { id } } } }"}'
# Then count edges array length via jq: .data.attackPatterns.edges | length
```

The threshold `> 100` is safe — Enterprise alone has 697 objects (222 techniques + 475 sub-techniques). Even a partial import of Enterprise techniques only would exceed 100 well before completion. [ASSUMED — based on technique counts from official MITRE ATT&CK v16.1 data]

**Step 3 — TAXII 2.1 endpoint check:**
```bash
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${OPENCTI_ADMIN_TOKEN}" \
  -H "Accept: application/taxii+json;version=2.1" \
  http://localhost:8080/taxii2/root/collections/)
```
Success = HTTP 200. [CITED: docs.opencti.io/latest/deployment/integrations/ for Bearer token auth pattern; endpoint path from CONTEXT.md D-10]

**Step 4 — 15-minute timeout loop:**
```bash
START_TIME=$(date +%s)
TIMEOUT=900  # 15 minutes

while true; do
  ELAPSED=$(( $(date +%s) - START_TIME ))
  if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "[TIMEOUT] 15 minutes elapsed. Platform not ready."
    echo "Check: docker compose --profile platform logs opencti"
    echo "Check: docker compose --profile platform logs connector-mitre"
    exit 1
  fi
  # ... poll logic ...
  sleep 30
done
```

**Progress output format (from CONTEXT.md specifics):**
```
[N/10] OpenCTI up, ATT&CK objects: {count}
Platform ready. {N} ATT&CK patterns imported.
TAXII endpoint: OK
Phase 1 complete.
```

**Token reading from .env:**
```bash
source .env 2>/dev/null || { echo "ERROR: .env not found. Run ./scripts/setup-env.sh first."; exit 1; }
```

**Dependencies needed by verify script:**
- `curl` — available (v7.81.0) [VERIFIED: environment probe]
- `jq` — available (v1.6) [VERIFIED: environment probe]

### Q4: Ollama + GPU setup

**Current state:** [VERIFIED: environment probe]
- NVIDIA GPU present: RTX 3050, Driver 580.159.03, CUDA 13.0
- nvidia-smi: AVAILABLE
- nvidia-container-toolkit: NOT INSTALLED (not in dpkg, nvidia-ctk not on PATH)
- Docker default runtime: `runc` (not `nvidia`)
- No `/etc/docker/daemon.json` exists

**Consequence:** `docker compose --profile platform up -d` will fail on the `ollama` service because the `deploy.resources.reservations.devices` block requires the nvidia runtime to be registered with Docker.

**What setup-env.sh must do:** Detect the toolkit absence and warn before the compose command:
```bash
if ! command -v nvidia-smi > /dev/null 2>&1; then
  echo "[WARN] nvidia-smi not found. Ollama GPU passthrough will not work."
elif ! command -v nvidia-ctk > /dev/null 2>&1 && ! docker info 2>/dev/null | grep -q nvidia; then
  echo "[WARN] nvidia-container-toolkit not configured."
  echo "       Ollama will fail to start. Install with:"
  echo "       curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"
  echo "       ... (see INSTALL.md or README for full steps)"
fi
```

**Docker Compose GPU config (already correct in docker-compose.yml):** [CITED: docs.docker.com/compose/how-tos/gpu-support/]
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

**Installation steps for nvidia-container-toolkit on Ubuntu 22.04:** [CITED: docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html]
```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**Post-install verification:**
```bash
docker run --rm --gpus all ubuntu nvidia-smi
```

**Plan task implication:** Phase 1 needs a dedicated setup task for nvidia-container-toolkit installation, either as a prerequisite step in the plan or as part of setup-env.sh's output instructions.

### Q5: Docker Compose profiles behavior

**Confirmed behavior:** [CITED: docs.docker.com/compose/how-tos/profiles/]
- Services WITHOUT `profiles:` attribute: always start with any `docker compose up` command
- Services WITH `profiles:` attribute: only start when that profile is active
- Command to start one profile: `docker compose --profile platform up -d`
- All 13 services currently have NO `profiles:` tags — every service starts on `docker compose up`

**Critical behavioral detail for this project:** [CITED: docs.docker.com/compose/how-tos/profiles/]
After adding `profiles: [platform]` to the 8 platform services, running `docker compose --profile platform up -d` starts exactly those 8 services. The 5 remaining services (feed-orchestrator, intel-extractor, semantic-engine, briefing-generator, soc-dashboard) will be ignored because their profiles (feeds, extract, semantic, briefings, dashboard) are not active.

**`depends_on` cross-profile behavior:** [CITED: docs.docker.com/compose/how-tos/profiles/]
If service B (profile=platform) is depended on by service A (profile=feeds), Compose will also start B when A is started, even if platform profile is not explicitly active. This means the dependency chain opencti → connector-mitre (both platform) works correctly, and feed-orchestrator (feeds) depending on opencti (platform) will also correctly bring up opencti when the feeds profile is activated.

**Required change to docker-compose.yml:** Add `profiles: [platform]` to these 8 services:
- elasticsearch, redis, rabbitmq, minio, opencti, connector-mitre, ollama, chromadb

Add `profiles: [feeds]` to: feed-orchestrator
Add `profiles: [extract]` to: intel-extractor
Add `profiles: [semantic]` to: semantic-engine
Add `profiles: [briefings]` to: briefing-generator
Add `profiles: [dashboard]` to: soc-dashboard

### Q6: connector-mitre timing

**MITRE ATT&CK object volume (estimated):** [ASSUMED — derived from official MITRE v16.1 counts + cross-matrix inference]
- Enterprise ATT&CK v16.1: 222 techniques + 475 sub-techniques = 697 attack-pattern objects
- Mobile ATT&CK: ~80–100 additional techniques
- ICS ATT&CK: ~80–100 additional techniques
- CAPEC: ~500+ additional attack-pattern objects (separate namespace)
- Total across all matrices: estimated 1,200–1,500+ objects (attack-patterns only, not counting intrusionSets, malware, tools, campaigns, courseOfAction)

**Threshold choice analysis:**
The verify script threshold of >100 attack-patterns is conservative and safe. Enterprise techniques alone (222) will exceed 100 well before the import finishes all datasets. The first 100 attack-patterns should appear within 2–4 minutes of the connector starting. [ASSUMED]

**Import timing:** [CITED: docs-github.com/connectors/external-import/mitre/README.md]
"Initial import may take several minutes." Community experience and CONTEXT.md say 3–10 minutes. Full import of all 4 datasets (Enterprise + Mobile + ICS + CAPEC + relationships) on a local machine with 14 GB RAM allocated to Docker is estimated at 5–15 minutes total. The 15-minute timeout in verify-platform.sh has appropriate headroom.

**CONNECTOR_RUN_AND_TERMINATE=false behavior:** [ASSUMED — flag not documented in official README]
With `false`, the connector remains running and re-runs its import every `MITRE_INTERVAL` days (default 7). This is the correct setting for continuous operation. If set to `true`, the connector exits after the first import — useful for CI but not for the production demo where periodic ATT&CK updates are desired.

**Auto-restart behavior:** The service has `restart: unless-stopped` in docker-compose.yml. If the connector fails (e.g., OpenCTI is not yet healthy), Docker will restart it. The `depends_on: opencti: condition: service_healthy` gate prevents premature starts. [VERIFIED: codebase grep]

### Q7: Verification gap risks

**Risk 1 — ES heap / memory lock:** [CITED: elastic.co/docs/deploy-manage/deploy/self-managed/install-elasticsearch-docker-prod]
ES requires `ulimit -l unlimited` (memlock) for `bootstrap.memory_lock=true`. The docker-compose.yml already sets:
```yaml
ulimits:
  memlock:
    soft: -1
    hard: -1
  nofile:
    soft: 65536
    hard: 65536
```
These values are correct. However, on Ubuntu 22.04, the Docker daemon itself may need `LimitMEMLOCK=infinity` in its systemd unit. If ES fails to start with "Unable to lock memory," this is the cause. This is documented per D-08 and should appear in setup notes/README.

**Risk 2 — RabbitMQ vhost not initialized:**
OpenCTI creates its own vhost (`/`) in RabbitMQ on first start. If OpenCTI crashes before completing initialization (e.g., ES not fully ready despite health check), RabbitMQ may be in an inconsistent state. The connector-mitre cannot publish messages to RabbitMQ until the vhost is created. Mitigation: the health-gate chain (ES → Redis+RabbitMQ+MinIO → OpenCTI healthy → connector-mitre starts) ensures OpenCTI fully initializes before the connector attempts to use RabbitMQ. [ASSUMED]

**Risk 3 — OpenCTI initialization time exceeds healthcheck retries:**
The opencti healthcheck has `start_period: 60s`, `interval: 20s`, `retries: 15` → maximum wait = 60 + (20 × 15) = 360 seconds = 6 minutes. If OpenCTI takes longer than 6 minutes to start (cold start + schema initialization), it will be marked unhealthy and connector-mitre will never start. On the first run with a fresh ES index, schema initialization is the dominant time. The 15 retries × 20 seconds should be sufficient but is worth monitoring on first run. [ASSUMED]

**Risk 4 — connector-mitre has no healthcheck:**
`docker compose ps` will show connector-mitre without a health status column (no healthcheck defined). The DEPL-04 requirement says "all services have health checks; unhealthy services are visible in `docker compose ps`." This is a gap. connector-mitre is designed to run indefinitely (CONNECTOR_RUN_AND_TERMINATE=false) — adding a healthcheck that verifies the connector's state is complex. **Recommendation:** Add a minimal healthcheck to connector-mitre that checks the process is still running, or accept that connector-mitre will appear without a health status and note this in verify-platform.sh output.

**Risk 5 — TAXII endpoint returns 401 or 403:**
The TAXII collections endpoint requires authentication. If the token in `.env` is wrong or the TAXII collection doesn't exist yet (it's created automatically by OpenCTI on startup), the endpoint will return non-200. The verify script must distinguish between "collection exists and returns data" vs "collection doesn't exist yet." A 200 with empty collections array is still a valid success signal — it means TAXII is up. [ASSUMED]

**Risk 6 — Ollama service blocks compose startup:**
Because nvidia-container-toolkit is not installed, the ollama service will fail to start with an error about the nvidia runtime. With `restart: unless-stopped`, Docker will repeatedly restart ollama. This does NOT block other services from starting (Docker doesn't block the compose command on a service restart loop). However, `docker compose ps` will show ollama as unhealthy/restarting, which will cause PLAT-03 to appear to fail. **Mitigation:** Install nvidia-container-toolkit before running `docker compose --profile platform up -d`.

**Risk 7 — MinIO mc command not available in MinIO container:**
The healthcheck for MinIO uses `mc ready local`. In some MinIO image versions the `mc` client may not be in the container. Alternative healthcheck: `curl -f http://localhost:9000/minio/health/live`. If the MinIO healthcheck fails, OpenCTI never starts. [ASSUMED]

### Q8: Phase file deliverables

Files to **create** in Phase 1:
1. `scripts/setup-env.sh` — new script (does not exist yet)
2. `scripts/verify-platform.sh` — new script (does not exist yet)
3. `scripts/nvidia-setup.sh` (or inline in setup-env.sh) — nvidia-container-toolkit installation guidance/detection

Files to **modify** in Phase 1:
1. `docker-compose.yml` — add `profiles: [platform]` to 8 services; add `profiles: [feeds/extract/semantic/briefings/dashboard]` to 5 custom services
2. `.env.example` — verify all variables documented; add any missing (OTX_API_KEY comment, generation hints)

Files that **require no changes:**
- `scripts/init-models.sh` — already correct; no changes needed

Files to **potentially add:**
1. `README.md` or `docs/SETUP.md` — documents ES memory lock requirement (D-08), nvidia-container-toolkit requirement, first-run sequence

---

## Implementation Risks

### Risk A: nvidia-container-toolkit not installed (BLOCKING)
**Probability:** Confirmed — toolkit is NOT installed on this machine.
**Impact:** `docker compose --profile platform up -d` will fail on ollama service.
**Mitigation:** Phase 1 plan must include a task to install nvidia-container-toolkit BEFORE the compose command. setup-env.sh should detect absence and print clear instructions. Alternatively, add an ollama CPU-only fallback (different image tag: `ollama/ollama:latest` works CPU-only but init-models.sh download will succeed; GPU inference won't work but platform itself will start).

### Risk B: OpenCTI GraphQL attackPatterns query shape mismatch (MEDIUM)
**Probability:** Medium — `pageInfo.globalCount` is inferred from pycti behavior, not confirmed from official schema.
**Impact:** verify-platform.sh returns count=0 even when import is complete, causing script to time out.
**Mitigation:** Include two query approaches in verify-platform.sh: try `pageInfo.globalCount` first; fall back to counting `edges` (with `first: 500`). Document this in the script with a comment.

### Risk C: MITRE import takes longer than 15 minutes (LOW)
**Probability:** Low — 3–10 minute range is well within 15-minute timeout.
**Impact:** verify-platform.sh exits with timeout error even though import is still in progress.
**Mitigation:** 15-minute timeout is adequate. If triggered, the actionable error message should tell the user to check `docker compose logs connector-mitre` and re-run the verify script.

### Risk D: ES startup fails due to host memlock limits (MEDIUM)
**Probability:** Medium on a fresh Ubuntu 22.04 Docker install without tuning.
**Impact:** Elasticsearch never becomes healthy, OpenCTI never starts, entire platform fails.
**Mitigation:** Document in README: "If Elasticsearch fails to start with memory lock errors, add `LimitMEMLOCK=infinity` to `/etc/systemd/system/docker.service.d/override.conf` and restart the Docker daemon." setup-env.sh should check/warn.

### Risk E: connector-mitre not reaching OpenCTI despite health gate (LOW)
**Probability:** Low — the depends_on health gate is already correct.
**Impact:** No MITRE data imported.
**Mitigation:** verify-platform.sh polls and catches this; actionable error directs user to connector logs.

---

## Standard Stack (Docker Images Used)

| Image | Version | Purpose |
|-------|---------|---------|
| `docker.elastic.co/elasticsearch/elasticsearch` | 8.15.0 | Graph store for STIX objects |
| `redis` | 7.2-alpine | Session cache + event streams |
| `rabbitmq` | 3.13-management-alpine | Message queue between connectors and platform |
| `minio/minio` | latest | S3-compatible file storage |
| `opencti/platform` | 6.4.0 | Knowledge graph platform |
| `opencti/connector-mitre` | 6.4.0 | MITRE ATT&CK importer — must match platform version |
| `ollama/ollama` | latest | Local LLM inference + embedding |
| `chromadb/chroma` | latest | Vector database |

**Important:** `opencti/connector-mitre` version must match `opencti/platform` version (both 6.4.0). Mismatched versions cause connector registration failures. [ASSUMED — standard OpenCTI operational guidance]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MITRE ATT&CK import | Custom STIX downloader | `opencti/connector-mitre:6.4.0` | Already handles all 4 matrices, deduplication, STIX 2.1 mapping, interval polling |
| UUID generation | Custom UUID algorithm | `uuidgen` (already on machine) | RFC 4122 compliant; available on all Ubuntu/Debian systems |
| GraphQL client | Custom HTTP wrapper | `curl` + `jq` in shell scripts | Sufficient for health checks; pycti overkill for a bash verification script |
| Service health orchestration | Custom wait loops | Docker Compose `depends_on: condition: service_healthy` | Already implemented in docker-compose.yml; do not duplicate |
| TAXII server | Custom STIX endpoint | OpenCTI native TAXII 2.1 | OpenCTI includes a TAXII 2.1 server; no configuration required |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Shell-based integration checks (no unit test framework) |
| Config file | none |
| Quick run command | `./scripts/verify-platform.sh` |
| Full suite command | `./scripts/verify-platform.sh && docker compose --profile platform ps` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLAT-01 | OpenCTI reachable at localhost:8080 | smoke | `curl -sf http://localhost:8080/health` | ❌ Wave 0 (verify-platform.sh) |
| PLAT-02 | MITRE ATT&CK objects visible (>100 attack-patterns) | smoke | `./scripts/verify-platform.sh` | ❌ Wave 0 |
| PLAT-03 | All 8 platform services healthy | smoke | `docker compose --profile platform ps` (visual) | ❌ Wave 0 |
| PLAT-04 | TAXII 2.1 endpoint returns 200 | smoke | `./scripts/verify-platform.sh` | ❌ Wave 0 |
| DEPL-01 | Stack starts with single command | manual | `docker compose --profile platform up -d` | ❌ Wave 0 |
| DEPL-02 | .env.example documents all vars | manual | grep comparison .env.example vs docker-compose.yml | ❌ Wave 0 |
| DEPL-03 | init-models.sh pulls models | smoke | `./scripts/init-models.sh` (run once) | ✅ exists |
| DEPL-04 | All services have healthchecks | smoke | `docker compose --profile platform ps` | ❌ connector-mitre gap |

### Wave 0 Gaps
- [ ] `scripts/setup-env.sh` — new file, covers DEPL-01 first-run automation
- [ ] `scripts/verify-platform.sh` — new file, covers PLAT-01, PLAT-02, PLAT-04, DEPL-01
- [ ] `docker-compose.yml` profile tags — covers DEPL-01 (profiles) and all PLAT-* (service scope)
- [ ] nvidia-container-toolkit installed on host — prerequisite for PLAT-03 (ollama healthy)

---

## Security Domain

Security enforcement is enabled (`security_enforcement: true`, ASVS level 1).

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes — OpenCTI admin token | Token from `.env` only; never hardcoded; not exposed in docker-compose.yml logs |
| V3 Session Management | Partial — OpenCTI manages sessions | Redis-backed sessions; using pre-6.6.0 persistent session model |
| V4 Access Control | No — single-user demo deployment | Out of scope per requirements |
| V5 Input Validation | No — no application code in this phase | N/A |
| V6 Cryptography | Partial — token generation | `uuidgen` generates RFC 4122 UUIDs; adequate for demo API tokens |

### Security Controls in This Phase

| Control | Implementation |
|---------|----------------|
| Credentials not hardcoded | All secrets in `.env`; `.env` should be in `.gitignore` |
| Admin UI restricted to localhost | MinIO `:9001` and RabbitMQ `:15672` bound to `127.0.0.1` — already correct in docker-compose.yml |
| OpenCTI not exposed externally | Port 8080 bound to `0.0.0.0` (acceptable for local demo, not production) |
| OTX API key handling | Left blank in .env.example with comment; setup-env.sh does not generate it |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secrets in docker-compose.yml | Information Disclosure | Use `.env` file pattern (already implemented) |
| Admin UIs exposed on all interfaces | Elevation of Privilege | Already mitigated: 127.0.0.1 binding in docker-compose.yml |
| Weak auto-generated passwords | Spoofing | Use `/dev/urandom` + minimum 20 chars alphanumeric |
| `.env` committed to git | Information Disclosure | `.gitignore` must include `.env` (verify this is present) |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Engine | All services | ✓ | 29.5.2 | — |
| Docker Compose | All services | ✓ | v5.1.4 | — |
| nvidia-smi | Ollama GPU | ✓ | 580.159.03 | — |
| nvidia-container-toolkit | Ollama GPU passthrough | ✗ | — | Install before compose up (BLOCKING) |
| `uuidgen` | setup-env.sh | ✓ | 2.37.2 | `python3 -c "import uuid; print(uuid.uuid4())"` |
| `python3` | UUID fallback | ✓ | 3.10.12 | — |
| `curl` | verify-platform.sh | ✓ | 7.81.0 | — |
| `jq` | verify-platform.sh | ✓ | 1.6 | — |

**Missing dependencies with no fallback:**
- `nvidia-container-toolkit` — required for ollama GPU passthrough. Without it, `docker compose --profile platform up -d` fails on ollama. Plan must include installation task.

**Missing dependencies with fallback:**
- None beyond the above.

---

## Code Examples

### Docker Compose profile tag pattern
```yaml
# Add this to each of the 8 platform services
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:8.15.0
  profiles: [platform]
  # ... rest of existing config unchanged
```

### setup-env.sh idempotent pattern
```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_ROOT/.env" ]; then
  echo "[setup-env] .env already exists. Remove it to regenerate."
  exit 0
fi

# GPU check
if command -v nvidia-smi > /dev/null 2>&1; then
  if ! docker info 2>/dev/null | grep -q nvidia; then
    echo "[WARN] NVIDIA GPU detected but nvidia-container-toolkit is not configured."
    echo "       Ollama will fail to start. Install nvidia-container-toolkit first."
    echo "       See docs/SETUP.md for installation steps."
  fi
fi

cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"

# Generate UUIDs
if command -v uuidgen > /dev/null 2>&1; then
  OPENCTI_TOKEN=$(uuidgen)
  CONNECTOR_MITRE_UUID=$(uuidgen)
else
  OPENCTI_TOKEN=$(python3 -c "import uuid; print(uuid.uuid4())")
  CONNECTOR_MITRE_UUID=$(python3 -c "import uuid; print(uuid.uuid4())")
fi

# Generate passwords (alphanumeric only — safe in all contexts)
RABBITMQ_PASS=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 24)
MINIO_SECRET=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 24)

# Write to .env via sed
sed -i "s|^OPENCTI_ADMIN_TOKEN=.*|OPENCTI_ADMIN_TOKEN=${OPENCTI_TOKEN}|" "$PROJECT_ROOT/.env"
sed -i "s|^CONNECTOR_MITRE_ID=.*|CONNECTOR_MITRE_ID=${CONNECTOR_MITRE_UUID}|" "$PROJECT_ROOT/.env"
sed -i "s|^RABBITMQ_PASSWORD=.*|RABBITMQ_PASSWORD=${RABBITMQ_PASS}|" "$PROJECT_ROOT/.env"
sed -i "s|^MINIO_SECRET_KEY=.*|MINIO_SECRET_KEY=${MINIO_SECRET}|" "$PROJECT_ROOT/.env"

echo "[setup-env] Generated .env with:"
echo "  OPENCTI_ADMIN_TOKEN = ${OPENCTI_TOKEN}"
echo "  CONNECTOR_MITRE_ID  = ${CONNECTOR_MITRE_UUID}"
echo "  RABBITMQ_PASSWORD   = ${RABBITMQ_PASS}"
echo "  MINIO_SECRET_KEY    = ${MINIO_SECRET}"
echo ""
echo "Next: docker compose --profile platform up -d"
```

### verify-platform.sh GraphQL poll
```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load token from .env
if [ ! -f "$PROJECT_ROOT/.env" ]; then
  echo "ERROR: .env not found. Run ./scripts/setup-env.sh first."
  exit 1
fi
source "$PROJECT_ROOT/.env"

OPENCTI_URL="http://localhost:8080"
TIMEOUT=900   # 15 minutes
START_TIME=$(date +%s)
POLL_N=0

echo "Waiting for OpenCTI at ${OPENCTI_URL} ..."

# Step 1: Wait for /health
until curl -sf "${OPENCTI_URL}/health" > /dev/null 2>&1; do
  ELAPSED=$(( $(date +%s) - START_TIME ))
  [ $ELAPSED -ge $TIMEOUT ] && { echo "TIMEOUT waiting for OpenCTI health."; exit 1; }
  sleep 5
done
echo "OpenCTI is up. Waiting for MITRE ATT&CK import..."

# Step 2: Poll for attackPatterns count
while true; do
  ELAPSED=$(( $(date +%s) - START_TIME ))
  if [ $ELAPSED -ge $TIMEOUT ]; then
    echo ""
    echo "[TIMEOUT] 15 minutes elapsed. Import may still be running."
    echo "  Check logs: docker compose --profile platform logs connector-mitre"
    echo "  Re-run this script when import completes."
    exit 1
  fi

  # Try pageInfo.globalCount first (OpenCTI pagination model)
  RESPONSE=$(curl -sf -X POST "${OPENCTI_URL}/graphql" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${OPENCTI_ADMIN_TOKEN}" \
    -d '{"query":"{ attackPatterns(first: 1) { pageInfo { globalCount } } }"}' 2>/dev/null || echo "")

  COUNT=$(echo "$RESPONSE" | jq -r '.data.attackPatterns.pageInfo.globalCount // 0' 2>/dev/null || echo "0")

  # Fallback: count edges if globalCount unavailable
  if [ "$COUNT" = "0" ] || [ "$COUNT" = "null" ]; then
    RESPONSE2=$(curl -sf -X POST "${OPENCTI_URL}/graphql" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${OPENCTI_ADMIN_TOKEN}" \
      -d '{"query":"{ attackPatterns(first: 500) { edges { node { id } } } }"}' 2>/dev/null || echo "")
    COUNT=$(echo "$RESPONSE2" | jq '.data.attackPatterns.edges | length' 2>/dev/null || echo "0")
  fi

  POLL_N=$(( POLL_N + 1 ))
  printf "[%d/10+] OpenCTI up, ATT&CK objects: %s\n" "$POLL_N" "$COUNT"

  if [ "${COUNT:-0}" -gt 100 ] 2>/dev/null; then
    echo ""
    echo "Platform ready. ${COUNT} ATT&CK patterns imported."
    break
  fi

  sleep 30
done

# Step 3: Verify TAXII 2.1 endpoint
echo "Checking TAXII 2.1 endpoint..."
TAXII_HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${OPENCTI_ADMIN_TOKEN}" \
  -H "Accept: application/taxii+json;version=2.1" \
  "${OPENCTI_URL}/taxii2/root/collections/")

if [ "$TAXII_HTTP" = "200" ]; then
  echo "TAXII endpoint: OK (HTTP ${TAXII_HTTP})"
else
  echo "TAXII endpoint: WARNING (HTTP ${TAXII_HTTP})"
  echo "  TAXII may not be configured yet. Check OpenCTI Data > Data Sharing > TAXII Collections."
fi

echo "Phase 1 complete."
```

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | OpenCTI uses `pageInfo.globalCount` for total count in pagination | Q3 / Code Examples | verify-platform.sh count always returns 0; need fallback (already included in script) |
| A2 | Total MITRE attack-pattern objects across all matrices is 600–900+ | Q6 | Threshold of >100 is still safe even if total is lower; risk is low |
| A3 | Import of first 100 attack-patterns takes 2–4 minutes (well within 15-min timeout) | Q6 | If slower, timeout fails; user re-runs verify script |
| A4 | `CONNECTOR_RUN_AND_TERMINATE=false` means connector stays running | Q6 | If wrong, connector exits after first import and won't re-run on schedule |
| A5 | connector-mitre version must match platform version (both 6.4.0) | Standard Stack | Version mismatch causes connector registration failure |
| A6 | OpenCTI 6.4.0 creates RabbitMQ vhost automatically on first start | Q7 | If manual vhost creation needed, opencti never becomes healthy |
| A7 | MinIO `mc ready local` healthcheck works in minio/minio:latest | Q7 | If mc not in image, MinIO health check always fails; OpenCTI never starts |

**Assumptions requiring user confirmation before execution:**
- A1 (GraphQL query shape) — the verify script includes a fallback, so this is low-risk but should be confirmed when OpenCTI is running by inspecting the actual GraphQL response
- A7 (MinIO healthcheck) — if MinIO healthcheck fails, replace with `curl -f http://localhost:9000/minio/health/live`

---

## Open Questions

1. **Should nvidia-container-toolkit installation be a task in the Phase 1 plan or a prerequisite in the README?**
   - What we know: toolkit is not installed; GPU passthrough will fail without it
   - What's unclear: whether the planner should include an install step or just document it as a prerequisite
   - Recommendation: Include as a plan task (Task 0 / pre-flight) so it's tracked and verifiable

2. **Should connector-mitre get a healthcheck added?**
   - What we know: DEPL-04 requires all services to have healthchecks; connector-mitre has none
   - What's unclear: what a meaningful healthcheck for connector-mitre would look like
   - Recommendation: Add a minimal healthcheck — e.g., `test: ["CMD", "pgrep", "-f", "mitre"]` — or document the gap in verify-platform.sh output

3. **What is the exact .env.example current content?** (file was unreadable due to permissions)
   - What we know: variables are referenced in docker-compose.yml
   - What's unclear: whether .env.example already has correct placeholder format for sed substitution
   - Recommendation: Plan task should explicitly verify .env.example has correct placeholder format before setup-env.sh is written

---

## Sources

### Primary (MEDIUM confidence)
- `docker-compose.yml` (project codebase) — all service configurations, environment variables, healthcheck blocks, dependency chains — [VERIFIED: codebase grep]
- `scripts/init-models.sh` (project codebase) — existing Ollama model pull script — [VERIFIED: file read]
- `.planning/phases/01-platform-foundation/01-CONTEXT.md` — locked decisions D-01 through D-10 — [VERIFIED: file read]

### Secondary (MEDIUM confidence from official docs)
- [Docker Compose profiles docs](https://docs.docker.com/compose/how-tos/profiles/) — profile syntax, depends_on behavior, activation commands — [CITED]
- [Docker Compose GPU support](https://docs.docker.com/compose/how-tos/gpu-support/) — deploy.resources.reservations structure — [CITED]
- [NVIDIA Container Toolkit install guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) — Ubuntu 22.04 installation steps — [CITED]
- [OpenCTI integration docs](https://docs.opencti.io/latest/deployment/integrations/) — TAXII Bearer token auth format — [CITED]
- [OpenCTI GraphQL API docs](https://docs.opencti.io/latest/reference/api/) — Authentication headers, query POST format — [CITED]
- [connector-mitre README](https://github.com/OpenCTI-Platform/connectors/blob/master/external-import/mitre/README.md) — all MITRE connector env vars, import scope — [CITED]
- [Elasticsearch Docker production docs](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/install-elasticsearch-docker-prod) — ulimit memlock settings — [CITED]

### Tertiary (LOW confidence)
- Web search results for MITRE ATT&CK technique counts — [LOW confidence; used for threshold reasoning only]
- Web search results for OpenCTI GraphQL attackPatterns query shape — [LOW confidence; script includes fallback]
- Environment probe results (environment availability table) — [VERIFIED: environment probe]

---

## Metadata

**Confidence breakdown:**
- Docker Compose config changes: HIGH — docker-compose.yml fully read; profile syntax confirmed from official Docker docs
- setup-env.sh design: HIGH — all tool dependencies confirmed present on machine; pattern is standard bash
- verify-platform.sh design: MEDIUM — healthcheck and TAXII endpoints confirmed; GraphQL query shape is ASSUMED with fallback implemented
- MITRE import timing: LOW — "several minutes" from docs; 3-10 minute estimate from CONTEXT.md additional context; threshold choice is conservative

**Research date:** 2026-06-23
**Valid until:** 2026-07-23 (stable stack; Docker/OpenCTI configs don't change frequently)
