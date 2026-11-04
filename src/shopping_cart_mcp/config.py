"""Runtime configuration, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Settings:
    # Where the Spring Boot gateway (or the bundled mock backend) lives.
    backend_url: str = "http://localhost:8111/shoppingcart/api"
    backend_audience: str = "shopping-cart-api"
    # Demo-only HS256 secret used to mint short-lived downstream tokens.
    backend_secret: str = ""
    # Public URL of THIS server, as clients (ChatGPT, Claude, ...) reach it.
    public_url: str = "http://localhost:8000"
    # OAuth: the authorization server that issues access tokens.
    issuer: str = "http://localhost:9000"
    audience: str = "shopping-cart-mcp"
    auth_mode: str = "dev"  # "dev" = local public key file, "jwks" = remote JWKS
    jwks_uri: str | None = None
    dev_public_key_file: str = ".dev/public.pem"
    # Safety limits.
    max_order_total: Decimal = Decimal("5000")
    timeout: float = 10.0
    client_profile: str = "standard"  # default tool-schema dialect: standard | gemini
    host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        secret = e("BACKEND_SECRET", "")
        if len(secret) < 32:
            raise RuntimeError("BACKEND_SECRET must be set to at least 32 characters")
        mode = e("AUTH_MODE", "dev")
        if mode not in ("dev", "jwks"):
            raise RuntimeError("AUTH_MODE must be 'dev' or 'jwks'")
        jwks = e("JWKS_URI")
        if mode == "jwks" and not jwks:
            raise RuntimeError("JWKS_URI is required when AUTH_MODE=jwks")
        d = cls()
        return cls(
            backend_url=e("BACKEND_URL", d.backend_url).rstrip("/"),
            backend_audience=e("BACKEND_AUDIENCE", d.backend_audience),
            backend_secret=secret,
            public_url=e("PUBLIC_URL", d.public_url).rstrip("/"),
            issuer=e("OAUTH_ISSUER", d.issuer).rstrip("/"),
            audience=e("OAUTH_AUDIENCE", d.audience),
            auth_mode=mode,
            jwks_uri=jwks,
            dev_public_key_file=e("DEV_PUBLIC_KEY_FILE", d.dev_public_key_file),
            max_order_total=Decimal(e("MAX_ORDER_TOTAL", str(d.max_order_total))),
            timeout=float(e("BACKEND_TIMEOUT", str(d.timeout))),
            client_profile=e("CLIENT_PROFILE", d.client_profile),
            host=e("HOST", d.host),
            port=int(e("PORT", str(d.port))),
        )
