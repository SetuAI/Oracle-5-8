# AMFI MCP Server

An open-source **Model Context Protocol (MCP)** server that gives any AI
assistant access to official **Indian mutual-fund NAV data** from AMFI (the
Association of Mutual Funds in India).

Ask Claude, GitHub Copilot, Cursor, or any MCP-compatible client things like
*"What's the latest NAV of Parag Parikh Flexi Cap?"* and get a real, current
answer — using AMFI's official, free, no-API-key feed.

## Why this exists

AI models don't know today's mutual-fund NAVs, and most existing market-data
MCP servers cover US stocks — not Indian mutual funds. This server fills that
gap with the authoritative Indian source, and needs **no API key**.

## Tools

| Tool | What it does |
|------|--------------|
| `search_mutual_funds(query)` | Find schemes by name (e.g. "hdfc small cap"), returning each scheme's code and latest NAV. |
| `get_fund_nav(scheme_code)` | Get the latest official NAV and date for one scheme, by its numeric AMFI code. |

Data source: AMFI's daily [NAVAll feed](https://www.amfiindia.com/spages/NAVAll.txt).

## Install


```bash
git clone https://github.com/SetuAI/amfi-mcp-server.git
cd amfi-mcp-server
pip install -e .
```

## Run

```bash
amfi-mcp
```

The server communicates over stdio, so it will sit quietly waiting for an MCP
client to connect. To inspect it by hand:

```bash
npx @modelcontextprotocol/inspector amfi-mcp
```

Then: **Connect → Tools → List Tools →** try `search_mutual_funds` with
`hdfc small cap`, then `get_fund_nav` with a scheme code from the results.

## Connect it to an AI client

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "amfi": {
      "command": "amfi-mcp"
    }
  }
}
```

(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`,
Windows: `%APPDATA%\Claude\claude_desktop_config.json`. Fully quit and reopen
Claude Desktop afterwards.)

### VS Code (GitHub Copilot)

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "amfi": {
      "command": "amfi-mcp"
    }
  }
}
```

Click **Start**, open Copilot Chat, switch to **Agent** mode, and ask a
mutual-fund question.

## Example prompts

- "Search for HDFC small cap funds and give me their latest NAVs."
- "What's the NAV of scheme code 122639?"
- "Find Parag Parikh flexi cap and tell me today's value."

## How it works

- `amfi_client.py` downloads and parses AMFI's NAV file, caches it in memory
  (refreshing at most once per hour), and offers the lookups.
- `server.py` wraps those lookups as MCP tools with `FastMCP`.

The NAV file updates once per business day, so values are accurate as of
AMFI's last publishing day. This project is not affiliated with AMFI; it
simply reads AMFI's public feed. Data is provided as-is, for informational
purposes, and is not investment advice.

## Requirements

- Python 3.10+
- Outbound internet access to `www.amfiindia.com`

## License

MIT — see [LICENSE](LICENSE).
