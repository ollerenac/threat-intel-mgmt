# Phase 6: SOC Dashboard - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning

<domain>
## Phase Boundary

A React frontend at `localhost:3000` that unifies all five backend services into a demo-ready three-view interface for SOC analysts. Delivers DASH-01 through DASH-06. Does NOT add new AI capabilities, auth, or production hardening — those are out of scope per REQUIREMENTS.md.

The dashboard is the only user-facing surface in TIM v1. It must be fully self-contained: `docker compose --profile dashboard up -d` starts it alongside the platform, no manual steps.

Two small backend additions are also in scope for this phase:
- `GET /feeds/status` on feed-orchestrator — per-feed health data for Overview (DASH-01)
- `GET /stats` on briefing-generator — top ATT&CK techniques for Overview (DASH-02)

</domain>

<decisions>
## Implementation Decisions

### Frontend Stack
- **D-01:** **Vite + React** (plain JSX, no TypeScript). `npm create vite@latest` scaffold under `services/dashboard/`. This is the first and only JavaScript service in the repo — keep the footprint minimal.
- **D-02:** **Plain `fetch` + `useEffect`** for all data fetching. No React Query, no SWR, no axios. Each view manages its own polling with `setInterval` / `clearInterval` inside a useEffect cleanup.
- **D-03:** No component library. Plain CSS or minimal inline styles. The demo audience is a SOC client evaluating capabilities, not a design review board.

### View: Overview (DASH-01, DASH-02)
- **D-04:** Feed health data comes from **`GET /feeds/status`** on feed-orchestrator (new endpoint). Returns per-feed: `name`, `last_run`, `ioc_count`, `status`. The dashboard calls this endpoint; no direct OpenCTI dependency for this view.
- **D-05:** Top ATT&CK techniques (DASH-02) come from **`GET /stats`** on briefing-generator (new endpoint). Reuses `_collect_threat_data()` pycti wiring — returns `{"top_techniques": [{"id": "T1566", "name": "Phishing", "count": N}, ...]}` for the last 24h without running Ollama. Lightweight read-only query.
- **D-06:** Total IOC count (last 24h) for the Overview header stat also comes from `/stats` — briefing-generator already queries `indicator.list()` with a 24h filter.

### View: Threat Hunt (DASH-03, DASH-04)
- **D-07:** Search box calls **`POST /search`** on semantic-engine (port 8002) with `{"query": text, "n_results": 10}`. Results shown as a ranked list with similarity score badge.
- **D-08:** Clicking a result opens **OpenCTI at `localhost:8080`** in a new tab. Deep-link format: `http://localhost:8080/dashboard/observations/indicators/{opencti_id}` — the `id` field from the semantic-engine result.

### View: Briefings (AIBR-03, AIBR-04, DASH-05)
- **D-09:** **Period selector + Generate button**: dropdown with options 24h / 72h / 7d (maps to `period_hours` 24 / 72 / 168) next to a "Generate Briefing" button. POST `/generate` to briefing-generator (port 8003).
- **D-10:** **Auto-poll every 3 seconds** after POST /generate returns `briefing_id`. Show a spinner with "Generating…" text while `status == "generating"`. Stop polling when `status == "done"` or `"error"`. No manual refresh button needed.
- **D-11:** PDF download via `GET /briefings/{id}/pdf` — standard `<a href=... download>` link rendered for each briefing in the list when `status == "done"`. List refreshed by calling `GET /briefings` on load and after each new generation completes.

### Docker Packaging
- **D-12:** **Multi-stage Dockerfile** — `node:20-slim` build stage (`npm ci && npm run build` → `dist/`), then `nginx:alpine` serve stage. Final image ~15MB. Nginx serves `dist/` on port 3000.
- **D-13:** Docker Compose profile name: `dashboard`. Start command: `docker compose --profile platform --profile dashboard up -d`. Port mapping: `3000:80` (nginx listens on 80 inside container, mapped to 3000 on host). DASH-06 satisfied.
- **D-14:** **CORS middleware** added to all three FastAPI services that the dashboard calls (feed-orchestrator, semantic-engine, briefing-generator): `CORSMiddleware(allow_origins=["http://localhost:3000"])`. Two-line add per service. No nginx reverse proxy — simpler for a demo.

### API Surface Summary (for planner)
| Endpoint | Service | Port | Status |
|----------|---------|------|--------|
| `GET /feeds/status` | feed-orchestrator | 8001 | **NEW — add in this phase** |
| `GET /stats` | briefing-generator | 8003 | **NEW — add in this phase** |
| `POST /search` | semantic-engine | 8002 | exists |
| `POST /generate` | briefing-generator | 8003 | exists |
| `GET /briefings/{id}` | briefing-generator | 8003 | exists |
| `GET /briefings/{id}/pdf` | briefing-generator | 8003 | exists |
| `GET /briefings` | briefing-generator | 8003 | exists |
| `GET /health` | all services | various | exists |

</decisions>

<canonical_refs>
## Canonical References

- `.planning/REQUIREMENTS.md` — DASH-01 through DASH-06, AIBR-03, AIBR-04 requirement text
- `.planning/ROADMAP.md` — Phase 6 goal, success criteria, depends-on
- `.planning/phases/05-briefing-generator/05-04-PLAN.md` — briefing-generator endpoint contracts (POST /generate, GET /briefings, GET /briefings/{id}/pdf)
- `.planning/phases/05-briefing-generator/05-02-PLAN.md` — _collect_threat_data() pycti pattern (reuse in /stats endpoint)
- `services/briefing-generator/main.py` — existing endpoint implementations to pattern /stats after
- `services/feed-orchestrator/` — source for /feeds/status implementation
- `services/semantic-engine/` — /search endpoint contract
- `docker-compose.yml` — existing service definitions, profiles, port conventions

</canonical_refs>

<code_context>
## Codebase Context

**Existing services (all FastAPI, Python):**
- `services/feed-orchestrator/` — port 8001, tracks per-feed run history
- `services/semantic-engine/` — port 8002, POST /search endpoint
- `services/briefing-generator/` — port 8003, POST /generate, GET /briefings*, GET /health
- `services/intel-extractor/` — port 8001 (check for conflict), not called by dashboard

**Nothing Node/JS exists yet** — `services/dashboard/` must be created from scratch. Pattern: mirror the other service directories (Dockerfile, top-level `src/`, one entry point).

**Docker Compose conventions:**
- Services use `profiles:` array in compose to gate startup
- Healthchecks use Python `urllib.request` (no curl in slim images)
- Secrets via environment variables from `.env`

**OpenCTI deep-link base:** `http://localhost:8080/dashboard/observations/indicators/{id}` — verify against live instance if format changes.

</code_context>
