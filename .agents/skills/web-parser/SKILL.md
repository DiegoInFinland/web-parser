---
name: web-parser
description: Analyze websites using web-parser MCP tools — summarize content, inspect HTML, extract links, and detect suspicious code.
---

## Description

This skill provides three tools to fetch and analyze web pages: `fetch_html` to get a readable summary, `fetch_suspicious_html` to get raw HTML source for security analysis, and `extract_links` to extract all hyperlinks.

## When to use

Use this whenever the user asks about a website's content, wants to check if a site looks suspicious, wants to find links on a page, or wants to understand what technologies a site uses.

## How to use

### `fetch_html` — Summarize website content

Use this to get a readable, structured summary of any web page. After fetching:

- Identify the **type of site** (news portal, forum, blog, documentation, e-commerce, social media, corporate, wiki, etc.)
- List the **highlights**: latest news, top stories, featured content, or key sections
- Include **important links** the user might want to visit
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
