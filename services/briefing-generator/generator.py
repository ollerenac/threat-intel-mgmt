"""
generator.py — Core briefing generation logic for briefing-generator.

Provides:
  run_generate(briefing_id, period_hours)  — async entry point (via asyncio.to_thread)
  briefings                                 — module-level state dict (lost on restart, D-10)

All blocking I/O (pycti reads, ollama chat) is inside _run_generate_sync(), called via
asyncio.to_thread from the async run_generate() wrapper (BC-03: event loop not blocked).

Entity list calls use _safe_list() defensive wrapper (assumption A2: not all entity types
may accept filters kwarg — fallback to first=10 on failure).
"""
import asyncio
import logging
import ollama
from datetime import datetime, timezone, timedelta

from config import OLLAMA_MODEL, OLLAMA_URL, OLLAMA_TIMEOUT
from opencti_client import build_pycti_client

logger = logging.getLogger(__name__)

# Module-level singleton — timeout set for 30-45s LLM prose generation (Pitfall 3)
_ollama_client = ollama.Client(host=OLLAMA_URL, timeout=OLLAMA_TIMEOUT)

# Module-level state — lost on restart, acceptable for demo (D-10)
briefings: dict[str, dict] = {}

SYSTEM_PROMPT = """\
You are a senior threat intelligence analyst. Write a 200-300 word executive summary \
for C-suite leadership covering the threat landscape for the given period. Be factual, \
concise, and avoid technical jargon. Highlight business risk and strategic implications. \
Do not include lists, headers, or markdown — write in plain professional prose only."""

SECTOR_KEYWORDS = {"finance", "critical-infrastructure", "healthcare", "energy", "government"}


def _make_updated_at_filter(period_hours: int) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(hours=period_hours)).isoformat()
    return {
        "mode": "and",
        "filters": [{"key": "updated_at", "values": [since]}],
        "filterGroups": [],
    }


def _extract_sectors(indicators: list[dict]) -> list[str]:
    found = set()
    for ind in indicators:
        for label in ind.get("objectLabel", []):
            v = label.get("value", "").lower()
            if v in SECTOR_KEYWORDS:
                found.add(v)
    return sorted(found)


def _collect_threat_data(client, period_hours: int) -> dict:
    filters = _make_updated_at_filter(period_hours)

    # ponytail: each call wrapped independently — A2: not all entity types may accept filters kwarg
    def _safe_list(entity, **kwargs):
        try:
            return entity.list(**kwargs) or []
        except Exception as exc:
            logger.warning("[generator] list failed (%s), falling back to first=10", exc)
            try:
                return entity.list(first=10) or []
            except Exception:
                return []

    indicators = _safe_list(client.indicator, filters=filters, first=10,
                            orderBy="updated_at", orderMode="desc")
    actors     = _safe_list(client.threat_actor, filters=filters, first=10)
    malware    = _safe_list(client.malware, filters=filters, first=10)
    campaigns  = _safe_list(client.campaign, filters=filters, first=10)
    patterns   = _safe_list(client.attack_pattern, filters=filters, first=10)

    # D-04: sort IOCs by confidence score descending, take first 10
    indicators = sorted(indicators, key=lambda x: x.get("x_opencti_score", 0), reverse=True)[:10]
    sectors = _extract_sectors(indicators)

    return {
        "indicators": indicators,
        "actors": actors,
        "malware": malware,
        "campaigns": campaigns,
        "attack_patterns": patterns,
        "sectors": sectors,
    }


def _build_stats_block(data: dict, period_hours: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    iocs = data["indicators"]
    ioc_types: dict[str, int] = {}
    for ind in iocs:
        t = ind.get("x_opencti_main_observable_type", "Unknown")
        ioc_types[t] = ioc_types.get(t, 0) + 1

    top_conf = max((i.get("x_opencti_score", 0) for i in iocs), default=0) / 100

    actor_names   = [a.get("name", "Unknown") for a in data["actors"]]
    malware_names = [m.get("name", "Unknown") for m in data["malware"]]
    campaigns     = data["campaigns"]
    patterns      = data["attack_patterns"]
    pattern_strs  = [
        f"{p.get('x_mitre_id', '')} ({p.get('name', '')})"
        for p in patterns
    ]
    sectors = data.get("sectors", [])

    return (
        f"Period: last {period_hours}h (ending {now}).\n"
        f"New IOCs: {len(iocs)} ({', '.join(f'{c} {t}' for t, c in ioc_types.items()) or 'none'})"
        + (f", top confidence: {top_conf:.2f}" if iocs else "") + ".\n"
        f"Active threat actors: {', '.join(actor_names) or 'none identified'}.\n"
        f"Active malware: {', '.join(malware_names) or 'none identified'}.\n"
        f"Active campaigns: {len(campaigns)} identified.\n"
        f"Top ATT&CK techniques: {', '.join(pattern_strs[:3]) or 'none'}.\n"
        f"Affected sectors: {', '.join(sectors) or 'none identified'}.\n"
    )


def _call_ollama(stats_block: str) -> str:
    response = _ollama_client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": stats_block},
        ],
        options={"temperature": 0.3},
        # NOTE: NO format="json" — we want plain prose output (anti-pattern from extractor.py)
    )
    text = response.message.content.strip()
    # Truncate if LLM overshoots (deferred: no re-prompt per CONTEXT.md)
    words = text.split()
    if len(words) > 320:
        text = " ".join(words[:300]) + "..."
    return text


def _run_generate_sync(briefing_id: str, period_hours: int) -> None:
    """All blocking I/O here — pycti + ollama are sync clients (BC-03)."""
    client = build_pycti_client()
    data = _collect_threat_data(client, period_hours)
    stats_block = _build_stats_block(data, period_hours)
    text = _call_ollama(stats_block)
    briefings[briefing_id]["text"] = text
    briefings[briefing_id]["status"] = "done"


async def run_generate(briefing_id: str, period_hours: int) -> None:
    try:
        await asyncio.to_thread(_run_generate_sync, briefing_id, period_hours)
    except Exception as exc:
        logger.error("[generator] generation failed: %s", exc)
        briefings[briefing_id]["status"] = "error"
        briefings[briefing_id]["error"] = str(exc)
