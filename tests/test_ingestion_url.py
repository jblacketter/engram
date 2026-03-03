"""Tests for ingestion.url_scraper — URL content extraction and SSRF prevention."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingestion.url_scraper import (
    SSRFError,
    _extract_content,
    _validate_url,
    scrape_url,
)


class TestValidateUrl:
    """SSRF prevention — _validate_url."""

    def test_allows_http(self):
        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 0, "", ("93.184.216.34", 0)),
            ]
            result = _validate_url("http://example.com/page")
        assert result == "http://example.com/page"

    def test_allows_https(self):
        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 0, "", ("93.184.216.34", 0)),
            ]
            result = _validate_url("https://example.com/page")
        assert result == "https://example.com/page"

    def test_rejects_file_scheme(self):
        with pytest.raises(SSRFError, match="Scheme.*not allowed"):
            _validate_url("file:///etc/passwd")

    def test_rejects_ftp_scheme(self):
        with pytest.raises(SSRFError, match="Scheme.*not allowed"):
            _validate_url("ftp://internal.server/file")

    def test_rejects_gopher_scheme(self):
        with pytest.raises(SSRFError, match="Scheme.*not allowed"):
            _validate_url("gopher://evil.com/")

    def test_rejects_non_standard_port(self):
        with pytest.raises(SSRFError, match="Port.*not allowed"):
            _validate_url("http://example.com:8080/api")

    def test_rejects_port_9090(self):
        with pytest.raises(SSRFError, match="Port.*not allowed"):
            _validate_url("https://example.com:9090/api")

    def test_allows_port_80(self):
        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 0, "", ("93.184.216.34", 0)),
            ]
            _validate_url("http://example.com:80/page")

    def test_allows_port_443(self):
        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 0, "", ("93.184.216.34", 0)),
            ]
            _validate_url("https://example.com:443/page")

    def test_rejects_loopback_ipv4(self):
        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 0, "", ("127.0.0.1", 0)),
            ]
            with pytest.raises(SSRFError, match="Loopback"):
                _validate_url("http://localhost/admin")

    def test_rejects_loopback_ipv6(self):
        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.getaddrinfo.return_value = [
                (10, 1, 0, "", ("::1", 0, 0, 0)),
            ]
            with pytest.raises(SSRFError, match="Loopback"):
                _validate_url("http://localhost/admin")

    def test_rejects_private_10_network(self):
        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 0, "", ("10.0.0.1", 0)),
            ]
            with pytest.raises(SSRFError, match="Private"):
                _validate_url("http://internal.corp/api")

    def test_rejects_private_172_network(self):
        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 0, "", ("172.16.0.1", 0)),
            ]
            with pytest.raises(SSRFError, match="Private"):
                _validate_url("http://docker-host/api")

    def test_rejects_private_192_network(self):
        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 0, "", ("192.168.1.1", 0)),
            ]
            with pytest.raises(SSRFError, match="Private"):
                _validate_url("http://home-router/admin")

    def test_rejects_link_local(self):
        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 0, "", ("169.254.1.1", 0)),
            ]
            with pytest.raises(SSRFError, match="Link-local"):
                _validate_url("http://link-local-host/")

    def test_rejects_cloud_metadata(self):
        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 0, "", ("169.254.169.254", 0)),
            ]
            with pytest.raises(SSRFError):
                _validate_url("http://metadata.google.internal/")

    def test_rejects_no_hostname(self):
        with pytest.raises(SSRFError, match="No hostname"):
            _validate_url("http:///path")

    def test_rejects_unresolvable_hostname(self):
        import socket

        with patch("ingestion.url_scraper.socket") as mock_socket:
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.gaierror = socket.gaierror
            mock_socket.getaddrinfo.side_effect = socket.gaierror("Name not found")
            with pytest.raises(SSRFError, match="Cannot resolve"):
                _validate_url("http://nonexistent.invalid/")


class TestExtractContent:
    """HTML content extraction."""

    def test_extracts_title(self):
        html = "<html><head><title>Test Page</title></head><body>Content</body></html>"
        title, text = _extract_content(html)
        assert title == "Test Page"

    def test_extracts_body_text(self):
        html = "<html><body><p>Hello world</p></body></html>"
        title, text = _extract_content(html)
        assert "Hello world" in text

    def test_prefers_article_over_body(self):
        html = (
            "<html><body>"
            "<nav>Navigation</nav>"
            "<article><p>Article content</p></article>"
            "<footer>Footer</footer>"
            "</body></html>"
        )
        title, text = _extract_content(html)
        assert "Article content" in text

    def test_strips_script_tags(self):
        html = "<html><body><script>alert('xss')</script><p>Safe content</p></body></html>"
        _, text = _extract_content(html)
        assert "alert" not in text
        assert "Safe content" in text

    def test_strips_style_tags(self):
        html = "<html><body><style>.hidden{display:none}</style><p>Visible</p></body></html>"
        _, text = _extract_content(html)
        assert "hidden" not in text
        assert "Visible" in text

    def test_strips_nav_tags(self):
        html = "<html><body><nav>Menu items</nav><main><p>Main content</p></main></body></html>"
        _, text = _extract_content(html)
        assert "Main content" in text

    def test_empty_html_returns_empty(self):
        _, text = _extract_content("<html><body></body></html>")
        assert text == ""


class TestScrapeUrl:
    """Full URL scraping pipeline."""

    @pytest.mark.asyncio
    async def test_scrape_creates_memories(self):
        html = "<html><head><title>Test</title></head><body><p>Page content here</p></body></html>"
        mock_memory = MagicMock()
        mock_memory.id = "mem-1"

        with (
            patch("ingestion.url_scraper._validate_url", return_value="https://example.com"),
            patch("ingestion.url_scraper._fetch_with_redirects", new_callable=AsyncMock) as mock_fetch,
            patch("ingestion.url_scraper.memory_service") as svc,
        ):
            mock_fetch.return_value = (html, "https://example.com")
            svc.create_memory = AsyncMock(return_value=mock_memory)

            results = await scrape_url(
                url="https://example.com",
                tags=["test"],
            )

        assert len(results) >= 1
        assert results[0]["status"] == "ok"
        call_kwargs = svc.create_memory.call_args[1]
        assert "ingested" in call_kwargs["tags"]
        assert "web" in call_kwargs["tags"]
        assert call_kwargs["metadata"]["ingestion"]["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_scrape_rejects_ssrf(self):
        with patch("ingestion.url_scraper._validate_url", side_effect=SSRFError("blocked")):
            with pytest.raises(SSRFError):
                await scrape_url(url="http://localhost/admin")

    @pytest.mark.asyncio
    async def test_scrape_rejects_empty_content(self):
        html = "<html><body></body></html>"
        with (
            patch("ingestion.url_scraper._validate_url", return_value="https://example.com"),
            patch("ingestion.url_scraper._fetch_with_redirects", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_fetch.return_value = (html, "https://example.com")
            with pytest.raises(ValueError, match="No text content"):
                await scrape_url(url="https://example.com")
