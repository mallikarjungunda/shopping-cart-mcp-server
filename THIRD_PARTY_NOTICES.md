# Third-party notices

The source code in this repository is original work licensed under the
[MIT License](LICENSE). No third-party source code is copied or vendored here.

The project depends on the packages below. They are installed separately (by
`pip`, or into the Docker image) and remain under their own licenses. Licenses
are listed as declared by each project; check the installed version's metadata
for the authoritative text, for example with `pip-licenses`.

## Runtime dependencies

| Package | License |
|---|---|
| [fastmcp](https://github.com/jlowin/fastmcp) | Apache-2.0 |
| [mcp](https://github.com/modelcontextprotocol/python-sdk) (via fastmcp) | MIT |
| [pydantic](https://github.com/pydantic/pydantic) (via fastmcp) | MIT |
| [httpx](https://github.com/encode/httpx) | BSD-3-Clause |
| [PyJWT](https://github.com/jpadilla/pyjwt) | MIT |
| [cryptography](https://github.com/pyca/cryptography) (via `pyjwt[crypto]`) | Apache-2.0 OR BSD-3-Clause |

## Optional dependencies (`mock`, `dev`)

| Package | License |
|---|---|
| [fastapi](https://github.com/fastapi/fastapi) | MIT |
| [uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause |
| [pytest](https://github.com/pytest-dev/pytest) | MIT |
| [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) | Apache-2.0 |

## Used by examples and docs only

| Package | Where | License |
|---|---|---|
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | `examples/claude_api.py` | MIT |
| [google-genai](https://github.com/googleapis/python-genai) | `examples/gemini_interactions.py` | Apache-2.0 |
| [mermaid](https://github.com/mermaid-js/mermaid) | `docs/index.html` (loaded from a CDN) | MIT |

## Trademarks

ChatGPT, Claude, Gemini and other product names mentioned in this repository
are trademarks of their respective owners. This project is an independent demo
and is not affiliated with or endorsed by them.
