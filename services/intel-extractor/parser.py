"""
parser.py — Document text extraction for intel-extractor.
"""
import io
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
import trafilatura

logger = logging.getLogger(__name__)

def _check_ssrf(hostname: str) -> None:
    """Raise ValueError if hostname resolves to any non-globally-routable address.

    Checks loopback, link-local, private, reserved, multicast, and !is_global to
    cover RFC1918, CGN (100.64/10), IPv6 link-local (fe80::/10), ULA (fc00::/7),
    and documentation/test ranges that an explicit list would miss.

    ponytail: TOCTOU (DNS rebinding) accepted — DNS is re-resolved at request time by
    trafilatura/requests; pinning the IP would require a custom transport. Risk is low
    for a local analyst tool where the analyst controls all inputs.
    """
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve '{hostname}': {exc}") from exc
    for addr_str in addrs:
        addr = ipaddress.ip_address(addr_str)
        if (
            not addr.is_global
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_private
            or addr.is_reserved
            or addr.is_multicast
        ):
            raise ValueError("URL resolves to a private/internal address — not permitted")


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

    SSRF guards: http/https only, no embedded credentials, no private/internal IPs,
    no redirects in the requests fallback path.
    Primary: trafilatura; fallback: requests + BeautifulSoup.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"URL scheme '{parsed.scheme}' not allowed — only http and https are permitted"
        )
    if parsed.username or parsed.password:
        raise ValueError("URL credentials are not permitted")
    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("URL has no hostname")
    _check_ssrf(hostname)

    resp = requests.get(url, timeout=15, allow_redirects=False, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    result = trafilatura.extract(resp.text)
    if result:
        return result
    logger.info("[parser] trafilatura extract failed for %s — falling back to BeautifulSoup", hostname)
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text(separator="\n", strip=True)
