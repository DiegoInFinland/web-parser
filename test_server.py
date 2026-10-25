import asyncio
import socket

import httpx
import pytest

import server
from core.client import FetchURL, SafeURL
from core.config import settings


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture
def public_dns(monkeypatch):
    async def getaddrinfo(self, host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.215.14", port))]

    monkeypatch.setattr(asyncio.BaseEventLoop, "getaddrinfo", getaddrinfo)


def mock_client(monkeypatch, handler):
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def make_client(**kwargs):
        return original_client(transport=transport, **kwargs)

    monkeypatch.setattr(server.httpx, "AsyncClient", make_client)


def test_mcp_v2_registers_both_tools():
    assert {tool.name for tool in run(server.mcp.list_tools())} == {
        "fetch_html", "fetch_suspicious_html",
    }


def test_mcp_v2_reports_unsafe_url_as_tool_error():
    from mcp import Client

    async def call():
        async with Client(server.mcp) as client:
            return await client.call_tool("fetch_html", {"url": "http://127.0.0.1"})

    result = run(call())
    assert result.is_error
    assert "non-public" in result.content[0].text


def test_rejects_non_public_addresses_and_schemes():
    for url in ("http://127.0.0.1", "http://[::1]", "http://10.0.0.1", "file:///etc/passwd"):
        with pytest.raises(ValueError):
            run(SafeURL(url).resolve())


def test_rejects_mixed_dns_answers(monkeypatch):
    async def mixed_dns(self, host, port, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.215.14", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", port)),
        ]

    monkeypatch.setattr(asyncio.BaseEventLoop, "getaddrinfo", mixed_dns)
    with pytest.raises(ValueError, match="non-public"):
        run(SafeURL("https://example.org").resolve())


def test_connects_to_validated_ip_with_original_host_and_sni(monkeypatch, public_dns):
    def handler(request):
        assert request.url.host == "93.184.215.14"
        assert request.headers["host"] == "example.org"
        assert request.extensions["sni_hostname"] == "example.org"
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text="<p>Hi</p>")

    mock_client(monkeypatch, handler)
    assert run(FetchURL("https://example.org", False, []).fetch()) == (
        "https://example.org", "<p>Hi</p>"
    )


def test_redirect_to_private_address_is_rejected(monkeypatch, public_dns):
    mock_client(monkeypatch, lambda request: httpx.Response(
        302, headers={"location": "http://127.0.0.1/admin"}
    ))
    with pytest.raises(ValueError, match="non-public"):
        run(FetchURL("https://example.org", True, []).fetch())


def test_follows_redirect_and_returns_html(monkeypatch, public_dns):
    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/destination"})
        assert request.url.path == "/destination"
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>Done</p>")

    mock_client(monkeypatch, handler)
    assert run(FetchURL("https://example.org/start", True, []).fetch()) == (
        "https://example.org/destination", "<p>Done</p>"
    )


@pytest.mark.parametrize("tool_name", ["fetch_html", "fetch_suspicious_html"])
def test_tools_return_final_url_after_redirect(monkeypatch, public_dns, tool_name):
    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/destination"})
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>Done</p>")

    mock_client(monkeypatch, handler)
    result = run(server.mcp.call_tool(tool_name, {
        "url": "https://example.org/start", "follow_redirects": True,
    })).structured_content

    assert result["url"] == "https://example.org/destination"
    assert result["requested_url"] == "https://example.org/start"


def test_rejects_non_html(monkeypatch, public_dns):
    mock_client(monkeypatch, lambda request: httpx.Response(
        200, headers={"content-type": "application/pdf"}, content=b"not html"
    ))
    with pytest.raises(ValueError, match="not HTML"):
        run(FetchURL("https://example.org", False, []).fetch())


def test_rejects_declared_oversize_body(monkeypatch, public_dns):
    mock_client(monkeypatch, lambda request: httpx.Response(200, headers={
        "content-type": "text/html",
        "content-length": str(settings.MAX_RESPONSE_BYTES + 1),
    }, content=b"short"))
    with pytest.raises(ValueError, match="too large"):
        run(FetchURL("https://example.org", False, []).fetch())


def test_rejects_oversize_stream(monkeypatch, public_dns):
    class BigStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(settings.MAX_RESPONSE_BYTES // 65536 + 1):
                yield b"x" * 65536

    mock_client(monkeypatch, lambda request: httpx.Response(
        200, headers={"content-type": "text/html"}, stream=BigStream()
    ))
    with pytest.raises(ValueError, match="too large"):
        run(FetchURL("https://example.org", False, []).fetch())


def test_response_limit_uses_settings(monkeypatch, public_dns):
    monkeypatch.setattr(settings, "MAX_RESPONSE_BYTES", 4)
    mock_client(monkeypatch, lambda request: httpx.Response(
        200, headers={"content-type": "text/html"}, content=b"12345"
    ))

    with pytest.raises(ValueError, match="too large"):
        run(FetchURL("https://example.org", False, []).fetch())


def test_raw_tool_does_not_reserialize_html(monkeypatch):
    html = '<!DOCTYPE html><HTML><BODY class="x">hi</BODY></HTML>'

    async def fake_fetch(self):
        return self.url, html

    monkeypatch.setattr(FetchURL, "fetch", fake_fetch)
    assert run(server.fetch_suspicious_html("https://example.org"))["html"] == html
    result = run(server.mcp.call_tool("fetch_suspicious_html", {"url": "https://example.org"}))
    assert result.structured_content["html"] == html


def test_fetch_html_extracts_title_and_main_text(monkeypatch):
    async def fake_fetch(self):
        return self.url, (
            "<html><head><title>Example Page</title><script>head()</script></head>"
            "<body><header>Menu</header><nav>Links</nav>"
            "<main><h1>Heading</h1><p>Hello <strong>world</strong>.</p>"
            "<aside>Sidebar</aside><small>Promotion</small>"
            "<script>body()</script></main><footer>Legal</footer></body></html>"
        )

    monkeypatch.setattr(FetchURL, "fetch", fake_fetch)
    result = run(server.fetch_html("https://example.org", tags=["small"]))

    assert result["title"] == "Example Page"
    assert result["content"] == "Heading\nHello world."
    assert result["length"] == len(result["content"])


def test_fetch_html_returns_links_through_mcp(monkeypatch):
    async def fake_fetch(self):
        return self.url, '<html><body><a href="/next">Next</a></body></html>'

    monkeypatch.setattr(FetchURL, "fetch", fake_fetch)
    result = run(server.mcp.call_tool("fetch_html", {"url": "https://example.org"}))

    assert result.structured_content["links"] == ["https://example.org/next"]


def test_fetch_html_metadata_uses_final_url(monkeypatch):
    async def fake_fetch(self):
        return "https://example.org/final/page", (
            '<html><head><title>Final</title><meta name="description" content="Summary">'
            '<meta property="og:title" content="Shared title">'
            '<link rel="canonical" href="../canonical"></head>'
            '<body><a href="next">Next</a></body></html>'
        )

    monkeypatch.setattr(FetchURL, "fetch", fake_fetch)
    result = run(server.fetch_html("https://example.org/start", follow_redirects=True))

    assert result["url"] == "https://example.org/final/page"
    assert result["requested_url"] == "https://example.org/start"
    assert result["links"] == ["https://example.org/final/next"]
    assert result["canonical"] == "https://example.org/canonical"
    assert result["description"] == "Summary"
    assert result["og:title"] == "Shared title"


def test_fetch_html_falls_back_to_body(monkeypatch):
    async def fake_fetch(self):
        return self.url, (
            "<html><head><title>News</title></head><body><nav>Menu</nav>"
            "<h1>Story</h1><p>First paragraph.</p><p>Second paragraph.</p>"
            "</body></html>"
        )

    monkeypatch.setattr(FetchURL, "fetch", fake_fetch)
    result = run(server.fetch_html("https://example.org"))

    assert result["title"] == "News"
    assert result["content"] == "Story\nFirst paragraph.\nSecond paragraph."
