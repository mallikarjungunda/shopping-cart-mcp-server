"""HTTP client for the shopping-cart services behind the gateway.

The user's own MCP access token is never forwarded. Instead we mint a short-lived
downstream token that names the customer (from the verified token's `sub`) and is
addressed to the backend audience.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import jwt

from .config import Settings
from .sanitize import clean_text


class BackendError(Exception):
    """A backend failure, carrying a message that is safe to show to the model."""

    def __init__(self, status: int, public_message: str):
        super().__init__(public_message)
        self.status = status
        self.public_message = public_message


class Backend:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._s = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.backend_url, timeout=settings.timeout
        )

    def _token(self, customer_id: str) -> str:
        now = int(time.time())
        claims = {
            "iss": "shopping-cart-mcp",
            "aud": self._s.backend_audience,
            "sub": customer_id,
            "iat": now,
            "exp": now + 60,
        }
        return jwt.encode(claims, self._s.backend_secret, algorithm="HS256")

    async def request(
        self,
        method: str,
        path: str,
        customer_id: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        hdrs = {"Authorization": f"Bearer {self._token(customer_id)}", **(headers or {})}
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            r = await self._client.request(method, path, params=clean, json=json, headers=hdrs)
        except httpx.HTTPError:
            raise BackendError(503, "The store is temporarily unavailable. Try again shortly.") from None
        if r.status_code < 400:
            return r.json() if r.content else None
        raise BackendError(r.status_code, self._message(r))

    @staticmethod
    def _message(r: httpx.Response) -> str:
        if r.status_code >= 500:
            return "The store had an internal error. Try again shortly."
        if r.status_code in (401, 403):
            return "The store rejected this request for the current user."
        if r.status_code == 404:
            return "Not found."
        if r.status_code == 429:
            return "Too many requests. Slow down and retry shortly."
        try:
            detail = r.json().get("detail") or r.json().get("message") or ""
        except Exception:
            detail = ""
        return clean_text(detail, 160) or "The request was not valid."

    async def aclose(self) -> None:
        await self._client.aclose()
