---
phase: 01-platform-foundation
plan: "02"
subsystem: docker-compose
tags: [profiles, healthcheck, docker-compose, platform]
status: complete

dependency_graph:
  requires:
    - "01-01"
  provides:
    - "docker-compose profiles: all 13 services profile-gated"
    - "connector-mitre healthcheck: pgrep-based process check"
  affects:
    - "01-03"
    - "01-04"

tech_stack:
  added: []
  patterns:
    - "Docker Compose profiles: [profile-name] field for service activation control"
    - "CMD-SHELL pgrep healthcheck for Python process services without HTTP endpoints"

key_files:
  created: []
  modified:
    - docker-compose.yml

decisions:
  - "profiles: [platform] on 8 services (elasticsearch, redis, rabbitmq, minio, opencti, connector-mitre, ollama, chromadb) — enables docker compose --profile platform up -d startup command"
  - "profiles: [feeds|extract|semantic|briefings|dashboard] on 5 custom-build services — prevents build failures for services whose build contexts do not exist yet"
  - "connector-mitre healthcheck uses CMD-SHELL pgrep -f 'python.*mitre' per plan spec — pgrep matches the long-running Python process (CONNECTOR_RUN_AND_TERMINATE=false)"
  - "start_period: 120s for connector-mitre — accounts for OpenCTI health-gate dependency wait plus initial ATT&CK import setup time"

metrics:
  duration: "11m"
  completed: "2026-06-23"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
---

# Phase 1 Plan 2: Docker Compose Profile Tags and connector-mitre Healthcheck Summary

**One-liner:** Profile-gated all 13 Docker Compose services (8 platform, 5 custom-build) and added pgrep-based healthcheck to connector-mitre to satisfy DEPL-01 and DEPL-04.

---

## What Was Built

Added `profiles:` keys to all 13 services in `docker-compose.yml` so that services activate only when the matching profile is passed to `docker compose`. Added a `healthcheck:` block to `connector-mitre` — the only platform-profile service that previously lacked one.

**Profile distribution:**
- `profiles: [platform]` (8 services): elasticsearch, redis, rabbitmq, minio, opencti, connector-mitre, ollama, chromadb
- `profiles: [feeds]` (1 service): feed-orchestrator
- `profiles: [extract]` (1 service): intel-extractor
- `profiles: [semantic]` (1 service): semantic-engine
- `profiles: [briefings]` (1 service): briefing-generator
- `profiles: [dashboard]` (1 service): soc-dashboard

**connector-mitre healthcheck added:**
```yaml
healthcheck:
  test: ["CMD-SHELL", "pgrep -f 'python.*mitre' || exit 1"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 120s
```

---

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Add profiles tags to all 13 services | 1799299 | docker-compose.yml (+13 lines) |
| 2 | Add healthcheck to connector-mitre (DEPL-04) | 6378d97 | docker-compose.yml (+6 lines) |

---

## Verification Results

All acceptance criteria passed:

| Check | Expected | Result |
|-------|----------|--------|
| `docker compose --profile platform config --services \| sort` | 8 services | chromadb, connector-mitre, elasticsearch, minio, ollama, opencti, rabbitmq, redis |
| `docker compose config --services` (no profile) | 0 services | (empty) |
| `grep -c "profiles: [platform]" docker-compose.yml` | 8 | 8 |
| `grep -c "profiles: [feeds]" docker-compose.yml` | 1 | 1 |
| `grep -c "profiles: [extract]" docker-compose.yml` | 1 | 1 |
| `grep -c "profiles: [semantic]" docker-compose.yml` | 1 | 1 |
| `grep -c "profiles: [briefings]" docker-compose.yml` | 1 | 1 |
| `grep -c "profiles: [dashboard]" docker-compose.yml` | 1 | 1 |
| `grep -c "pgrep" docker-compose.yml` | 1 | 1 |
| connector-mitre healthcheck in `docker compose config` output | present | CMD-SHELL pgrep -f 'python.*mitre' |

---

## Deviations from Plan

None — plan executed exactly as written.

All 13 Edit calls used the exact old_string/new_string patterns specified in the plan. No other service content was modified (dependency chains, mem_limits, environment variables, port bindings, network assignments, and restart policies are unchanged).

---

## Requirements Addressed

| Requirement | Description | Status |
|-------------|-------------|--------|
| PLAT-03 | Profile-gated service startup | Satisfied — `docker compose --profile platform up -d` activates exactly 8 services |
| DEPL-01 | Profile-gated startup command operational | Satisfied — no-profile invocation activates 0 services |
| DEPL-04 | All platform services have healthchecks | Satisfied — connector-mitre was the only gap; now all 8 platform-profile services have healthcheck blocks |

---

## Known Stubs

None. This plan modifies only infrastructure configuration (docker-compose.yml). No application code, UI components, or data sources are involved.

---

## Threat Flags

No new security-relevant surface introduced. All changes are additive metadata keys (`profiles:`, `healthcheck:`) on existing service definitions. The connector-mitre healthcheck uses `pgrep` (read-only process inspection) — no new network endpoints or auth paths created.

---

## Self-Check: PASSED

Files verified:
- [x] `/home/researcher/Research/threat_int_mgmt/docker-compose.yml` — exists and modified
- [x] Commit `1799299` exists in git log (Task 1)
- [x] Commit `6378d97` exists in git log (Task 2)
- [x] `docker compose --profile platform config --services` returns exactly 8 services
- [x] `docker compose config --services` (no profile) returns 0 services
- [x] `grep -c "profiles: [platform]" docker-compose.yml` returns 8
- [x] `grep -c "pgrep" docker-compose.yml` returns 1
- [x] connector-mitre healthcheck present in `docker compose config` output
