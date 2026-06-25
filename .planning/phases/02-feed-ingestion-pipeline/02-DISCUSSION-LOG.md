# Phase 2: Feed Ingestion Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-25
**Phase:** 02-feed-ingestion-pipeline
**Areas discussed:** Feed health storage, Feed failure behavior, Startup run + OTX key absence, STIX object richness

---

## Feed health storage

| Option | Description | Selected |
|--------|-------------|----------|
| Redis hash keys | Write `tim:feed_status:{feed_name}` HSET with last_run/ioc_count/status/error_msg. No HTTP endpoint needed on orchestrator. Dashboard reads Redis directly. | ✓ |
| Add /status HTTP endpoint | Add FastAPI to feed-orchestrator, expose GET /status on port 8004. Matches intel-extractor pattern. | |
| JSON file on shared volume | Write to /data/feed_status.json on a Docker volume. Simple but coarser, file lock risk. | |

**User's choice:** Redis hash keys (recommended)

**Follow-up — fields to include:**

| Option | Description | Selected |
|--------|-------------|----------|
| Core fields only | last_run, ioc_count, status (ok/error/running/never_run/disabled), error_msg | ✓ |
| Extended metrics | Add duration_seconds, iocs_new vs deduplicated, next_scheduled_run, consecutive_failure_count | |
| You decide | Claude picks fields for demo-quality health panel | |

**User's choice:** Core fields only (recommended)
**Notes:** Pure background worker pattern confirmed — no FastAPI, no exposed port on feed-orchestrator.

---

## Feed failure behavior

**Download failures:**

| Option | Description | Selected |
|--------|-------------|----------|
| Retry 3× with exponential backoff | 30s → 60s → 120s, then skip and mark status=error. APScheduler native retry. | ✓ |
| Log + skip immediately | First failure → status=error, move on. Simple but fragile for transient blips. | |
| Retry once, then skip | One immediate retry then skip. Middle ground. | |

**User's choice:** Retry 3× with exponential backoff (recommended)

**pycti insertion failures:**

| Option | Description | Selected |
|--------|-------------|----------|
| Retry the full batch with backoff, then skip | Same 3× pattern. IOCs lost for that run; next run re-downloads. Acceptable for demo. | ✓ |
| Buffer failed bundles in Redis, retry next cycle | Store STIX bundles in Redis list, flush on next run. More resilient, significantly more complex. | |
| You decide | Claude picks given demo scope | |

**User's choice:** Retry the full batch with backoff, then skip (recommended)
**Notes:** "Lost IOCs are acceptable" confirmed — feeds run frequently enough that gaps are minimal. No buffer needed.

---

## Startup run + OTX key absence

**Startup behavior:**

| Option | Description | Selected |
|--------|-------------|----------|
| Run all feeds immediately at startup, then schedule | All feeds fire on container start, then cadence. Critical for demo — no 6h OTX wait. | ✓ |
| Wait for first scheduled tick | Strictly cron-based. Clean but bad for demo/first setup. | |
| Run fast feeds immediately, slow ones wait | URLhaus/MalwareBazaar/ThreatFox immediately; OTX/Feodo wait for tick. Adds complexity. | |

**User's choice:** Run all feeds immediately at startup, then schedule (recommended)

**OTX key absence:**

| Option | Description | Selected |
|--------|-------------|----------|
| Skip OTX silently, run other 4 feeds | Check key at startup, log warning, mark Redis status=disabled, run remaining feeds normally. | ✓ |
| Fail loudly and refuse to start | Container exits if any required config missing. | |
| Start but error on first OTX job | OTX job runs at tick, fails with error, marks Redis status=error. | |

**User's choice:** Skip OTX silently and run the other 4 feeds (recommended)
**Notes:** "Getting started before OTX key is in hand" was the motivating context. Graceful degradation preferred.

---

## STIX object richness

**STIX scope for Phase 2:**

| Option | Description | Selected |
|--------|-------------|----------|
| Indicators only | STIX indicator SDOs, malware family in labels. Simple, stays within FEED-01–06. | ✓ |
| Indicators + malware SDOs with relationships | Create malware SDO + 'indicates' relationship. Richer graph, ~30–40% more complexity. | |
| Indicators + malware SDOs for feeds with clean data only | ThreatFox/MalwareBazaar get SDO treatment; others get labels only. Two code paths. | |

**User's choice:** Indicators only for Phase 2 (recommended)

**Confidence score weights:**

| Option | Description | Selected |
|--------|-------------|----------|
| Tiered weights by source quality | Feodo=30, OTX=25, ThreatFox=20, URLhaus=15, MalwareBazaar=15 | ✓ |
| Flat weights, feed_count drives score | All sources quality_weight=0. Simple but undifferentiated. | |
| You decide the weights | Claude picks reasonable per-source weights | |

**User's choice:** Tiered weights (recommended)
**Notes:** Malware SDO enrichment explicitly deferred to intel-extractor (Phase 3).

---

## Claude's Discretion

- Recency bonus formula: `max(0, 10 - days_since_first_seen)` linear decay over 10 days
- Per-feed scheduling jitter: ±60s random offset to avoid thundering-herd on startup
- Redis key TTL: no TTL on feed status keys (persist indefinitely)
- Docker healthcheck probe: Redis ping check

## Deferred Ideas

- **CIRCL MISP**: 6th feed from design doc §4.2; different client/format. Deferred post-v1.
- **`malware` SDOs + relationships**: Richer graph, better demo narrative. Deferred to intel-extractor Phase 3 or a follow-on feed expansion.
- **Persistent bundle buffer**: Redis-backed retry queue for pycti insertion failures. Deferred — retry-and-skip sufficient for demo.
