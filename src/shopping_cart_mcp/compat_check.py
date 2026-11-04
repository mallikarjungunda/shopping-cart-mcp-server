"""Check what a given client would see, and flag Gemini-incompatible schemas.

  shopping-cart-compat-check http://127.0.0.1:8000/mcp --token "$TOKEN" [--profile gemini]

Exits non-zero if problems are found, so it can run in CI against a deployment.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from .adapters import PROFILE_HEADER

# Not part of the OpenAPI 3.0 subset Gemini function declarations accept.
RISKY = {"anyOf", "oneOf", "allOf", "$ref", "$defs", "definitions", "additionalProperties",
         "pattern", "exclusiveMinimum", "exclusiveMaximum", "title", "default", "const"}


def find_problems(tools: list[dict]) -> list[str]:
    problems: list[str] = []

    def walk(node, where):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in RISKY:
                    problems.append(f"{where}: uses '{k}'")
                walk(v, f"{where}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")

    for t in tools:
        if not (t.get("description") or "").strip():
            problems.append(f"{t['name']}: missing description")
        schema = t.get("inputSchema") or {}
        if schema.get("type") != "object":
            problems.append(f"{t['name']}: input schema is not an object")
        walk(schema, t["name"])
    return problems


async def run(url: str, token: str, profile: str | None) -> list[dict]:
    headers = {PROFILE_HEADER: profile} if profile else None
    transport = StreamableHttpTransport(url, headers=headers, auth=token)
    async with Client(transport) as c:
        return [{"name": t.name, "description": t.description,
                 "inputSchema": t.input_schema} for t in await c.list_tools()]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("url")
    p.add_argument("--token", required=True)
    p.add_argument("--profile", choices=["standard", "gemini"])
    p.add_argument("--show", action="store_true", help="print the tool schemas")
    a = p.parse_args()
    tools = asyncio.run(run(a.url, a.token, a.profile))
    if a.show:
        print(json.dumps(tools, indent=2))
    problems = find_problems(tools)
    print(f"{len(tools)} tools, profile={a.profile or 'default'}: "
          f"{'OK, no Gemini-incompatible schema features' if not problems else f'{len(problems)} problem(s)'}")
    for line in problems:
        print("  -", line)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
