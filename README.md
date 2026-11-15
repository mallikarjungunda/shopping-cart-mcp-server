# Shopping Cart MCP Server

A demo MCP (Model Context Protocol) server, built with Python and [FastMCP](https://gofastmcp.com), that lets **authenticated users shop through LLMs** such as ChatGPT, Claude and Gemini. It exposes cart, catalog and order operations from [spring-boot-kafka-example](https://github.com/mallikarjungunda/spring-boot-kafka-example) as MCP tools.

**Technical specification:** https://mallikarjungunda.github.io/shopping-cart-mcp-server/

Think of it as a waiter: the LLM is the customer, the backend services are the kitchen, and this server only takes orders from the menu (the tools), checks who is at the table (the OAuth token), and never lets the customer name their own price.

## Tools

| Tool | Scope | Purpose |
|---|---|---|
| `search_products`, `get_product` | any valid token | Browse the catalog |
| `view_cart` | `cart:read` | Show the cart and its version |
| `add_to_cart`, `update_cart_item`, `remove_from_cart` | `cart:write` | Change the cart |
| `checkout` | `orders:write` | `confirm=false` previews and returns a `confirmation_token`; `confirm=true` with that token places the order |
| `get_order_status`, `list_orders` | `orders:read` | Track orders (PENDING, APPROVED, REJECTED) |

Safety rules built in: the customer ID comes only from the verified token; prices come only from the store; checkout needs the current cart version plus a short-lived token from a preview of that exact cart, and is idempotent (repeating a confirm call returns the same order); order totals are capped; product text is sanitized before the model sees it; tools a token has no scope for are hidden.

## Quick start (local demo)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # then set BACKEND_SECRET (32+ chars) and export the variables
shopping-cart-devtoken keys     # demo RSA key pair in .dev/
shopping-cart-mock-backend &    # stand-in for the Spring services, port 8111
shopping-cart-mcp               # MCP server at http://127.0.0.1:8000/mcp
shopping-cart-devtoken mint alice   # prints a test access token
```

Try it with the MCP Inspector (`npx @modelcontextprotocol/inspector`), pointing it at `http://127.0.0.1:8000/mcp` with header `Authorization: Bearer <token>`. For ChatGPT, expose the server over HTTPS (for example with a tunnel), set `PUBLIC_URL` to that address, and point `OAUTH_ISSUER` at your authorization server.

## Connecting clients

One set of tools serves every LLM. Only the *published tool schemas* differ per client (see `adapters.py`): Gemini gets a conservative schema because its function declarations accept an OpenAPI subset. The server still validates every call against the full rules.

| Client | How it connects | Notes |
|---|---|---|
| **Claude.ai / Claude Desktop** | Settings, Connectors, add custom connector with the server URL | Calls come from Anthropic's cloud, so the URL must be public HTTPS. Uses OAuth: your authorization server needs dynamic client registration, or enter a client ID and secret under Advanced settings. Allow the callback `https://claude.ai/api/mcp/auth_callback` (Anthropic notes it may move to `claude.com`) |
| **Claude API** | `mcp_servers` plus an `mcp_toolset`, beta `mcp-client-2025-11-20` | You obtain and refresh the access token. See `examples/claude_api.py` |
| **Claude Code** | `claude mcp add --transport http ...` | See `examples/claude_code.sh` |
| **Gemini API** | `mcp_server` tool in the Interactions API with `url` and `headers` | Streamable HTTP only. Send `X-Client-Profile: gemini`. Use a stable HTTPS host. See `examples/gemini_interactions.py` |
| **Gemini CLI** | `mcpServers` in `settings.json` with `httpUrl` and `headers` | See `examples/gemini_cli_settings.json` |
| **ChatGPT** | Developer mode connector with the server URL | Planned next |

Profile selection order: `X-Client-Profile` header, then the MCP client name (anything containing "gemini" or "google"), then `CLIENT_PROFILE` (default `standard`).

Check what a client will see, and catch Gemini-incompatible schemas, with:

```bash
shopping-cart-compat-check http://127.0.0.1:8000/mcp --token "$TOKEN" --profile gemini
```

The Claude and Gemini examples have not been run against the live vendor APIs from this repo; verify them with your own keys.

## Tests

```bash
pytest -q    # 35 tests: token checks, scopes, cart, checkout, isolation, limits, client profiles
```

## Layout

```
src/shopping_cart_mcp/
  server.py        tools and instructions
  auth.py          JWT verification and protected-resource metadata
  backend.py       backend client; mints short-lived downstream tokens
  sanitize.py      cleans untrusted store text
  mock_backend.py  demo stand-in for the Spring services (follows the spec contract)
  adapters.py      per-client tool-schema profiles (standard, gemini)
  compat_check.py  CLI that shows what a client sees and flags incompatibilities
  devtools.py      key generation and token minting for local development
examples/          connection snippets for Claude and Gemini
docs/              technical specification (GitHub Pages)
```

## Status

Done: MCP server, mock backend, tests. Next: update the Spring services (cart service, product price, order changes), the Spring Security authorization server, then the ChatGPT connection and Claude/Gemini adapters. The demo downstream token uses a shared HS256 secret; replace it with proper token exchange before any real use.

[![M8ven Score](https://m8ven.ai/badge/mcp/mallikarjungunda-shopping-cart-mcp-server-11sge9?v=fe8d3feb7504aa626e3f14addf397d5b)](https://m8ven.ai/mcp/mallikarjungunda-shopping-cart-mcp-server-11sge9?s=readme)

## License

Released under the [MIT License](LICENSE). Dependency licenses are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
