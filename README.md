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
| `checkout` | `orders:write` | `confirm=false` previews, `confirm=true` places the order |
| `get_order_status`, `list_orders` | `orders:read` | Track orders (PENDING, APPROVED, REJECTED) |

Safety rules built in: the customer ID comes only from the verified token; prices come only from the store; checkout needs the current cart version and is idempotent; order totals are capped; product text is sanitized before the model sees it; tools a token has no scope for are hidden.

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

## Tests

```bash
pytest -q    # 18 tests: token checks, scopes, cart, checkout, isolation, limits
```

## Layout

```
src/shopping_cart_mcp/
  server.py        tools and instructions
  auth.py          JWT verification and protected-resource metadata
  backend.py       backend client; mints short-lived downstream tokens
  sanitize.py      cleans untrusted store text
  mock_backend.py  demo stand-in for the Spring services (follows the spec contract)
  devtools.py      key generation and token minting for local development
docs/              technical specification (GitHub Pages)
```

## Status

Done: MCP server, mock backend, tests. Next: update the Spring services (cart service, product price, order changes), the Spring Security authorization server, then the ChatGPT connection and Claude/Gemini adapters. The demo downstream token uses a shared HS256 secret; replace it with proper token exchange before any real use.
