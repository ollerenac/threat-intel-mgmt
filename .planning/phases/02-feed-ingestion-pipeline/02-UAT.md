---
status: complete
phase: 02-feed-ingestion-pipeline
source:
  - 02-01-SUMMARY.md
  - 02-02-SUMMARY.md
  - 02-03-SUMMARY.md
  - 02-04-SUMMARY.md
  - 02-05-SUMMARY.md
  - 02-06-SUMMARY.md
  - 02-07-SUMMARY.md
  - 02-08-SUMMARY.md
started: 2026-06-25T14:15:00Z
updated: 2026-06-25T14:35:00Z
---

## Current Test

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Stop feed-orchestrator, restart fresh with --profile platform --profile feeds. Container reaches healthy state; logs show 5 scheduler jobs registered and "Scheduler started"; no Python exceptions at boot.
result: pass

### 2. URLhaus IOCs Visible in OpenCTI
expected: Navigate to http://localhost:8080 → Observations → Indicators. Filter or scroll to find indicators sourced from URLhaus (labeled "urlhaus" or with url:value STIX pattern). At least hundreds of indicators should be present from the initial run.
result: pass

### 3. Feodo IOCs Visible in OpenCTI
expected: In OpenCTI Indicators list, find at least one indicator with pattern type [ipv4-addr:value = '...'] and label "c2" — these are Feodo botnet C2 entries. At least 2 should be present.
result: pass

### 4. Confidence Values on Indicators
expected: In the OpenCTI Indicators list, a Confidence column (or field in indicator detail) shows numeric values. URLhaus IOCs should show ~15–25, Feodo IOCs ~65 (newly seen), not 0 or blank.
result: pass
note: Score field shows 45 for a URLhaus IOC (correct: 1×25 + recency_bonus(5) + quality_weight(15) = 45)

### 5. MalwareBazaar and ThreatFox Gracefully Disabled
expected: With no MALWAREBAZAAR_AUTH_KEY or THREATFOX_AUTH_KEY set, both feeds log "status=disabled" at startup and do not crash.
result: pass
source: observed during cold-start (test 1) — logs showed "disabled: MALWAREBAZAAR_AUTH_KEY not configured" and "disabled: THREATFOX_AUTH_KEY not configured" with no exceptions

### 6. OTX Feed Active When Key Is Set
expected: Since OTX_API_KEY is configured, OTX feed should log status=ok after its run.
result: pass
source: observed during cold-start (test 1) — logs showed "[otx] initial run starting" and "[otx] run complete: 0 indicators inserted" (no disable/exception — key present, 0 new indicators due to dedup)

### 7. Pytest Suite: 25/25 Tests Pass
expected: From inside the feed-orchestrator container (or host if deps installed), run:
  cd services/feed-orchestrator && python3 -m pytest tests/ -q
  Output: 25 passed in under 1s. Zero failures, zero errors.
result: pass

### 8. Deduplicator Key Prefix (Technical Check)
expected: Inspect Redis dedup keys:
  docker compose exec redis redis-cli KEYS 'tim:ioc_seen:*' | head -3
  Keys should be of the form tim:ioc_seen:<64-char-sha256-hex>. No raw IOC values, no other key shapes.
result: pass

### 9. BaseFeed Importable Inside Container (Technical Check)
expected: Run:
  docker compose --profile platform --profile feeds exec feed-orchestrator python3 -c "from feeds.base import BaseFeed; print('ok')"
  Should print "ok" with exit code 0. No ImportError.
result: pass

### 10. Dockerfile pycti pin (auto-verified)
expected: Dockerfile uses python:3.12-slim base and requirements.txt pins pycti==6.4.11
result: pass
source: automated
coverage_id: 02-02-D1

### 11. config.py QUALITY_WEIGHTS importable (auto-verified)
expected: config.py importable with QUALITY_WEIGHTS['feodo']==30 and FEED_INTERVALS['urlhaus']==1
result: pass
source: automated
coverage_id: 02-02-D2

### 12. No hmset() calls in codebase (auto-verified)
expected: status.py and feeds/base.py use hset(mapping=...) — no deprecated hmset() calls
result: pass
source: automated
coverage_id: 02-02-D5

### 13. Dedup key count confirmed (auto-verified)
expected: 22,656 tim:ioc_seen: keys in Redis after initial run; restart does not duplicate indicator count
result: pass
source: automated
coverage_id: 02-08-D3

### 14. APScheduler 5 jobs registered (auto-verified)
expected: APScheduler logs show 5 feed jobs added and URLhaus fired on 1h schedule
result: pass
source: automated
coverage_id: 02-08-D4

## Summary

total: 14
passed: 14
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
