# Phase 1: Platform Foundation - Pattern Map

**Mapped:** 2026-06-23
**Files analyzed:** 5 (3 new, 1 modified-structural, 1 verify/update)
**Analogs found:** 3 / 5 (2 files have no codebase analog — new pattern territory)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `docker-compose.yml` | config | request-response (service orchestration) | `docker-compose.yml` itself | self (modify in place) |
| `scripts/setup-env.sh` | utility | file-I/O (read template, write .env) | `scripts/init-models.sh` | role-match (same: bash utility, project-root relative paths, curl wait loop pattern) |
| `scripts/verify-platform.sh` | utility | request-response (HTTP polling loop) | `scripts/init-models.sh` | role-match (same: bash utility, until-curl wait loop, docker compose exec pattern) |
| `.env.example` | config | file-I/O (template source) | `.env.example` itself | self (verify/update in place) — file unreadable; planner must check permissions |
| `docs/SETUP.md` | config | none | none | no analog |

---

## Pattern Assignments

### `docker-compose.yml` — ADD `profiles:` tags (config, orchestration)

**Analog:** `docker-compose.yml` itself (lines 17–311)

**Profiles insertion pattern** — add `profiles:` as the second key under each service name, immediately after `image:`:

```yaml
# PATTERN: profiles key placement (after image:, before environment:/volumes:)
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:8.15.0
  profiles: [platform]          # <-- INSERT HERE
  environment:
    ...
```

**Complete profile assignment map** (from D-02):

```yaml
# profiles: [platform]  →  elasticsearch, redis, rabbitmq, minio,
#                           opencti, connector-mitre, ollama, chromadb
# profiles: [feeds]     →  feed-orchestrator
# profiles: [extract]   →  intel-extractor
# profiles: [semantic]  →  semantic-engine
# profiles: [briefings] →  briefing-generator
# profiles: [dashboard] →  soc-dashboard
```

**Existing structural pattern to preserve** (docker-compose.yml lines 36–44, 51–58, 69–77 — healthcheck block format):

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:9200/_cluster/health"]
  interval: 15s
  timeout: 10s
  retries: 10
  start_period: 30s
networks:
  - tim-network
restart: unless-stopped
```

**connector-mitre healthcheck gap** (line 145–162 — currently no healthcheck block):
connector-mitre is the only service without a `healthcheck:` block. Add a minimal process check:

```yaml
# Add to connector-mitre service (after mem_limit: 512m)
healthcheck:
  test: ["CMD", "pgrep", "-f", "mitre"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

**Invariants — do NOT change these** (docker-compose.yml lines 125–133):

```yaml
# depends_on health-gate chain — already correct, do not modify
depends_on:
  elasticsearch:
    condition: service_healthy
  redis:
    condition: service_healthy
  rabbitmq:
    condition: service_healthy
  minio:
    condition: service_healthy
```

---

### `scripts/setup-env.sh` — NEW idempotent .env generator (utility, file-I/O)

**Analog:** `scripts/init-models.sh` (lines 1–21)

**Header and set -e pattern** (init-models.sh lines 1–6):

```bash
#!/bin/bash
# <one-line description of script purpose>
# <usage line: ./scripts/setup-env.sh>

set -e
```

**Project-root resolution pattern** (init-models.sh uses implicit working directory; setup-env.sh needs explicit resolution because it writes files):

```bash
# Resolve project root relative to script location (not cwd)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
```

**Bracketed log prefix pattern** (init-models.sh lines 8, 13, 16, 18 — consistent `[script-name]` prefix):

```bash
echo "[init-models] Esperando que Ollama esté listo..."
echo "[init-models] Descargando nomic-embed-text (embeddings)..."
echo "[init-models] Modelos listos."
```
Copy this pattern for setup-env.sh using `[setup-env]` prefix on all echo lines.

**Idempotency guard pattern** (no codebase analog — use RESEARCH.md pattern):

```bash
if [ -f "$PROJECT_ROOT/.env" ]; then
  echo "[setup-env] .env already exists. Remove it to regenerate."
  exit 0
fi
```

**GPU detection pattern** (no codebase analog — from RESEARCH.md Q4):

```bash
if command -v nvidia-smi > /dev/null 2>&1; then
  if ! docker info 2>/dev/null | grep -q nvidia; then
    echo "[setup-env] WARN: NVIDIA GPU detected but nvidia-container-toolkit is not configured."
    echo "            Ollama will fail to start. Install nvidia-container-toolkit first."
    echo "            See docs/SETUP.md for installation steps."
  fi
fi
```

**UUID generation with fallback** (RESEARCH.md Q2 — both confirmed available on host):

```bash
if command -v uuidgen > /dev/null 2>&1; then
  OPENCTI_TOKEN=$(uuidgen)
  CONNECTOR_MITRE_UUID=$(uuidgen)
else
  OPENCTI_TOKEN=$(python3 -c "import uuid; print(uuid.uuid4())")
  CONNECTOR_MITRE_UUID=$(python3 -c "import uuid; print(uuid.uuid4())")
fi
```

**Password generation pattern** (RESEARCH.md Q2 — alphanumeric only to avoid shell quoting issues):

```bash
RABBITMQ_PASS=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 24)
MINIO_SECRET=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 24)
```

**sed substitution pattern** (RESEARCH.md Q2 — use `|` delimiter to avoid conflicts with URL values):

```bash
sed -i "s|^OPENCTI_ADMIN_TOKEN=.*|OPENCTI_ADMIN_TOKEN=${OPENCTI_TOKEN}|" "$PROJECT_ROOT/.env"
sed -i "s|^CONNECTOR_MITRE_ID=.*|CONNECTOR_MITRE_ID=${CONNECTOR_MITRE_UUID}|" "$PROJECT_ROOT/.env"
sed -i "s|^RABBITMQ_PASSWORD=.*|RABBITMQ_PASSWORD=${RABBITMQ_PASS}|" "$PROJECT_ROOT/.env"
sed -i "s|^MINIO_SECRET_KEY=.*|MINIO_SECRET_KEY=${MINIO_SECRET}|" "$PROJECT_ROOT/.env"
```

**Summary output pattern** (from CONTEXT.md specifics — print generated values so user can record them):

```bash
echo "[setup-env] Generated .env with:"
echo "  OPENCTI_ADMIN_TOKEN = ${OPENCTI_TOKEN}"
echo "  CONNECTOR_MITRE_ID  = ${CONNECTOR_MITRE_UUID}"
echo "  RABBITMQ_PASSWORD   = ${RABBITMQ_PASS}"
echo "  MINIO_SECRET_KEY    = ${MINIO_SECRET}"
echo ""
echo "Next: docker compose --profile platform up -d"
```

**Variables NOT auto-generated** (use placeholder defaults from .env.example — do not overwrite):
- `OPENCTI_ADMIN_EMAIL` — default `admin@tim.local`
- `OPENCTI_BASE_URL` — default `http://localhost:8080`
- `RABBITMQ_USER` — default `tim`
- `MINIO_ACCESS_KEY` — default `minioadmin`
- `OTX_API_KEY` — left blank (Phase 2 concern)

---

### `scripts/verify-platform.sh` — NEW polling health script (utility, request-response)

**Analog:** `scripts/init-models.sh` (lines 1–21)

**Header and set -e pattern** (init-models.sh lines 1–6): same as setup-env.sh above.

**Project-root resolution pattern**: same as setup-env.sh above.

**Until-curl wait loop pattern** (init-models.sh lines 9–11 — the core polling idiom in this codebase):

```bash
until curl -sf http://localhost:11434/api/tags > /dev/null; do
  sleep 3
done
```
Adapt for OpenCTI health endpoint with timeout guard:

```bash
until curl -sf http://localhost:8080/health > /dev/null 2>&1; do
  ELAPSED=$(( $(date +%s) - START_TIME ))
  [ $ELAPSED -ge $TIMEOUT ] && { echo "TIMEOUT waiting for OpenCTI health."; exit 1; }
  sleep 5
done
```

**Token sourcing pattern** (no codebase analog — new for this project):

```bash
if [ ! -f "$PROJECT_ROOT/.env" ]; then
  echo "ERROR: .env not found. Run ./scripts/setup-env.sh first."
  exit 1
fi
# shellcheck source=/dev/null
source "$PROJECT_ROOT/.env"
```

**15-minute timeout scaffold** (RESEARCH.md Q3):

```bash
START_TIME=$(date +%s)
TIMEOUT=900   # 15 minutes
POLL_N=0
```

**GraphQL poll with fallback** (RESEARCH.md Q3 — primary + fallback query, jq parse):

```bash
# Primary: pageInfo.globalCount (OpenCTI pagination model)
RESPONSE=$(curl -sf -X POST "http://localhost:8080/graphql" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OPENCTI_ADMIN_TOKEN}" \
  -d '{"query":"{ attackPatterns(first: 1) { pageInfo { globalCount } } }"}' 2>/dev/null || echo "")
COUNT=$(echo "$RESPONSE" | jq -r '.data.attackPatterns.pageInfo.globalCount // 0' 2>/dev/null || echo "0")

# Fallback: count edges if globalCount unavailable or 0
if [ "$COUNT" = "0" ] || [ "$COUNT" = "null" ]; then
  RESPONSE2=$(curl -sf -X POST "http://localhost:8080/graphql" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${OPENCTI_ADMIN_TOKEN}" \
    -d '{"query":"{ attackPatterns(first: 500) { edges { node { id } } } }"}' 2>/dev/null || echo "")
  COUNT=$(echo "$RESPONSE2" | jq '.data.attackPatterns.edges | length' 2>/dev/null || echo "0")
fi
```

**Progress output format** (CONTEXT.md specifics — approved output format):

```bash
POLL_N=$(( POLL_N + 1 ))
printf "[%d/10+] OpenCTI up, ATT&CK objects: %s\n" "$POLL_N" "$COUNT"
```

**Success threshold check** (RESEARCH.md Q3 — >100 is conservative and safe):

```bash
if [ "${COUNT:-0}" -gt 100 ] 2>/dev/null; then
  echo ""
  echo "Platform ready. ${COUNT} ATT&CK patterns imported."
  break
fi
sleep 30
```

**Timeout error message pattern** (CONTEXT.md D-08 — actionable, directs user to logs):

```bash
echo "[TIMEOUT] 15 minutes elapsed. Import may still be running."
echo "  Check logs: docker compose --profile platform logs connector-mitre"
echo "  Re-run this script when import completes."
exit 1
```

**TAXII endpoint check** (RESEARCH.md Q3 — Bearer token + Accept header required):

```bash
TAXII_HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${OPENCTI_ADMIN_TOKEN}" \
  -H "Accept: application/taxii+json;version=2.1" \
  "http://localhost:8080/taxii2/root/collections/")

if [ "$TAXII_HTTP" = "200" ]; then
  echo "TAXII endpoint: OK (HTTP ${TAXII_HTTP})"
else
  echo "TAXII endpoint: WARNING (HTTP ${TAXII_HTTP})"
  echo "  TAXII may not be ready yet. Check: Data > Data Sharing > TAXII Collections in OpenCTI."
fi

echo "Phase 1 complete."
```

---

### `.env.example` — VERIFY/UPDATE (config, file-I/O)

**Analog:** `.env.example` itself — file was unreadable due to filesystem permissions.

**Planner action required:** The plan task for `.env.example` must begin with a permission/content check before any edit. The variables that must be present (confirmed from docker-compose.yml environment blocks) are:

| Variable | Used By (docker-compose.yml line) | Placeholder format for sed |
|---|---|---|
| `OPENCTI_ADMIN_TOKEN` | opencti:107, connector-mitre:149, feed-orchestrator:213, intel-extractor:234, semantic-engine:253, briefing-generator:276 | `OPENCTI_ADMIN_TOKEN=REPLACE_WITH_UUID` |
| `CONNECTOR_MITRE_ID` | connector-mitre:150 | `CONNECTOR_MITRE_ID=REPLACE_WITH_UUID` |
| `RABBITMQ_USER` | rabbitmq:63, opencti:114 | `RABBITMQ_USER=tim` |
| `RABBITMQ_PASSWORD` | rabbitmq:64, opencti:115 | `RABBITMQ_PASSWORD=REPLACE_WITH_PASSWORD` |
| `MINIO_ACCESS_KEY` | minio:83, opencti:119 | `MINIO_ACCESS_KEY=minioadmin` |
| `MINIO_SECRET_KEY` | minio:84, opencti:120 | `MINIO_SECRET_KEY=REPLACE_WITH_PASSWORD` |
| `OPENCTI_BASE_URL` | opencti:104 | `OPENCTI_BASE_URL=http://localhost:8080` |
| `OPENCTI_ADMIN_EMAIL` | opencti:105 | `OPENCTI_ADMIN_EMAIL=admin@tim.local` |
| `OPENCTI_ADMIN_PASSWORD` | opencti:106 | `OPENCTI_ADMIN_PASSWORD=REPLACE_WITH_STRONG_PASSWORD` |
| `OTX_API_KEY` | feed-orchestrator (Phase 2) | `OTX_API_KEY=` (blank, with comment) |

**sed-compatibility constraint:** Placeholder values for the 4 auto-generated variables must be non-empty strings starting at column 0 so that `sed -i "s|^VAR=.*|VAR=value|"` matches. Format: `VAR=REPLACE_WITH_UUID` not `VAR=` (empty) and not `VAR= # comment`.

---

### `docs/SETUP.md` — NEW installation guide (optional, no data flow)

**No codebase analog.** Planner should use RESEARCH.md Q4 content directly.

**Required sections** (from RESEARCH.md Q4 and Q7):
1. nvidia-container-toolkit installation (Ubuntu 22.04 steps from RESEARCH.md lines 288–295)
2. Elasticsearch memory lock requirement (Docker daemon LimitMEMLOCK=infinity — RESEARCH.md Risk D)
3. MinIO healthcheck fallback (if `mc ready local` fails, use `curl -f http://localhost:9000/minio/health/live` — RESEARCH.md Risk 7)
4. First-run sequence (D-06: setup-env.sh → compose up → init-models.sh → verify-platform.sh)

---

## Shared Patterns

### Bracketed log prefix (all scripts)
**Source:** `scripts/init-models.sh` lines 8, 13, 16, 18
**Apply to:** `setup-env.sh`, `verify-platform.sh`

```bash
echo "[script-name] Message text here."
```
Every user-facing echo uses `[script-name]` as prefix. Errors use bare `ERROR:` prefix (no bracket) for visual distinction.

### set -e + shebang header (all scripts)
**Source:** `scripts/init-models.sh` lines 1, 6
**Apply to:** `setup-env.sh`, `verify-platform.sh`

```bash
#!/bin/bash
set -e
```

### Project-root path resolution (scripts that read/write project files)
**Source:** new pattern — init-models.sh uses implicit cwd; setup-env.sh and verify-platform.sh must be cwd-independent
**Apply to:** `setup-env.sh`, `verify-platform.sh`

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
```

### Docker Compose service structure invariants (docker-compose.yml)
**Source:** `docker-compose.yml` — all 13 services share these constraints
**Apply to:** all services when adding `profiles:` tag

- `restart: unless-stopped` — required on every service
- `mem_limit:` — required on every service; do not add services without one
- `networks: [tim-network]` — required on every service
- `healthcheck:` — required on every platform-profile service (connector-mitre is the gap to fix)

### curl + Authorization Bearer pattern (verify-platform.sh)
**Source:** RESEARCH.md Q3 (no codebase analog yet — first authenticated HTTP call in this project)
**Apply to:** `verify-platform.sh` GraphQL poll and TAXII check

```bash
curl -sf -X POST "http://localhost:8080/graphql" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OPENCTI_ADMIN_TOKEN}" \
  -d '{"query":"..."}'
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `docs/SETUP.md` | documentation | none | No docs/ directory or markdown guides exist in codebase yet |
| `.env.example` (edit) | config | file-I/O | File exists but was unreadable due to permissions; planner must verify content before editing |

---

## Metadata

**Analog search scope:** `/home/researcher/Research/threat_int_mgmt/scripts/`, `docker-compose.yml`, `.env.example`
**Files scanned:** 3 (init-models.sh, docker-compose.yml; .env.example unreadable)
**Pattern extraction date:** 2026-06-23

**Key constraint for planner:** `.env.example` permissions must be verified before the setup-env.sh task is implemented. If the file uses empty placeholders (`VAR=`) rather than named placeholders (`VAR=REPLACE_WITH_UUID`), the sed substitution pattern will not match and setup-env.sh will silently produce a broken .env.
