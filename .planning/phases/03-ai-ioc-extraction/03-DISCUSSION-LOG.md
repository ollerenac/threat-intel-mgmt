# Phase 3: AI IOC Extraction - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-25
**Phase:** 03-ai-ioc-extraction
**Areas discussed:** LLM extraction prompt, STIX object scope, Job processing model, ATT&CK technique lookup

---

## LLM Extraction Prompt

### Q1: Prompt structure

| Option | Description | Selected |
|--------|-------------|----------|
| Single-pass JSON schema | One prompt per chunk with all IOC types + ATT&CK in one JSON response | ✓ |
| Two-pass: IOCs then ATT&CK | Separate Ollama calls for IOC extraction and technique extraction | |
| You decide | Claude picks the strategy | |

**User's choice:** Single-pass JSON schema
**Notes:** Fewer Ollama calls, faster per chunk. Combined with few-shot example to improve reliability.

### Q2: Few-shot examples

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, include a few-shot example | 1 example in system prompt (~200 tokens), dramatically improves JSON formatting for 3B models | ✓ |
| No, zero-shot with clear instructions | Rely on Ollama `format='json'` parameter only | |
| You decide | Claude picks | |

**User's choice:** Yes, include a few-shot example
**Notes:** Paired with Ollama `format='json'` for double enforcement.

### Q3: Malformed JSON handling

| Option | Description | Selected |
|--------|-------------|----------|
| Retry once, then skip the chunk | Single retry, skip on second failure | |
| Retry with a simpler fallback prompt | Strip-down plain-text prompt, parse with regex | ✓ |
| You decide | Claude picks | |

**User's choice:** Retry with a simpler fallback prompt
**Notes:** Fallback prompt: "List all IPs, domains, file hashes, and URLs, one per line, format: TYPE:VALUE". Preserves at least basic IOC extraction even when JSON formatting fails.

---

## STIX Object Scope

### Q1: STIX objects created per extraction

| Option | Description | Selected |
|--------|-------------|----------|
| indicator + report | One report SDO per job + one indicator per IOC, relationship edges to attack-patterns | ✓ |
| indicator only | Consistent with Phase 2, no report SDO | |
| Full graph: indicator + report + malware + threat-actor | Complete design doc scope, significantly more complex | |

**User's choice:** indicator + report
**Notes:** Malware/threat-actor SDOs deferred — indicator + report is the right scope for Phase 3 demo impact without over-engineering.

### Q2: ATT&CK technique representation

| Option | Description | Selected |
|--------|-------------|----------|
| STIX relationship edge | indicator → indicates → attack-pattern, visible as graph edge in OpenCTI | ✓ |
| Labels field only | Technique ID as a label string, searchable but not visually linked | |
| You decide | Claude picks | |

**User's choice:** STIX relationship edge
**Notes:** This is the demo-critical moment — the graph edge makes ATT&CK mapping visible in OpenCTI's knowledge graph view.

---

## Job Processing Model

### Q1: Sync vs async

| Option | Description | Selected |
|--------|-------------|----------|
| Async with in-memory job store | POST returns job_id immediately, background task processes, Python dict for state | ✓ |
| Synchronous (wait for result) | POST blocks until complete, simpler but may timeout on large PDFs | |
| Async with Redis job store | Persistent across restarts, same Redis instance as Phase 2 | |

**User's choice:** Async with in-memory job store
**Notes:** In-memory is sufficient for demo. Redis upgrade path available if needed. Jobs lost on restart is acceptable.

### Q2: GET /jobs/{id} response schema

| Option | Description | Selected |
|--------|-------------|----------|
| Status + counts + OpenCTI IDs | {status, iocs_extracted, techniques_found, report_id, processing_time_s} | ✓ |
| Full STIX bundle in response | Complete JSON bundle, large response, requires STIX parsing in dashboard | |
| You decide | Claude picks | |

**User's choice:** Status + counts + OpenCTI IDs
**Notes:** Dashboard shows "Extracted 12 IOCs, 3 ATT&CK techniques" using this response — no STIX parsing needed in the frontend.

---

## ATT&CK Technique Lookup

### Q1: Mapping mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| LLM extracts names → Python queries OpenCTI | Technique keywords from LLM → GraphQL search → canonical Txxxx ID | ✓ |
| LLM outputs Txxxx IDs directly | Simpler prompt, high hallucination risk for 3B model | |
| You decide | Claude picks | |

**User's choice:** LLM extracts names → Python queries OpenCTI
**Notes:** Eliminates hallucinated T-IDs entirely. Python code does the authoritative Txxxx lookup against OpenCTI's 709 pre-loaded attack-patterns.

### Q2: No-match handling

| Option | Description | Selected |
|--------|-------------|----------|
| Skip the unmatched technique | Log and continue, no broken relationship created | ✓ |
| Fuzzy match against technique names | difflib.get_close_matches at 0.7 threshold | |
| You decide | Claude picks | |

**User's choice:** Skip the unmatched technique
**Notes:** Accuracy over completeness. Broken graph edges are worse than missing edges for a demo.

---

## Claude's Discretion

- Chunk size: ~1500 tokens with ~150 token overlap
- IOC dedup within job: Python set of (type, value) tuples
- URL scraping: trafilatura primary, BeautifulSoup fallback
- PDF parsing: pypdf2 primary, error on image-based PDFs (no OCR)
- Healthcheck: GET /health via curl on port 8001
- LLM temperature: 0 (deterministic extraction)

## Deferred Ideas

- `malware`, `threat-actor`, `intrusion-set`, `campaign` SDOs — full graph from design doc §5.1
- OCR for image-based PDFs (tesseract)
- Streaming LLM responses via SSE
- Persistent job store (Redis upgrade path documented in deferred section of CONTEXT.md)
