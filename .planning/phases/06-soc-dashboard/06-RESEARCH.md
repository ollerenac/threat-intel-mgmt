# Phase 06: SOC Dashboard — Research

**Researched:** 2026-06-26
**Domain:** React/Vite frontend + FastAPI backend additions + Docker/nginx packaging
**Confidence:** HIGH (all findings sourced from live codebase reads and npm registry)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Vite + React, plain JSX (no TypeScript). `npm create vite@latest` scaffold under `services/dashboard/`.
- **D-02:** Plain `fetch` + `useEffect` for all data fetching. No React Query, no SWR, no axios. Polling via `setInterval` / `clearInterval` inside useEffect cleanup.
- **D-03:** No component library, no icon library. Plain CSS or minimal inline styles.
- **D-04:** Feed health from `GET /feeds/status` on feed-orchestrator (port 8001) — new endpoint.
- **D-05:** Top ATT&CK techniques from `GET /stats` on briefing-generator (port 8003) — new endpoint. Returns `{"top_techniques": [{"id": "T1566", "name": "Phishing", "count": N}, ...]}` for last 24h.
- **D-06:** Total IOC count (last 24h) also from `/stats` on briefing-generator.
- **D-07:** Threat Hunt calls `POST /search` on semantic-engine (port 8002) with `{"query": text, "n_results": 10}`.
- **D-08:** Deep-link format: `http://localhost:8080/dashboard/observations/indicators/{opencti_id}`.
- **D-09:** Briefings period selector: 24h / 72h / 7d → `period_hours` 24 / 72 / 168. POST `/generate` on briefing-generator.
- **D-10:** Auto-poll every 3 seconds after POST /generate returns `briefing_id`. Stop on `status == "done"` or `"error"`.
- **D-11:** PDF download via `GET /briefings/{id}/pdf` as `<a href=... download>`.
- **D-12:** Multi-stage Dockerfile — `node:20-slim` build, `nginx:alpine` serve. Final image ~15MB.
- **D-13:** Compose profile `dashboard`. Port mapping `3000:80` (nginx on 80 → host 3000). Start: `docker compose --profile platform --profile dashboard up -d`.
- **D-14:** `CORSMiddleware(allow_origins=["http://localhost:3000"])` added to feed-orchestrator, semantic-engine, briefing-generator.

### Claude's Discretion

- File structure within `services/dashboard/src/`
- CSS approach (plain CSS file vs. inline styles)
- How to organize the three view components
- nginx.conf content (port, gzip, try_files for SPA)
- How `GET /stats` aggregates attack_pattern data from `_collect_threat_data()`

### Deferred Ideas (OUT OF SCOPE)

- TypeScript
- Any component or icon library
- Mobile/responsive layout
- Authentication
- Production hardening (TLS, RBAC, audit logging)
- Seed demo data
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | Overview view: feed health (last update, IOC count, status per feed) | `GET /feeds/status` — new endpoint on feed-orchestrator; status data in Redis `tim:feed_status:{name}` hashes |
| DASH-02 | Overview: IOC count last 24h + top 5 ATT&CK techniques | `GET /stats` — new endpoint on briefing-generator; reuses `_collect_threat_data()` + `attack_pattern.list()` |
| DASH-03 | Threat Hunt: natural language query → semantic results | `GET /search?q=...&n_results=10` on semantic-engine (port 8002) |
| DASH-04 | Threat Hunt results link to OpenCTI object | `opencti_url` field in each result; deep-link to `localhost:8080` |
| DASH-05 | Briefings view: list briefings + PDF download | `GET /briefings`, `POST /generate`, `GET /briefings/{id}`, `GET /briefings/{id}/pdf` on briefing-generator |
| DASH-06 | Dashboard at localhost:3000, no setup after `docker compose up -d` | nginx:alpine serving Vite dist, compose profile `dashboard`, port `3000:80` |
</phase_requirements>

---

## Summary

Phase 6 is a pure integration and packaging phase. No new AI capabilities. The work divides into four buckets:

1. **Two new backend endpoints** — `GET /feeds/status` on feed-orchestrator and `GET /stats` on briefing-generator. These are small FastAPI additions; the data already exists (Redis hashes, pycti call).
2. **React/Vite frontend** — three-view SPA under `services/dashboard/`. All data fetched via plain `fetch`. No external npm dependencies beyond Vite + React core.
3. **Docker packaging** — multi-stage Dockerfile, nginx.conf for SPA routing, docker-compose wiring under `dashboard` profile.
4. **CORS middleware** — two-line addition to three existing FastAPI services.

The biggest structural finding is that **feed-orchestrator is currently not an HTTP server at all** — it runs `signal.pause()` and has no FastAPI app, no uvicorn, no ports exposed. Adding `GET /feeds/status` requires converting it to a hybrid service: keep the scheduler thread, add a FastAPI app served by uvicorn in the foreground.

**Primary recommendation:** Treat this as four independent work streams that can be sequenced as: (1) backend endpoint additions → (2) CORS middleware → (3) Vite scaffold → (4) Docker packaging.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Feed health display | Browser/Client | API (feed-orchestrator) | Browser polls /feeds/status; orchestrator reads Redis |
| IOC count + ATT&CK techniques | Browser/Client | API (briefing-generator) | Browser polls /stats; generator queries pycti |
| Semantic search | Browser/Client | API (semantic-engine) | User triggers; browser calls /search and renders results |
| OpenCTI deep-link | Browser/Client | — | Pure anchor href; no backend involvement |
| Briefing generation + poll | Browser/Client | API (briefing-generator) | POST /generate → poll GET /briefings/{id} |
| PDF download | Browser/Client | API (briefing-generator) | Anchor href to /briefings/{id}/pdf |
| Static asset serving | CDN/Static (nginx) | — | nginx:alpine serves Vite dist/ |
| CORS enforcement | API / Backend | — | FastAPI CORSMiddleware on all three called services |

---

## Critical Finding: feed-orchestrator Has No HTTP Server

**[VERIFIED: codebase read]**

`services/feed-orchestrator/main.py` is a pure scheduler process. It:
- Has no `app = FastAPI(...)` declaration
- Has no uvicorn invocation
- Calls `signal.pause()` to block the main thread
- Has no port exposed in docker-compose (`profiles: [feeds]`, no `ports:` key)
- `requirements.txt` does NOT include fastapi or uvicorn

**Consequence for planning:** Adding `GET /feeds/status` requires:
1. Add `fastapi` and `uvicorn` to `services/feed-orchestrator/requirements.txt`
2. Create a FastAPI app in `main.py` (or a new `api.py`)
3. Run uvicorn in a thread alongside the scheduler (uvicorn's `Server.serve()` in a daemon thread, or use `threading.Thread`)
4. Expose port `8001` in docker-compose under the `feeds` profile
5. Add `depends_on: feed-orchestrator` to soc-dashboard in docker-compose
6. Add urllib.request healthcheck for the new HTTP endpoint

**Pattern (from semantic-engine):** Use `asynccontextmanager` lifespan to start the scheduler as a background asyncio task, OR run uvicorn in the main thread and the scheduler in a daemon thread.

**Simpler approach given this is a demo:** Run FastAPI/uvicorn in the main thread via `uvicorn.run(app, ...)`. Move the scheduler start into a FastAPI lifespan startup hook. The feed runs are already threaded via APScheduler.

---

## Critical Finding: semantic-engine /search Is GET, Not POST

**[VERIFIED: codebase read]**

`services/semantic-engine/main.py` line 41:
```python
@app.get("/search")
def search_iocs(q: str = "", n_results: int = 10):
```

The endpoint is `GET /search?q={query}&n_results=10`, not `POST /search` with a JSON body as stated in CONTEXT.md D-07. The dashboard must call it as a GET with query params, not POST with a body.

---

## Critical Finding: docker-compose Port Mismatch

**[VERIFIED: codebase read]**

The existing `soc-dashboard` stub in docker-compose.yml (line 362) has:
```yaml
ports:
  - "3000:3000"
```

But D-12/D-13 specify nginx listens on port **80** inside the container, mapped to host port 3000. The correct mapping is `"3000:80"`. This must be fixed when wiring the dashboard service.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vite | 8.1.0 | Build tool + dev server | [VERIFIED: npm registry] — fastest Vite build, no TypeScript overhead |
| react | 19.2.7 | UI library | [VERIFIED: npm registry] — project decision D-01 |
| react-dom | 19.2.7 | DOM renderer | [VERIFIED: npm registry] — paired with react |
| @vitejs/plugin-react | 6.0.3 | JSX transform for Vite | [VERIFIED: npm registry] — standard Vite+React pairing |

### Npm packages NOT needed (confirmed by decisions)
- No axios (plain fetch — D-02)
- No react-router (three tabs via `useState` active tab — D-03 spirit)
- No component library (D-03)
- No testing framework beyond what exists in Python services

**Installation (Vite scaffold):**
```bash
npm create vite@latest dashboard -- --template react
cd dashboard
npm install
```

This produces `vite`, `react`, `react-dom`, and `@vitejs/plugin-react` in package.json. No additional npm packages needed.

### Python additions (feed-orchestrator only)
```
fastapi==0.115.14    # match briefing-generator version
uvicorn              # no version pin — match briefing-generator pattern
```

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| vite | npm | ~5 yrs | 140M/wk | github.com/vitejs/vite | SUS (too-new patch) | Approved — canonical package, 140M downloads; seam flags latest patch release date not project age |
| react | npm | ~12 yrs | 148M/wk | github.com/facebook/react | SUS (too-new patch) | Approved — canonical package |
| react-dom | npm | ~12 yrs | 139M/wk | github.com/facebook/react | SUS (too-new patch) | Approved — canonical package |
| @vitejs/plugin-react | npm | ~4 yrs | ~60M/wk | github.com/vitejs/vite | [ASSUMED] OK | Approved — official Vite org package |

**Packages removed due to SLOP verdict:** none

**Note on SUS verdicts:** The legitimacy seam flagged `vite`, `react`, `react-dom` as `too-new` because their *latest patch* published recently. All three are canonical packages with 100M+ weekly downloads and decade-long histories. The `too-new` signal applies to their latest patch version date, not the packages themselves. No human-verify checkpoint needed for these.

---

## API Contracts (Verified from Codebase)

### GET /feeds/status (feed-orchestrator, port 8001) — NEW

Status data source: Redis hashes at `tim:feed_status:{feed_name}`.

Feed names (from `build_enabled_feeds()` in main.py): `urlhaus`, `malwarebazaar`, `threatfox`, `feodo`, `otx` — exact name strings come from each feed's `.name` attribute (read `feeds/base.py` to confirm).

Redis hash fields per feed (`status.py`):
```
last_run   — ISO-8601 UTC string (or absent if never run)
ioc_count  — string-encoded integer
status     — "ok" | "error" | "running" | "never_run" | "disabled"
error_msg  — string (max 500 chars)
```

Proposed `/feeds/status` response:
```json
{
  "feeds": [
    {
      "name": "urlhaus",
      "last_run": "2026-06-26T14:00:00+00:00",
      "ioc_count": 1240,
      "status": "ok"
    }
  ]
}
```

The endpoint reads all 5 known feed keys from Redis and returns them. If a key doesn't exist yet (feed never ran), return `{"name": "...", "last_run": null, "ioc_count": 0, "status": "never_run"}`.

### GET /stats (briefing-generator, port 8003) — NEW

Reuses `_collect_threat_data(client, period_hours=24)` from `generator.py` — already queries `client.attack_pattern.list()`. No Ollama call. Read-only.

Proposed response shape (per D-05):
```json
{
  "ioc_count_24h": 47,
  "top_techniques": [
    {"id": "T1566", "name": "Phishing", "count": 12},
    {"id": "T1059", "name": "Command and Scripting Interpreter", "count": 8}
  ]
}
```

`ioc_count_24h` = `len(data["indicators"])` (already filtered to 24h in `_collect_threat_data`).
`top_techniques` = top 5 from `data["attack_patterns"]` with count derived from cross-referencing indicators (or simply the count of patterns returned, since attack_pattern.list already filters by 24h).

**Implementation note:** `_collect_threat_data` uses `asyncio.to_thread` in the async context — but `/stats` can call `_run_stats_sync()` directly via `asyncio.to_thread` the same way `run_generate` does.

### GET /search (semantic-engine, port 8002) — EXISTS (corrected from CONTEXT.md)

**Endpoint is GET with query params, not POST with body.**

```
GET /search?q={query}&n_results=10
```

Response:
```json
{
  "query": "ransomware targeting finance",
  "results": [
    {
      "ioc_type": "Domain-Name",
      "value": "evil.example.com",
      "score": 0.8743,
      "opencti_url": "http://localhost:8080/dashboard/observations/indicators/{uuid}",
      "embedded_text": "Domain-Name evil.example.com confidence:75"
    }
  ],
  "count": 3
}
```

`opencti_url` is already a full URL (set by semantic-engine's `OPENCTI_BASE_URL=http://localhost:8080`). The dashboard can use it directly as the deep-link href — no need to construct the URL from `id` as D-08 describes.

### POST /generate (briefing-generator, port 8003) — EXISTS

```json
// Request
{"period_hours": 24}

// Response (immediate)
{"briefing_id": "uuid", "status": "generating"}
```

### GET /briefings/{id} (briefing-generator) — EXISTS

```json
{
  "briefing_id": "uuid",
  "status": "done",
  "text": "...",
  "created_at": "2026-06-26T14:00:00+00:00",
  "period_hours": 24,
  "error": null
}
```

### GET /briefings (briefing-generator) — EXISTS

Returns array of `{briefing_id, created_at, period_hours, status}` — no text, no pdf.

### GET /briefings/{id}/pdf (briefing-generator) — EXISTS

Returns `application/pdf` bytes. Use as `<a href="http://localhost:8003/briefings/{id}/pdf" download>`.

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (localhost:3000)
        │
        ├── [Overview tab, 30s poll] ──► GET /feeds/status ──► feed-orchestrator:8001
        │                                                               │
        │                                                          Redis hashes
        │                           ──► GET /stats ──────────────► briefing-generator:8003
        │                                                               │
        │                                                          pycti (OpenCTI)
        │
        ├── [Threat Hunt tab] ──────► GET /search?q=... ──────► semantic-engine:8002
        │                                                               │
        │                                                        ChromaDB + Ollama
        │
        └── [Briefings tab] ─────┬── GET /briefings ──────────► briefing-generator:8003
                                  ├── POST /generate
                                  ├── GET /briefings/{id} (3s poll)
                                  └── GET /briefings/{id}/pdf (anchor href)

nginx:alpine (port 80 inside container)
  └── serves Vite dist/
  └── try_files for SPA routing
  └── mapped to host port 3000
```

### Recommended Project Structure
```
services/dashboard/
├── Dockerfile           # multi-stage: node:20-slim build → nginx:alpine serve
├── nginx.conf           # port 80, try_files $uri $uri/ /index.html
├── package.json         # vite + react + react-dom + @vitejs/plugin-react
├── index.html           # Vite entry point
└── src/
    ├── main.jsx         # ReactDOM.createRoot, mounts <App />
    ├── App.jsx          # tab state, renders active view
    ├── App.css          # all styles (flat CSS, design tokens as CSS vars)
    ├── views/
    │   ├── Overview.jsx
    │   ├── ThreatHunt.jsx
    │   └── Briefings.jsx
    └── api.js           # fetch wrappers — one function per endpoint
```

Keeps file count minimal (ponytail: flat structure, 7 files total). No sub-component files needed at demo scope.

### Pattern 1: useEffect Polling with Cleanup
```jsx
// Source: React 18 docs — useEffect cleanup pattern
useEffect(() => {
  const fetchData = () =>
    fetch('http://localhost:8001/feeds/status')
      .then(r => r.json())
      .then(setFeeds)
      .catch(() => setError('feed-orchestrator unreachable'));

  fetchData();
  const id = setInterval(fetchData, 30_000);
  return () => clearInterval(id);  // cleanup on unmount
}, []);
```
**[ASSUMED]** — standard React pattern; clearInterval cleanup prevents memory leaks and stale-closure calls.

### Pattern 2: Multi-Stage Dockerfile
```dockerfile
# Stage 1: build
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

```nginx
# nginx.conf
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;  # SPA fallback
    }
}
```
**[ASSUMED]** — canonical nginx SPA pattern; no verification needed for this demo scope.

### Pattern 3: FastAPI CORS Middleware
```python
# Source: FastAPI docs — CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```
Add to: `services/feed-orchestrator/api.py` (new file), `services/semantic-engine/main.py`, `services/briefing-generator/main.py`.
**[ASSUMED]** — standard FastAPI pattern used across all prior phases.

### Pattern 4: feed-orchestrator HTTP Addition
```python
# New: services/feed-orchestrator/api.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading
from scheduler import build_scheduler
# ...

app = FastAPI(title="feed-orchestrator", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], ...)

@app.get("/feeds/status")
def feeds_status():
    redis_client = _get_redis()  # module-level singleton
    names = ["urlhaus", "malwarebazaar", "threatfox", "feodo", "otx"]
    feeds = []
    for name in names:
        h = redis_client.hgetall(f"tim:feed_status:{name}")
        feeds.append({
            "name": name,
            "last_run": h.get("last_run"),
            "ioc_count": int(h.get("ioc_count", 0)),
            "status": h.get("status", "never_run"),
        })
    return {"feeds": feeds}

@app.get("/health")
def health():
    return {"status": "ok"}
```

**main.py changes:** Replace `signal.pause()` with:
1. Start scheduler in daemon thread before uvicorn.run
2. `uvicorn.run(app, host="0.0.0.0", port=8001)`

The scheduler's APScheduler background threads are daemon threads; uvicorn's event loop becomes the main thread blocker.

### Anti-Patterns to Avoid
- **POST /search with JSON body:** The semantic-engine endpoint is `GET /search?q=...`, not POST. Do not send a JSON body.
- **Missing CORS before testing:** Add CORS middleware before attempting any browser → API call; the browser will silently block cross-origin requests.
- **Polling without cleanup:** Always return `() => clearInterval(id)` from useEffect. Without it, the component unmounts but the interval fires on stale state → React warning + potential infinite loop.
- **3000:3000 port mapping:** nginx listens on port 80 inside the container. The mapping must be `"3000:80"`, not `"3000:3000"`. (The stub in docker-compose.yml currently has `3000:3000` — this must be corrected.)
- **opencti_url construction in browser:** The `opencti_url` from semantic-engine results is already a full URL — do not reconstruct it from `id`. Use it directly.
- **Blocking pycti in async context for /stats:** Use `asyncio.to_thread()` for the pycti call in `/stats`, same as `run_generate` does.
- **feed-orchestrator without FastAPI:** `signal.pause()` is not compatible with an HTTP server. The scheduler must be moved to a thread; uvicorn becomes the main-thread blocker.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SPA 404 on page refresh | Custom 404 handler | nginx `try_files $uri $uri/ /index.html` | One line; handles all subpath cases |
| Tab routing | React Router | `useState` for active tab + conditional render | Three tabs, no deep-linking needed; full router is overkill |
| CSS variables / design tokens | CSS-in-JS runtime | CSS custom properties in `:root` | Zero runtime overhead, browser-native |
| Feed name list | Discovery from Redis | Hardcoded list of 5 known names | Feed names are stable constants defined in Python source |

**Key insight:** At demo scope with 3 views and 7 API calls, every abstraction layer adds more surface than it removes.

---

## Common Pitfalls

### Pitfall 1: semantic-engine /search Is GET, Not POST
**What goes wrong:** Dashboard sends `POST /search` with JSON body → 405 Method Not Allowed.
**Why it happens:** CONTEXT.md D-07 describes it as POST, but the implementation is `@app.get("/search")` with query params.
**How to avoid:** Use `fetch('http://localhost:8002/search?q=' + encodeURIComponent(query) + '&n_results=10')`.
**Warning signs:** Browser network tab shows 405 on /search.

### Pitfall 2: feed-orchestrator Has No HTTP Server
**What goes wrong:** Dashboard calls `http://localhost:8001/feeds/status` → connection refused.
**Why it happens:** feed-orchestrator uses `signal.pause()` as its blocking mechanism — no uvicorn, no FastAPI.
**How to avoid:** The plan must add FastAPI + uvicorn to feed-orchestrator before the dashboard can work.
**Warning signs:** `docker compose exec feed-orchestrator curl localhost:8001` hangs.

### Pitfall 3: Port Mapping 3000:3000 vs 3000:80
**What goes wrong:** nginx starts on port 80 inside container; `3000:3000` mapping means nothing listens on 3000 → `curl localhost:3000` fails.
**Why it happens:** docker-compose stub was written before the nginx decision was finalized.
**How to avoid:** Fix compose to `"3000:80"` when adding the nginx Dockerfile.

### Pitfall 4: CORS Preflight Blocks All API Calls
**What goes wrong:** Browser sends OPTIONS preflight; backend returns 405 → all fetch calls fail silently.
**Why it happens:** FastAPI does not enable CORS by default. The browser enforces this for cross-origin requests from localhost:3000 to localhost:8001/8002/8003.
**How to avoid:** Add `CORSMiddleware` to all three FastAPI services as first step before building any frontend.
**Warning signs:** Browser console shows "CORS policy: No 'Access-Control-Allow-Origin' header".

### Pitfall 5: Vite Env Variables in Docker Build
**What goes wrong:** `VITE_*` env vars baked into the build at compile time — runtime env vars in docker-compose have no effect.
**Why it happens:** Vite replaces `import.meta.env.VITE_*` at build time, not runtime.
**How to avoid:** For this demo, hardcode service URLs as constants in `api.js` (e.g., `const BRIEFING_URL = 'http://localhost:8003'`). The `VITE_*` env vars in the compose stub are misleading — they only work if passed at `npm run build` time inside the Docker build stage.
**Warning signs:** API calls go to undefined:8003 or localhost during development but wrong URL in container.

### Pitfall 6: briefings Dict Lost on Restart
**What goes wrong:** After `docker compose restart briefing-generator`, all briefings disappear from list.
**Why it happens:** `briefings: dict` is module-level, in-memory only (D-10 decision: acceptable for demo).
**How to avoid:** Document this in user-facing notes. The dashboard's `GET /briefings` list will be empty after restart. Not a bug — expected behavior per D-10.

---

## Code Examples

### api.js — Centralized fetch wrappers
```javascript
// Source: codebase conventions — all other services use module-level constants
const FEED_URL = 'http://localhost:8001';
const SEARCH_URL = 'http://localhost:8002';
const BRIEFING_URL = 'http://localhost:8003';

export const getFeedsStatus = () =>
  fetch(`${FEED_URL}/feeds/status`).then(r => r.json());

export const getStats = () =>
  fetch(`${BRIEFING_URL}/stats`).then(r => r.json());

export const searchIOCs = (query, n = 10) =>
  fetch(`${SEARCH_URL}/search?q=${encodeURIComponent(query)}&n_results=${n}`)
    .then(r => r.json());

export const postGenerate = (periodHours) =>
  fetch(`${BRIEFING_URL}/generate`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({period_hours: periodHours}),
  }).then(r => r.json());

export const getBriefing = (id) =>
  fetch(`${BRIEFING_URL}/briefings/${id}`).then(r => r.json());

export const listBriefings = () =>
  fetch(`${BRIEFING_URL}/briefings`).then(r => r.json());

export const pdfUrl = (id) => `${BRIEFING_URL}/briefings/${id}/pdf`;
```

### Briefings polling pattern
```jsx
const handleGenerate = async () => {
  setGenerating(true);
  const { briefing_id } = await postGenerate(periodHours);

  const id = setInterval(async () => {
    const b = await getBriefing(briefing_id);
    if (b.status === 'done' || b.status === 'error') {
      clearInterval(id);
      setGenerating(false);
      const list = await listBriefings();
      setBriefings(list);
    }
  }, 3000);
};
```

---

## Docker Compose Changes Required

Three compose changes needed in this phase:

1. **Fix soc-dashboard port mapping:** `"3000:3000"` → `"3000:80"`
2. **Add port 8001 to feed-orchestrator:** expose port and healthcheck (urllib.request probe — no curl in python:3.12-slim)
3. **Add `feed-orchestrator` to soc-dashboard `depends_on`:** it's currently missing from the stub

Correct healthcheck for feed-orchestrator HTTP endpoint:
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Vite scaffold / build | ✓ | (npm view works) | — |
| npm | package install | ✓ | — | — |
| Docker | container build | assumed ✓ | — | — |
| nginx:alpine image | serve stage | ✓ (standard) | latest | — |
| node:20-slim image | build stage | ✓ (standard) | 20-slim | — |

Step 2.6: feed-orchestrator needs `fastapi` and `uvicorn` added to requirements.txt — these are already installed in the briefing-generator image so the pattern is proven.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Manual browser + curl smoke tests (no JS test framework per D-03 spirit; no pytest for frontend) |
| Config file | none |
| Quick run command | `curl -s http://localhost:3000 \| grep -c '<div'` (returns non-zero if HTML served) |
| Full suite command | see integration checklist below |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | 
|--------|----------|-----------|-------------------|
| DASH-01 | Feed health cards render with name, timestamp, IOC count, status dot | integration | `curl -s http://localhost:8001/feeds/status \| python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['feeds'])==5"` |
| DASH-02 | IOC count + top ATT&CK list on Overview | integration | `curl -s http://localhost:8003/stats \| python3 -c "import sys,json; d=json.load(sys.stdin); assert 'top_techniques' in d"` |
| DASH-03 | Threat Hunt returns ranked results | integration | `curl -s 'http://localhost:8002/search?q=phishing&n_results=5' \| python3 -c "import sys,json; d=json.load(sys.stdin); assert 'results' in d"` |
| DASH-04 | Clicking result opens OpenCTI deep-link | manual | Open dashboard, enter query, click top result — verify new tab opens to localhost:8080 |
| DASH-05 | Briefings list + PDF download works | integration | `curl -s http://localhost:8003/briefings` returns JSON array; `curl -I http://localhost:8003/briefings/{id}/pdf` returns Content-Type: application/pdf |
| DASH-06 | Dashboard at localhost:3000 | integration | `curl -sf http://localhost:3000 \| grep -q 'SOC Dashboard'` |

### Integration Checklist (Wave 0 verification sequence)

Run after `docker compose --profile platform --profile feeds --profile semantic --profile briefings --profile dashboard up -d`:

```bash
# 1. Dashboard loads
curl -sf http://localhost:3000 | grep -q root && echo "PASS: dashboard HTML served"

# 2. /feeds/status endpoint exists and returns 5 feeds
curl -sf http://localhost:8001/feeds/status | python3 -c \
  "import sys,json; d=json.load(sys.stdin); assert len(d['feeds'])==5; print('PASS: feeds/status')"

# 3. /stats endpoint exists
curl -sf http://localhost:8003/stats | python3 -c \
  "import sys,json; d=json.load(sys.stdin); assert 'top_techniques' in d; print('PASS: /stats')"

# 4. CORS headers present (simulate browser origin)
curl -sf -H "Origin: http://localhost:3000" http://localhost:8003/health -I | \
  grep -q "access-control-allow-origin" && echo "PASS: CORS on briefing-generator"

# 5. Semantic search returns results
curl -sf "http://localhost:8002/search?q=malware&n_results=3" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('PASS: search returns', d['count'], 'results')"

# 6. PDF generation round-trip
ID=$(curl -sf -X POST http://localhost:8003/generate \
  -H "Content-Type: application/json" -d '{"period_hours":24}' | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['briefing_id'])")
sleep 60  # wait for Ollama generation
curl -sf "http://localhost:8003/briefings/$ID" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); assert d['status']=='done'; print('PASS: briefing done')"
curl -sf -I "http://localhost:8003/briefings/$ID/pdf" | \
  grep -q "application/pdf" && echo "PASS: PDF download"
```

### Wave 0 Gaps
- [ ] `services/dashboard/` directory does not exist yet — entire scaffold is Wave 0
- [ ] `services/feed-orchestrator/api.py` — new file for HTTP endpoints
- [ ] `services/briefing-generator/stats.py` — new file for /stats implementation (or inline in main.py)

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | demo scope — no auth per REQUIREMENTS.md out-of-scope |
| V3 Session Management | no | no sessions |
| V4 Access Control | no | demo scope |
| V5 Input Validation | yes | Threat Hunt query: max length check before fetch (matches semantic-engine's 500-char server-side limit) |
| V6 Cryptography | no | no crypto operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via IOC values in results | Tampering | React's JSX renders as text by default — do not use `dangerouslySetInnerHTML` |
| Open redirect via opencti_url | Spoofing | Low risk for demo; CONTEXT confirms no auth. If future hardening: validate URL prefix matches `http://localhost:8080` |
| CORS misconfiguration | Information Disclosure | `allow_origins=["http://localhost:3000"]` — explicit origin, not `"*"` |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| webpack | Vite | 2021+ | 10-100x faster dev server HMR |
| Create React App | `npm create vite@latest` | 2023 (CRA deprecated) | CRA is unmaintained; Vite is the standard |
| React 18 | React 19 | 2024 | React 19 is current (19.2.7 on npm); API surface unchanged for this use case |

**Deprecated/outdated:**
- `create-react-app`: Unmaintained since 2023. Use `npm create vite@latest -- --template react`.
- `react-scripts`: Bundled in CRA, avoid entirely.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `useEffect` + `setInterval` cleanup pattern works as described | Code Examples | Low — canonical React pattern, well-documented |
| A2 | nginx `try_files` SPA pattern works with Vite's default dist output | Architecture Patterns | Low — standard pattern for any SPA |
| A3 | Feed `.name` attributes match the 5 string values listed (`urlhaus`, `malwarebazaar`, `threatfox`, `feodo`, `otx`) | API Contracts | Medium — planner should read `feeds/base.py` and each feed class to confirm exact `.name` values |
| A4 | `asyncio.to_thread` is correct pattern for pycti in `/stats` endpoint | Common Pitfalls | Low — same pattern used in `run_generate`; confirmed working in Phase 5 |
| A5 | FastAPI CORSMiddleware syntax unchanged from Phase 5 briefing-generator pattern | Code Examples | Low — pinned `fastapi==0.115.14` across services |
| A6 | `@vitejs/plugin-react` 6.0.3 is compatible with React 19.2.7 | Standard Stack | Low — both from official Vite/React orgs; Vite 8.x supports React 19 |

---

## Open Questions

1. **Feed `.name` attribute values**
   - What we know: `build_enabled_feeds()` returns 5 instances; Redis keys use `tim:feed_status:{feed.name}`
   - What's unclear: Exact string values of `.name` on each feed class (not read — `feeds/base.py` and each feed file)
   - Recommendation: Planner reads `feeds/urlhaus.py` etc. and hardcodes the list in `api.py`; no dynamic discovery needed

2. **attack_pattern count for /stats**
   - What we know: `_collect_threat_data` returns `attack_patterns` list (max 10 via `first=10`)
   - What's unclear: Whether to count relationships or just return the pattern list as top 5
   - Recommendation: Return the top 5 items from `attack_patterns` list with a static `count: 1` each, or derive count by cross-referencing indicators' `objectRelationship`. Simplest: return the list ordered by pycti default, call it "top 5 observed".

3. **`VITE_*` env vars in the compose stub**
   - What we know: They're defined in docker-compose but Vite bakes env vars at build time
   - What's unclear: Whether the planner intends to pass them via `--build-arg` or hardcode
   - Recommendation: Hardcode service URLs in `api.js` as constants; ignore the `VITE_*` env vars in compose for now (they have no runtime effect for a static nginx serve).

---

## Sources

### Primary (HIGH confidence — codebase reads)
- `services/feed-orchestrator/main.py` — confirmed no HTTP server, scheduler-only process
- `services/feed-orchestrator/status.py` — confirmed Redis key pattern and field names
- `services/semantic-engine/main.py` — confirmed GET /search (not POST)
- `services/semantic-engine/searcher.py` — confirmed result schema: `{ioc_type, value, score, opencti_url, embedded_text}`
- `services/briefing-generator/main.py` — confirmed all endpoint shapes
- `services/briefing-generator/generator.py` — confirmed `_collect_threat_data()` pattern for /stats reuse
- `docker-compose.yml` — confirmed soc-dashboard stub with `3000:3000` mismatch and missing feed-orchestrator port

### Secondary (npm registry)
- `npm view vite version` → 8.1.0 [VERIFIED]
- `npm view react version` → 19.2.7 [VERIFIED]
- `npm view react-dom version` → 19.2.7 [VERIFIED]
- `npm view @vitejs/plugin-react version` → 6.0.3 [VERIFIED]

### Tertiary (ASSUMED)
- nginx SPA try_files pattern
- useEffect setInterval cleanup pattern
- Multi-stage Dockerfile pattern

---

## Metadata

**Confidence breakdown:**
- API contracts: HIGH — all read from live source files
- Standard stack: HIGH — verified via npm view
- Architecture patterns: MEDIUM — standard patterns, not Context7-verified this session
- Docker/nginx: MEDIUM — standard patterns, well-established

**Research date:** 2026-06-26
**Valid until:** 2026-07-26 (stable domain; Vite/React patch versions may update but API surface unchanged)
