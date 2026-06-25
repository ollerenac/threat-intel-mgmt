"""
parser.py — Document text extraction for intel-extractor.
"""
import io
import logging
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
import trafilatura

logger = logging.getLogger(__name__)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract plain text from PDF bytes. Raises ValueError for image-based or unreadable PDFs."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_text = [page.extract_text() for page in reader.pages]
    except Exception as exc:
        raise ValueError(f"PDF appears to be image-based — no extractable text found") from exc
    full_text = "\n".join(t for t in pages_text if t)
    if not full_text.strip():
        raise ValueError("PDF appears to be image-based — no extractable text found")
    return full_text


def extract_url_text(url: str) -> str:
    """Fetch and extract plain text from a URL.

    SSRF guard: only http/https schemes are permitted.
    Primary: trafilatura; fallback: requests + BeautifulSoup.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"URL scheme '{parsed.scheme}' not allowed — only http and https are permitted"
        )

    downloaded = trafilatura.fetch_url(url)  # returns None on failure, does NOT raise
    if downloaded:
        result = trafilatura.extract(downloaded)
        if result:
            return result

    logger.info("[parser] trafilatura failed for %s — falling back to requests+BeautifulSoup", url)
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text(separator="\n", strip=True)
