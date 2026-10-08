##############################################################################
# server.py
#
# PURPOSE:
#   This is the MCP SERVER. It exposes India mutual-fund NAV data (from
#   amfi_client.py) as tools that any MCP-compatible AI app -- Claude
#   Desktop, VS Code / GitHub Copilot, Cursor, the MCP Inspector -- can call.
#
# WHY THIS IS USEFUL AS AN OPEN-SOURCE SERVER:
#   AI models do not know today's mutual-fund NAVs, and most existing MCP
#   market-data servers cover US stocks, not Indian mutual funds. This
#   server fills that gap using AMFI's official, free, no-API-key feed, so
#   anyone can ask an AI assistant "what's the latest NAV of <fund>?" and
#   get a real, current answer.
#
# THE TOOLS THIS SERVER OFFERS:
#   1. search_mutual_funds(query)      -> find schemes by name
#   2. get_fund_nav(scheme_code)       -> latest NAV for one scheme
#
#
#   To inspect it by hand:
#       npx @modelcontextprotocol/inspector python3 server.py
##############################################################################

from mcp.server.fastmcp import FastMCP

from amfi_client import search_schemes, get_nav_by_scheme_code

# ─────────────────────────────────────────────────────────────
# CREATE THE SERVER
# ─────────────────────────────────────────────────────────────

mcp = FastMCP("amfi-mutual-funds")


# ─────────────────────────────────────────────────────────────
# TOOL 1: SEARCH FOR SCHEMES BY NAME
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def search_mutual_funds(query: str) -> list[dict]:
    """
    Searches Indian mutual-fund schemes by name and returns matches with
    their latest NAV.

    Use this when the user names a fund in words rather than by its numeric
    scheme code -- for example "HDFC small cap" or "SBI bluechip". Each
    result includes the scheme code, which can then be passed to
    get_fund_nav for an exact lookup.

    Args:
        query: Part of a scheme name, e.g. "parag parikh flexi cap".

    Returns:
        A list of matching schemes, each with its scheme_code, scheme_name,
        nav, and date. Returns an empty list if nothing matches.
    """
    return search_schemes(query, limit=10)


# ─────────────────────────────────────────────────────────────
# TOOL 2: GET THE LATEST NAV FOR ONE SCHEME
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_fund_nav(scheme_code: str) -> dict:
    """
    Gets the latest official NAV for a single Indian mutual-fund scheme,
    looked up by its numeric AMFI scheme code.

    Use this once you know the exact scheme code (for example, from
    search_mutual_funds). The NAV and its date come from AMFI's official
    daily feed, so they are accurate as of the last publishing day.

    Args:
        scheme_code: The numeric AMFI scheme code, e.g. "120503".

    Returns:
        The scheme's latest NAV and date if found. If the scheme code is not
        found, returns a result marked as not found, so the AI can say so
        rather than inventing a number.
    """
    return get_nav_by_scheme_code(scheme_code)


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────
#
# This function is the console-script entry point (see pyproject.toml), so
# after installing the package you can just run:  amfi-mcp

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
