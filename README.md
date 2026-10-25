# web-parser

A lightweight MCP server that helps AI agents inspect public web pages. It fetches HTML, extracts page text, links, and metadata, and lets agents review the raw HTML for suspicious patterns, including embedded JavaScript. It does not execute JavaScript or fetch external script files.

## Setup

```sh
docker build -t web-parser .
```

Add the following configuration to your AI client, for example:

```json
{
  "mcpServers": {
    "web-parser": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "web-parser"]
    }
  }
}
```

Restart your AI client to load the MCP server. Configuration paths and formats may vary depending on the client.

## Example workflow

1. Ask the agent to fetch the page with fetch_html, following redirects if needed. It checks that the URL returns an HTML response and provides the page’s text, title, metadata, and links.
2. Have the agent compare those results with what you expect—for example, the correct page title, latest post, canonical URL, and navigation links.
3. If something looks unexpected, have it fetch the same page with fetch_suspicious_html and inspect the static HTML for unfamiliar script sources, obfuscation, or redirect-related code.
4. Ask for a report that separates confirmed observations from patterns that need human review.

Example request: _“Check https://myblog.example/about, following redirects. Report the requested and final URLs, whether it returned HTML, and whether the title and content look expected. Then inspect up to five same-domain links, following redirects for each. Don’t execute JavaScript; flag suspicious source patterns with evidence.”_

## Limitations

The server does not run JavaScript code. So it cannot verify or confirm that a page works in a browser.

## Development and tests

The default build is production: it contains only the server and runtime dependencies, and runs as an unprivileged user.

```sh
docker build -t web-parser .
docker run --rm -i web-parser
```

The development target also contains the tests, pytest, and the MCP CLI. Run the server or override its command to run tests:

```sh
docker build --target development -t web-parser:dev .
docker run --rm -i web-parser:dev
docker run --rm --network none web-parser:dev python -m pytest -q -p no:cacheprovider test_server.py
```

The test target runs the suite by default (no external network is needed):

```sh
docker build --target test -t web-parser:test .
docker run --rm --network none web-parser:test
```
