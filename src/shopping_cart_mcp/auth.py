"""OAuth resource-server wiring.

This server never logs users in. It only verifies access tokens issued by the
authorization server (JWT signature, issuer, audience, expiry, scopes) and
publishes protected-resource metadata so clients such as ChatGPT can discover
where to authenticate.
"""
from __future__ import annotations

from pathlib import Path

from fastmcp.exceptions import ToolError
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token
from pydantic import AnyHttpUrl

from .config import Settings

SCOPES = ["cart:read", "cart:write", "orders:read", "orders:write"]


def build_verifier(s: Settings) -> JWTVerifier:
    common = dict(issuer=s.issuer, audience=s.audience)
    if s.auth_mode == "jwks":
        return JWTVerifier(jwks_uri=s.jwks_uri, algorithm="RS256", **common)
    pem = Path(s.dev_public_key_file).read_text()
    return JWTVerifier(public_key=pem, algorithm="RS256", **common)


def build_auth(s: Settings, verifier: JWTVerifier | None = None) -> RemoteAuthProvider:
    return RemoteAuthProvider(
        token_verifier=verifier or build_verifier(s),
        authorization_servers=[AnyHttpUrl(s.issuer)],
        base_url=s.public_url,
        scopes_supported=SCOPES,
        resource_name="Shopping Cart MCP Server",
    )


def current_customer() -> str:
    """The customer ID comes ONLY from the verified token, never from tool input."""
    token = get_access_token()
    sub = (token.claims or {}).get("sub") if token else None
    if not sub:
        raise ToolError("Authentication required.")
    return str(sub)
