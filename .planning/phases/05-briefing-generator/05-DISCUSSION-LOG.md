# Phase 5: Briefing Generator - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-26
**Phase:** 05-briefing-generator
**Areas discussed:** Data scope, LLM prompt design, PDF library, Briefing storage

---

## Data scope

| Option | Description | Selected |
|--------|-------------|----------|
| IOCs + ATT&CK techniques only | 2 pycti calls, fits context easily | |
| Full threat picture | IOCs + actors + campaigns + ATT&CK + sectors, 5+ pycti calls | ✓ |
| IOCs only | Smallest context, thin for exec audience | |

**User's choice:** Full threat picture

---

| Option | Description | Selected |
|--------|-------------|----------|
| Capped at 10 per type | ~800–1200 tokens data, predictable context | ✓ |
| Capped at 25 per type | Richer but risks crowding 4k window | |
| Uncapped | Complex aggregation, unpredictable | |

**User's choice:** Capped at 10 per type (recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Threat actors + malware families | threat_actor.list() + malware.list() + campaign.list() | ✓ |
| Threat actors only | Simpler, skip malware/campaigns | |
| Let Claude decide | Lock high-level intent, researcher figures out pycti calls | |

**User's choice:** Threat actors + malware families (recommended)

---

## LLM prompt design

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-aggregated stats block | Compact text ~300 tokens, predictable context | ✓ |
| Structured JSON dump | Raw pycti dicts, expensive tokens, LLM may describe structure | |
| Hybrid: stats + top-5 IOC examples | Richer but more complexity | |

**User's choice:** Pre-aggregated stats block (recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Formal SOC-to-executive | C-suite audience, plain prose, no markdown, business risk focus | ✓ |
| Technical analyst briefing | SOC audience, includes MITRE IDs inline | |
| Structured report with sections | Markdown headers, easier to parse, harder to size | |

**User's choice:** Formal SOC-to-executive (recommended)

---

## PDF library

| Option | Description | Selected |
|--------|-------------|----------|
| fpdf2 | Pure Python, ~1 MB, zero system deps, multi_cell() for word-wrap | ✓ |
| reportlab | Industry standard, heavier (~5 MB), pure Python | |
| weasyprint | HTML→PDF, best typography, needs fontconfig + Pango system libs | |

**User's choice:** fpdf2 (recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: title + date + body | Clean, professional — title, period, plain prose body | ✓ |
| Styled: header block + body + footer | Header + footer with page numbers, extra fpdf2 draw calls | |

**User's choice:** Minimal layout (recommended)

---

## Briefing storage

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory dict | Consistent with intel-extractor jobs, simplest, lost on restart | ✓ |
| JSON files on disk | Survives restarts, trivial file I/O | |
| SQLite | Full persistence, queryable, overkill for 200-word text blob | |

**User's choice:** In-memory dict (recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Async with polling | POST returns immediately, GET polls, consistent with intel-extractor | ✓ |
| Synchronous (wait for response) | Simpler API, HTTP timeout risk for longer windows | |

**User's choice:** Async with polling (recommended)

---

## Claude's Discretion

- pycti field selection per entity type (which fields to request in list calls)
- Exact `updated_at` filter syntax for pycti 6.4.x
- Dockerfile structure and requirements.txt order (follow intel-extractor)
- Handling LLM output outside 200–300 word target (truncate vs. re-prompt)

## Deferred Ideas

- Briefing persistence across restarts (SQLite/JSON on disk) — v2
- `GET /briefings` list endpoint — trivial to add, not in AIBR requirements, Phase 6 may want it
- Configurable period beyond 24/72h — accepted via API but only 24/72 tested
- LLM re-prompt when output is wrong length — truncation is adequate for demo
- Multi-page PDF with IOC table — v2 styling pass
