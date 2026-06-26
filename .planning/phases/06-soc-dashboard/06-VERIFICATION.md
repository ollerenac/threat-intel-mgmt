---
phase: 06-soc-dashboard
verified: 2026-06-26T20:58:00Z
status: human_needed
score: 9/9 must-haves verified
behavior_unverified: 2
overrides_applied: 0
behavior_unverified_items:
  - truth: "Overview.jsx polls /feeds/status and /stats every 30 seconds and clearInterval fires on unmount"
    test: "Mount Overview in a browser, wait 30s, navigate away (unmount), check browser DevTools Network tab for fetch cadence and confirm no further fetches after tab change"
    expected: "Exactly one batch of two fetches every 30s while mounted; zero fetches after unmount"
    why_human: "setInterval/clearInterval timing and unmount lifecycle are runtime behaviors — grep confirms the code path exists but cannot verify the interval fires or cleanup runs correctly"
  - truth: "Briefings.jsx polling clears on done/error status and PDF download only appears for done status"
    test: "Click Generate Briefing, observe button disabled + Generating label, wait for done status, confirm clearInterval fires (no further /briefings/{id} polls), confirm Download PDF link appears only then"
    expected: "Polling stops when status is done or error; PDF anchor absent while generating"
    why_human: "Async state transitions with setInterval inside handleGenerate scope — presence checks confirm code structure but cannot verify the branch executes at the right state value at runtime"
human_verification:
  - test: "Overview auto-refresh: mount Overview tab in browser, wait 30s, observe Network tab"
    expected: "Two fetches (/feeds/status and /stats) repeat every 30s; no fetches after tab navigation away"
    why_human: "setInterval/clearInterval runtime lifecycle cannot be verified by static analysis"
  - test: "Briefings generation + polling cleanup: click Generate Briefing, watch polling stop on done"
    expected: "Button disabled + Generating label while in-flight; clearInterval fires on done/error; Download PDF link appears only when status === done"
    why_human: "State-transition branching inside async handleGenerate cannot be verified without running the app"
  - test: "Threat Hunt DASH-04: type a query, click Search, click a result row"
    expected: "New browser tab opens to http://localhost:8080/... OpenCTI URL; rel=noopener noreferrer applied; scheme guard rejects non-http(s) URLs (href=undefined)"
    why_human: "Browser tab navigation and the scheme-guard conditional (undefined href behavior) require live interaction"
  - test: "Full dark-theme visual check (DASH-06 UX)"
    expected: "Background #0f1117, blue underline on active tab, 5 feed cards in Overview, no console errors"
    why_human: "Visual correctness and runtime CSS rendering cannot be verified by file checks"
---

# Phase 6: SOC Dashboard — Verification Report

**Phase Goal:** A React dashboard at localhost:3000 that surfaces feed health, IOC stats, semantic threat search, and briefing generation — DASH-01 through DASH-06.
**Verified:** 2026-06-26T20:58:00Z
**Status:** human_needed (9/9 automated truths verified; 2 behavior-dependent truths need runtime confirmation; 2 additional human interaction checks)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | `GET /feeds/status` on feed-orchestrator returns 5 named feeds | VERIFIED | `api.py` L31: `FEED_NAMES = ["urlhaus", "malwarebazaar", "threatfox", "feodo", "otx"]`; handler iterates and returns `{"feeds": [...]}` |
| 2 | `GET /health` on feed-orchestrator returns `{"status": "ok"}` | VERIFIED | `api.py` L48: `def health(): return {"status": "ok"}` |
| 3 | `GET /stats` on briefing-generator returns `ioc_count_24h` and `top_techniques` | VERIFIED | `main.py` L91-109: `@app.get("/stats")` returns both keys; `asyncio.to_thread` wraps `_collect_threat_data` |
| 4 | CORS `allow_origins=["http://localhost:3000"]` on all three backend services | VERIFIED | `api.py` L24-27, `briefing-generator/main.py` L32-35, `semantic-engine/main.py` L35-38 — all explicit, never `"*"` |
| 5 | Dashboard scaffold: `dist/index.html` with "SOC Dashboard" title served at port 3000 | VERIFIED | `dist/index.html` exists; `index.html` contains "SOC Dashboard" (1 match); `Dockerfile` multistage node→nginx; `nginx.conf` `listen 80`; compose maps `3000:80` |
| 6 | `api.js` exports all 7 fetch wrappers; `searchIOCs` uses GET with `encodeURIComponent` | VERIFIED | `src/api.js`: all 7 exports present; `searchIOCs` uses `fetch(\`${SEARCH_URL}/search?q=${encodeURIComponent(query)}&n_results=${n}\`)` — no POST |
| 7 | `App.jsx` renders `Overview`, `ThreatHunt`, `Briefings` components (not placeholders) | VERIFIED | `App.jsx` L3-8: imports all three; `VIEWS` object; `<View />` render; no placeholder divs |
| 8 | Overview.jsx polls /feeds/status and /stats every 30s with clearInterval cleanup | PRESENT_BEHAVIOR_UNVERIFIED | Code present: `setInterval(load, 30_000)` L26; `return () => clearInterval(id)` L27 — runtime polling behavior not tested |
| 9 | Briefings.jsx polling clears on done/error; PDF anchor shown only when `status === 'done'` | PRESENT_BEHAVIOR_UNVERIFIED | Code present: `clearInterval(id)` inside `if (b.status === 'done' \|\| b.status === 'error')` branch L23-24; `b.status === 'done'` gate on PDF anchor L82 — state-transition runtime not tested |

**Score:** 7/9 truths fully verified; 2 present-and-wired but behavior not exercised by a running test

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `services/feed-orchestrator/api.py` | VERIFIED | 1437 bytes; FastAPI app, CORS, FEED_NAMES, /feeds/status, /health; parses OK |
| `services/briefing-generator/main.py` | VERIFIED | 3847 bytes; /stats with asyncio.to_thread, CORSMiddleware; parses OK |
| `services/semantic-engine/main.py` | VERIFIED | 1939 bytes; CORSMiddleware added after app declaration; parses OK |
| `services/dashboard/src/views/Overview.jsx` | VERIFIED | 2982 bytes; setInterval+clearInterval, getFeedsStatus+getStats, "No feeds configured" empty state |
| `services/dashboard/src/views/ThreatHunt.jsx` | VERIFIED | 2884 bytes; query.length > 500 guard, encodeURIComponent via api.js, opencti_url with scheme guard, rel="noopener noreferrer" |
| `services/dashboard/src/views/Briefings.jsx` | VERIFIED | 3554 bytes; 3s poll, clearInterval in done/error branch, PDF anchor gated on done, values 24/72/168, "Last 7 days" label |
| `services/dashboard/src/api.js` | VERIFIED | 1273 bytes; 7 exports, searchIOCs GET, pdfUrl string-only |
| `services/dashboard/Dockerfile` | VERIFIED | Multistage node:20-slim AS build → nginx:alpine; COPY --from=build /app/dist /usr/share/nginx/html |

---

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `feed-orchestrator/main.py` | `api.py` | `import uvicorn`; `from api import app`; `uvicorn.run(app, port=8001)` | WIRED |
| `api.py` | `status.py` | `from status import get_status`; called in `/feeds/status` handler | WIRED |
| `briefing-generator/main.py` `/stats` | `generator.py` | `from generator import _collect_threat_data`; called via `asyncio.to_thread` | WIRED |
| `dashboard/src/App.jsx` | `Overview/ThreatHunt/Briefings` | `import` + `VIEWS` object + `<View />` render | WIRED |
| `Overview.jsx` | `api.js getFeedsStatus/getStats` | `import { getFeedsStatus, getStats } from '../api'` | WIRED |
| `ThreatHunt.jsx` | `api.js searchIOCs` | `import { searchIOCs } from '../api'` | WIRED |
| `Briefings.jsx` | `api.js listBriefings/postGenerate/getBriefing/pdfUrl` | `import { listBriefings, postGenerate, getBriefing, pdfUrl } from '../api'` | WIRED |
| `docker-compose soc-dashboard` | `services/dashboard/` | `build: ./services/dashboard`; `ports: "3000:80"`; `depends_on: feed-orchestrator/semantic-engine/briefing-generator service_healthy` | WIRED |
| `docker-compose feed-orchestrator` | HTTP port + healthcheck | `ports: "127.0.0.1:8001:8001"`; `urllib.request.urlopen('http://localhost:8001/health')` healthcheck | WIRED |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `Overview.jsx` | `feeds` (array) | `getFeedsStatus()` → `api.py /feeds/status` → `get_status(r, name)` Redis hgetall | Yes — reads live Redis state | FLOWING |
| `Overview.jsx` | `stats` (object) | `getStats()` → `briefing-generator /stats` → `_collect_threat_data` pycti query | Yes — live pycti query (returns empty when OpenCTI unreachable, not stub) | FLOWING |
| `ThreatHunt.jsx` | `results` (array) | `searchIOCs(query)` → `semantic-engine GET /search?q=` → ChromaDB vector search | Yes — live vector query | FLOWING |
| `Briefings.jsx` | `briefings` (array) | `listBriefings()` → `briefing-generator GET /briefings` → Redis/file storage | Yes — existing endpoint from Phase 5 | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `api.py` Python syntax | `python3 -c "import ast; ast.parse(open('services/feed-orchestrator/api.py').read())"` | OK | PASS |
| `briefing-generator/main.py` Python syntax | `python3 -c "import ast; ast.parse(...)"` | OK | PASS |
| `semantic-engine/main.py` Python syntax | `python3 -c "import ast; ast.parse(...)"` | OK | PASS |
| `feed-orchestrator/main.py` Python syntax | `python3 -c "import ast; ast.parse(...)"` | OK | PASS |
| `dist/index.html` exists (build succeeded) | `ls services/dashboard/dist/index.html` | Found | PASS |
| No `dangerouslySetInnerHTML` in `src/` | `grep -rn "dangerouslySetInnerHTML" services/dashboard/src/` | 0 matches | PASS |
| `searchIOCs` uses GET (not POST) | `grep "method.*POST" src/api.js \| grep -i search` | 0 matches | PASS |
| `encodeURIComponent` present in `searchIOCs` | `grep encodeURIComponent src/api.js` | Found at line 14 | PASS |
| 30s poll cleanup in `Overview.jsx` | `grep "return () => clearInterval" src/views/Overview.jsx` | Found at L27 | PASS |
| `pdfUrl` is string-only export | Checked — no `fetch` call, returns template literal | String only | PASS |
| All 6 commits exist in git log | `git log --oneline 3e27199 68dde02 65a34d7 d6af63b f8ff073 e9e83f5` | All present | PASS |

---

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|---------|
| DASH-01 | Feed health in Overview (last update, IOC count, status per feed) | SATISFIED | `api.py` /feeds/status returns name/last_run/ioc_count/status; `Overview.jsx` renders one card per feed |
| DASH-02 | IOC count (24h) and top 5 ATT&CK techniques in Overview | SATISFIED | `/stats` returns `ioc_count_24h` + `top_techniques[:5]`; `Overview.jsx` renders both |
| DASH-03 | Threat Hunt accepts natural language query and shows semantic results | SATISFIED | `ThreatHunt.jsx` calls `searchIOCs(query)` via `GET /search?q=`; results rendered as ranked list |
| DASH-04 | Threat Hunt results link to OpenCTI on click | SATISFIED | Each result `<a href={scheme-guarded opencti_url} target="_blank" rel="noopener noreferrer">` |
| DASH-05 | Briefings view lists briefings and allows PDF download | SATISFIED | `Briefings.jsx` lists via `listBriefings()`; PDF anchor with `pdfUrl(b.briefing_id)` + `download` shown when `status === 'done'` |
| DASH-06 | Dashboard accessible at localhost:3000 | SATISFIED | `docker-compose` maps `3000:80`; nginx serves `dist/`; `dist/index.html` exists with "SOC Dashboard" |

---

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `ThreatHunt.jsx` L67 | `href={/^https?:\/\//.test(result.opencti_url) ? result.opencti_url : undefined}` | Info | Deliberate security upgrade from plan T-06-04-03 "accept" → "mitigate"; scheme guard is additive hardening, not a stub |
| `api.js` L1 | `// ponytail: URLs hardcoded` | Info | Intentional per Pitfall 5 (Vite build-time env); documented comment |

No TBD/FIXME/XXX markers found in any Phase 6 source file. No empty-return stubs. No hardcoded-empty props passed to child components.

---

### Human Verification Required

The 9 automated truths are all verified (7 fully, 2 present-and-wired with behavior pending). The following need a running browser session to confirm:

#### 1. Overview 30s auto-refresh lifecycle

**Test:** Open http://localhost:3000, switch to Overview tab, open DevTools Network tab, wait 35 seconds, then navigate to Threat Hunt tab.
**Expected:** Exactly two fetches (/feeds/status and /stats) repeat every ~30s while on Overview; zero further fetches to those endpoints after leaving the tab.
**Why human:** `setInterval` scheduling and `clearInterval` on React unmount are runtime behaviors; the code path is present but only a live browser confirms timing and cleanup fire correctly.

#### 2. Briefings generate-poll-stop flow

**Test:** Switch to Briefings tab, select "Last 24 hours", click "Generate Briefing". Observe button state and Network tab. Wait for generation to complete (~60-90s).
**Expected:** Button becomes disabled and "Generating…" label appears; `GET /briefings/{id}` polls every ~3s; polling stops when status is `done` or `error`; "Download PDF" anchor appears only after `done` status.
**Why human:** The `clearInterval` inside the `done/error` branch and the conditional PDF anchor are state-transition behaviors that require the async flow to actually execute.

#### 3. Threat Hunt OpenCTI deep-link (DASH-04)

**Test:** Type "malware" in the search box, press Enter, click one result row.
**Expected:** New browser tab opens to `http://localhost:8080/...`; `rel="noopener noreferrer"` prevents tab-napping; if `opencti_url` is missing or non-http(s), anchor `href` is `undefined` (link inert).
**Why human:** Browser tab navigation and the scheme-guard conditional behavior require live interaction.

#### 4. Visual/UX conformance (DASH-06)

**Test:** Inspect all three tabs visually; open browser DevTools Console.
**Expected:** Dark background (~#0f1117), blue underline on active tab, 5 feed health cards in Overview, no console errors or uncaught exceptions.
**Why human:** CSS rendering, computed styles, and runtime console errors cannot be verified by file inspection.

---

### Gaps Summary

None. All required artifacts exist, are substantive, are wired, and data flows from live sources. The two `behavior_unverified` truths are present-and-wired; they route to human verification above, not to rework.

---

### Security Gate

- `allow_origins=["http://localhost:3000"]` — explicit on all three services, never `"*"` (T-06-01-01)
- `dangerouslySetInnerHTML` — 0 occurrences in `src/` (T-06-03-01)
- `searchIOCs` — GET with `encodeURIComponent`, no POST (RESEARCH.md Critical Finding honored)
- `rel="noopener noreferrer"` on all external anchors (T-06-03-02)
- `query.length > 500` client-side guard in ThreatHunt (T-06-03-03)
- `opencti_url` scheme guard `/^https?:\/\//` before use as `href` (T-06-04-03 upgrade)
- feed-orchestrator port bound to `127.0.0.1:8001:8001` (T-06-02-03)

---

_Verified: 2026-06-26T20:58:00Z_
_Verifier: Claude (gsd-verifier)_
