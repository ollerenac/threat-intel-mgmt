---
phase: 01
slug: platform-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-23
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Shell-based integration checks (no unit test framework — infra phase) |
| **Config file** | none |
| **Quick run command** | `./scripts/verify-platform.sh` |
| **Full suite command** | `./scripts/verify-platform.sh && docker compose --profile platform ps` |
| **Estimated runtime** | ~15 min (dominated by MITRE import wait) |

---

## Sampling Rate

- **After every task commit:** Run `docker compose --profile platform ps` (service health snapshot)
- **After every plan wave:** Run `./scripts/verify-platform.sh` (full integration check)
- **Before `/gsd-verify-work`:** Full suite must exit 0; all 8 platform services must show healthy
- **Max feedback latency:** 900 seconds (15-min MITRE import timeout)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| nvidia-setup | 01 | 0 | PLAT-03 | — | toolkit installed before compose starts | manual | `docker run --rm --gpus all ubuntu nvidia-smi` | ❌ W0 | ⬜ pending |
| profile-tags | 01 | 0 | DEPL-01 | — | N/A | smoke | `docker compose --profile platform config --services` | ❌ W0 | ⬜ pending |
| setup-env-sh | 01 | 0 | DEPL-01 | T-secrets-in-file | secrets only in .env, not in compose or git | smoke | `./scripts/setup-env.sh && grep OPENCTI_ADMIN_TOKEN .env` | ❌ W0 | ⬜ pending |
| verify-platform-sh | 01 | 0 | PLAT-01–04 | — | exits 0 when platform is ready | smoke | `./scripts/verify-platform.sh` | ❌ W0 | ⬜ pending |
| env-example-check | 01 | 0 | DEPL-02 | T-secrets-hardcoded | all vars have placeholders, none have real values | manual | `grep -v '^#' .env.example | grep -v '^$'` (visual review) | ✅ exists | ⬜ pending |
| compose-up | 01 | 1 | PLAT-03 | — | N/A | smoke | `docker compose --profile platform ps` | N/A | ⬜ pending |
| mitre-import | 01 | 1 | PLAT-02 | — | N/A | smoke | `./scripts/verify-platform.sh` | ❌ W0 | ⬜ pending |
| taxii-verify | 01 | 1 | PLAT-04 | T-token-in-header | token read from .env, not hardcoded in script | smoke | `./scripts/verify-platform.sh` (includes TAXII check) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/setup-env.sh` — idempotent .env generator covering DEPL-01 first-run automation
- [ ] `scripts/verify-platform.sh` — polling script covering PLAT-01, PLAT-02, PLAT-04
- [ ] `docker-compose.yml` profile tags — 8 services get `profiles: [platform]`, 5 custom services get their phase profiles
- [ ] nvidia-container-toolkit installed on host — prerequisite for Ollama GPU passthrough (PLAT-03 blocker)

*Note: `scripts/init-models.sh` already exists and requires no changes — covers DEPL-03.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docker compose up -d` starts stack without steps beyond .env | DEPL-01 | Requires running the full docker compose command and watching output | Run `docker compose --profile platform up -d`; confirm all 8 services start, no exit code 1 |
| .env.example documents all required variables | DEPL-02 | Requires human judgment on documentation completeness | Read .env.example; verify each docker-compose.yml variable reference has a placeholder line |
| All services visible as healthy in `docker compose ps` | DEPL-04 | Requires visual inspection of health column | Run `docker compose --profile platform ps`; verify all services show `healthy` except connector-mitre (no healthcheck — known gap) |
| nvidia-container-toolkit installed and working | PLAT-03 | Requires root-level APT install and systemd restart | See docs/SETUP.md; run `docker run --rm --gpus all ubuntu nvidia-smi` after install |

---

## Known Verification Gaps

| Gap | Requirement | Risk | Mitigation |
|-----|-------------|------|------------|
| connector-mitre has no healthcheck | DEPL-04 | DEPL-04 cannot be fully satisfied for connector-mitre | Add minimal `pgrep -f mitre` healthcheck in docker-compose.yml, or document known limitation in verify-platform.sh |
| GraphQL `pageInfo.globalCount` shape unconfirmed | PLAT-02 | verify-platform.sh may return count=0 despite successful import | Script includes two-approach fallback; confirm actual query shape on first run by inspecting raw response |
| MinIO `mc ready local` healthcheck may fail | PLAT-03 | If mc not in minio/minio:latest image, MinIO health never passes | Replace healthcheck with `curl -f http://localhost:9000/minio/health/live` if needed |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency ≤ 900s (15-min MITRE import)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
