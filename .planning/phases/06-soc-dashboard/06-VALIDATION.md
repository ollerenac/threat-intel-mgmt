---
phase: 6
slug: soc-dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-26
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | curl smoke tests + manual browser (no JS test framework — D-03 spirit, no pytest for frontend) |
| **Config file** | none |
| **Quick run command** | `curl -sf http://localhost:3000 \| grep -q root && echo OK` |
| **Full suite command** | integration checklist below |
| **Estimated runtime** | ~90 seconds (excluding 60s Ollama PDF round-trip) |

---

## Sampling Rate

- **After every task commit:** Run `curl -sf http://localhost:3000 | grep -q root && echo OK`
- **After every plan wave:** Run the full integration checklist
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | DASH-06 | — | N/A | integration | `curl -sf http://localhost:3000 \| grep -q root` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | DASH-01 | — | N/A | integration | `curl -sf http://localhost:8001/feeds/status \| python3 -c "import sys,json;d=json.load(sys.stdin);assert len(d['feeds'])==5"` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | DASH-02 | — | N/A | integration | `curl -sf http://localhost:8003/stats \| python3 -c "import sys,json;d=json.load(sys.stdin);assert 'top_techniques' in d"` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 1 | DASH-03 | T-XSS | React JSX renders IOC values as text; no dangerouslySetInnerHTML | integration | `curl -sf 'http://localhost:8002/search?q=phishing&n_results=5' \| python3 -c "import sys,json;d=json.load(sys.stdin);assert 'results' in d"` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 1 | DASH-04 | T-REDIRECT | opencti_url used as-is (demo scope) | manual | Open dashboard, run query, click result — verify new tab opens to localhost:8080 | ❌ W0 | ⬜ pending |
| 06-04-01 | 04 | 1 | DASH-05 | — | N/A | integration | `curl -sf http://localhost:8003/briefings` returns JSON array | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/dashboard/` — entire scaffold does not exist yet; Wave 0 creates it
- [ ] `services/feed-orchestrator/api.py` — new file: FastAPI HTTP endpoints for `/feeds/status`
- [ ] `/stats` endpoint in briefing-generator — new endpoint returning `top_techniques` + IOC counts

*Wave 0 is the largest in this phase — the dashboard directory and two backend additions are all new files.*

---

## Full Integration Checklist

Run after `docker compose --profile platform --profile feeds --profile semantic --profile briefings --profile dashboard up -d`:

```bash
# 1. Dashboard HTML served
curl -sf http://localhost:3000 | grep -q root && echo "PASS: dashboard HTML served"

# 2. /feeds/status returns 5 feeds
curl -sf http://localhost:8001/feeds/status | python3 -c \
  "import sys,json; d=json.load(sys.stdin); assert len(d['feeds'])==5; print('PASS: feeds/status')"

# 3. /stats endpoint exists with top_techniques
curl -sf http://localhost:8003/stats | python3 -c \
  "import sys,json; d=json.load(sys.stdin); assert 'top_techniques' in d; print('PASS: /stats')"

# 4. CORS headers on backend services
curl -sf -H "Origin: http://localhost:3000" http://localhost:8003/health -I | \
  grep -q "access-control-allow-origin" && echo "PASS: CORS on briefing-generator"

# 5. Semantic search (GET, not POST)
curl -sf "http://localhost:8002/search?q=malware&n_results=3" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('PASS: search returns', d['count'], 'results')"

# 6. Briefings list
curl -sf http://localhost:8003/briefings | python3 -c \
  "import sys,json; d=json.load(sys.stdin); assert isinstance(d,list); print('PASS: briefings list')"
```

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Click result opens OpenCTI | DASH-04 | Requires browser interaction + new tab | Open http://localhost:3000, run a Threat Hunt query, click a result — verify new tab opens to `http://localhost:8080/...` |
| Overview polling updates live | DASH-01 | Requires time-based observation | Wait 30s on Overview — verify feed timestamps refresh without page reload |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
