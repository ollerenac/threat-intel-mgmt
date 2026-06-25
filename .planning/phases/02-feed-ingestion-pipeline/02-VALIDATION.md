---
phase: 2
slug: feed-ingestion-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | services/feed-orchestrator/tests/conftest.py — Wave 0 installs |
| **Quick run command** | `docker compose exec feed-orchestrator pytest tests/ -x -q` |
| **Full suite command** | `docker compose exec feed-orchestrator pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `docker compose exec feed-orchestrator pytest tests/ -x -q`
- **After every plan wave:** Run `docker compose exec feed-orchestrator pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | FEED-01 | — | N/A | unit | `pytest tests/test_normalizer.py -x -q` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | FEED-02 | — | N/A | unit | `pytest tests/test_normalizer.py -x -q` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | FEED-03 | — | N/A | integration | manual — requires OpenCTI | — | ⬜ pending |
| 02-02-01 | 02 | 2 | FEED-04 | — | N/A | unit | `pytest tests/test_dedup.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | FEED-05 | — | N/A | integration | manual — requires OpenCTI + Redis | — | ⬜ pending |
| 02-03-01 | 03 | 3 | FEED-06 | — | N/A | integration | manual — verify scheduled runs | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/feed-orchestrator/tests/conftest.py` — shared fixtures (mock pycti client, mock Redis)
- [ ] `services/feed-orchestrator/tests/test_normalizer.py` — stubs for FEED-01, FEED-02
- [ ] `services/feed-orchestrator/tests/test_dedup.py` — stubs for FEED-04
- [ ] `pytest` + `pytest-mock` installed in Dockerfile

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| IOC visible in OpenCTI after feed run | FEED-01 | Requires live OpenCTI instance | Run `docker compose exec feed-orchestrator python -c "from feeds.urlhaus import run; run()"` then check localhost:8080 |
| Duplicate IOC results in one object | FEED-04 | Requires live pycti dedup behavior | Submit same IOC pattern from URLhaus and ThreatFox, count objects in OpenCTI |
| Feeds auto-run on schedule | FEED-05 | Time-based — must wait one interval | Start service, wait one cadence interval (URLhaus=1h), verify new IOCs appear |
| OTX disabled gracefully when key absent | FEED-06 | Env-dependent behavior | Remove OTX_API_KEY from .env, restart service, verify Redis shows `status=disabled` for OTX |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
