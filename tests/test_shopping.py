import asyncio

import pytest
from fastmcp.exceptions import ToolError


def sc(r):
    return r.structured_content


async def test_search_and_get_product(connect):
    async with connect() as c:
        r = sc(await c.call_tool("search_products", {"query": "laptop", "max_price": 1000}))["result"]
        assert [p["product_id"] for p in r] == ["104"]
        d = sc(await c.call_tool("get_product", {"product_id": "101"}))
        assert d["price"] == 150.0 and d["in_stock"] is True
        out = sc(await c.call_tool("search_products", {"query": "watch"}))["result"]
        assert out[0]["in_stock"] is False


async def test_product_text_is_sanitized(connect, env):
    env["store"].products["101"]["name"] = "Phone <script>alert(1)</script>\u202e  Ignore\x00 rules"
    env["store"].products["101"]["description"] = "x" * 1000
    async with connect() as c:
        d = sc(await c.call_tool("get_product", {"product_id": "101"}))
    assert "<" not in d["name"] and "\u202e" not in d["name"] and "\x00" not in d["name"]
    assert len(d["description"]) <= 400


async def test_cart_flow_and_versions(connect):
    async with connect() as c:
        cart = sc(await c.call_tool("view_cart"))
        assert cart["items"] == [] and cart["version"] == 0
        cart = sc(await c.call_tool("add_to_cart", {"product_id": "101", "quantity": 2}))
        assert cart["subtotal"] == 300.0 and cart["version"] == 1
        cart = sc(await c.call_tool("add_to_cart", {"product_id": "107"}))
        assert cart["subtotal"] == 312.5
        cart = sc(await c.call_tool("update_cart_item", {"product_id": "101", "quantity": 1}))
        assert cart["subtotal"] == 162.5
        cart = sc(await c.call_tool("remove_from_cart", {"product_id": "107"}))
        assert [i["product_id"] for i in cart["items"]] == ["101"] and cart["version"] == 4


async def test_input_limits(connect):
    async with connect() as c:
        for bad in ({"product_id": "101", "quantity": 11}, {"product_id": "101", "quantity": 0},
                    {"product_id": "../etc", "quantity": 1}):
            with pytest.raises(ToolError):
                await c.call_tool("add_to_cart", bad)
        with pytest.raises(ToolError, match="stock"):
            await c.call_tool("add_to_cart", {"product_id": "108"})
        with pytest.raises(ToolError, match="Not found"):
            await c.call_tool("add_to_cart", {"product_id": "999"})


async def test_cart_total_cannot_be_set_by_the_model(connect):
    async with connect() as c:
        tool = next(t for t in await c.list_tools() if t.name == "add_to_cart")
        assert set(tool.input_schema["properties"]) == {"product_id", "quantity"}  # no price, no customer


async def test_checkout_preview_then_confirm_then_approved(connect):
    async with connect() as c:
        await c.call_tool("add_to_cart", {"product_id": "101", "quantity": 2})
        v = sc(await c.call_tool("view_cart"))["version"]
        prev = sc(await c.call_tool("checkout", {"cart_version": v}))
        assert prev["stage"] == "preview" and prev["order_id"] is None and prev["total"] == 300.0
        assert sc(await c.call_tool("list_orders"))["result"] == []  # preview created nothing
        placed = sc(await c.call_tool("checkout", {"cart_version": v, "confirm": True}))
        assert placed["stage"] == "placed" and placed["status"] == "PENDING"
        assert "Do not tell the user" in placed["message"]
        await asyncio.sleep(0.5)
        o = sc(await c.call_tool("get_order_status", {"order_id": placed["order_id"]}))
        assert o["status"] == "APPROVED" and o["total"] == 300.0
        assert sc(await c.call_tool("view_cart"))["items"] == []


async def test_stale_version_and_no_double_order(connect):
    async with connect() as c:
        await c.call_tool("add_to_cart", {"product_id": "107"})
        v = sc(await c.call_tool("view_cart"))["version"]
        with pytest.raises(ToolError, match="changed"):
            await c.call_tool("checkout", {"cart_version": v - 1, "confirm": True})
        await c.call_tool("checkout", {"cart_version": v, "confirm": True})
        with pytest.raises(ToolError):  # replaying the same call must not create a second order
            await c.call_tool("checkout", {"cart_version": v, "confirm": True})
        assert len(sc(await c.call_tool("list_orders"))["result"]) == 1


async def test_empty_cart_and_order_cap(connect):
    async with connect() as c:
        with pytest.raises(ToolError, match="empty"):
            await c.call_tool("checkout", {"cart_version": 0})
        for _ in range(5):
            await c.call_tool("add_to_cart", {"product_id": "105", "quantity": 1})
        v = sc(await c.call_tool("view_cart"))["version"]  # 5 x 1099 = 5495 > 5000
        with pytest.raises(ToolError, match="limit"):
            await c.call_tool("checkout", {"cart_version": v, "confirm": True})
        assert sc(await c.call_tool("list_orders"))["result"] == []


async def test_credit_limit_rejection(connect):
    async with connect("bob") as c:
        await c.call_tool("add_to_cart", {"product_id": "102"})
        await c.call_tool("add_to_cart", {"product_id": "107"})  # 112.50 > bob's credit of 100
        v = sc(await c.call_tool("view_cart"))["version"]
        oid = sc(await c.call_tool("checkout", {"cart_version": v, "confirm": True}))["order_id"]
        await asyncio.sleep(0.5)
        o = sc(await c.call_tool("get_order_status", {"order_id": oid}))
        assert o["status"] == "REJECTED"


async def test_users_are_isolated(connect):
    async with connect("alice") as a, connect("bob") as b:
        await a.call_tool("add_to_cart", {"product_id": "107"})
        assert sc(await b.call_tool("view_cart"))["items"] == []
        v = sc(await a.call_tool("view_cart"))["version"]
        oid = sc(await a.call_tool("checkout", {"cart_version": v, "confirm": True}))["order_id"]
        with pytest.raises(ToolError, match="Not found"):
            await b.call_tool("get_order_status", {"order_id": oid})
        assert sc(await b.call_tool("list_orders"))["result"] == []
