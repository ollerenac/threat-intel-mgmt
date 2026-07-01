// ponytail: relative paths — nginx proxies /api/* to backends over Docker internal network
const FEED_URL     = '/api/feeds';
const SEARCH_URL   = '/api/semantic';
const BRIEFING_URL = '/api/briefings';
const EXTRACTOR_URL = '/api/extractor';

export const getFeedsStatus = () =>
  fetch(`${FEED_URL}/feeds/status`).then(r => r.json());

export const getAlerts = () =>
  fetch(`${FEED_URL}/feeds/alerts`).then(r => r.json());

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

export const getFeedsRecent = (limit = 200) =>
  fetch(`${FEED_URL}/feeds/recent?limit=${limit}`).then(r => r.json());

export const getRecentDocs = () =>
  fetch(`${EXTRACTOR_URL}/recent`).then(r => r.json());

export const getExtractorStats = () =>
  fetch(`${EXTRACTOR_URL}/stats`).then(r => r.json());

export const getSemanticStats = () =>
  fetch(`${SEARCH_URL}/stats`).then(r => r.json());

export const getCVEStats = () =>
  fetch(`${BRIEFING_URL}/cve/stats`).then(r => r.json());

export const getCollectorStatus = () =>
  fetch(`${EXTRACTOR_URL}/collector/status`).then(r => r.json());
