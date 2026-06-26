# Phase 6: SOC Dashboard — Discussion Log

**Date:** 2026-06-26
**Phase:** 06-soc-dashboard

## Areas Discussed

### 1. Frontend Toolchain
- **Q:** What React bundler/framework? → **Vite + React** (plain JSX, no TS)
- **Q:** Data fetching approach? → **Plain fetch + useEffect** (no library)
- Rationale: First JS in the repo, keep footprint minimal.

### 2. Briefings View — Generate Trigger
- **Q:** Generate trigger UI? → **Period selector (24h/72h/7d) + Generate button**
- **Q:** Status while generating? → **Auto-poll every 3s** until done/error

### 3. Overview Data Sources
- **Q:** Feed health (DASH-01) source? → **New GET /feeds/status on feed-orchestrator**
- **Q:** ATT&CK techniques (DASH-02) source? → **New GET /stats on briefing-generator** (reuses _collect_threat_data pycti wiring, no Ollama)

### 4. Docker Packaging
- **Q:** Serve method? → **nginx + Vite build** (multi-stage Dockerfile, node:20-slim → nginx:alpine)
- **Q:** CORS? → **CORSMiddleware on each FastAPI service** (allow_origins localhost:3000)

## Deferred Ideas
- None raised during discussion.

## Claude Discretion Items
- OpenCTI deep-link format assumed: `localhost:8080/dashboard/observations/indicators/{id}` — verify against live instance
- intel-extractor port conflict with feed-orchestrator (both on 8001?) — planner to verify
