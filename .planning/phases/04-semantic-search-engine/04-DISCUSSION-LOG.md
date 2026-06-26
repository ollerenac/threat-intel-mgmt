# Phase 4: Semantic Search Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-25
**Phase:** 04-semantic-search-engine
**Areas discussed:** Embedding content, Indexing startup, Search result shape

---

## Embedding Content

### Q1: What text to embed per IOC?

| Option | Description | Selected |
|--------|-------------|----------|
| Enriched context | `{type}: {value} — {description} {labels}` — best search quality, captures threat narrative | ✓ |
| Value + type only | `{type}: {value}` — simple but degrades semantic search to near-substring results | |
| You decide | Claude picks | |

**User's choice:** Enriched context (Recommended)

### Q2: Where to pull enrichment from?

| Option | Description | Selected |
|--------|-------------|----------|
| OpenCTI indicator fields only | name + description + labels — one API call per indicator, no graph traversal | ✓ |
| Indicator + linked report titles | Richer but ~3-5x slower indexing (second pycti call per indicator) | |
| You decide | Claude picks | |

**User's choice:** OpenCTI indicator fields only (Recommended)

### Q3: Handling no-description IOCs (most feed-sourced)?

| Option | Description | Selected |
|--------|-------------|----------|
| Embed value + type + labels only | Skip blank description silently; labels like `malware-distribution` still add signal | ✓ |
| Exclude no-description IOCs | Only index IOCs with descriptions — misses most URLhaus/Feodo IOCs | |
| Fallback to source feed name | Use report/bundle source as fallback text | |

**User's choice:** Embed value + type + labels only (Recommended)

---

## Indexing Startup

### Q1: Startup indexing strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| Incremental watermark | Store `last_indexed_at`, only fetch indicators updated after that — fast restarts | ✓ |
| Full re-index if ChromaDB empty, else skip | Simpler logic but won't pick up IOC updates on restarts | |
| Always full re-index | Correct but ~18 min every restart — bad for demo | |

**User's choice:** Incremental watermark (Recommended)
**Notes:** 22k+ IOCs at ~50ms/embedding estimated ~18 min for full index. Watermark solves this for all subsequent restarts.

### Q2: /health during initial index?

| Option | Description | Selected |
|--------|-------------|----------|
| Serve immediately, index in background | `/health` returns `{status: ok, indexed: N, total: M}` — same pattern as intel-extractor | ✓ |
| Block /health until indexed | Docker healthcheck holds entire stack up for ~18 min on first run | |

**User's choice:** Serve immediately, index in background (Recommended)

---

## Search Result Shape

### Q1: How many results?

| Option | Description | Selected |
|--------|-------------|----------|
| Top 10, fixed | Good for dashboard Threat Hunt list; simple default | ✓ |
| Configurable via ?limit= (default 10) | More flexible but adds API complexity | |
| You decide | Claude picks | |

**User's choice:** Top 10, fixed (Recommended)

### Q2: Similarity threshold?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, threshold 0.3 | Drop results below 0.3; expose as `SIMILARITY_THRESHOLD` env var | ✓ |
| No cutoff — always return top 10 | Simpler but can return obviously-unrelated IOCs | |
| You decide | Claude picks | |

**User's choice:** Yes, threshold 0.3 (Recommended)

### Q3: Include embedded_text in results?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, include embedded_text | Shows WHY the IOC matched; stored in ChromaDB metadata, no extra call | ✓ |
| No — just value, score, opencti_url, ioc_type | Minimal response | |

**User's choice:** Yes, include embedded_text (Recommended)

---

## Claude's Discretion

- ChromaDB collection strategy (single vs. per-type)
- Exact pycti pagination approach for indicator listing
- Dockerfile and requirements.txt structure (follow intel-extractor)
- Whether to add optional `?limit=` param (planner decides)

## Deferred Ideas

- Filtering results by IOC type (e.g., only domains) — Phase 6 dashboard concern
- Graph-traversal enrichment (linked report titles) — deferred as too slow for 22k corpus
- Semantic search over non-indicator objects (threat actors, malware) — out of Phase 4 scope
