// ponytail: URLs hardcoded — Vite bakes env vars at build time; runtime compose env has no effect (RESEARCH.md Pitfall 5)
const FEED_URL = 'http://localhost:8001';
const SEARCH_URL = 'http://localhost:8002';
const BRIEFING_URL = 'http://localhost:8003';

export const getFeedsStatus = () =>
  fetch(`${FEED_URL}/feeds/status`).then(r => r.json());

export const getStats = () =>
  fetch(`${BRIEFING_URL}/stats`).then(r => r.json());

// GET with query params — semantic-engine/main.py line 41 confirms @app.get("/search"), NOT POST
export const searchIOCs = (query, n = 10) =>
  fetch(`${SEARCH_URL}/search?q=${encodeURIComponent(query)}&n_results=${n}`)
    .then(r => r.json());

export const postGenerate = (periodHours) =>
  fetch(`${BRIEFING_URL}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ period_hours: periodHours }),
  }).then(r => r.json());

export const getBriefing = (id) =>
  fetch(`${BRIEFING_URL}/briefings/${id}`).then(r => r.json());

export const listBriefings = () =>
  fetch(`${BRIEFING_URL}/briefings`).then(r => r.json());

// Returns URL string — not a fetch call; used as <a href={pdfUrl(id)} download>
export const pdfUrl = (id) => `${BRIEFING_URL}/briefings/${id}/pdf`;
