---
phase: 02-feed-ingestion-pipeline
plan: "05"
subsystem: feed-parsers
tags: [python, stix, malwarebazaar, threatfox, redis, requests]

requires:
  - plan: 02-02
    provides: BaseFeed abstract class, config.py with QUALITY_WEIGHTS/FEED_INTERVALS

provides:
  - feeds/malwarebazaar.py — MalwareBazaarFeed with SHA-256 STIX pattern and disabled-if-no-key
  - feeds/threatfox.py — ThreatFoxFeed with ip:port split, multi-type IOC normalization, disabled-if-no-key

affects: [02-feed-ingestion-pipeline, main.py build_enabled_feeds()]

tech-stack:
  added: []
  patterns:
    - disabled-if-no-key guard in run() before super().run() (D-07)
    - SHA-256 STIX pattern with single-quoted property name (Pitfall 3)
    - ip:port extraction via rsplit(":", 1)[0] for IPv6 safety (Pitfall 2)
    - Single-quote escaping in IOC values before STIX interpolation (T-02-05-02)

key-files:
  created:
    - services/feed-orchestrator/feeds/malwarebazaar.py
    - services/feed-orchestrator/feeds/threatfox.py

key-decisions:
  - "SHA-256 STIX property name requires single quotes: [file:hashes.'SHA-256' = '...'] — hyphen in key name breaks unquoted STIX"
  - "ip:port split uses rsplit(':', 1)[0] not split(':')[0] — IPv6 addresses contain multiple colons"
  - "Unknown ThreatFox ioc_types (email, mutex) silently skipped — no error, no partial output"
  - "IOC values single-quote-escaped before STIX interpolation to prevent pattern injection (T-02-05-02)"
  - "Large result set threshold (>50000 rows) logged as warning, processing continues (T-02-05-04)"

requirements-completed: [FEED-02]

duration: 5min
completed: "2026-06-25"
status: complete
---

# Phase 02 Plan 05: MalwareBazaar + ThreatFox Feed Parsers Summary

**MalwareBazaarFeed and ThreatFoxFeed implementing JSON POST fetch, STIX normalization with SHA-256 single-quote quoting and ThreatFox ip:port split, both gracefully disabling when auth keys are absent**

## Performance

- **Duration:** ~5 min
- **Tasks:** 2/2
- **Files created:** 2

## Accomplishments

### Task 1: MalwareBazaarFeed (`feeds/malwarebazaar.py`)

- `run()` checks `MALWAREBAZAAR_AUTH_KEY`; if empty writes `status=disabled` via `hset(mapping=...)` and returns immediately (D-07 pattern)
- `fetch()` POSTs to `https://mb-api.abuse.ch/api/v1/` with `Auth-Key` header, validates `query_status == "ok"`, returns `data[]`
- `normalize()` builds `[file:hashes.'SHA-256' = '...']` STIX pattern — single quotes around `SHA-256` required because the hyphen would break unquoted STIX property access (Pitfall 3)
- Labels collected from `signature` + `tags` fields; empty strings filtered
- IOC values single-quote-escaped before interpolation (T-02-05-02)

### Task 2: ThreatFoxFeed (`feeds/threatfox.py`)

- Same disabled-if-no-key guard on `THREATFOX_AUTH_KEY`
- `fetch()` POSTs to `https://threatfox-api.abuse.ch/api/v1/` with `days=7`, validates `query_status`; logs warning if result exceeds 50 000 rows (T-02-05-04)
- `_parse_ioc(ioc_type, ioc_value)` maps five known types to STIX patterns:
  - `ip:port` → `rsplit(":", 1)[0]` extracts IP (Pitfall 2 — IPv6 safe), emits `[ipv4-addr:value = '...']`
  - `domain` → `[domain-name:value = '...']`
  - `url` → `[url:value = '...']`
  - `md5_hash` → `[file:hashes.MD5 = '...']`
  - `sha256_hash` → `[file:hashes.'SHA-256' = '...']`
  - Unknown types → `None` (silently skipped)

## Task Commits

1. **Task 1: MalwareBazaarFeed** — `cdcadf1`
2. **Task 2: ThreatFoxFeed** — `43a8bec`

## Verification Results

```
tests/test_malwarebazaar.py  2 passed
tests/test_threatfox.py      4 passed
Full regression (12 tests)   12 passed
grep -c SHA-256 malwarebazaar.py  → 4
grep -c SHA-256 threatfox.py      → 2
grep -c rsplit threatfox.py       → 3
python3 -c "from feeds.malwarebazaar import MalwareBazaarFeed; from feeds.threatfox import ThreatFoxFeed" → OK
```

## Decisions Made

- SHA-256 property name in STIX requires single quotes — `[file:hashes.'SHA-256' = '...']` — hyphen in the key name is illegal in unquoted STIX property access
- `rsplit(":", 1)[0]` chosen over `split(":")[0]` for ip:port extraction — handles IPv6 addresses that contain multiple colons
- Unknown `ioc_type` values return `None` from `_parse_ioc` and are silently skipped in `normalize()` — consistent with plan scope (email, mutex out of scope)
- Single-quote escaping (`value.replace("'", "\\'")`) applied before interpolation in all STIX patterns (T-02-05-02 mitigation)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

No new trust boundaries introduced beyond those in the plan's threat model. Auth-Key headers sent only via `requests` headers dict (not URL); exception messages from `requests` do not include headers by default (T-02-05-01 verified by design).

## Self-Check: PASSED

- `services/feed-orchestrator/feeds/malwarebazaar.py` — FOUND
- `services/feed-orchestrator/feeds/threatfox.py` — FOUND
- Commit `cdcadf1` — FOUND
- Commit `43a8bec` — FOUND
