---
phase: 01-platform-foundation
plan: "03"
subsystem: deployment-scripts
tags: [bash, setup-automation, verification, documentation]
status: complete

dependency_graph:
  requires:
    - "01-01"   # .env.example permissions fixed + .gitignore in place
    - "01-02"   # docker-compose.yml profiles + connector-mitre healthcheck
  provides:
    - scripts/setup-env.sh
    - scripts/verify-platform.sh
    - docs/SETUP.md
  affects: []

tech_stack:
  added: []
  patterns:
    - SCRIPT_DIR/PROJECT_ROOT resolution via BASH_SOURCE[0] (cwd-independent scripts)
    - Idempotency guard pattern (exit 0 if .env exists)
    - uuidgen with python3 uuid fallback
    - tr -dc 'a-zA-Z0-9' | head -c 24 for alphanumeric password generation
    - sed -i with | delimiter for .env substitution
    - dual-approach GraphQL poll (pageInfo.globalCount + edges fallback)
    - TAXII 2.1 check with Authorization: Bearer + Accept: application/taxii+json;version=2.1

key_files:
  created:
    - scripts/setup-env.sh
    - scripts/verify-platform.sh
    - docs/SETUP.md
  modified: []

decisions:
  - "D-05/D-06/D-07: setup-env.sh — idempotent .env generator using uuidgen + /dev/urandom passwords"
  - "D-08/D-09: verify-platform.sh — 15-minute polling loop with dual GraphQL approach + TAXII check"
  - "D-10: TAXII 2.1 endpoint verified via Bearer token + application/taxii+json;version=2.1 Accept header"
  - "dual-approach GraphQL: pageInfo.globalCount primary, edges|length fallback (Risk B mitigation from RESEARCH.md)"

metrics:
  duration: "4 minutes"
  completed: "2026-06-23"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 0
---

# Phase 1 Plan 3: First-Run Scripts and Setup Guide Summary

**One-liner:** Idempotent .env generator (uuidgen + /dev/urandom passwords), dual-approach GraphQL poller with TAXII 2.1 check, and nvidia-container-toolkit install guide in four structured sections.

---

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create scripts/setup-env.sh | 1643478 | scripts/setup-env.sh |
| 2 | Create scripts/verify-platform.sh | 8685a46 | scripts/verify-platform.sh |
| 3 | Create docs/SETUP.md | 8fe6f4b | docs/SETUP.md |

---

## What Was Built

### scripts/setup-env.sh (D-05, D-06, D-07)

Idempotent `.env` generator. Resolves `PROJECT_ROOT` via `BASH_SOURCE[0]` so it works
regardless of the caller's working directory. On first run:

1. NVIDIA GPU detection (warns but does not block if toolkit is absent)
2. Copies `.env.example` to `.env`
3. Generates two UUIDs via `uuidgen` (python3 fallback)
4. Generates two 24-character alphanumeric passwords via `tr -dc 'a-zA-Z0-9' < /dev/urandom`
5. Substitutes all four values via `sed -i` with `|` delimiter (URL-safe)
6. Prints summary of generated values for operator record-keeping

On second run: prints `[setup-env] .env already exists. Remove it to regenerate.` and exits 0.

### scripts/verify-platform.sh (D-08, D-09, D-10)

Platform readiness poller. Sources `.env` for `OPENCTI_ADMIN_TOKEN`. Three-step sequence:

1. **Health wait:** polls `localhost:8080/health` every 5s with 15-minute overall timeout
2. **GraphQL poll:** 30-second interval. Primary approach: `pageInfo.globalCount`; if 0 or null, fallback to `edges | length` with `first: 500`. Prints `[N/10+] OpenCTI up, ATT&CK objects: COUNT` each cycle. Exits when count > 100.
3. **TAXII check:** `GET /taxii2/root/collections/` with `Authorization: Bearer` and `Accept: application/taxii+json;version=2.1`. Warns (non-fatal) if not HTTP 200.

### docs/SETUP.md

Four-section operator guide:
- **Section 1:** Prerequisites table (Docker 24+, Compose v2, NVIDIA GPU)
- **Section 2:** Five-command `nvidia-container-toolkit` install for Ubuntu 22.04 with post-install verification
- **Section 3:** Four-step first-run sequence with per-step explanations
- **Section 4:** Three troubleshooting entries: ES `LimitMEMLOCK=infinity`, MinIO `minio/health/live` healthcheck fallback, verify-platform.sh timeout recovery

---

## Verification Results

```
bash -n scripts/setup-env.sh     → syntax ok
bash -n scripts/verify-platform.sh → syntax ok
ls -la scripts/setup-env.sh      → -rwxrwxr-x (executable)
ls -la scripts/verify-platform.sh → -rwxrwxr-x (executable)
grep -c "nvidia-container-toolkit" docs/SETUP.md → 5  (>= 2 required)
grep -c "LimitMEMLOCK" docs/SETUP.md → 2
grep -c "minio/health/live" docs/SETUP.md → 1
```

---

## Deviations from Plan

### Auto-applied patterns

**[Rule 2 - Missing critical] Added `[setup-env]` prefix to "Next step" echo line**
- The plan action listed the next-step echo without a bracket prefix. Applied the
  `[setup-env]` prefix for consistency with all other echo lines per the must_haves truth
  "Both scripts use the [setup-env] / [verify-platform] bracketed prefix on all echo lines."
- No files beyond scope affected.

**[Rule 2 - Missing critical] Added shellcheck source=/dev/null comment in verify-platform.sh**
- Added `# shellcheck source=/dev/null` before `source "$PROJECT_ROOT/.env"` to suppress
  static analysis warnings — standard practice for dynamic source paths.

None of these deviations alter observable behavior. Plan executed exactly to spec.

---

## Requirements Satisfied

| Requirement | Status | Evidence |
|-------------|--------|----------|
| DEPL-01 | Complete | setup-env.sh automates .env generation; first-run sequence documented in SETUP.md |
| DEPL-02 | Complete | SETUP.md documents all env vars; .env.example already complete (Plan 01) |
| DEPL-03 | Complete | SETUP.md documents init-models.sh as Step 3 of first-run sequence |
| PLAT-01 | Complete | verify-platform.sh Step 1 confirms OpenCTI at localhost:8080 |
| PLAT-02 | Complete | verify-platform.sh Step 2 polls attackPatterns count > 100 |
| PLAT-04 | Complete | verify-platform.sh Step 3 verifies TAXII 2.1 endpoint |

---

## Known Stubs

None. All scripts implement complete functionality. `docs/SETUP.md` documents the live
`nvidia-container-toolkit` steps from RESEARCH.md Q4 (no placeholders).

---

## Threat Flags

No new network endpoints, auth paths, or trust boundaries introduced. The threat surface
in this plan (T-03-01 through T-03-04) was pre-mapped in the plan's `<threat_model>`:

| Threat ID | Disposition | Implementation |
|-----------|-------------|----------------|
| T-03-03 | mitigated | `tr -dc 'a-zA-Z0-9' | head -c 24` — 24-char alphanumeric passwords |
| T-03-04 | mitigated | source path hardcoded to `$PROJECT_ROOT/.env`; .gitignore in place (Plan 01) |

---

## Self-Check: PASSED

- [x] scripts/setup-env.sh exists at correct path
- [x] scripts/verify-platform.sh exists at correct path
- [x] docs/SETUP.md exists at correct path
- [x] Commits 1643478, 8685a46, 8fe6f4b all verified in git log
- [x] Both scripts executable (chmod +x applied)
- [x] Both scripts pass bash -n syntax check
- [x] docs/SETUP.md contains nvidia-container-toolkit (5 occurrences, >= 2 required)
- [x] docs/SETUP.md contains LimitMEMLOCK=infinity
- [x] docs/SETUP.md contains minio/health/live
- [x] STATE.md not modified (orchestrator owns that write)
- [x] ROADMAP.md not modified (orchestrator owns that write)
