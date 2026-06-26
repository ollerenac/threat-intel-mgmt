---
phase: 06-soc-dashboard
plan: "02"
subsystem: dashboard-scaffold
tags: [vite, react, nginx, docker, docker-compose]
status: complete

dependency_graph:
  requires:
    - services/feed-orchestrator/api.py (GET /health — targeted by new healthcheck)
  provides:
    - services/dashboard/ (Vite+React SPA scaffold)
    - services/dashboard/Dockerfile (multi-stage nginx:alpine image)
    - services/dashboard/nginx.conf (SPA routing)
    - docker-compose soc-dashboard service (corrected, profile: dashboard)
    - docker-compose feed-orchestrator HTTP port + urllib healthcheck
  affects:
    - docker-compose.yml (soc-dashboard block, feed-orchestrator block)

tech_stack:
  added:
    - vite@^8.1.0 (build tool)
    - react@^19.2.7 (UI library)
    - react-dom@^19.2.7 (DOM renderer)
    - "@vitejs/plugin-react@^6.0.2" (JSX transform)
    - nginx:alpine (static serve stage in Dockerfile)
    - node:20-slim (build stage in Dockerfile)
  patterns:
    - Multi-stage Dockerfile (node:20-slim build → nginx:alpine serve)
    - nginx SPA fallback (try_files $uri $uri/ /index.html)
    - useState tab routing (no react-router — D-03)
    - CSS custom properties for design tokens (UI-SPEC colors and spacing)
    - urllib.request healthcheck probe (no curl in python:3.12-slim)
    - localhost-only port bind (127.0.0.1:8001:8001) for internal service

key_files:
  created:
    - services/dashboard/package.json
    - services/dashboard/vite.config.js
    - services/dashboard/index.html
    - services/dashboard/src/main.jsx
    - services/dashboard/src/App.jsx
    - services/dashboard/src/App.css
    - services/dashboard/Dockerfile
    - services/dashboard/nginx.conf
  modified:
    - docker-compose.yml (soc-dashboard block + feed-orchestrator block)

decisions:
  - "Removed @types/react, @types/react-dom, oxlint from devDependencies — template artifacts not needed for plain JSX with no TypeScript"
  - "App.jsx uses named export default (not function App) — matches PATTERNS.md pattern"
  - "main.jsx uses React.createElement(App) per plan spec — avoids JSX in the entry point"
  - "feed-orchestrator healthcheck changed from Redis ping to HTTP probe — Redis ping tested the wrong thing; the dashboard depends on the HTTP API being up, not just Redis connectivity"
  - "feed-orchestrator port bound to 127.0.0.1 — T-06-02-03 mitigation; matches semantic-engine host-binding convention"

metrics:
  duration: "~8m"
  completed: "2026-06-26"
  tasks_completed: 2
  files_changed: 9

requirements_satisfied:
  - DASH-06 (dashboard at localhost:3000, no setup after docker compose up -d)
---

# Phase 6 Plan 02: Vite+React Scaffold + Docker Packaging — Summary

**One-liner:** Vite+React SPA scaffolded under services/dashboard/ with multi-stage nginx Dockerfile and docker-compose soc-dashboard stub corrected (build path, port 3000:80, service_healthy depends_on); feed-orchestrator given HTTP port and urllib healthcheck.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Scaffold Vite+React project under services/dashboard/ | 65a34d7 | package.json, vite.config.js, index.html, src/main.jsx, src/App.jsx, src/App.css |
| 2 | Write Dockerfile + nginx.conf and fix docker-compose.yml | d6af63b | Dockerfile, nginx.conf, docker-compose.yml |

## What Was Built

### Task 1: Vite+React scaffold

`services/dashboard/` created from scratch via `npm create vite@latest -- --template react`, then adapted:

- `package.json`: trimmed to react, react-dom (dependencies) + @vitejs/plugin-react, vite (devDependencies). Removed template artifacts: @types/react, @types/react-dom, oxlint.
- `index.html`: title changed to "SOC Dashboard" (DASH-06 smoke test target).
- `src/App.jsx`: three-tab shell — `TABS = ['Overview', 'Threat Hunt', 'Briefings']`, useState active tab, nav with `.tab` / `.tab.active` classes. No router library per D-03.
- `src/App.css`: full design system from UI-SPEC as CSS custom properties on `:root` — 9 color tokens, 5 spacing tokens, body/nav/tab/card/input/button-primary/status-dot rules.
- `src/main.jsx`: mounts App via `ReactDOM.createRoot` + `React.createElement(App)`.
- Generated boilerplate deleted: `src/assets/`, `src/index.css`, `README.md`, `public/`.
- `npm run build` produces `dist/` in 84ms with no errors.

### Task 2: Dockerfile, nginx.conf, docker-compose fixes

`services/dashboard/Dockerfile`:
- Stage 1: `FROM node:20-slim AS build` — `npm ci` + `npm run build`
- Stage 2: `FROM nginx:alpine` — copies `dist/` to `/usr/share/nginx/html`, copies `nginx.conf`, exposes port 80.

`services/dashboard/nginx.conf`:
- `listen 80`, `root /usr/share/nginx/html`, `try_files $uri $uri/ /index.html` — SPA fallback routing.

`docker-compose.yml` — soc-dashboard block (4 fixes):
- `build`: `./services/soc-dashboard` → `./services/dashboard`
- `ports`: `"3000:3000"` → `"3000:80"` (nginx listens on 80)
- `environment`: entire VITE_* block removed (T-06-02-01 mitigation — Vite bakes env at build time; no runtime effect on static nginx serve)
- `depends_on`: replaced simple list (opencti, intel-extractor, semantic-engine, briefing-generator) with service_healthy conditions on feed-orchestrator, semantic-engine, briefing-generator only.

`docker-compose.yml` — feed-orchestrator block (2 additions):
- `ports: - "127.0.0.1:8001:8001"` — localhost-only bind (T-06-02-03 mitigation).
- `healthcheck` replaced Redis ping with urllib.request HTTP probe on `http://localhost:8001/health` — tests the HTTP API the dashboard actually depends on.

## Verification

All automated checks passed:

```
Dockerfile: FROM node:20-slim AS build ✓
Dockerfile: FROM nginx:alpine ✓
Dockerfile: COPY --from=build /app/dist /usr/share/nginx/html ✓
nginx.conf: try_files ✓, listen 80 ✓
docker-compose: 3000:80 ✓, ./services/dashboard ✓, no 3000:3000 ✓
docker-compose: feed-orchestrator in depends_on ✓, no VITE_ vars ✓
docker-compose: intel-extractor removed from depends_on ✓
docker-compose: 127.0.0.1:8001:8001 ✓, urllib.request healthcheck ✓
docker-compose: YAML valid (python3 yaml.safe_load) ✓
npm run build: ✓ built in 84ms, dist/index.html produced ✓
index.html: "SOC Dashboard" in title ✓
App.css: --color-bg: #0f1117 ✓, --color-accent: #3b82f6 ✓
App.jsx: Overview ✓, Threat Hunt ✓, Briefings ✓, no react-router ✓
No .ts/.tsx files ✓
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Template devDependencies trimmed**
- **Found during:** Task 1 — Step 2 (inspect package.json)
- **Issue:** `npm create vite@latest` added `@types/react`, `@types/react-dom`, `oxlint` as devDependencies not listed in the plan's allowed set.
- **Fix:** Removed the three packages from package.json. TypeScript types are unused for plain JSX; oxlint is not part of the build.
- **Files modified:** services/dashboard/package.json
- **Commit:** 65a34d7

**2. [Rule 2 - Security] feed-orchestrator healthcheck upgraded from Redis probe to HTTP probe**
- **Found during:** Task 2 — reading existing feed-orchestrator compose block
- **Issue:** Existing healthcheck tested `redis.ping()` — this verifies Redis connectivity but NOT that the FastAPI HTTP server is up. `soc-dashboard` depends on the HTTP API, so the healthcheck must probe `GET /health`. A passing Redis healthcheck with a failing uvicorn would allow soc-dashboard to start against a broken backend.
- **Fix:** Replaced Redis healthcheck with `urllib.request.urlopen('http://localhost:8001/health')` — tests the actual service the dashboard calls.
- **Files modified:** docker-compose.yml
- **Commit:** d6af63b

## Known Stubs

None. App.jsx renders the active tab name as text — this is an intentional placeholder until Plan 03 adds the three view components (`Overview.jsx`, `ThreatHunt.jsx`, `Briefings.jsx`). The placeholder is the stated goal of this plan: "A bootable Vite+React scaffold with a placeholder App.jsx."

## Threat Flags

None. All threat mitigations from the plan's threat model applied:
- T-06-02-01: VITE_* env block removed from soc-dashboard (information disclosure mitigation)
- T-06-02-02: nginx:alpine serves only pre-built dist/ — no dynamic content (accepted)
- T-06-02-03: feed-orchestrator port bound to 127.0.0.1:8001:8001 (DoS surface reduction)

## Self-Check: PASSED

- `services/dashboard/Dockerfile` exists ✓
- `services/dashboard/nginx.conf` exists ✓
- `services/dashboard/package.json` exists with correct deps ✓
- `services/dashboard/src/App.jsx` exists with three tabs ✓
- `services/dashboard/src/App.css` exists with design tokens ✓
- `services/dashboard/src/main.jsx` exists ✓
- `docker-compose.yml` has 3000:80, ./services/dashboard, feed-orchestrator service_healthy ✓
- `docker-compose.yml` feed-orchestrator has 127.0.0.1:8001:8001 and urllib healthcheck ✓
- Commits 65a34d7 and d6af63b exist ✓
