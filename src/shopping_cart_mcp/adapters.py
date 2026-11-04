"""Per-client adapters.

One set of tools serves every LLM; only the *published* tool schemas differ.

* standard  - full JSON Schema (ChatGPT, Claude, MCP Inspector, ...).
* gemini    - a conservative schema. Gemini function declarations accept an
              OpenAPI-3.0 subset, and unsupported keywords can fail the whole
              request with a generic 400. We drop the risky keywords and move
              the constraints into each parameter's description.

Dropping keywords from the *published* schema does not weaken validation: the
server still validates every call against the real Python types.

A client is matched, in order, by: the `X-Client-Profile` request header (Gemini
API and Gemini CLI can send custom headers), the MCP `clientInfo.name`, then the
CLIENT_PROFILE setting.
"""
from __future__ import annotations

import copy
from typing import Any

from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware

PROFILE_HEADER = "x-client-profile"
PROFILES = ("standard", "gemini")

# clientInfo.name fragments -> profile
_NAME_HINTS = {"gemini": "gemini", "google-genai": "gemini", "google": "gemini"}

# Keywords outside the OpenAPI subset (or that some Gemini surfaces reject).
_DROP = {"title", "additionalProperties", "pattern", "minimum", "maximum", "exclusiveMinimum",
         "exclusiveMaximum", "minLength", "maxLength", "format", "default", "examples",
         "$schema", "$defs", "definitions", "$id", "const"}


def _constraint_note(node: dict) -> str:
    parts = []
    lo = node.get("minimum", node.get("exclusiveMinimum"))
    hi = node.get("maximum", node.get("exclusiveMaximum"))
    if lo is not None and hi is not None:
        parts.append(f"{lo} to {hi}")
    elif lo is not None:
        parts.append(f"{'above' if 'exclusiveMinimum' in node else 'at least'} {lo}")
    elif hi is not None:
        parts.append(f"at most {hi}")
    if node.get("maxLength"):
        parts.append(f"max {node['maxLength']} characters")
    if node.get("default") is not None:
        parts.append(f"default {node['default']}")
    return ", ".join(parts)


def compat_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a Gemini-safe copy of a JSON Schema."""

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(n) for n in node]
        if not isinstance(node, dict):
            return node
        node = dict(node)
        # Optional param: anyOf [X, null]  ->  X   (optional = not in "required")
        for key in ("anyOf", "oneOf"):
            if key in node:
                options = [o for o in node.pop(key) if o.get("type") != "null"]
                if len(options) == 1:
                    node = {**options[0], **{k: v for k, v in node.items()}}
                elif options:
                    node = {**options[0], **node}
        note = _constraint_note(node)
        if note:
            base = (node.get("description") or "").rstrip(". ")
            node["description"] = f"{base}. Allowed: {note}." if base else f"Allowed: {note}."
        out = {}
        for k, v in node.items():
            if k in _DROP:
                continue
            if k == "properties":
                out[k] = {name: walk(s) for name, s in v.items()}
            elif k == "items":
                out[k] = walk(v)
            else:
                out[k] = v
        if "properties" in out and "type" not in out:
            out["type"] = "object"
        return out

    result = walk(copy.deepcopy(schema))
    result.setdefault("type", "object")
    result.setdefault("properties", {})
    return result


def resolve_profile(default: str, header: str | None, client_name: str | None) -> str:
    if header and header.strip().lower() in PROFILES:
        return header.strip().lower()
    name = (client_name or "").lower()
    for hint, profile in _NAME_HINTS.items():
        if hint in name:
            return profile
    return default if default in PROFILES else "standard"


class ClientProfileMiddleware(Middleware):
    """Publishes tool schemas in the dialect the connecting client can accept."""

    def __init__(self, default_profile: str = "standard"):
        self.default = default_profile

    async def on_list_tools(self, context, call_next):
        tools = await call_next(context)
        header = get_http_headers().get(PROFILE_HEADER)
        name = None
        try:  # the field is client_info in newer MCP SDKs, clientInfo in older ones
            params = context.fastmcp_context.session.client_params
            name = (getattr(params, "client_info", None) or getattr(params, "clientInfo")).name
        except Exception:
            pass
        if resolve_profile(self.default, header, name) != "gemini":
            return tools
        return [t.model_copy(update={"parameters": compat_schema(t.parameters)}) for t in tools]
