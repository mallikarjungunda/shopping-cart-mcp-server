"""Claude API: use the MCP connector in the Messages API.

Anthropic's cloud calls your server, so it must be reachable over public HTTPS.
You obtain (and refresh) the OAuth access token yourself and pass it as
`authorization_token`. For a quick test, mint one with `shopping-cart-devtoken mint alice`
(this only works if the server trusts that dev key).

Not run against the live API in this repo's tests (no API key available there).
Requires: pip install anthropic
"""
import os

import anthropic

client = anthropic.Anthropic()
response = client.beta.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=1000,
    messages=[{"role": "user", "content": "Find a laptop under $1000 and add it to my cart."}],
    mcp_servers=[{
        "type": "url",
        "url": os.environ["MCP_URL"],  # e.g. https://YOUR-HOST/mcp
        "name": "shopping-cart",
        "authorization_token": os.environ["MCP_TOKEN"],
    }],
    tools=[{"type": "mcp_toolset", "mcp_server_name": "shopping-cart"}],
    betas=["mcp-client-2025-11-20"],
)
for block in response.content:
    print(getattr(block, "text", block))
