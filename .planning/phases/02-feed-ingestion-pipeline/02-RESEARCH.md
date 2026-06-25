# Phase 02: Feed Ingestion Pipeline - Research

**Researched:** 2026-06-25
**Domain:** Python threat-intelligence feed ingestion — pycti, APScheduler, stix2, redis-py, abuse.ch APIs
**Confidence:** MEDIUM (library APIs verified via PyPI + official docs; feed field names verified via live endpoints)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Feed status written to Redis hash keys `tim:feed_status:{feed_name}`. No HTTP endpoint on the orchestrator — pure background worker.
- **D-02:** Each feed status hash has exactly 4 fields: `last_run` (ISO-8601), `ioc_count` (int), `status` (`ok` / `error` / `running` / `never_run` / `disabled`), `error_msg` (string or empty).
- **D-03:** Dashboard reads feed health directly from Redis — no intermediate API.
- **D-04:** Download failure: retry 3× with exponential backoff (30s → 60s → 120s). If all retries fail: mark `status=error` in Redis, continue with remaining feeds.
- **D-05:** pycti insertion failure: same 3× backoff, then skip. IOCs lost for that run; next schedule re-downloads. No persistent buffer.
- **D-06:** Container start: run all enabled feeds immediately, then schedule on configured cadences.
- **D-07:** `OTX_API_KEY` absent: log warning, set Redis `tim:feed_status:otx` = `{status: disabled}`, skip OTX. Other 4 feeds run normally.
- **D-08:** `indicator` SDOs only. Malware family names in `labels` field. No `malware` SDOs, no `indicates` relationships.
- **D-09:** Confidence score: `score = min(100, feed_count * 25 + recency_bonus + quality_weight)`. Weights: Feodo=30, OTX=25, ThreatFox=20, URLhaus=15, MalwareBazaar=15.

### Claude's Discretion

- Recency bonus: `max(0, 10 - days_since_first_seen)` — linear decay over 10 days, floor at 0.
- Feed scheduling jitter: ±60s random offset per feed to avoid thundering-herd on startup.
- Redis key TTL: feed status keys have no TTL (persist indefinitely).
- Healthcheck probe: `python -c "import redis; r=redis.from_url('redis://redis:6379'); r.ping()"`.

### Deferred Ideas (OUT OF SCOPE)

- CIRCL MISP feed (different client/format — deferred to future expansion)
- `malware` SDOs + `indicates` relationships (Phase 3 intel-extractor owns SDO enrichment)
- Persistent bundle buffer for pycti insertion failures
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FEED-01 | Feed orchestrator downloads URLhaus feed and normalizes IOCs to STIX 2.1 | URLhaus CSV API confirmed; field mapping to STIX url pattern documented |
| FEED-02 | Feed orchestrator downloads MalwareBazaar, ThreatFox, Feodo Tracker feeds | All three APIs confirmed; field names, auth requirements, and response shapes documented |
| FEED-03 | Feed orchestrator downloads AlienVault OTX feed (with API key) | OTXv2 SDK confirmed; getall() method and indicator type constants documented |
| FEED-04 | IOCs from all feeds are deduplicated before insertion into OpenCTI | Redis SETNX-based pre-dedup + pycti update=True pattern documented |
| FEED-05 | Each IOC has a confidence score (0-100) based on feed count, recency, and quality | Scoring formula locked in D-09; recency bonus formula in discretion |
| FEED-06 | Feeds run on schedule automatically (no manual trigger required) | APScheduler BackgroundScheduler confirmed; startup + interval pattern documented |
</phase_requirements>

---

## Summary

The `feed-orchestrator` is a headless Python background worker with no HTTP surface. It downloads IOCs from 5 threat intelligence feeds, normalizes each to a STIX 2.1 `indicator` SDO with a computed confidence score, deduplicates via a Redis seen-set, and submits to OpenCTI via pycti. APScheduler drives scheduling with an immediate first-pass on startup followed by recurring cadence runs.

The key library version constraint is **pycti must match the OpenCTI platform version**. The stack runs `opencti/platform:6.4.0`, so `pycti==6.4.11` (latest 6.4.x) is required. Using the latest 7.x pycti against a 6.4 platform will cause GraphQL schema mismatches.

Feed authentication varies significantly: URLhaus and Feodo Tracker require no authentication for bulk CSV downloads. MalwareBazaar, ThreatFox, and AlienVault OTX all require API keys (Auth-Key header for the abuse.ch feeds, OTX_API_KEY for OTX). The STATE.md confirms the OTX key is already stored in `.env`. MalwareBazaar and ThreatFox keys must also be provisioned (free accounts at abuse.ch portal).

**Primary recommendation:** Implement each feed as a standalone function/class with a `fetch()` and `normalize()` method. APScheduler calls each via `add_job(feed.run, 'interval', hours=N)`. On startup, call `feed.run()` directly for all enabled feeds before `scheduler.start()`, which ensures IOCs appear in OpenCTI within seconds of `docker compose up`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Feed download & parsing | feed-orchestrator container | — | Isolated worker; no HTTP surface |
| STIX normalization + scoring | feed-orchestrator container | — | Transformation happens before OpenCTI insertion |
| Deduplication (seen-set) | Redis (`tim:ioc_seen:*`) | pycti update=True | Redis O(1) SETNX prevents duplicate pycti calls; pycti update=True as fallback safety net |
| Feed status state | Redis (`tim:feed_status:*`) | — | Dashboard (Phase 6) reads directly from Redis; no intermediate API |
| STIX object persistence | OpenCTI / Elasticsearch | — | pycti submits; OpenCTI owns the graph |
| Schedule management | APScheduler in-process | — | BackgroundScheduler thread; no external scheduler needed |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pycti` | `6.4.11` | OpenCTI GraphQL client | Official client; handles idempotency + merge automatically; **must match OpenCTI 6.4.0** |
| `APScheduler` | `3.11.2` | Background job scheduling | Standard Python scheduler for interval/cron jobs; well-maintained, Docker-compatible |
| `stix2` | `3.0.2` | STIX 2.1 object construction | OASIS CTI official Python library; validates patterns at construction time |
| `redis` | `8.0.1` | Redis client for dedup + status | Official redis-py client; maintained by Redis Inc. |
| `requests` | `2.x` | HTTP downloads for CSV/JSON feeds | Standard; already a pycti transitive dependency |
| `OTXv2` | `1.5.12` | AlienVault OTX Python SDK | Official SDK from AlienVault-OTX GitHub org |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-dateutil` | `2.x` | Parse ISO-8601 / mixed date strings from feed responses | Feed timestamps come in varying formats (UTC strings, naive datetimes) |
| `tenacity` | `8.x` | Retry with exponential backoff (alternative to hand-rolling) | Cleaner than manual sleep-loop for D-04/D-05 retry logic |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| APScheduler 3.x | APScheduler 4.x | APScheduler 4 is a near-complete API rewrite (async-first); 3.x is stable, synchronous, and simpler for this use case |
| `tenacity` | `time.sleep` + manual loop | Manual loop is fine for 3 retries; tenacity only adds value if retry logic becomes complex |
| `stix2` library | Build STIX dicts by hand | stix2 validates patterns at construction — catches malformed patterns before they reach OpenCTI |

**Installation:**
```bash
pip install pycti==6.4.11 APScheduler==3.11.2 stix2==3.0.2 redis==8.0.1 OTXv2==1.5.12 python-dateutil tenacity
```

**Version verification:** [VERIFIED: pip index versions — PyPI registry, 2026-06-25]
- `pycti`: latest is 7.260624.0 (CalVer), but 6.4.11 matches `opencti/platform:6.4.0` [VERIFIED: pip index versions]
- `APScheduler`: 3.11.2 [VERIFIED: pip index versions]
- `stix2`: 3.0.2 [VERIFIED: pip index versions]
- `redis`: 8.0.1 [VERIFIED: pip index versions]
- `OTXv2`: 1.5.12 [VERIFIED: pip index versions]

---

## Package Legitimacy Audit

> Package legitimacy gate run against PyPI ecosystem, 2026-06-25. The seam returned `SUS` for all packages due to "unknown-downloads" (PyPI weekly download stats unavailable in this session). All packages are confirmed official/established by source repository and long version history.

| Package | Registry | Age | Source Repo | Verdict | Disposition |
|---------|----------|-----|-------------|---------|-------------|
| `pycti` | PyPI | ~8 yrs (v1.x from 2018) | github.com/OpenCTI-Platform/opencti | SUS (no dl stats) | Approved — official OpenCTI client |
| `APScheduler` | PyPI | ~14 yrs (v1.0 ~2012) | github.com/agronholm/apscheduler | SUS (no dl stats) | Approved — widely used scheduler |
| `stix2` | PyPI | ~8 yrs | oasis-open.github.io/cti-documentation | SUS (no dl stats) | Approved — OASIS official library |
| `redis` | PyPI | ~14 yrs | github.com/redis/redis-py | SUS (no dl stats) | Approved — official Redis client |
| `OTXv2` | PyPI | ~9 yrs (v1.0 ~2015, last update 2021-04) | github.com/AlienVault-OTX/OTX-Python-SDK | SUS (no dl stats, last release 2021) | Approved with caution — maintained by AlienVault (LevelBlue); last release Apr 2021 but SDK is stable API-wise |

**Packages removed due to SLOP verdict:** none

**Packages flagged as suspicious:** `OTXv2` flagged `SUS` by seam (last PyPI release 2021-04-02). The GitHub repo is the official AlienVault SDK. The package is stable; the OTX REST API it wraps has not changed fundamentally. No checkpoint required, but implementer should be aware the SDK may need manual patching if the OTX API changes. [ASSUMED: API stability since 2021]

---

## Architecture Patterns

### System Architecture Diagram

```
[Docker: feed-orchestrator]
        │
        ├── startup: run_all_feeds_immediately()
        │       │
        │       └── [APScheduler BackgroundScheduler].start()
        │               │
        │    ┌──────────┼──────────────────────┐
        │    ▼          ▼                      ▼
        │  URLhaus   MalwareBazaar  ...   AlienVault OTX
        │  (1h)       (2h)                   (6h)
        │
        ├── per feed run:
        │   1. write Redis tim:feed_status:{name} → status=running
        │   2. HTTP download (with 3× retry backoff)
        │   3. parse response → list of raw IOC dicts
        │   4. normalize each IOC → stix2.Indicator object
        │   5. compute confidence score
        │   6. Redis SETNX tim:ioc_seen:{sha256(pattern)} → skip if exists
        │   7. pycti indicator.create(..., update=True)
        │   8. write Redis tim:feed_status:{name} → status=ok, ioc_count=N
        │
        ├── [Redis :6379]
        │   ├── tim:feed_status:{name} → hash (last_run, ioc_count, status, error_msg)
        │   └── tim:ioc_seen:{hash}    → "1" (seen-set for dedup)
        │
        └── [OpenCTI :8080]
            └── pycti GraphQL → IndicatorAdd mutation
```

### Recommended Project Structure

```
services/feed-orchestrator/
├── Dockerfile
├── requirements.txt
├── main.py                    # Entry point: startup run + scheduler.start()
├── config.py                  # Feed configs (URL, cadence, quality_weight), env vars
├── scheduler.py               # APScheduler setup, add_job() calls
├── feeds/
│   ├── __init__.py
│   ├── base.py                # BaseFeed abstract class (fetch, normalize, run)
│   ├── urlhaus.py             # URLhaus CSV downloader + normalizer
│   ├── malwarebazaar.py       # MalwareBazaar JSON API
│   ├── threatfox.py           # ThreatFox JSON API
│   ├── feodo.py               # Feodo Tracker CSV
│   └── otx.py                 # AlienVault OTX via OTXv2 SDK
├── normalizer.py              # IOC type detection, STIX pattern builder, confidence scorer
├── deduplicator.py            # Redis SETNX seen-set logic
├── opencti_client.py          # pycti wrapper: connect, indicator.create with retry
└── status.py                  # Redis feed status writer
```

### Pattern 1: Feed Base Class

**What:** Each feed implements `fetch()` → raw data, `normalize(raw)` → list of STIX indicator kwargs, and `run()` which orchestrates status updates, retry, dedup, and pycti insertion.

**When to use:** All 5 feeds. The `BaseFeed.run()` contains all error handling, retry, and status update logic so individual feed classes only implement parsing.

```python
# Source: [ASSUMED] — standard pattern for this architecture
import time, hashlib, logging
from datetime import datetime, timezone

class BaseFeed:
    name: str
    quality_weight: int
    
    def fetch(self) -> list[dict]:
        raise NotImplementedError
    
    def normalize(self, raw: list[dict]) -> list[dict]:
        """Return list of pycti indicator.create() kwargs dicts."""
        raise NotImplementedError
    
    def run(self, redis_client, pycti_client):
        redis_client.hset(f"tim:feed_status:{self.name}", mapping={
            "status": "running",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "ioc_count": 0,
            "error_msg": "",
        })
        try:
            raw = self._fetch_with_retry()
            indicators = self.normalize(raw)
            count = self._insert_deduplicated(indicators, redis_client, pycti_client)
            redis_client.hset(f"tim:feed_status:{self.name}", mapping={
                "status": "ok",
                "last_run": datetime.now(timezone.utc).isoformat(),
                "ioc_count": count,
                "error_msg": "",
            })
        except Exception as e:
            redis_client.hset(f"tim:feed_status:{self.name}", mapping={
                "status": "error",
                "last_run": datetime.now(timezone.utc).isoformat(),
                "ioc_count": 0,
                "error_msg": str(e)[:500],
            })

    def _fetch_with_retry(self) -> list[dict]:
        delays = [30, 60, 120]
        for i, delay in enumerate(delays):
            try:
                return self.fetch()
            except Exception as e:
                if i == len(delays) - 1:
                    raise
                time.sleep(delay)
```

### Pattern 2: APScheduler Startup + Interval

**What:** Run all feeds immediately on startup, then register each on its cadence. The `start()` call must come AFTER the immediate run calls so the scheduler thread is already alive when jobs begin.

**When to use:** `main.py` entry point.

```python
# Source: apscheduler.readthedocs.io/en/3.x/userguide.html [MEDIUM confidence]
import random, logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR

scheduler = BackgroundScheduler()

def on_job_error(event):
    logging.error(f"Feed job failed: {event.job_id} — {event.exception}")

scheduler.add_listener(on_job_error, EVENT_JOB_ERROR)

# Run all feeds immediately, then schedule
for feed in enabled_feeds:
    jitter = random.uniform(-60, 60)  # ±60s jitter per D-09 discretion
    feed.run(redis_client, pycti_client)  # immediate first pass
    scheduler.add_job(
        feed.run,
        'interval',
        hours=feed.interval_hours,
        args=[redis_client, pycti_client],
        jitter=60,  # APScheduler 3.x built-in jitter param
        id=f"feed_{feed.name}",
    )

scheduler.start()

# Block main thread
import signal
signal.pause()  # or use threading.Event().wait()
```

### Pattern 3: pycti Indicator Creation

**What:** Submit a normalized STIX indicator to OpenCTI. Use `update=True` as the safety net for any duplicates that slip through Redis dedup.

**When to use:** After dedup check passes. Wrap in its own retry loop per D-05.

```python
# Source: docs.opencti.io/latest/development/python/ [MEDIUM confidence]
# and opencti_indicator.py source inspection [LOW confidence]
from pycti import OpenCTIApiClient

client = OpenCTIApiClient(
    url="http://opencti:8080",
    token=OPENCTI_ADMIN_TOKEN,
)

indicator = client.indicator.create(
    name="Feodo C2 IP: 185.220.101.47",
    description="Botnet C2 server from Feodo Tracker",
    pattern_type="stix",
    pattern="[ipv4-addr:value = '185.220.101.47']",
    x_opencti_main_observable_type="IPv4-Addr",
    valid_from="2026-06-23T10:00:00Z",       # ISO-8601 UTC string
    confidence=85,                             # 0-100 STIX confidence
    x_opencti_score=85,                        # OpenCTI-specific score (use same value)
    objectLabel=["c2", "botnet", "Emotet"],    # malware families + tags in labels
    externalReferences=[{
        "source_name": "Feodo Tracker",
        "url": "https://feodotracker.abuse.ch/",
    }],
    indicator_types=["malicious-activity"],
    update=True,                               # idempotent upsert — deduplicates by pattern
)
```

### Pattern 4: Redis Deduplication

**What:** Before calling pycti, check whether this IOC value has already been inserted in this run window. Use Redis `SETNX` (set-if-not-exists) with a TTL matching the feed's longest cadence.

**When to use:** After normalization, before pycti call.

```python
# Source: redis.readthedocs.io [LOW confidence]
import hashlib, redis

r = redis.from_url("redis://redis:6379", decode_responses=True)

def is_duplicate(ioc_pattern: str) -> bool:
    """Returns True if this IOC was already inserted; marks it seen if not."""
    key = "tim:ioc_seen:" + hashlib.sha256(ioc_pattern.encode()).hexdigest()
    # SETNX returns True if key was set (new), False if already existed
    # TTL: 24h — longer than any feed cadence, shorter than forever
    was_new = r.set(key, "1", nx=True, ex=86400)
    return not was_new  # True = duplicate
```

### Pattern 5: Redis Feed Status Update

**What:** Write all 4 status fields atomically in a single `hset(mapping=...)` call.

**When to use:** At start of run (status=running) and at end (status=ok or status=error).

```python
# Source: redis.readthedocs.io [LOW confidence]
# Note: hmset() is DEPRECATED in redis-py 4.x+. Use hset(mapping=...) instead.
r.hset("tim:feed_status:urlhaus", mapping={
    "last_run": "2026-06-25T06:00:00+00:00",
    "ioc_count": "142",
    "status": "ok",
    "error_msg": "",
})
# Read back:
status = r.hgetall("tim:feed_status:urlhaus")
# {"last_run": "...", "ioc_count": "142", "status": "ok", "error_msg": ""}
```

### Anti-Patterns to Avoid

- **Using pycti 7.x with OpenCTI 6.4.0:** GraphQL schema version mismatch causes silent failures or 400 errors. Pin `pycti==6.4.11`.
- **Calling `hmset()` in redis-py 4.x+:** Deprecated and removed; use `hset(mapping={...})`.
- **Fetching CSV feeds on every IOC's schedule:** URLhaus and Feodo CSVs are bulk files — download once per feed run, parse all rows, not one HTTP call per IOC.
- **Blocking the main thread during feed fetch in the scheduler:** The BaseFeed.run() is called in the APScheduler ThreadPoolExecutor; if it blocks for >120s (max retry wait), the next run may queue behind it. Keep retry waits short relative to cadence.
- **Storing raw IOC value as Redis dedup key:** Use `sha256(pattern)` not the raw value; the pattern string is the canonical dedup key because the same IP can appear in multiple ioc_types.
- **Not setting `x_opencti_main_observable_type`:** pycti requires this field; missing it silently prevents observable linking in OpenCTI's graph.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff retry | Custom sleep-loop | `tenacity` or fixed `[30, 60, 120]` delays | Edge cases in jitter, max attempts, exception filtering |
| STIX pattern validation | String formatting | `stix2.Indicator(pattern=...)` | stix2 validates at construction; malformed patterns silently accepted by pycti but rejected by OpenCTI at import time |
| OpenCTI GraphQL mutations | Raw HTTP + `requests` | `pycti` | pycti wraps all mutations, handles auth header, retries transport errors, and manages deterministic ID generation |
| Background scheduling | `threading.Timer` loop | `APScheduler BackgroundScheduler` | APScheduler handles missed-fire policy, jitter, executor pool, error events |
| Deduplication across restarts | In-memory set | Redis SETNX with TTL | In-memory set is lost on container restart; Redis persists |

**Key insight:** The most critical don't-hand-roll is STIX patterns — an invalid pattern string (e.g., wrong quote style, missing brackets) passes through Python undetected but causes the OpenCTI worker to reject the entire bundle, silently dropping IOCs.

---

## Feed-Specific Reference

### URLhaus (FEED-01)

| Property | Value |
|----------|-------|
| URL | `https://urlhaus.abuse.ch/downloads/csv_recent/` |
| Auth | None required for bulk CSV |
| Format | CSV with comment header lines starting with `#` |
| Update cadence | Every 5 minutes (do not fetch more often) |
| Fields | `id`, `dateadded`, `url`, `url_status`, `last_online`, `threat`, `tags`, `urlhaus_link`, `reporter` |
| IOC field | `url` column |
| IOC type | URL |
| STIX pattern | `[url:value = '{url}']` |
| Labels | `tags` column (comma-separated, e.g., "Mozi,exe") |
| Skip condition | `url_status == 'offline'` — optional filter for active-only |

[VERIFIED: urlhaus.abuse.ch/downloads/csv_recent/ — live endpoint accessed 2026-06-25]

### MalwareBazaar (FEED-02)

| Property | Value |
|----------|-------|
| URL | `https://mb-api.abuse.ch/api/v1/` |
| Auth | `Auth-Key: {MALWAREBAZAAR_AUTH_KEY}` header — free account at abuse.ch |
| Format | HTTP POST with JSON body |
| Request body | `{"query": "get_recent", "selector": "time"}` (last 60 min) |
| Fields | `sha256_hash`, `md5_hash`, `sha1_hash`, `first_seen`, `signature`, `tags`, `file_type`, `file_name`, `file_size` |
| IOC field | `sha256_hash` (primary), also `md5_hash`, `sha1_hash` |
| IOC type | File hash |
| STIX pattern | `[file:hashes.'SHA-256' = '{sha256}']` |
| Labels | `signature` (malware family) + `tags` list |
| Note | Response check: `data["query_status"] == "ok"` before processing |

[VERIFIED: bazaar.abuse.ch/api/ — official API docs accessed 2026-06-25]

### ThreatFox (FEED-02)

| Property | Value |
|----------|-------|
| URL | `https://threatfox-api.abuse.ch/api/v1/` |
| Auth | `Auth-Key: {THREATFOX_AUTH_KEY}` header — free account at abuse.ch |
| Format | HTTP POST with JSON body |
| Request body | `{"query": "get_iocs", "days": 7}` (max 7 days) |
| Fields | `ioc` (value), `ioc_type`, `threat_type`, `malware`, `malware_printable`, `confidence_level`, `first_seen`, `last_seen`, `tags`, `reporter` |
| IOC types | `domain`, `ip:port`, `url`, `md5_hash`, `sha256_hash` |
| STIX patterns | See STIX pattern table below |
| Labels | `malware_printable` + `tags` list |
| Note | `ioc_type == "ip:port"` — split on `:` to get IP and port separately |

[VERIFIED: threatfox.abuse.ch/api/ — official API docs accessed 2026-06-25]

**ThreatFox ioc_type → STIX pattern mapping:**

| ioc_type | STIX pattern |
|----------|-------------|
| `domain` | `[domain-name:value = '{ioc}']` |
| `ip:port` | `[ipv4-addr:value = '{ip}']` (extract IP from `ip:port`) |
| `url` | `[url:value = '{ioc}']` |
| `md5_hash` | `[file:hashes.MD5 = '{ioc}']` |
| `sha256_hash` | `[file:hashes.'SHA-256' = '{ioc}']` |

### Feodo Tracker (FEED-02)

| Property | Value |
|----------|-------|
| URL | `https://feodotracker.abuse.ch/downloads/ipblocklist.csv` |
| Auth | None required |
| Format | CSV with comment header lines starting with `#` |
| Update cadence | Every 5 minutes |
| Fields | `first_seen_utc`, `dst_ip`, `dst_port`, `c2_status`, `last_online`, `malware` |
| IOC field | `dst_ip` |
| IOC type | IPv4 address |
| STIX pattern | `[ipv4-addr:value = '{dst_ip}']` |
| Labels | `malware` column (e.g., "Dridex", "Emotet", "QakBot") + "c2" |
| Note | Quality weight is 30 (highest) — highest-confidence manual C2 blocklist |

[VERIFIED: feodotracker.abuse.ch/blocklist/ — official site accessed 2026-06-25]

### AlienVault OTX (FEED-03)

| Property | Value |
|----------|-------|
| SDK | `OTXv2` package |
| Auth | `OTX_API_KEY` env var — already in `.env` per STATE.md |
| Init | `otx = OTXv2(api_key, server='https://otx.alienvault.com')` |
| Fetch method | `pulses = otx.getall(modified_since=datetime_6h_ago)` |
| Pulse structure | `pulse['indicators']` — list of indicator dicts |
| Indicator fields | `{'indicator': '<value>', 'type': '<IndicatorType>', 'title': '...', 'expiration': '...', 'is_active': 1}` |
| IOC types | `IPv4`, `domain`, `URL`, `FileHash-MD5`, `FileHash-SHA256`, `FileHash-SHA1` |
| Skip condition | If `OTX_API_KEY` not set: log warning, set `tim:feed_status:otx → {status: disabled}`, return |
| Network | `otx.alienvault.com` — external call required (allowed per requirements: OTX is free feed) |

[VERIFIED: github.com/AlienVault-OTX/OTX-Python-SDK OTXv2.py — source code accessed 2026-06-25]

**OTX indicator type → STIX pattern mapping:**

| OTX type | STIX pattern |
|----------|-------------|
| `IPv4` | `[ipv4-addr:value = '{indicator}']` |
| `domain` | `[domain-name:value = '{indicator}']` |
| `URL` | `[url:value = '{indicator}']` |
| `FileHash-MD5` | `[file:hashes.MD5 = '{indicator}']` |
| `FileHash-SHA256` | `[file:hashes.'SHA-256' = '{indicator}']` |
| `FileHash-SHA1` | `[file:hashes.'SHA-1' = '{indicator}']` |
| `hostname` | `[domain-name:value = '{indicator}']` |
| others | skip (email, mutex, etc. not in scope) |

---

## STIX 2.1 Pattern Reference

[VERIFIED: stix2.readthedocs.io/patterns + threatfox.abuse.ch/api/ + multiple official sources, 2026-06-25]

```
# URL
[url:value = 'https://example.com/malware.exe']

# Domain
[domain-name:value = 'evil.example.com']

# IPv4
[ipv4-addr:value = '185.220.101.47']

# MD5 hash — no quotes needed for "MD5" (no hyphen)
[file:hashes.MD5 = 'd41d8cd98f00b204e9800998ecf8427e']

# SHA-256 — single quotes required because property name contains hyphen
[file:hashes.'SHA-256' = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855']

# SHA-1 — single quotes required
[file:hashes.'SHA-1' = 'da39a3ee5e6b4b0d3255bfef95601890afd80709']
```

**Critical syntax rules:**
1. Always wrap in square brackets `[...]`
2. String values use single quotes `'value'`
3. Property names containing hyphens (`SHA-256`, `SHA-1`) require single quotes around the property name
4. `MD5` (no hyphen) does NOT require quoted property name but quoting is harmless

---

## Common Pitfalls

### Pitfall 1: pycti version mismatch with OpenCTI platform

**What goes wrong:** Using `pycti>=7.x` against `opencti/platform:6.4.0` causes GraphQL schema errors on `IndicatorAdd` mutation — the 7.x client sends fields the 6.x server doesn't understand, or the server returns fields the 7.x client can't parse. Errors may be silent (pycti returns None, IOC dropped).

**Why it happens:** pycti uses CalVer (`7.YYMMDD.0`) since early 2026. The 6.x series tracks the 6.x OpenCTI series.

**How to avoid:** Pin `pycti==6.4.11` in `requirements.txt`. If the platform is upgraded later, update pycti to match.

**Warning signs:** `indicator.create()` returns `None` or raises `GraphQLError`; zero IOCs appear in OpenCTI despite no retry exhaustion.

### Pitfall 2: ThreatFox ip:port IOC type

**What goes wrong:** ThreatFox returns `ioc_type = "ip:port"` with `ioc = "185.220.101.47:4444"`. Building the pattern as `[ipv4-addr:value = '185.220.101.47:4444']` is invalid STIX and will fail pattern validation.

**Why it happens:** ThreatFox includes the C2 port in the IOC value string rather than a separate field.

**How to avoid:** When `ioc_type == "ip:port"`, split on `:` and use only the IP part in the STIX pattern. Optionally add port to `description` or `labels`.

**Warning signs:** stix2 raises `InvalidValueError` at indicator construction; or pycti silently rejects the object.

### Pitfall 3: STIX hash property quoting

**What goes wrong:** Using `[file:hashes.SHA-256 = '...']` (no quotes around property name) causes a pattern parse error because `SHA-256` is not a valid bare identifier (contains hyphen).

**Why it happens:** STIX pattern grammar requires property names with special characters to be quoted.

**How to avoid:** Always use `[file:hashes.'SHA-256' = '...']` and `[file:hashes.'SHA-1' = '...']`. `MD5` can be unquoted.

**Warning signs:** `stix2.exceptions.InvalidValueError` or `PatternParseException` at indicator construction time.

### Pitfall 4: URLhaus/Feodo CSV comment header parsing

**What goes wrong:** The first several lines of URLhaus and Feodo CSV files are comment lines starting with `#`. Using `csv.DictReader()` without skipping comments causes the reader to include comment lines as data rows, producing parsing errors.

**Why it happens:** Both feeds use `#` comment headers to document the CSV schema inline.

**How to avoid:** Either use `pandas.read_csv(comment='#')`, or open as text and filter lines not starting with `#` before passing to `csv.DictReader`.

**Warning signs:** `KeyError` on column access; rows where `url` column contains `# id,dateadded,...`.

### Pitfall 5: APScheduler job misfire during immediate run

**What goes wrong:** If `scheduler.start()` is called before the immediate feed runs complete, and a feed takes longer than its interval, APScheduler may fire a second run before the first finishes — causing concurrent pycti writes.

**Why it happens:** ThreadPoolExecutor allows parallel job execution by default.

**How to avoid:** Call all `feed.run()` functions synchronously BEFORE calling `scheduler.start()`. Or set `max_instances=1` on each job.

**Warning signs:** Two "status=running" writes without an intervening "status=ok", or pycti rate errors.

### Pitfall 6: OTXv2 getall() returns ALL historical pulses on first call

**What goes wrong:** `otx.getall()` without `modified_since` returns every pulse the account is subscribed to — potentially thousands, taking many minutes and producing hundreds of thousands of IOCs.

**Why it happens:** OTX subscriptions accumulate over time; the default is to return all pulses.

**How to avoid:** On first run, pass `modified_since=datetime.utcnow() - timedelta(days=7)` to limit to recent pulses. On subsequent runs, track the last-run timestamp and pass that as `modified_since`.

**Warning signs:** First OTX run takes >5 minutes; memory spike in the container.

---

## Code Examples

### Complete pycti Indicator Create Pattern

```python
# Source: docs.opencti.io/latest/development/python/ + opencti_indicator.py source [LOW confidence]
from pycti import OpenCTIApiClient
from datetime import datetime, timezone

client = OpenCTIApiClient(
    url="http://opencti:8080",
    token=OPENCTI_ADMIN_TOKEN,
    log_level="error",  # suppress INFO spam
)

# Map IOC pattern type to x_opencti_main_observable_type
OBSERVABLE_TYPE_MAP = {
    "url": "Url",
    "domain-name": "Domain-Name",
    "ipv4-addr": "IPv4-Addr",
    "file": "StixFile",
}

def create_indicator(client, name, pattern, observable_type, confidence,
                     labels, source_name, valid_from=None):
    if valid_from is None:
        valid_from = datetime.now(timezone.utc).isoformat()
    return client.indicator.create(
        name=name,
        pattern_type="stix",
        pattern=pattern,
        x_opencti_main_observable_type=observable_type,
        valid_from=valid_from,
        confidence=confidence,
        x_opencti_score=confidence,
        objectLabel=labels,
        externalReferences=[{"source_name": source_name}],
        indicator_types=["malicious-activity"],
        update=True,
    )
```

### Confidence Scoring

```python
# Source: CONTEXT.md D-09 (locked decision) [HIGH confidence — user decision]
from datetime import datetime, timezone

QUALITY_WEIGHTS = {
    "feodo": 30,
    "otx": 25,
    "threatfox": 20,
    "urlhaus": 15,
    "malwarebazaar": 15,
}

def compute_confidence(feed_name: str, first_seen_dt: datetime,
                       seen_in_feeds: int = 1) -> int:
    quality_weight = QUALITY_WEIGHTS.get(feed_name, 10)
    days_old = (datetime.now(timezone.utc) - first_seen_dt).days
    recency_bonus = max(0, 10 - days_old)  # linear decay, floor at 0
    score = seen_in_feeds * 25 + recency_bonus + quality_weight
    return min(100, score)
```

### APScheduler Full Setup

```python
# Source: apscheduler.readthedocs.io/en/3.x/ [MEDIUM confidence]
import logging, signal
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED

logger = logging.getLogger(__name__)

def build_scheduler(feeds, redis_client, pycti_client) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(
        executors={"default": {"type": "threadpool", "max_workers": 5}},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60},
    )
    
    def on_event(event):
        if event.exception:
            logger.error(f"Feed job {event.job_id} failed: {event.exception}")
        elif hasattr(event, 'scheduled_run_time'):
            logger.warning(f"Feed job {event.job_id} missed scheduled run")
    
    scheduler.add_listener(on_event, EVENT_JOB_ERROR | EVENT_JOB_MISSED)
    
    for feed in feeds:
        scheduler.add_job(
            feed.run,
            trigger="interval",
            hours=feed.interval_hours,
            args=[redis_client, pycti_client],
            id=f"feed_{feed.name}",
            jitter=60,               # ±60s jitter per design decision
            max_instances=1,         # prevent concurrent runs of same feed
            coalesce=True,           # skip missed fires rather than run N times
        )
    return scheduler
```

---

## Docker Service Structure

The `feed-orchestrator` service stub is already present in `docker-compose.yml` (line 244) with `profiles: [feeds]`. It needs:
1. A `healthcheck` block (currently missing — see CONTEXT.md D-03 discretion)
2. The `OTX_API_KEY` env var passed through
3. Optional: `MALWAREBAZAAR_AUTH_KEY` and `THREATFOX_AUTH_KEY` env vars

```yaml
# Addition to existing feed-orchestrator service block in docker-compose.yml
feed-orchestrator:
  build: ./services/feed-orchestrator
  profiles: [feeds]
  environment:
    - OPENCTI_URL=http://opencti:8080
    - OPENCTI_TOKEN=${OPENCTI_ADMIN_TOKEN}
    - REDIS_URL=redis://redis:6379
    - OTX_API_KEY=${OTX_API_KEY}
    - MALWAREBAZAAR_AUTH_KEY=${MALWAREBAZAAR_AUTH_KEY}
    - THREATFOX_AUTH_KEY=${THREATFOX_AUTH_KEY}
  mem_limit: 1g
  depends_on:
    opencti:
      condition: service_healthy
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "python", "-c",
           "import redis; r=redis.from_url('redis://redis:6379'); r.ping()"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s
  networks:
    - tim-network
  restart: unless-stopped
```

**Dockerfile pattern (matching Phase 1 conventions):**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | Service runtime | Yes | 3.10.12 (host) / 3.12 (Docker image) | — |
| Docker Compose | Service deployment | Yes (per STATE.md — platform running) | 29.5 + v5 | — |
| Redis | Dedup + status | Yes (running in stack) | 7.2-alpine | — |
| OpenCTI | STIX target | Yes (9 services healthy per STATE.md) | 6.4.0 | — |
| OTX_API_KEY | AlienVault OTX | Yes (stored in .env per STATE.md) | — | Skip OTX, run 4 feeds |
| MALWAREBAZAAR_AUTH_KEY | MalwareBazaar API | Unknown — not in .env.example | — | Feed disabled if key absent |
| THREATFOX_AUTH_KEY | ThreatFox API | Unknown — not in .env.example | — | Feed disabled if key absent |

**Missing dependencies with no fallback:** None that block core functionality.

**Missing dependencies with fallback:** MalwareBazaar and ThreatFox auth keys are not confirmed present. If absent, treat same as OTX pattern (D-07): log warning, set `status=disabled` in Redis, skip feed.

> **Action for planner:** Add `MALWAREBAZAAR_AUTH_KEY` and `THREATFOX_AUTH_KEY` (both optional with empty default) to `.env.example`. Add same pattern as OTX (D-07) for each: if key empty, log warning + set status=disabled.

---

## Runtime State Inventory

> Phase 2 is greenfield (new service `services/feed-orchestrator/` does not yet exist). Not a rename/refactor phase. Omitted per instructions.

---

## Validation Architecture

**nyquist_validation is enabled** (config.json: `"nyquist_validation": true`).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (industry standard for Python) |
| Config file | `services/feed-orchestrator/pytest.ini` (Wave 0 gap — does not exist yet) |
| Quick run command | `pytest services/feed-orchestrator/tests/ -x -q` |
| Full suite command | `pytest services/feed-orchestrator/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FEED-01 | URLhaus CSV parsed and normalized to STIX url:value indicators | unit | `pytest tests/test_urlhaus.py -x` | No — Wave 0 |
| FEED-02a | MalwareBazaar response normalized to STIX file:hashes.'SHA-256' | unit | `pytest tests/test_malwarebazaar.py -x` | No — Wave 0 |
| FEED-02b | ThreatFox ip:port split correctly to ipv4-addr pattern | unit | `pytest tests/test_threatfox.py -x` | No — Wave 0 |
| FEED-02c | Feodo CSV parsed, dst_ip mapped to STIX ipv4-addr pattern | unit | `pytest tests/test_feodo.py -x` | No — Wave 0 |
| FEED-03 | OTX getall() iterates pulses, maps indicator types to STIX patterns | unit | `pytest tests/test_otx.py -x` | No — Wave 0 |
| FEED-04 | Duplicate IOC pattern → second call returns is_duplicate=True | unit | `pytest tests/test_deduplicator.py -x` | No — Wave 0 |
| FEED-05 | Confidence score with known inputs matches expected formula output | unit | `pytest tests/test_normalizer.py::test_confidence -x` | No — Wave 0 |
| FEED-06 | Scheduler registers N jobs and immediately fires all feeds on startup | integration | Manual verify (check Redis keys after `docker compose up`) | No — manual |

### Sampling Rate

- **Per task commit:** `pytest services/feed-orchestrator/tests/ -x -q`
- **Per wave merge:** `pytest services/feed-orchestrator/tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `services/feed-orchestrator/tests/conftest.py` — fixtures: mock redis, mock pycti client, sample feed responses
- [ ] `services/feed-orchestrator/tests/test_urlhaus.py` — FEED-01
- [ ] `services/feed-orchestrator/tests/test_malwarebazaar.py` — FEED-02
- [ ] `services/feed-orchestrator/tests/test_threatfox.py` — FEED-02
- [ ] `services/feed-orchestrator/tests/test_feodo.py` — FEED-02
- [ ] `services/feed-orchestrator/tests/test_otx.py` — FEED-03
- [ ] `services/feed-orchestrator/tests/test_deduplicator.py` — FEED-04
- [ ] `services/feed-orchestrator/tests/test_normalizer.py` — FEED-05
- [ ] `services/feed-orchestrator/pytest.ini` — configure pytest for the service
- [ ] Framework install: `pip install pytest pytest-mock` in requirements.txt

---

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high` per config.json.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Service-to-service via token in env var, not user auth |
| V3 Session Management | No | No user sessions — background worker |
| V4 Access Control | No | No user-facing endpoints |
| V5 Input Validation | Yes | Validate feed response structure before normalization; reject malformed IOC values |
| V6 Cryptography | No | No crypto operations in scope |
| V9 Data Protection | Yes | API keys must stay in env vars, never logged; `error_msg` in Redis must not log key values |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed feed response (CSV injection, unexpected fields) | Tampering | Strict field access with `.get()` and defaults; validate IOC value format before STIX pattern construction |
| API key leakage via logging | Information Disclosure | Log only key presence (`"OTX_API_KEY set: True"`), never key value; ensure `error_msg` doesn't contain exception trace with key |
| Oversized feed response DoS | Denial of Service | Enforce response size limit via `requests` stream + size check; limit rows processed per run |
| Redis key collision with OpenCTI's Redis | Tampering | Use `tim:ioc_seen:` and `tim:feed_status:` namespaces — already decided in D-01 |
| STIX pattern injection from feed data | Tampering | IOC values used in pattern must be sanitized: escape single quotes (`'` → `\'`) before interpolation into pattern string |

**Critical security note — STIX pattern injection:** Feed data from URLhaus/ThreatFox/etc. is untrusted input. If an IOC value contains a single quote (e.g., a URL with `'`), naive string interpolation into `[url:value = '{ioc}']` creates an invalid pattern. Always escape or validate IOC values before pattern construction. The `stix2` library does this automatically when using its `Indicator` class directly.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pycti` 6.x linear versioning | CalVer (`7.YYMMDD.0`) since Feb 2026 | ~Feb 2026 | Must pin to `6.4.x` to match platform 6.4.0 |
| `redis-py` `hmset()` | `hset(mapping={...})` | redis-py 4.x (~2021) | `hmset()` removed; use `hset` with `mapping` kwarg |
| APScheduler 4.x (async-first) | APScheduler 3.x (sync, stable) | 4.x available since 2024 | 3.x is correct choice for this sync Python service |
| OTXv2 `getall()` all history | `getall(modified_since=N_hours_ago)` | Always available | Must pass `modified_since` to avoid pulling all historical pulses on first run |

**Deprecated/outdated:**
- `hmset()` in redis-py: removed in 4.x — use `hset(mapping={...})`
- `pycti>=7.0.0` with OpenCTI 6.4.x: incompatible — do not use latest pycti

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | OTXv2 SDK stable despite last PyPI release in April 2021 | Standard Stack | OTX API may have changed; SDK may fail with auth or endpoint errors. Mitigation: test OTX connection in Wave 0. |
| A2 | `pycti.indicator.create()` accepts `objectLabel` kwarg for labels | Code Examples | Actual param name might differ (e.g., `labels`, `x_opencti_labels`). Must verify against source before coding. |
| A3 | MalwareBazaar and ThreatFox require Auth-Key (not confirmed keys are in .env) | Feed Reference | If keys absent and not handled gracefully, feeds fail with 403. Add D-07-style disabled handling. |
| A4 | `confidence` and `x_opencti_score` are independent fields that both should be set | Code Examples | May be the same field; setting both might cause conflict. Verify in pycti source. |
| A5 | URLhaus CSV recent download requires NO authentication | Feed Reference | API page showed auth requirement for some downloads; the `csv_recent` URL specifically confirmed no-auth via direct access. |
| A6 | OTXv2 indicator type strings are exactly "IPv4", "domain", "URL", "FileHash-MD5", "FileHash-SHA256", "FileHash-SHA1" | Feed Reference | Type strings could differ in SDK vs. actual API response. Verify by printing `pulse['indicators'][0]['type']` in a test. |

**If this table were empty:** All claims verified — but A1–A6 represent real implementation risks that the implementer must validate in Wave 0.

---

## Open Questions (RESOLVED)

1. **MalwareBazaar and ThreatFox API keys — are they in .env?**
   - STATE.md only confirms `OTX_API_KEY` stored. MB and TF also require Auth-Keys (free at abuse.ch).
   - Recommendation: Add both as optional vars in `.env.example`; implement D-07-style disabled handling for each.
   - **DISPOSITION (RESOLVED):** Plans treat MB and TF keys as optional with empty-string defaults — same pattern as OTX (D-07). If absent, feed logs warning and sets `status=disabled`. No blocker.

2. **pycti `objectLabel` vs `labels` parameter name**
   - The pycti source inspection showed `objectLabel` (list) as the parameter. Training data shows `labels`. These may differ.
   - Recommendation: Verify in `pycti/entities/opencti_indicator.py` line by line in Wave 0 before writing the normalizer.
   - **DISPOSITION (RESOLVED):** Plan 02 Task 2 now includes a required verify step: executor must grep the installed pycti source (`opencti_indicator.py`) to confirm the exact parameter name before finalizing `opencti_client.py`. If the name differs from `objectLabel`, the call is updated in place. This is load-bearing — wrong parameter means all indicators are submitted with no labels silently.

3. **Redis dedup TTL strategy for cross-feed dedup**
   - The design assigns feed_count bonuses for IOCs seen in multiple feeds. If Redis TTL is 24h, an IOC from Feed A at hour 0 blocks Feed B at hour 2 from inserting (Redis SETNX returns false) — so the second-feed confidence boost is never applied.
   - Recommendation: Store dedup key as `{pattern_hash}:{feed_name}` to allow cross-feed confidence merging, OR accept that cross-feed dedup uses pycti's `update=True` merge and the confidence is set per-feed-run independently. The simplest approach: use pycti update=True as the sole dedup and drop the Redis seen-set for cross-feed tracking.
   - **DISPOSITION (RESOLVED — accepted limitation):** `seen_in_feeds` will always equal 1 in live system. Each IOC is seen once per run window per feed; Redis SETNX blocks the second-feed insert before it reaches pycti. The cross-feed confidence bonus (seen_in_feeds > 1) is a known non-delivery for demo scope. `compute_confidence()` still produces valid scores in the range [15, 65] for single-feed IOCs. Unit tests may exercise `seen_in_feeds > 1` by calling `compute_confidence()` directly. Documented in Plan 07 must_haves. No code change required.

4. **`x_opencti_main_observable_type` valid values**
   - Confirmed: `"IPv4-Addr"`, `"Domain-Name"`, `"Url"`, `"StixFile"`. Need to verify exact casing for OpenCTI 6.4.
   - Recommendation: Check OpenCTI enum in pycti source or OpenCTI GraphQL schema.
   - **DISPOSITION (RESOLVED):** Observable types are passed directly from each feed's `normalize()` output using the `OBSERVABLE_TYPE_MAP` defined in `normalizer.py`. The four values (`Url`, `Domain-Name`, `IPv4-Addr`, `StixFile`) are taken verbatim from the RESEARCH.md code example (Pattern 3) which was sourced from pycti documentation. If a value is wrong, pycti will raise or return None — surfaced immediately in Wave 3 integration testing.

---

## Sources

### Primary (MEDIUM confidence)

- [docs.opencti.io/latest/development/python/](https://docs.opencti.io/latest/development/python/) — pycti indicator.create() method, update=True pattern
- [docs.opencti.io/latest/usage/deduplication/](https://docs.opencti.io/latest/usage/deduplication/) — OpenCTI deduplication by pattern
- [apscheduler.readthedocs.io/en/3.x/userguide.html](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — BackgroundScheduler, add_job, listeners
- [stix2.readthedocs.io/en/latest/guide/creating.html](https://stix2.readthedocs.io/en/latest/guide/creating.html) — Indicator construction
- [stix2.readthedocs.io/en/latest/guide/patterns.html](https://stix2.readthedocs.io/en/latest/guide/patterns.html) — Pattern syntax
- [redis.readthedocs.io/en/stable/commands.html](https://redis.readthedocs.io/en/stable/commands.html) — hset(mapping=...), hgetall, hexists

### Secondary (LOW confidence — web verified)

- [threatfox.abuse.ch/api/](https://threatfox.abuse.ch/api/) — ThreatFox API format, response fields
- [bazaar.abuse.ch/api/](https://bazaar.abuse.ch/api/) — MalwareBazaar API, get_recent fields
- [feodotracker.abuse.ch/blocklist/](https://feodotracker.abuse.ch/blocklist/) — Feodo CSV URL, no-auth confirmed
- [urlhaus.abuse.ch/downloads/csv_recent/](https://urlhaus.abuse.ch/downloads/csv_recent/) — URLhaus CSV columns, no-auth confirmed
- [github.com/AlienVault-OTX/OTX-Python-SDK](https://github.com/AlienVault-OTX/OTX-Python-SDK) — OTXv2 getall() signature, indicator type constants
- [PyPI registry](https://pypi.org) — all 5 package version confirmations

---

## Metadata

**Confidence breakdown:**
- Standard stack (library names + versions): HIGH — confirmed via PyPI pip index
- Feed API formats: MEDIUM — verified via live endpoints and official docs
- pycti API parameter names: LOW-MEDIUM — documented in official docs but parameter name casing (objectLabel vs labels) must be verified in source
- APScheduler patterns: MEDIUM — official docs confirm BackgroundScheduler and add_job API
- Architecture patterns: HIGH — follows locked decisions from CONTEXT.md

**Research date:** 2026-06-25
**Valid until:** 2026-07-25 (stable library APIs; abuse.ch feed URLs are stable; pycti version pin must be updated if platform version changes)
