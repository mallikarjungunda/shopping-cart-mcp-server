import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from mcp.types import Implementation

from shopping_cart_mcp.adapters import PROFILE_HEADER, compat_schema, resolve_profile
from shopping_cart_mcp.compat_check import find_problems, run


def test_compat_schema_strips_risky_keywords_and_keeps_meaning():
    src = {"type": "object", "title": "T", "additionalProperties": False,
           "properties": {
               "q": {"anyOf": [{"type": "string", "maxLength": 100}, {"type": "null"}], "default": None,
                     "description": "Keywords"},
               "n": {"type": "integer", "minimum": 1, "maximum": 10, "default": 1},
               "p": {"type": "number", "exclusiveMinimum": 0},
               "id": {"type": "string", "pattern": "^[a-z]+$"}},
           "required": ["n"]}
    out = compat_schema(src)
    assert out["required"] == ["n"] and out["type"] == "object"
    assert out["properties"]["q"]["type"] == "string"
    assert "1 to 10" in out["properties"]["n"]["description"]
    assert "above 0" in out["properties"]["p"]["description"]
    assert find_problems([{"name": "t", "description": "d", "inputSchema": out}]) == []
    assert src["properties"]["n"]["minimum"] == 1  # input not mutated


def test_compat_schema_handles_empty_params():
    assert compat_schema({}) == {"type": "object", "properties": {}}


@pytest.mark.parametrize("header,name,default,expected", [
    ("gemini", None, "standard", "gemini"), ("GEMINI", "claude-ai", "standard", "gemini"),
    ("standard", "gemini-cli", "standard", "standard"), (None, "gemini-cli", "standard", "gemini"),
    (None, "claude-ai", "standard", "standard"), (None, None, "gemini", "gemini"),
    ("bogus", None, "standard", "standard")])
def test_resolve_profile(header, name, default, expected):
    assert resolve_profile(default, header, name) == expected


def names(tools):
    return {t.name for t in tools}


async def test_standard_profile_keeps_full_schema(env, token):
    t = token("alice")
    tools = await run(f"{env['url']}/mcp", t, None)
    assert find_problems(tools)  # checker flags anyOf, pattern, etc. on the standard schemas
    search = next(x for x in tools if x["name"] == "search_products")
    assert "anyOf" in str(search["inputSchema"])


async def test_gemini_header_gets_compatible_schema(env, token):
    tools = await run(f"{env['url']}/mcp", token("alice"), "gemini")
    assert len(tools) == 9 and find_problems(tools) == []
    add = next(x for x in tools if x["name"] == "add_to_cart")
    assert "1 to 10" in add["inputSchema"]["properties"]["quantity"]["description"]
    assert set(add["inputSchema"]["required"]) == {"product_id"}


async def test_gemini_detected_from_client_name(env, token):
    c = Client(f"{env['url']}/mcp", auth=token("alice"), client_info=Implementation(name="gemini-cli", version="1"))
    async with c:
        tools = await c.list_tools()
    assert find_problems([{"name": t.name, "description": t.description, "inputSchema": t.input_schema}
                          for t in tools]) == []


async def test_validation_still_enforced_under_gemini_profile(env, token):
    transport = StreamableHttpTransport(f"{env['url']}/mcp", headers={PROFILE_HEADER: "gemini"}, auth=token("alice"))
    async with Client(transport) as c:
        for bad in ({"product_id": "101", "quantity": 11}, {"product_id": "../x", "quantity": 1}):
            with pytest.raises(ToolError):
                await c.call_tool("add_to_cart", bad)
        r = await c.call_tool("add_to_cart", {"product_id": "101", "quantity": 2})
        assert r.structured_content["subtotal"] == 300.0


async def test_scope_filtering_still_applies_with_gemini_profile(env, token):
    tools = await run(f"{env['url']}/mcp", token("alice", ["cart:read"]), "gemini")
    assert names(type("T", (), {"name": t["name"]}) for t in tools) == {"search_products", "get_product", "view_cart"}
