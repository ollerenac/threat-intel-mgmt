---
phase: 06-soc-dashboard
plan: "03"
subsystem: dashboard-views
tags: [react, vite, fetch, polling, xss-prevention]
status: complete

dependency_graph:
  requires:
    - services/dashboard/src/App.jsx (Plan 02 scaffold)
    - services/dashboard/src/App.css (Plan 02 design tokens)
    - services/feed-orchestrator/api.py (GET /feeds/status — Plan 01)
    - services/briefing-generator/main.py (GET /stats, GET /briefings, POST /generate — Plan 01)
    - services/semantic-engine/main.py (GET /search?q= — existing, CORS added Plan 01)
  provides:
    - services/dashboard/src/api.js (7 fetch wrappers)
    - services/dashboard/src/views/Overview.jsx (30s poll, feed health + stats)
    - services/dashboard/src/views/ThreatHunt.jsx (GET search, opencti_url deeplink)
    - services/dashboard/src/views/Briefings.jsx (3s poll, PDF download)
  affects:
    - services/dashboard/src/App.jsx (placeholder replaced with real view routing)
    - services/dashboard/src/App.css (bug fix + feed-grid class)

tech_stack:
  added: []
  patterns:
    - Plain fetch + useEffect polling (D-02 — no React Query, no SWR, no axios)
    - setInterval with clearInterval cleanup in useEffect return (RESEARCH.md Pattern 1)
    - GET with encodeURIComponent query params for /search (RESEARCH.md Critical Finding)
    - opencti_url used directly as anchor href (RESEARCH.md Critical Finding)
    - React JSX text children only — no dangerouslySetInnerHTML (T-06-03-01 mitigation)

key_files:
  created:
    - services/dashboard/src/api.js
    - services/dashboard/src/views/Overview.jsx
    - services/dashboard/src/views/ThreatHunt.jsx
    - services/dashboard/src/views/Briefings.jsx
  modified:
    - services/dashboard/src/App.jsx
    - services/dashboard/src/App.css

decisions:
  - "searchIOCs uses GET with encodeURIComponent — not POST — semantic-engine/main.py line 41 confirms @app.get('/search') with query params"
  - "pdfUrl returns a string URL, not a fetch call — used as anchor href with download attribute"
  - "opencti_url from search results used directly as href — semantic-engine already returns full URL; no reconstruction from id"
  - "query.length > 500 guard in ThreatHunt mirrors semantic-engine server-side 400 limit (T-06-03-03)"
  - "clearInterval inside status check branch in handleGenerate — not on unmount — poll is local to the generate call scope"

metrics:
  duration: "~10m"
  completed: "2026-06-26"
  tasks_completed: 2
  files_changed: 6

requirements_satisfied:
  - DASH-01 (frontend: Overview.jsx polls /feeds/status, renders feed health cards)
  - DASH-02 (frontend: Overview.jsx polls /stats, renders ioc_count_24h and top_techniques)
  - DASH-03 (frontend: ThreatHunt.jsx calls GET /search, renders ranked results)
  - DASH-04 (frontend: each result is an anchor with href=opencti_url, target=_blank)
  - DASH-05 (frontend: Briefings.jsx lists briefings, polls /briefings/{id}, shows PDF download on done)
---

# Phase 6 Plan 03: View Components and API Layer — Summary

**One-liner:** api.js centralizes 7 fetch wrappers (searchIOCs as GET with query params, pdfUrl as string); Overview polls /feeds/status and /stats every 30s with clearInterval cleanup; ThreatHunt uses opencti_url directly as href; Briefings polls 3s and shows PDF only on done status; App.jsx wired to real components.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write api.js and Overview.jsx | f8ff073 | src/api.js, src/views/Overview.jsx |
| 2 | Write ThreatHunt.jsx and Briefings.jsx; wire App.jsx | e9e83f5 | src/views/ThreatHunt.jsx, src/views/Briefings.jsx, src/App.jsx, src/App.css |

## What Was Built

### Task 1: api.js and Overview.jsx

`services/dashboard/src/api.js`:
- Three URL constants at top: `FEED_URL=http://localhost:8001`, `SEARCH_URL=http://localhost:8002`, `BRIEFING_URL=http://localhost:8003` (hardcoded per Pitfall 5 — Vite bakes env vars at build time)
- `getFeedsStatus()` — GET /feeds/status
- `getStats()` — GET /stats
- `searchIOCs(query, n=10)` — GET /search?q={encodeURIComponent(query)}&n_results={n} (GET, not POST)
- `postGenerate(periodHours)` — POST /generate with JSON body
- `getBriefing(id)` — GET /briefings/{id}
- `listBriefings()` — GET /briefings
- `pdfUrl(id)` — returns string `${BRIEFING_URL}/briefings/${id}/pdf` (not a fetch call)

`services/dashboard/src/views/Overview.jsx`:
- Single useEffect with empty deps, loads getFeedsStatus + getStats in parallel via Promise.all
- 30s setInterval, `return () => clearInterval(id)` cleanup on unmount
- `statusClass()` helper: maps feed.status to CSS class (ok/error/never_run/stale by timestamp comparison)
- Feed health grid: one `.card` per feed showing name, last_run, ioc_count (28px), status dot
- Stats row: ioc_count_24h card + ATT&CK techniques ordered list formatted as `T{id} — {name} ({count})`
- Empty state: "No feeds configured" / "Feed orchestrator returned no data. Check service health."
- Error state: destructive color inline style

### Task 2: ThreatHunt.jsx, Briefings.jsx, App.jsx

`services/dashboard/src/views/ThreatHunt.jsx`:
- Controlled input with Enter key handler and "Search" button (btn-primary)
- Guard: `if (!query || query.length > 500) return` — mirrors semantic-engine server-side limit
- Each result is `<a href={result.opencti_url} target="_blank" rel="noopener noreferrer">` — opencti_url used directly
- Score badge: `result.score.toFixed(2)` with className="score-badge"
- Loading: "Searching…" replaces results list during fetch
- Empty state after search: "No results found" / "Try a broader query…"

`services/dashboard/src/views/Briefings.jsx`:
- useEffect on mount: listBriefings().then(setBriefings) with error handler
- Period selector: values 24 / 72 / 168 with labels "Last 24 hours" / "Last 72 hours" / "Last 7 days"
- handleGenerate: POST /generate → setInterval(3s) → getBriefing; on done/error: clearInterval inside branch, setGenerating(false), refresh list
- "Generating…" label shown alongside disabled button while polling
- PDF anchor shown only when `b.status === 'done'`; uses `pdfUrl(b.briefing_id)` with `download` attribute
- Empty state: "No briefings yet" / "Select a time period and click Generate Briefing…"

`services/dashboard/src/App.jsx`:
- Imports Overview, ThreatHunt, Briefings from ./views/
- `VIEWS` object maps tab name to component
- `const View = VIEWS[tab]` + `<View />` replaces placeholder `<div className="tab-content">{tab}</div>`
- Tab nav logic and className unchanged

`services/dashboard/src/App.css` (auto-fixed):
- Bug fix: `padding: var(--color-md)` → `padding: var(--space-md)` in `.card` (used wrong token namespace)
- Added `.feed-grid` with `display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr))`

## Verification

```
encodeURIComponent in searchIOCs: PASS
searchIOCs method POST: not found — PASS (uses GET)
pdfUrl in api.js: PASS (2 occurrences — export + usage in Briefings)
clearInterval in Overview.jsx: 1 — PASS
return () => clearInterval in Overview.jsx: PASS
"No feeds configured" in Overview.jsx: PASS
ioc_count in Overview.jsx: PASS
ioc_count_24h in Overview.jsx: PASS
top_techniques in Overview.jsx: PASS
opencti_url in ThreatHunt.jsx: PASS
query.length > 500 in ThreatHunt.jsx: PASS
target="_blank" in ThreatHunt.jsx: PASS
rel="noopener noreferrer" in ThreatHunt.jsx: PASS
clearInterval in Briefings.jsx: PASS
pdfUrl in Briefings.jsx: PASS
b.status === 'done' in Briefings.jsx: PASS
value={24}, value={72}, value={168}: PASS
"Last 7 days" in Briefings.jsx: PASS
Overview/ThreatHunt/Briefings imports in App.jsx: PASS
<View /> render in App.jsx: PASS
dangerouslySetInnerHTML in src/: 0 occurrences — PASS
npm run build: ✓ built in 82ms — PASS
dist/index.html contains "SOC Dashboard": PASS
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed var(--color-md) typo in App.css .card**
- **Found during:** Task 2 — reading App.css before adding feed-grid
- **Issue:** `.card { padding: var(--color-md) }` used the color token namespace instead of spacing; `--color-md` is undefined; padding resolved to zero
- **Fix:** Changed to `var(--space-md)` — correct spacing token
- **Files modified:** services/dashboard/src/App.css
- **Commit:** e9e83f5

## Known Stubs

None. All five files wire to real backend API endpoints. The components display loading/empty/error states when services are unreachable — these are correctness states, not stubs.

## Threat Flags

None. All mitigations from the plan's threat model applied:
- T-06-03-01: React JSX renders all values as text nodes; no dangerouslySetInnerHTML anywhere in src/
- T-06-03-02: `rel="noopener noreferrer"` on all external anchors; opencti_url accepted as-is (demo scope)
- T-06-03-03: `query.length > 500 return early` client-side guard in ThreatHunt before fetch
- T-06-03-04: clearInterval local to handleGenerate scope; cleared on done/error (acceptable for demo)

## Self-Check: PASSED

- `services/dashboard/src/api.js` exists, contains encodeURIComponent, pdfUrl string return ✓
- `services/dashboard/src/views/Overview.jsx` exists, contains clearInterval + return cleanup ✓
- `services/dashboard/src/views/ThreatHunt.jsx` exists, contains opencti_url, length guard, noopener ✓
- `services/dashboard/src/views/Briefings.jsx` exists, clearInterval in status branch, PDF only on done ✓
- `services/dashboard/src/App.jsx` imports and renders all three view components ✓
- No dangerouslySetInnerHTML in any src/ file ✓
- Commits f8ff073 and e9e83f5 exist ✓
- npm run build passes, dist/index.html contains "SOC Dashboard" ✓
