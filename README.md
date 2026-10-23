# web-parser

Small MCP server to fetch web pages.

## Docker targets

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
