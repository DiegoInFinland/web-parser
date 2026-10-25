import re, httpx
from typing import List
from urllib.parse import urljoin 
from bs4 import BeautifulSoup as bs
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from core.client import FetchURL
from core.config import settings

mcp = MCPServer("web-parser", instructions=settings.SAFETY_INSTRUCTIONS)

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
    soup = bs(html, "html.parser")
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
    result = FetchURL(url, follow_redirects, (tags or []) + settings.EXCLUDED_TAGS)
    # final_url is the URL after any redirects, and html is the fetched HTML content.
    final_url, html = await fetch_for_tool(result)
    soup = bs(html, "html.parser")

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
        elif node.name in settings.BLOCK_TAGS:
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

 
