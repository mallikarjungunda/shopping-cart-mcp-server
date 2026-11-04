"""Developer helpers: generate a demo RSA key pair and mint test access tokens.

Usage:
  shopping-cart-devtoken keys                      # writes .dev/private.pem, .dev/public.pem
  shopping-cart-devtoken mint alice --scopes cart:read cart:write orders:read orders:write
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ALL_SCOPES = ["cart:read", "cart:write", "orders:read", "orders:write"]


def generate_keys(directory: str | Path = ".dev") -> tuple[Path, Path]:
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv, pub = d / "private.pem", d / "public.pem"
    priv.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    os.chmod(priv, 0o600)
    pub.write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ))
    return priv, pub


def mint_token(
    private_key_pem: str,
    user: str,
    *,
    scopes: list[str] | None = None,
    issuer: str = "http://localhost:9000",
    audience: str = "shopping-cart-mcp",
    minutes: float = 15,
) -> str:
    now = int(time.time())
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": user,
        "scope": " ".join(ALL_SCOPES if scopes is None else scopes),
        "iat": now,
        "exp": now + int(minutes * 60),
    }
    return jwt.encode(claims, private_key_pem, algorithm="RS256")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keys")
    k.add_argument("--dir", default=".dev")
    m = sub.add_parser("mint")
    m.add_argument("user")
    m.add_argument("--scopes", nargs="*", default=None)
    m.add_argument("--key", default=".dev/private.pem")
    m.add_argument("--issuer", default=os.environ.get("OAUTH_ISSUER", "http://localhost:9000"))
    m.add_argument("--audience", default=os.environ.get("OAUTH_AUDIENCE", "shopping-cart-mcp"))
    m.add_argument("--minutes", type=float, default=15)
    a = p.parse_args()
    if a.cmd == "keys":
        priv, pub = generate_keys(a.dir)
        print(f"wrote {priv} and {pub}")
    else:
        print(mint_token(Path(a.key).read_text(), a.user, scopes=a.scopes,
                         issuer=a.issuer, audience=a.audience, minutes=a.minutes))


if __name__ == "__main__":
    main()
