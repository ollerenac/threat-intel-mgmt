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

_PRIVATE_NETS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
)


def _check_ssrf(hostname: str) -> None:
    """Raise ValueError if hostname resolves to a private/loopback/link-local address."""
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve '{hostname}': {exc}") from exc
    for addr_str in addrs:
        if any(ipaddress.ip_address(addr_str) in net for net in _PRIVATE_NETS):
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

    # ponytail: trafilatura follows redirects internally; redirect-to-private-IP bypass
    # is accepted as out-of-scope for this local analyst tool.
    downloaded = trafilatura.fetch_url(url)  # returns None on failure, does NOT raise
    if downloaded:
        result = trafilatura.extract(downloaded)
        if result:
            return result

    logger.info("[parser] trafilatura failed for %s — falling back to requests+BeautifulSoup", hostname)
    resp = requests.get(url, timeout=15, allow_redirects=False, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text(separator="\n", strip=True)
