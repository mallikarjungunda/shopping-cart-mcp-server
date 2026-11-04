#!/usr/bin/env bash
# Claude Code: add the server over Streamable HTTP with a bearer token.
# For a server protected by OAuth, add it without --header and run /mcp inside
# Claude Code to sign in through the browser. Check `claude mcp add --help` for
# the exact flags in your version.
claude mcp add --transport http shopping-cart "https://YOUR-HOST/mcp" \
  --header "Authorization: Bearer $TOKEN"
