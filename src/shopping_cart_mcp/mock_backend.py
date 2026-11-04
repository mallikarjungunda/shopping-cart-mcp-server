"""In-memory stand-in for the Spring Boot services, following the spec's contract.

DEMO ONLY. It lets the MCP server run and be tested before the Java services are
updated. It verifies the downstream token, derives the customer from it, computes
prices itself, and simulates the Kafka credit-check by approving or rejecting an
order shortly after it is created.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal

import jwt
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

SEED = [
    ("101", "Galaxy M30", "Mobiles", "Samsung", "6.4in AMOLED phone, 4GB RAM.", 150.00, 25),
    ("102", "Redmi Note 9", "Mobiles", "Xiaomi", "Budget phone with big battery.", 100.00, 40),
    ("103", "Pixel Buds", "Audio", "Google", "Wireless earbuds with noise control.", 99.00, 15),
    ("104", "ThinkPad E14", "Laptops", "Lenovo", "14in business laptop, 16GB RAM.", 899.00, 8),
    ("105", "MacBook Air 13", "Laptops", "Apple", "13in laptop, all-day battery.", 1099.00, 5),
    ("106", "Kindle Paperwhite", "Tablets", "Amazon", "6.8in e-reader with warm light.", 139.00, 30),
    ("107", "USB-C Cable 2m", "Accessories", "Anker", "Braided fast-charge cable.", 12.50, 200),
    ("108", "Limited Edition Watch", "Wearables", "Fossil", "Collector watch, sold out.", 250.00, 0),
]


class AddItem(BaseModel):
    productId: str
    quantity: int = Field(ge=1, le=10)


class SetQty(BaseModel):
    quantity: int = Field(ge=1, le=10)


class NewOrder(BaseModel):
    cartId: str
    cartVersion: int


class Store:
    def __init__(self, approval_delay: float, credit: dict[str, float], default_credit: float):
        self.lock = threading.RLock()
        self.approval_delay, self.credit, self.default_credit = approval_delay, credit, default_credit
        self.products = {p[0]: dict(productId=p[0], name=p[1], category=p[2], manufacturer=p[3],
                                    description=p[4], price=p[5], stock=p[6]) for p in SEED}
        self.carts: dict[str, dict] = {}
        self.orders: dict[str, dict] = {}
        self.idem: dict[tuple[str, str], str] = {}
        self.seq = 1000

    def cart(self, sub: str) -> dict:
        if sub not in self.carts:
            self.seq += 1
            self.carts[sub] = {"cartId": f"c-{self.seq}", "version": 0, "currency": "USD", "items": []}
        return self.carts[sub]

    @staticmethod
    def view(c: dict) -> dict:
        sub = sum(Decimal(str(i["unitPrice"])) * i["quantity"] for i in c["items"])
        return {**c, "items": [dict(i) for i in c["items"]], "subtotal": float(sub)}

    def resolve(self, o: dict) -> dict:
        if o["status"] == "PENDING" and time.time() - o["_t"] >= self.approval_delay:
            limit = self.credit.get(o["_sub"], self.default_credit)
            o["status"] = "APPROVED" if o["total"] <= limit else "REJECTED"
        return {k: v for k, v in o.items() if not k.startswith("_")}


def create_app(secret: str, audience: str = "shopping-cart-api", approval_delay: float = 2.0,
               credit: dict[str, float] | None = None, default_credit: float = 10000.0) -> FastAPI:
    store = Store(approval_delay, credit or {}, default_credit)
    app = FastAPI(title="Mock shopping cart backend (demo only)")
    app.state.store = store

    def customer(authorization: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Missing token")
        try:
            claims = jwt.decode(authorization[7:], secret, algorithms=["HS256"],
                                audience=audience, issuer="shopping-cart-mcp")
        except jwt.PyJWTError:
            raise HTTPException(401, "Invalid token") from None
        return claims["sub"]

    r = APIRouter(prefix="/shoppingcart/api", dependencies=[Depends(customer)])

    @r.get("/products")
    def products(query: str | None = None, category: str | None = None,
                 maxPrice: float | None = None, limit: int = Query(10, ge=1, le=50)):
        out = []
        for p in store.products.values():
            hay = " ".join(str(p[k]) for k in ("name", "category", "manufacturer", "description")).lower()
            if query and not all(w in hay for w in query.lower().split()):
                continue
            if category and category.lower() != p["category"].lower():
                continue
            if maxPrice is not None and p["price"] > maxPrice:
                continue
            out.append(dict(p))
        return out[:limit]

    @r.get("/products/{pid}")
    def product(pid: str):
        if pid not in store.products:
            raise HTTPException(404, "Not found")
        return dict(store.products[pid])

    @r.get("/carts/me")
    def get_cart(sub: str = Depends(customer)):
        with store.lock:
            return store.view(store.cart(sub))

    @r.post("/carts/me/items")
    def add_item(body: AddItem, sub: str = Depends(customer)):
        with store.lock:
            p = store.products.get(body.productId)
            if not p:
                raise HTTPException(404, "Not found")
            c = store.cart(sub)
            line = next((i for i in c["items"] if i["productId"] == p["productId"]), None)
            qty = body.quantity + (line["quantity"] if line else 0)
            if qty > 10:
                raise HTTPException(409, "Maximum quantity per item is 10.")
            if qty > p["stock"]:
                raise HTTPException(409, "Insufficient stock for that quantity.")
            if line:
                line["quantity"] = qty
            else:
                if len(c["items"]) >= 20:
                    raise HTTPException(409, "The cart is full (20 different items).")
                c["items"].append({"productId": p["productId"], "name": p["name"],
                                   "quantity": qty, "unitPrice": p["price"]})
            c["version"] += 1
            return store.view(c)

    @r.put("/carts/me/items/{pid}")
    def set_item(pid: str, body: SetQty, sub: str = Depends(customer)):
        with store.lock:
            c = store.cart(sub)
            line = next((i for i in c["items"] if i["productId"] == pid), None)
            if not line:
                raise HTTPException(404, "Not found")
            if body.quantity > store.products[pid]["stock"]:
                raise HTTPException(409, "Insufficient stock for that quantity.")
            line["quantity"] = body.quantity
            c["version"] += 1
            return store.view(c)

    @r.delete("/carts/me/items/{pid}")
    def del_item(pid: str, sub: str = Depends(customer)):
        with store.lock:
            c = store.cart(sub)
            n = len(c["items"])
            c["items"] = [i for i in c["items"] if i["productId"] != pid]
            if len(c["items"]) == n:
                raise HTTPException(404, "Not found")
            c["version"] += 1
            return store.view(c)

    @r.post("/orders")
    def create_order(body: NewOrder, sub: str = Depends(customer),
                     idempotency_key: str | None = Header(default=None)):
        if not idempotency_key:
            raise HTTPException(400, "Idempotency-Key header is required.")
        with store.lock:
            prior = store.idem.get((sub, idempotency_key))
            if prior:
                return store.resolve(store.orders[prior])
            c = store.cart(sub)
            if c["cartId"] != body.cartId or c["version"] != body.cartVersion:
                raise HTTPException(409, "The cart changed. Review it and try again.")
            if not c["items"]:
                raise HTTPException(422, "The cart is empty.")
            for i in c["items"]:
                store.products[i["productId"]]["stock"] -= i["quantity"]
            v = store.view(c)
            store.seq += 1
            oid = f"o-{store.seq}"
            store.orders[oid] = {"orderId": oid, "status": "PENDING", "total": v["subtotal"],
                                 "items": v["items"], "createdAt": datetime.now(timezone.utc).isoformat(),
                                 "_sub": sub, "_t": time.time()}
            store.idem[(sub, idempotency_key)] = oid
            c["items"], c["version"] = [], c["version"] + 1
            return store.resolve(store.orders[oid])

    @r.get("/orders/me")
    def my_orders(sub: str = Depends(customer), limit: int = Query(5, ge=1, le=20)):
        mine = [o for o in store.orders.values() if o["_sub"] == sub]
        return [store.resolve(o) for o in reversed(mine)][:limit]

    @r.get("/orders/{oid}")
    def order(oid: str, sub: str = Depends(customer)):
        o = store.orders.get(oid)
        if not o or o["_sub"] != sub:  # same answer for "missing" and "not yours"
            raise HTTPException(404, "Not found")
        return store.resolve(o)

    app.include_router(r)
    return app


def main() -> None:
    import uvicorn
    secret = os.environ.get("BACKEND_SECRET", "")
    if len(secret) < 32:
        raise SystemExit("BACKEND_SECRET must be set to at least 32 characters")
    app = create_app(secret, os.environ.get("BACKEND_AUDIENCE", "shopping-cart-api"),
                     credit={"bob": 100.0})
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("MOCK_PORT", "8111")))


if __name__ == "__main__":
    main()
