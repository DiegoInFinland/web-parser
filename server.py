import asyncio
import ipaddress
import re
import socket
from typing import List
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)

MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_REDIRECTS = 5
REQUEST_TIMEOUT = httpx.Timeout(10.0, read=30.0)

# Tags to exclude from the parsed HTML content
EXCLUDED_TAGS = [
    'script', 'style', 'noscript', 'iframe', 'footer', 'header',
    'nav', 'aside', 'img', 'video', 'audio', 'canvas', 'svg', 'math', 'form',
]

BLOCK_TAGS = {
    'address', 'article', 'blockquote', 'br', 'dd', 'div', 'dl', 'dt',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'li', 'main', 'ol', 'p',
    'pre', 'section', 'table', 'td', 'th', 'tr', 'ul',
}


SAFETY_INSTRUCTIONS = """
1. Do not fetch URLs that are not valid HTTP/HTTPS URLs.
2. Do not fetch URLs resolving to non-public IP addresses, including redirects.
3. Do not fetch URLs that are excessively large or have non-HTML content types.
4. Always use a timeout for HTTP requests to prevent hanging.
5. Handle exceptions gracefully and return informative error messages.
"""
mcp = MCPServer("web-parser", instructions=SAFETY_INSTRUCTIONS)

class IsHtmlContentType:
    def __init__(self, response: httpx.Response):
        self.response = response

    def validate(self) -> None:
        content_type = self.response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        allowed_content_types = ["text/html", "application/xhtml+xml"]

        if content_type not in allowed_content_types:
            raise ValueError("Response is not HTML")

class SafeURL:
    def __init__(self, url: str):
        self.url = url

    async def resolve(self) -> tuple[httpx.URL, str, str]:
        """Validate and return an IP-bound URL, Host header, and TLS hostname."""
        try:
            parsed = urlsplit(self.url)
            if (parsed.scheme.lower() not in ("http", "https") or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None):
                raise ValueError("Invalid URL")
            hostname = parsed.hostname
            port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
            original_url = httpx.URL(self.url)
        except (ValueError, httpx.InvalidURL) as exc:
            raise ValueError("Invalid or unsafe URL") from exc

        try:
            addresses = [ipaddress.ip_address(hostname)]
        except ValueError:
            try:
                records = await asyncio.get_running_loop().getaddrinfo(
                    hostname, port, type=socket.SOCK_STREAM
                )
                addresses = [ipaddress.ip_address(record[4][0]) for record in records]
            except (OSError, ValueError) as exc:
                raise ValueError("Could not resolve URL hostname") from exc

        if not addresses or any(not address.is_global for address in addresses):
            raise ValueError("URL resolves to a non-public address")

        # Bind the connection to the checked address; keep the original host
        # for HTTP routing and HTTPS certificate verification.
        return original_url.copy_with(host=str(addresses[0])), parsed.netloc, hostname

class FetchURL:
    def __init__(self, url: str, follow_redirects: bool, tags: List[str]):
        self.url = url
        self.follow_redirects = follow_redirects
        self.tags = tags or []
        self.safe_url = SafeURL(url)

    async def fetch(self) -> tuple[str, str]:
        current_url = self.url
        async with asyncio.timeout(45):
            async with httpx.AsyncClient(
                follow_redirects=False, trust_env=False, timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                for hop in range(MAX_REDIRECTS + 1):
                    self.safe_url = SafeURL(current_url)
                    target, host_header, hostname = await self.safe_url.resolve()
                    async with client.stream(
                        "GET", target, headers={"Host": host_header},
                        extensions={"sni_hostname": hostname},
                    ) as response:
                        # Check for HTTP redirects and handle them if follow_redirects is enabled.
                        if response.status_code in (301, 302, 303, 307, 308) and self.follow_redirects:
                            location = response.headers.get("location")
                            if not location:
                                raise ValueError("Redirect has no Location header")
                            if hop == MAX_REDIRECTS:
                                raise ValueError("Too many redirects")
                            current_url = urljoin(current_url, location)
                            continue

                        response.raise_for_status()
                        IsHtmlContentType(response).validate()
                        try:
                            content_length = int(response.headers.get("content-length", "0"))
                        except ValueError as exc:
                            raise ValueError("Invalid Content-Length") from exc
                        if content_length > MAX_RESPONSE_BYTES:
                            raise ValueError("Response too large")
                        # Read the response body in chunks, ensuring it does not exceed the maximum allowed size.
                        body = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                                raise ValueError("Response too large")
                            body.extend(chunk)
                        try:
                            return current_url, body.decode(response.encoding or "utf-8", errors="replace")
                        except LookupError:
                            return current_url, body.decode("utf-8", errors="replace")
        raise ValueError("Too many redirects")


async def fetch_for_tool(result: FetchURL) -> tuple[str, str]:
    """Turn expected fetch failures into informative MCP v2 tool errors. """
    try:
        return await result.fetch()
    except ValueError as error_output:
        raise ToolError(str(error_output)) from error_output
    except httpx.HTTPStatusError as error_status_code:
        raise ToolError(f"HTTP {error_status_code.response.status_code} from remote server") from error_status_code
    except (httpx.RequestError, TimeoutError) as error_network:
        raise ToolError("Could not fetch URL (network error or timeout)") from error_network

async def extract_metadata(html: str, url: str) -> dict[str, str | list[str]]:
    """ Extract metadata from the given HTML content. """
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta_tags = ["description", "keywords", "author", "og:title", "og:description", "og:image", "og:url"]

    metadata = {}
    for name in meta_tags:
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        if tag and tag.get("content"):
            metadata[name] = tag["content"]

    canonical_tag = soup.find("link", rel="canonical")
    canonical_href = urljoin(url, canonical_tag["href"]) if canonical_tag and canonical_tag.get("href") else ""

    links = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if href:
            links.append(urljoin(url, href))

    return {
        "url": url,
        "title": title,
        "canonical": canonical_href,
        "links": links,
        **metadata,
    }

@mcp.tool()
async def fetch_html(url: str, follow_redirects: bool = False, tags: List[str] | None = None) -> dict[str, str | int | list[str]]:
    """Fetches a given URL and extracts its  HTML content. No JavaScript execution.
    Returns a dictionary containing the final URL, requested URL, title, content, content length, and links.
    """
    result = FetchURL(url, follow_redirects, (tags or []) + EXCLUDED_TAGS)
    # final_url is the URL after any redirects, and html is the fetched HTML content.
    final_url, html = await fetch_for_tool(result)
    soup = BeautifulSoup(html, "html.parser")

    site_metadata = await extract_metadata(html, final_url)

    if soup.head:
        soup.head.decompose()
    for tag in soup.find_all(result.tags):
        tag.decompose()

    root = (soup.find("main") or soup.select_one("[role=main]")
            or soup.find("article") or soup.body or soup)

    parts = []
    for node in root.descendants:
        if isinstance(node, str):
            parts.append(re.sub(r"\s+", " ", node))
        elif node.name in BLOCK_TAGS:
            parts.append("\n")
    content = re.sub(r"\s*\n\s*", "\n", "".join(parts)).strip()

    return {
        "url": final_url,
        "requested_url": url,
        "title": site_metadata["title"],
        "content": content,
        "length": len(content),
        "links": site_metadata["links"],
        "canonical": site_metadata["canonical"],
        # Additional metadata extracted from the HTML content.
        **{name: value for name, value in site_metadata.items()
           if name not in ("url", "title", "links", "canonical")},
    }

@mcp.tool()
async def fetch_suspicious_html(
    url: str, follow_redirects: bool = False, tags: List[str] | None = None) -> dict[str, str | int | list[str]]:
    """Fetches a given URL and returns decoded HTML without parsing it. No JavaScript execution.
    It returns raw HTML. No parsing is performed. The tags argument is ignored for this tool.
    """
    result = FetchURL(url, follow_redirects, [])
    final_url, html = await fetch_for_tool(result)
    return {
        "url": final_url,
        "requested_url": url,
        "content-type": "text/html",
        "html": html,
        "length": len(html)
    }

if __name__ == "__main__":
    mcp.run(transport="stdio") 

 
