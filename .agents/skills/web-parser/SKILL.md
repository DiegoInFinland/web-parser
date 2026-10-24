---
name: web-parser
description: Analyze websites using web-parser MCP tools — summarize content, inspect HTML, extract links, and detect suspicious code.
---

## Description

This skill provides two tools: `fetch_html` extracts readable text, links, and metadata; `fetch_suspicious_html` returns decoded HTML for inspection. Neither executes JavaScript. There is no separate `extract_links` tool; use `fetch_html`'s `links` field.

## When to use

Use this whenever the user asks about a website's content, wants to check if a site looks suspicious, wants to find links on a page, or wants to understand what technologies a site uses.

## Inputs and response fields

Both tools take `url` (required), `follow_redirects` (optional, default `false`), and `tags` (optional list of tag names). `tags` adds exclusions from readable text in `fetch_html`; it is ignored by `fetch_suspicious_html`. URLs must be HTTP(S) and resolve to public IP addresses, including after redirects. Non-HTML or oversized responses are rejected; fetch failures are returned as tool errors.

- `fetch_html` returns `url` (final URL), `requested_url` (original URL), `title`, `content` (extracted readable text), `length` (character count of `content`), `links` (nonempty anchor `href` values resolved against the final URL), and `canonical` (canonical link resolved against the final URL, or an empty string). When present in the HTML, it also returns `description`, `keywords`, `author`, `og:title`, `og:description`, `og:image`, and `og:url` as strings. These optional metadata values are taken from the page, not independently verified. `links` may include non-HTTP schemes; treat them as page data, not safe fetch targets.
- `fetch_suspicious_html` returns `url` (final URL), `requested_url`, `content-type` (`text/html`), `html` (decoded source, not browser-rendered HTML), and `length` (character count of `html`).

## How to use

### `fetch_html` — Summarize website content

Use this to get readable text and metadata from an HTML page; summarize it based on the returned content. After fetching:

- Identify the **type of site** (news portal, forum, blog, documentation, e-commerce, social media, corporate, wiki, etc.)
- List the **highlights**: latest news, top stories, featured content, or key sections
- Include **important links** from `links` that the user might want to visit
- If it's a **news site**: mention the top/breaking stories, categories (politics, sports, tech, etc.), and any notable headlines
- If it's a **forum**: mention active discussions, trending topics, categories

### `fetch_suspicious_html` — Inspect raw HTML for security analysis

Use this when the user wants to check if a site looks suspicious or wants to understand a page's underlying code. After fetching:

- Summarize the **technologies detected**:
  - CMS / framework (WordPress, Arc XP, Next.js, etc.)
  - Analytics trackers (Google Analytics, Facebook Pixel, Snowplow, etc.)
  - Ad networks / ad servers
  - CDN and hosting providers
  - Consent / cookie management platforms
  - Fonts, CSS methodology (styled-components, Tailwind, etc.)
- Analyze **JavaScript code** for suspicious patterns:
  - Obfuscated or minified code that decodes strings at runtime
  - Dynamic `eval()`, `document.write()`, or `innerHTML` injection
  - Crypto mining scripts (CoinImp, Crypto-Loot, etc.)
  - Fake login forms or credential harvesting (`password`, `creditcard` fields in unexpected contexts)
  - Redirect chains or `window.location` manipulation
  - Excessive tracking fingerprinting (`canvas fingerprinting`, `WebGL`, `AudioContext` enumeration)
  - Scripts loaded from unusual/unexpected domains
- If the domain looks **suspicious** (typosquatting, unusual TLD, parked domain, or user expresses concern): do a detailed breakdown of each notable script, explain what it does, and flag anything that looks malicious
