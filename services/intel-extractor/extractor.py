"""
extractor.py — Core extraction pipeline for intel-extractor.

Provides:
  chunk_text()        — sliding-window chunker with overlap
  build_stix_pattern() — map IOC type+value to STIX 2.1 pattern + observable type
  call_llm()          — single-pass LLM extraction with D-03 fallback
  run_extraction()    — plain def background task: parse → chunk → LLM → dedup → write

D-03: On json.JSONDecodeError from LLM, retry with plain-text fallback prompt
      and parse TYPE:VALUE lines via regex.

T-03-04-01: LLM output parsed in try/except with .get() for all key access.
T-03-04-04: IOC counts and types logged; individual IOC values NOT logged at INFO.
"""
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import ollama

import stats_store
from config import OLLAMA_MODEL, OLLAMA_URL
from opencti_client import (
    build_pycti_client,
    create_indicator,
    create_relationship,
    create_report,
    lookup_attack_pattern,
)
from parser import extract_pdf_text, extract_url_text

logger = logging.getLogger(__name__)

# Module-level Ollama client singleton (D-06 / Assumption A1)
_ollama_client = ollama.Client(host=OLLAMA_URL)

# Module-level job state store — lost on restart, acceptable for demo scope (D-06)
jobs: dict[str, dict] = {}

# ── Prompts ──────────────────────────────────────────────────────────────────

# D-01: Single-pass JSON schema extraction prompt
# D-02: One few-shot example (~200 tokens) for format reliability with 3B models
SYSTEM_PROMPT = """\
You are a threat intelligence analyst. Extract structured IOCs and threat data \
from the provided text and return ONLY valid JSON — no prose, no markdown.

Required JSON format:
{
  "iocs": [{"type": "<type>", "value": "<value>"}, ...],
  "techniques": [{"name": "<name>", "description": "<description>"}, ...],
  "malware_families": ["<name>", ...],
  "threat_actors": ["<name>", ...],
  "targeted_sectors": ["<sector>", ...],
  "victim_technologies": ["<product or system>", ...],
  "campaign_summary": "<2-3 sentences: who did what, targeting what, and why it matters>"
}

IOC types: ip, domain, url, hash_md5, hash_sha1, hash_sha256, email

Example input:
"IRGC-affiliated actors exploited CVE-2023-1234 in Unitronics Vision PLCs at US water \
facilities, downloading tools from 1.2.3.4 and evil.example.com. The dropper \
(MD5 d41d8cd98f00b204e9800998ecf8427e) contacted http://c2.bad/beacon."

Example output:
{
  "iocs": [
    {"type": "ip",       "value": "1.2.3.4"},
    {"type": "domain",   "value": "evil.example.com"},
    {"type": "hash_md5", "value": "d41d8cd98f00b204e9800998ecf8427e"},
    {"type": "url",      "value": "http://c2.bad/beacon"}
  ],
  "techniques": [{"name": "exploitation of public-facing application", "description": "CVE-2023-1234 in Unitronics PLCs"}],
  "malware_families": [],
  "threat_actors": ["IRGC-affiliated"],
  "targeted_sectors": ["water", "critical infrastructure"],
  "victim_technologies": ["Unitronics Vision PLC"],
  "campaign_summary": "IRGC-affiliated actors exploited a vulnerability in Unitronics Vision PLCs at US water facilities. Attackers downloaded tools from external infrastructure to establish persistence on OT systems."
}

Extract all IOCs you find. Return empty lists for categories with no matches. \
If campaign_summary cannot be determined, return an empty string.
"""

# D-03 fallback: stripped-down plain-text prompt for when JSON parse fails
FALLBACK_PROMPT = (
    "List all IPs, domains, file hashes, and URLs from this text, "
    "one per line, format: TYPE:VALUE"
)

# ── STIX pattern mapping ──────────────────────────────────────────────────────
# Single-quoted property names for SHA-1 and SHA-256 per STIX 2.1 spec
# (proven in services/feed-orchestrator/feeds/threatfox.py lines 57-74)
IOC_TYPE_TO_STIX: dict[str, tuple[str, str]] = {
    "ip":          ("[ipv4-addr:value = '{v}']",          "IPv4-Addr"),
    "domain":      ("[domain-name:value = '{v}']",        "Domain-Name"),
    "url":         ("[url:value = '{v}']",                "Url"),
    "hash_md5":    ("[file:hashes.MD5 = '{v}']",          "StixFile"),
    "hash_sha1":   ("[file:hashes.'SHA-1' = '{v}']",      "StixFile"),
    "hash_sha256": ("[file:hashes.'SHA-256' = '{v}']",    "StixFile"),
    "email":       ("[email-addr:value = '{v}']",         "Email-Addr"),
}


# ── Core functions ────────────────────────────────────────────────────────────

def chunk_text(text: str, max_chars: int = 6000, overlap_chars: int = 600) -> list[str]:
    """
    Split text into overlapping chunks.

    Chunk size ~6000 chars ≈ 1500 tokens; overlap 600 chars ≈ 150 tokens (10%).
    Prevents IOC loss at chunk boundaries. If text fits in one chunk, returns [text].
    """
    if len(text) <= max_chars:
        return [text]
    chunks = []
    step = max_chars - overlap_chars
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += step
    return chunks


def build_stix_pattern(ioc_type: str, value: str) -> Optional[tuple[str, str]]:
    """
    Map an IOC type and value to a (STIX pattern string, observable type) tuple.

    Returns None for unknown IOC types (silently skip — D-09 principle).
    Single-quotes are escaped in the value before interpolation.
    """
    entry = IOC_TYPE_TO_STIX.get(ioc_type)
    if entry is None:
        return None
    pattern_template, observable_type = entry
    v = value.replace("'", "\\'")  # STIX single-quote escaping (threatfox.py line 59)
    return (pattern_template.replace("{v}", v), observable_type)


def _parse_fallback_text(text: str) -> dict:
    """
    Parse TYPE:VALUE lines from fallback LLM plain-text response (D-03).

    Returns a dict with the same four keys as the primary JSON schema,
    with iocs populated from matched lines and the rest empty.
    """
    # Map common LLM-output type labels to canonical IOC type strings
    type_map = {
        "IP": "ip",
        "DOMAIN": "domain",
        "URL": "url",
        "MD5": "hash_md5",
        "SHA1": "hash_sha1",
        "SHA256": "hash_sha256",
        "HASH": "hash_md5",  # ponytail: ambiguous HASH falls back to md5 for dedup
    }
    iocs = []
    for line in text.splitlines():
        m = re.match(r"^([A-Z0-9]+):(.+)$", line.strip())
        if m:
            raw_type = m.group(1).upper()
            value = m.group(2).strip()
            canonical = type_map.get(raw_type)
            if canonical and value:
                iocs.append({"type": canonical, "value": value})
    return {"iocs": iocs, "techniques": [], "malware_families": [], "threat_actors": []}


def call_llm(client: ollama.Client, model: str, text: str) -> dict:
    """
    Send one chunk to Ollama and return structured extraction result.

    Primary: JSON-mode chat with format="json" and num_ctx=8192 (Pitfall 7).
    D-03 fallback: on JSONDecodeError, retry with plain-text FALLBACK_PROMPT + regex parse.
    Uses .get() for all key access to survive schema divergence (Pitfall 2 / T-03-04-01).
    """
    empty = {"iocs": [], "techniques": [], "malware_families": [], "threat_actors": []}
    try:
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": text},
            ],
            format="json",
            options={"temperature": 0, "num_ctx": 8192},
        )
        data = json.loads(response.message.content)
        # Validate expected keys exist; fill missing with empty list (Pitfall 2)
        return {
            "iocs":                data.get("iocs", []),
            "techniques":          data.get("techniques", []),
            "malware_families":    data.get("malware_families", []),
            "threat_actors":       data.get("threat_actors", []),
            "targeted_sectors":    data.get("targeted_sectors", []),
            "victim_technologies": data.get("victim_technologies", []),
            "campaign_summary":    data.get("campaign_summary", ""),
        }
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("[extractor] LLM JSON parse failed (%s), trying fallback prompt", exc)
    except Exception as exc:
        logger.warning("[extractor] LLM call failed (%s), trying fallback prompt", exc)

    # D-03 fallback: plain-text prompt + regex parse
    try:
        fallback_response = client.chat(
            model=model,
            messages=[
                {"role": "user", "content": f"{FALLBACK_PROMPT}\n\n{text}"},
            ],
            options={"temperature": 0, "num_ctx": 8192},
        )
        return _parse_fallback_text(fallback_response.message.content)
    except Exception as exc:
        logger.warning("[extractor] fallback LLM call also failed (%s), skipping chunk", exc)
        return empty


def run_extraction(
    job_id: str,
    mode: str,
    content: Optional[bytes],
    url: Optional[str],
) -> None:
    """
    Background extraction pipeline — MUST be plain def, NOT async def.

    FastAPI runs plain def background tasks in a thread pool, which isolates
    synchronous pycti/requests calls from the event loop (Pitfall 5).

    Processing order (Pitfall 1 — all indicators created BEFORE create_report):
      1. Mark processing
      2. Parse document → full_text
      3. Chunk full_text
      4. LLM extract per chunk → raw_iocs + technique_keywords
      5. Dedup IOCs within this job
      6. Create pycti client
      7. Create indicators → collect indicator_ids
      8. ATT&CK lookup + create relationships
      9. Create report (only after step 7 complete)
     10. Update job state
    """
    jobs[job_id]["status"] = "processing"
    start_time = time.monotonic()
    source_name = url if url else f"pdf-upload-{job_id[:8]}"

    try:
        # Step 2: Parse
        if mode == "pdf":
            full_text = extract_pdf_text(content)
        elif mode == "url":
            full_text = extract_url_text(url)
        else:
            raise ValueError(f"Unknown mode: {mode!r}")
    except ValueError as exc:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(exc)
        return

    # Step 3: Chunk
    chunks = chunk_text(full_text)
    logger.info("[extractor] job %s: %d chunk(s) from %d chars", job_id, len(chunks), len(full_text))

    # Step 4: LLM extract per chunk
    raw_iocs: list[dict] = []
    technique_keywords: set[str] = set()
    targeted_sectors: set[str] = set()
    victim_technologies: set[str] = set()
    campaign_summary: str = ""

    for i, chunk in enumerate(chunks):
        result = call_llm(_ollama_client, OLLAMA_MODEL, chunk)
        raw_iocs.extend(result.get("iocs", []))
        for t in result.get("techniques", []):
            name = t.get("name", "").strip()
            if name:
                technique_keywords.add(name.lower())
        targeted_sectors.update(s.lower() for s in result.get("targeted_sectors", []) if s)
        victim_technologies.update(v for v in result.get("victim_technologies", []) if v)
        # Take the first non-empty summary (executive summary is usually in the first chunk)
        if not campaign_summary:
            campaign_summary = result.get("campaign_summary", "").strip()

    logger.info(
        "[extractor] job %s: %d raw IOCs, %d technique keywords",
        job_id, len(raw_iocs), len(technique_keywords),
    )

    # Step 5: Dedup IOCs within this job
    seen: set[tuple[str, str]] = set()
    unique_iocs: list[dict] = []
    for ioc in raw_iocs:
        key = (ioc.get("type", ""), ioc.get("value", ""))
        if key not in seen and key[0] and key[1]:
            seen.add(key)
            unique_iocs.append(ioc)

    logger.info("[extractor] job %s: %d unique IOC types after dedup", job_id, len(unique_iocs))

    # Step 6: Build pycti client
    try:
        oc_client = build_pycti_client()
    except Exception as exc:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = f"OpenCTI client init failed: {exc}"
        return

    now_iso = datetime.now(timezone.utc).isoformat()

    # Step 7: Create indicators
    indicator_ids: list[str] = []
    for ioc in unique_iocs:
        ioc_type = ioc.get("type", "")
        ioc_value = ioc.get("value", "")
        result_pat = build_stix_pattern(ioc_type, ioc_value)
        if result_pat is None:
            logger.info("[extractor] unknown IOC type '%s', skipping", ioc_type)
            continue
        pattern, observable_type = result_pat
        indicator = create_indicator(
            client=oc_client,
            name=f"{ioc_type}:{ioc_value}",
            pattern=pattern,
            observable_type=observable_type,
            confidence=75,
            labels=[ioc_type],
            source_name=source_name,
            valid_from=now_iso,
        )
        if indicator and indicator.get("id"):
            indicator_ids.append(indicator["id"])

    logger.info("[extractor] job %s: %d indicators created", job_id, len(indicator_ids))

    # Step 8: ATT&CK lookup + relationships
    matched_techniques: list[str] = []
    for keyword in technique_keywords:
        ap_id = lookup_attack_pattern(oc_client, keyword)
        if ap_id is None:
            continue
        matched_techniques.append(ap_id)
        for ind_id in indicator_ids:
            create_relationship(oc_client, from_id=ind_id, to_id=ap_id)

    # Step 9: Create report (AFTER step 7 — Pitfall 1)
    report_description = campaign_summary or f"Extracted by intel-extractor from {source_name}"
    if victim_technologies:
        report_description += f"\n\nSystems targeted: {', '.join(sorted(victim_technologies))}"
    report_labels = sorted(targeted_sectors) if targeted_sectors else []
    report_result = create_report(
        client=oc_client,
        name=source_name,
        published=now_iso,
        description=report_description,
        indicator_ids=indicator_ids + matched_techniques,
        labels=report_labels,
    )
    report_id = report_result["id"] if report_result else None

    # Step 10: Update job state
    elapsed = time.monotonic() - start_time
    stats_store.increment(docs=1, iocs=len(indicator_ids))
    jobs[job_id].update({
        "status": "complete",
        "iocs_extracted": len(indicator_ids),
        "techniques_found": len(matched_techniques),
        "report_id": report_id,
        "processing_time_s": round(elapsed, 2),
    })
    logger.info(
        "[extractor] job %s complete in %.1fs: %d IOCs, %d techniques, report %s",
        job_id, elapsed, len(indicator_ids), len(matched_techniques), report_id,
    )
