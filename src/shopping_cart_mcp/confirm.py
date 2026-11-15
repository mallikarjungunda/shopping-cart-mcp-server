"""Checkout confirmation tokens.

A checkout preview hands back a short-lived token bound to the customer, the
cart and the cart version. Placing the order requires that token, so the model
cannot place an order for a cart it has never previewed, and a token from one
cart or user is useless for another.

The token is stateless (an HMAC over those values plus an expiry), so it works
across server replicas. It proves a preview happened; it does not prove a human
agreed, so the client's own tool-approval prompt remains the human check.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

_LABEL = "checkout-confirm-v1"


def _mac(secret: str, customer: str, cart_id: str, version: int, exp: int) -> str:
    msg = json.dumps([_LABEL, customer, cart_id, version, exp], separators=(",", ":"))
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]


def issue_token(secret: str, customer: str, cart_id: str, version: int, ttl: int,
                now: float | None = None) -> str:
    exp = int(time.time() if now is None else now) + ttl
    return f"{exp}.{_mac(secret, customer, cart_id, version, exp)}"


def verify_token(secret: str, token: str | None, customer: str, cart_id: str, version: int,
                 now: float | None = None) -> bool:
    exp_s, _, mac = (token or "").partition(".")
    if not exp_s.isdigit() or not mac:
        return False
    exp = int(exp_s)
    if exp < (time.time() if now is None else now):
        return False
    return hmac.compare_digest(mac, _mac(secret, customer, cart_id, version, exp))
