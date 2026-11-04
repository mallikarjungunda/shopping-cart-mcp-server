import httpx
import pytest
from fastmcp.exceptions import ToolError

from shopping_cart_mcp.devtools import ALL_SCOPES

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
HDRS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def test_no_token_is_401(env):
    r = httpx.post(f"{env['url']}/mcp", json=INIT, headers=HDRS)
    assert r.status_code == 401
    assert "resource_metadata" in r.headers.get("www-authenticate", "")


def test_protected_resource_metadata(env):
    r = httpx.get(f"{env['url']}/.well-known/oauth-protected-resource/mcp")
    assert r.status_code == 200
    body = r.json()
    assert body["authorization_servers"][0].rstrip("/") == env["settings"].issuer
    assert set(body["scopes_supported"]) == set(ALL_SCOPES)


def test_garbage_token_rejected(env):
    r = httpx.post(f"{env['url']}/mcp", json=INIT, headers={**HDRS, "Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_wrong_audience_rejected(env, token):
    from shopping_cart_mcp.devtools import mint_token
    t = mint_token(env["private"], "alice", issuer=env["settings"].issuer, audience="someone-else")
    r = httpx.post(f"{env['url']}/mcp", json=INIT, headers={**HDRS, "Authorization": f"Bearer {t}"})
    assert r.status_code == 401


def test_wrong_issuer_rejected(env):
    from shopping_cart_mcp.devtools import mint_token
    t = mint_token(env["private"], "alice", issuer="http://evil.example", audience=env["settings"].audience)
    r = httpx.post(f"{env['url']}/mcp", json=INIT, headers={**HDRS, "Authorization": f"Bearer {t}"})
    assert r.status_code == 401


def test_expired_token_rejected(env, token):
    t = token("alice", minutes=-5)
    r = httpx.post(f"{env['url']}/mcp", json=INIT, headers={**HDRS, "Authorization": f"Bearer {t}"})
    assert r.status_code == 401


async def test_all_tools_with_full_scopes(connect):
    async with connect() as c:
        names = {t.name for t in await c.list_tools()}
    assert names == {"search_products", "get_product", "view_cart", "add_to_cart", "update_cart_item",
                     "remove_from_cart", "checkout", "get_order_status", "list_orders"}


async def test_scopes_limit_visible_tools(connect):
    async with connect(scopes=["cart:read"]) as c:
        names = {t.name for t in await c.list_tools()}
        assert names == {"search_products", "get_product", "view_cart"}
        with pytest.raises(ToolError):
            await c.call_tool("add_to_cart", {"product_id": "101", "quantity": 1})
