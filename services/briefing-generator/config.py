"""
config.py — Environment variable configuration for briefing-generator.

All env vars are read at import time and exposed as module-level constants.
Security: token values are NEVER logged. Only presence is logged via bool().
"""
import logging
import os

logger = logging.getLogger(__name__)

# ── OpenCTI connection ──────────────────────────────────────────────────────
OPENCTI_URL   = os.environ.get("OPENCTI_URL", "http://opencti:8080")
OPENCTI_TOKEN = os.environ.get("OPENCTI_TOKEN", "")

# ── Ollama (local LLM) ──────────────────────────────────────────────────────
OLLAMA_URL     = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL   = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "60"))  # LLM prose generation: 30-45s on 4GB VRAM

# ── Key presence logging (never log key values) ─────────────────────────────
logger.info("OPENCTI_TOKEN configured: %s", bool(OPENCTI_TOKEN))
logger.info("OLLAMA_URL configured: %s", OLLAMA_URL)
