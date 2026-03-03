"""URL content extraction with SSRF prevention."""

from __future__ import annotations

import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from core.services import memory_service

from .chunker import chunk_text

_ALLOWED_SCHEMES = {"http", "https"}
_ALLOWED_PORTS = {80, 443}
_MAX_REDIRECTS = 5
_TIMEOUT = 30.0
_USER_AGENT = "Engram/1.0"

# Tags to strip from HTML before extracting text
_STRIP_TAGS = {"script", "style", "nav", "header", "footer", "aside"}
# Priority order for content containers
_CONTENT_TAGS = ("article", "main", "body")


class SSRFError(Exception):
    """Raised when a URL fails SSRF validation."""


def _validate_url(url: str) -> str:
    """Validate a URL against SSRF rules. Returns the normalized URL.

    Checks:
    - Allowed schemes (http, https only)
    - Allowed ports (80, 443, or default)
    - Blocked IP ranges (loopback, RFC1918, link-local, cloud metadata)
    """
    parsed = urlparse(url)

    # Scheme check
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise SSRFError(f"Scheme '{parsed.scheme}' not allowed. Use http or https.")

    # Port check
    if parsed.port is not None and parsed.port not in _ALLOWED_PORTS:
        raise SSRFError(f"Port {parsed.port} not allowed. Use 80 or 443.")

    # Hostname resolution and IP check
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("No hostname in URL")

    try:
        addrinfos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise SSRFError(f"Cannot resolve hostname: {hostname}")

    for family, _type, _proto, _canonname, sockaddr in addrinfos:
        ip_str = sockaddr[0]
        ip = ipaddress.ip_address(ip_str)
        _check_ip(ip, hostname)

    return url


def _check_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, hostname: str) -> None:
    """Reject private, loopback, link-local, and metadata IPs."""
    if ip.is_loopback:
        raise SSRFError(f"Loopback address blocked: {hostname} -> {ip}")

    if ip.is_private:
        raise SSRFError(f"Private address blocked: {hostname} -> {ip}")

    if ip.is_link_local:
        raise SSRFError(f"Link-local address blocked: {hostname} -> {ip}")

    # Explicit cloud metadata check (covers 169.254.169.254)
    if isinstance(ip, ipaddress.IPv4Address):
        if ip == ipaddress.IPv4Address("169.254.169.254"):
            raise SSRFError(f"Cloud metadata address blocked: {hostname} -> {ip}")


async def scrape_url(
    url: str,
    source: str = "url",
    tags: list[str] | None = None,
    importance: float = 0.5,
) -> list[dict]:
    """Fetch URL, extract content, chunk, create memories.

    Returns list of {id, chunk_index, status}.
    """
    _validate_url(url)

    html, final_url = await _fetch_with_redirects(url)
    title, text = _extract_content(html)

    if not text.strip():
        raise ValueError(f"No text content extracted from {url}")

    chunks = chunk_text(text)
    total_chunks = len(chunks)
    tags = list(tags or [])

    results = []
    for i, chunk_content in enumerate(chunks):
        memory = await memory_service.create_memory(
            content=chunk_content,
            source=source,
            tags=tags + ["ingested", "web"],
            metadata={
                "ingestion": {
                    "url": final_url,
                    "title": title or "",
                    "chunk_index": i,
                    "total_chunks": total_chunks,
                }
            },
            importance=importance,
        )
        results.append({"id": str(memory.id), "chunk_index": i, "status": "ok"})

    return results


async def _fetch_with_redirects(url: str) -> tuple[str, str]:
    """Fetch URL with manual redirect following and per-hop SSRF validation.

    Returns (html_content, final_url).
    """
    current_url = url
    async with httpx.AsyncClient(
        timeout=_TIMEOUT,
        follow_redirects=False,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        for _ in range(_MAX_REDIRECTS):
            resp = await client.get(current_url)
            if resp.is_redirect:
                location = resp.headers.get("location", "")
                if not location:
                    raise ValueError("Redirect with no Location header")
                # Resolve relative redirects
                redirect_url = str(resp.url.join(location))
                _validate_url(redirect_url)
                current_url = redirect_url
                continue
            resp.raise_for_status()
            return resp.text, str(resp.url)

    raise ValueError(f"Too many redirects (>{_MAX_REDIRECTS})")


class _ContentExtractor(HTMLParser):
    """Extract text content from HTML, stripping unwanted elements."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._current_tag_stack: list[str] = []
        self._sections: dict[str, list[str]] = {"article": [], "main": [], "body": []}
        self._active_section: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._current_tag_stack.append(tag)

        if tag in _STRIP_TAGS:
            self._skip_depth += 1
            return

        if tag == "title":
            self._in_title = True

        if tag in ("article", "main", "body"):
            self._active_section = tag

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag in _STRIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

        if tag == "title":
            self._in_title = False

        if self._current_tag_stack and self._current_tag_stack[-1] == tag:
            self._current_tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
            return

        if self._skip_depth > 0:
            return

        text = data.strip()
        if not text:
            return

        # Add to all applicable sections
        for section_tag in _CONTENT_TAGS:
            if self._active_section == section_tag or section_tag == "body":
                self._sections[section_tag].append(text)

    def get_text(self) -> str:
        """Return extracted text, preferring article > main > body."""
        for tag in _CONTENT_TAGS:
            if self._sections[tag]:
                return "\n\n".join(self._sections[tag])
        return ""


def _extract_content(html: str) -> tuple[str, str]:
    """Parse HTML and extract (title, text_content)."""
    parser = _ContentExtractor()
    parser.feed(html)
    return parser.title.strip(), parser.get_text()
