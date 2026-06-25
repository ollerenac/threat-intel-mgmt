# Phase 2: Feed Ingestion Pipeline - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Build `feed-orchestrator` — a Python background service that downloads IOCs from 5 structured threat intelligence feeds on a configurable schedule, normalizes them to STIX 2.1 `indicator` objects with confidence scores, deduplicates via Redis, and delivers them to OpenCTI via pycti. The service starts all feeds immediately on container startup, then continues on scheduled cadences.

**In scope:**
- feed-orchestrator Python service (APScheduler + pycti + stix2)
- 5 feeds: URLhaus (1h), MalwareBazaar (2h), ThreatFox (2h), Feodo Tracker (4h), AlienVault OTX (6h)
- STIX 2.1 `indicator` SDOs with confidence scoring and labels
- Redis-based deduplication (O(1) hash lookup)
- Redis-based feed status state (last_run, ioc_count, status, error_msg per feed)
- Feed failure retry with exponential backoff
- Docker Compose service entry with healthcheck

**Out of scope for Phase 2:**
- CIRCL MISP (different client/format — deferred)
- `malware` SDOs or relationship objects (intel-extractor Phase 3 handles enrichment)
- HTTP API surface on feed-orchestrator (no FastAPI needed — pure worker)
- Dashboard UI for feed health (Phase 6)
- Seed data / demo scenarios (post-implementation)

</domain>

<decisions>
## Implementation Decisions

### Feed Health State Storage
- **D-01:** Feed status is written to Redis hash keys: `tim:feed_status:{feed_name}` (e.g., `tim:feed_status:urlhaus`). No HTTP endpoint on the orchestrator — pure background worker.
- **D-02:** Each feed status hash contains exactly 4 fields: `last_run` (ISO-8601 timestamp), `ioc_count` (integer count for that run), `status` (one of: `ok` / `error` / `running` / `never_run` / `disabled`), `error_msg` (string or empty).

### Feed Failure Handling
- **D-04:** On feed download failure: retry 3× with exponential backoff (30s → 60s → 120s). If all 3 retries fail, mark `status=error` in Redis and continue with remaining feeds. Other feeds are never blocked by one failing source.
- **D-05:** On pycti insertion failure (OpenCTI unavailable): same 3× backoff pattern, then skip. IOCs for that run are lost; the next scheduled run will re-download and retry. Acceptable for demo scope — no persistent buffer needed.

### Startup Behavior
- **D-06:** On container start, run all enabled feeds immediately (fire-and-forget initial pass), then schedule on their configured cadences. This ensures IOCs appear in OpenCTI within minutes of `docker compose up` — critical for demo setup.
- **D-07:** If `OTX_API_KEY` is not set in `.env` (empty string), log a warning at startup (`[OTX] disabled: OTX_API_KEY not configured`), set Redis `tim:feed_status:otx` = `{status: disabled}`, and skip OTX entirely. The other 4 feeds run normally. No container failure.

### STIX Object Modeling (Phase 2 Scope)
- **D-08:** `indicator` SDOs only. Malware family names from MalwareBazaar/ThreatFox go into the `labels` field (e.g., `labels: ["Emotet", "c2", "banking-trojan"]`). No `malware` SDOs or `indicates` relationships in Phase 2.
- **D-09:** Confidence scoring formula (FEED-05):
  ```
  score = min(100, feed_count * 25 + recency_bonus + quality_weight)
  ```
  Per-source quality weights:
  - Feodo Tracker: 30 (manually curated C2 blocklist, highest signal)
  - AlienVault OTX: 25 (analyst-curated pulses)
  - ThreatFox: 20 (community + analyst-reviewed)
  - URLhaus: 15 (automated with community validation)
  - MalwareBazaar: 15 (automated with community validation)
  
  `recency_bonus` and `feed_count` logic: Claude's discretion (suggest recency_bonus = max(0, 10 - days_old) capped at 10; feed_count = number of independent sources reporting the same IOC value).

### Claude's Discretion
- Phase 6 reads `tim:feed_status:{name}` keys directly from Redis — no intermediate HTTP API on feed-orchestrator. (D-03 upstream constraint for dashboard.)
- Recency bonus formula: `max(0, 10 - days_since_first_seen)` — linear decay over 10 days, floor at 0.
- Feed-level scheduling jitter: small random offset (±60s) per feed to avoid thundering-herd on startup.
- Redis key TTL: feed status keys have no TTL (persist indefinitely — always shows last known state).
- Healthcheck probe for docker-compose: `python -c "import redis; r=redis.from_url('redis://redis:6379'); r.ping()"` or equivalent.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Component Spec
- `docs/plans/2026-06-23-tim-system-design.md` §4.2 — Feed Orchestrator component spec: pipeline, feed table with cadences, confidence formula, tech stack (Python + APScheduler + pycti + stix2 + Redis)
- `docs/plans/2026-06-23-tim-system-design.md` §6.1 — Port assignments; note feed-orchestrator has NO exposed host port (internal only)
- `docs/plans/2026-06-23-tim-system-design.md` §6.4 — End-to-end IOC flow from orchestrator through OpenCTI to dashboard
- `docs/plans/2026-06-23-tim-system-design.md` §7.1 — Directory structure: service goes in `services/feed-orchestrator/`
- `docs/plans/2026-06-23-tim-system-design.md` §7.4 — `.env.example` variables including `OTX_API_KEY`

### Requirements
- `.planning/REQUIREMENTS.md` — FEED-01 through FEED-06 (the 6 feed ingestion requirements this phase must satisfy)

### Existing Infrastructure (build on, don't replace)
- `docker-compose.yml` — Existing service definitions; feed-orchestrator adds a new service entry following same patterns (depends_on, healthcheck, network: tim-network, profiles: [platform])
- `.env` / `.env.example` — Existing env var conventions; `OTX_API_KEY` already listed as optional

### Data Model
- `docs/plans/2026-06-23-tim-system-design.md` §5.1 — STIX SDO/SCO types in use; Phase 2 uses `indicator` only
- `docs/plans/2026-06-23-tim-system-design.md` §5.2 — Example `indicator` object structure with `confidence`, `labels`, `external_references` fields

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Redis** (already deployed): available at `redis://redis:6379` on `tim-network`. Used by Phase 1 for OpenCTI session cache. Feed-orchestrator can use the same instance for both dedup hashes and status keys — no new Redis container needed.
- **`.env` / `setup-env.sh`**: existing env scaffolding; `OTX_API_KEY` placeholder already in `.env.example` (Phase 1 artifact).
- **`scripts/verify-platform.sh`**: existing readiness check pattern — shows how to probe Docker services; can serve as reference for healthcheck probe design.

### Established Patterns
- **Docker Compose service pattern**: all services use `depends_on:` with `condition: service_healthy`, explicit `healthcheck:`, `networks: [tim-network]`, and `profiles: [platform]`. New service MUST follow this pattern.
- **Env-only credentials**: no hardcoded secrets anywhere — all credentials via `.env` vars. `OTX_API_KEY` is no exception.
- **No host-binding for internal services**: OpenCTI/Redis/RabbitMQ are internal-only. feed-orchestrator follows the same pattern — no ports exposed to host.

### Integration Points
- **OpenCTI API**: `http://opencti:8080` on `tim-network`. Auth via `Authorization: Bearer $OPENCTI_ADMIN_TOKEN`. pycti client handles the GraphQL transport.
- **Redis**: `redis://redis:6379` — shared instance; use key namespace `tim:feed_status:*` and `tim:ioc_seen:*` to avoid collisions.
- **`depends_on`**: feed-orchestrator must depend on `opencti` (healthy) and `redis` (healthy) before starting.

</code_context>

<specifics>
## Specific Ideas

- The design doc explicitly names `pycti` as the OpenCTI client because it "handles idempotency + merge automatically" — this is load-bearing: the planner should NOT swap it for raw GraphQL calls.
- The design doc confidence formula (`feed_count * 25 + recency_bonus + quality_weight`) is the authoritative spec; D-09 locks the quality weights that the doc left unspecified.
- CIRCL MISP appeared in the design doc as a potential 6th source but was NOT included in REQUIREMENTS.md success criteria — it is deferred, not dropped.

</specifics>

<deferred>
## Deferred Ideas

- **CIRCL MISP feed**: Mentioned in design doc §4.2 as a 6th source. Different client (MISP API), different format (MISP events), different authentication. Deferred to a future feed expansion phase or post-v1.
- **`malware` SDOs + `indicates` relationships**: MalwareBazaar/ThreatFox provide family context that could create a richer graph. Deferred — intel-extractor (Phase 3) is the designated owner of SDO enrichment.
- **Persistent bundle buffer**: Buffering failed pycti bundles in Redis for retry next cycle was considered for OpenCTI insertion failures. Deferred — retry-and-skip is sufficient for demo scope.

None — discussion stayed within phase scope on all other points.

</deferred>

---

*Phase: 2-feed-ingestion-pipeline*
*Context gathered: 2026-06-25*
