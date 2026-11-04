"""Gemini API: register the server as a remote MCP tool (Interactions API).

Verified from Google's announcements and third-party docs: the tool type is
`mcp_server`, the server must use Streamable HTTP, and the fields are name, url,
optional headers and optional allowed_tools. The SDK call below is a best-effort
sketch: check Google's current Interactions API docs for the exact signature and
model name. Not run against the live API in this repo's tests.

Send `X-Client-Profile: gemini` so the server publishes Gemini-safe tool schemas.
Use a stable HTTPS host: temporary tunnel hosts may be rejected before Gemini
ever contacts the server.
Requires: pip install google-genai
"""
import os

from google import genai

client = genai.Client()
tool = {
    "type": "mcp_server",
    "name": "shopping-cart",
    "url": os.environ["MCP_URL"],  # e.g. https://YOUR-HOST/mcp
    "headers": {"Authorization": f"Bearer {os.environ['MCP_TOKEN']}", "X-Client-Profile": "gemini"},
    # "allowed_tools": ["search_products", "view_cart"],  # restrict what Gemini may call
}
interaction = client.interactions.create(
    model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
    input="Find a laptop under $1000 and add it to my cart.",
    tools=[tool],
)
print(interaction)
