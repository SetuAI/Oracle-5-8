##############################################################################
# amfi_client.py
#
# PURPOSE:
#   This module talks to AMFI (the Association of Mutual Funds in India),
#   which publishes the official daily Net Asset Value (NAV) for every
#   mutual fund scheme in India as a single free text file. This module
#   downloads that file, parses it, caches it, and offers simple lookups:
#   find a scheme by name, and get a scheme's latest NAV.
#
# WHY A SEPARATE FILE:
#   We keep all the "talking to AMFI and understanding its data" logic here,
#   away from the MCP server. The server (server.py) only exposes tools; the
#   real work lives here. This makes each file easy to read on its own.
#
# THE AMFI DATA FORMAT:
#   AMFI serves one big semicolon-separated text file. Fund rows look like:
#
#     Scheme Code;ISIN Payout;ISIN Reinvest;Scheme Name;NAV;Date
#     120503;INF209K01157;INF209K01165;Aditya Birla ... Growth;512.34;27-Jul-2026
#
#   The file also contains blank lines and header lines (AMC names and
#   category names) that are NOT fund rows. We detect real fund rows by the
#   fact that they contain several ';' separators; everything else is
#   skipped.
#
# CACHING:
#   The full file is a few megabytes and updates once per day. We download
#   it once and keep it in memory for a while (see CACHE_TTL_SECONDS) so we
#   are not re-downloading it on every single lookup.
#
# NETWORK NOTE:
#   This module needs outbound internet access to reach AMFI. If you run it
#   in a sandbox that blocks external hosts, allow "www.amfiindia.com".
##############################################################################

from __future__ import annotations

import time
import httpx


# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────

# The official AMFI "all schemes" NAV feed.
AMFI_NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"

REQUEST_TIMEOUT_SECONDS = 30
CACHE_TTL_SECONDS = 60 * 60  # re-fetch at most once per hour


# ─────────────────────────────────────────────────────────────
# IN-MEMORY CACHE
# ─────────────────────────────────────────────────────────────
#
# We store the parsed schemes and the time we fetched them, so repeated
# lookups within the TTL do not hit the network again.

_cache: dict[str, object] = {
    "fetched_at": 0.0,
    "schemes": [],   # list of scheme dicts
}


# ─────────────────────────────────────────────────────────────
# FETCH + PARSE
# ─────────────────────────────────────────────────────────────

def _download_raw_nav_file() -> str:
    """
    Downloads the raw AMFI NAV text file and returns it as a string.

    Raises:
        httpx.HTTPError: If the download fails or times out.
    """
    response = httpx.get(AMFI_NAV_URL, 
                         timeout=REQUEST_TIMEOUT_SECONDS,
                         follow_redirects=True)
    response.raise_for_status()
    return response.text


def _parse_nav_file(raw_text: str) -> list[dict]:
    """
    Turns the raw AMFI text file into a list of scheme dictionaries.

    Args:
        raw_text: The full contents of the AMFI NAV file.

    Returns:
        A list of dicts, one per scheme, each shaped like:
            {
                "scheme_code": "120503",
                "scheme_name": "Aditya Birla Sun Life ... Growth",
                "nav": 512.34,
                "date": "27-Jul-2026",
                "isin": "INF209K01157"
            }
        Rows that are not valid fund rows (headers, blank lines) are skipped.
    """
    schemes: list[dict] = []

    for line in raw_text.splitlines():
        # A real fund row has at least 5 ';' separators (6 columns).
        # Header/AMC/category lines and blanks do not, so we skip them.
        parts = line.split(";")
        if len(parts) < 6:
            continue

        scheme_code = parts[0].strip()
        isin_payout = parts[1].strip()
        # Newer AMFI files add "Plan" and "Option" columns between the name
        # and the NAV, so NAV and Date are always the last two columns.
        # Anything between the name and the NAV is folded into the name.
        scheme_name = " - ".join(p.strip() for p in parts[3:-2] if p.strip())
        nav_text    = parts[-2].strip()
        date_text   = parts[-1].strip()

        # The header row literally says "Scheme Code" in column 0 -- skip it.
        if not scheme_code.isdigit():
            continue

        # NAV is sometimes "N.A." for schemes with no NAV that day.
        try:
            nav_value: float | None = float(nav_text)
        except ValueError:
            nav_value = None

        schemes.append(
            {
                "scheme_code": scheme_code,
                "scheme_name": scheme_name,
                "nav":         nav_value,
                "date":        date_text,
                "isin":        isin_payout,
            }
        )

    return schemes


def _get_all_schemes(force_refresh: bool = False) -> list[dict]:
    """
    Returns all parsed schemes, using the in-memory cache when it is fresh.

    Args:
        force_refresh: If True, ignore the cache and re-download.

    Returns:
        The full list of scheme dictionaries.
    """
    age = time.time() - float(_cache["fetched_at"])

    if force_refresh or not _cache["schemes"] or age > CACHE_TTL_SECONDS:
        raw = _download_raw_nav_file()
        _cache["schemes"] = _parse_nav_file(raw)
        _cache["fetched_at"] = time.time()

    return _cache["schemes"]  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────
# PUBLIC LOOKUPS (these are what the MCP tools call)
# ─────────────────────────────────────────────────────────────

def search_schemes(query: str, limit: int = 10) -> list[dict]:
    """
    Finds mutual-fund schemes whose name contains the query text.

    Args:
        query: Part of a scheme name, e.g. "hdfc small cap".
        limit: Maximum number of matches to return.

    Returns:
        A list of matching scheme dicts (scheme_code, scheme_name, nav,
        date). Empty list if nothing matches.
    """
    words = [w for w in query.lower().split() if w]
    if not words:
        return []

    matches = []
    for scheme in _get_all_schemes():
        name_lower = scheme["scheme_name"].lower()
        # Keep schemes whose name contains ALL of the query words.
        if all(word in name_lower for word in words):
            matches.append(scheme)
            if len(matches) >= limit:
                break

    return matches


def get_nav_by_scheme_code(scheme_code: str) -> dict:
    """
    Gets the latest NAV for one scheme by its AMFI scheme code.

    Args:
        scheme_code: The numeric AMFI scheme code, e.g. "120503".

    Returns:
        The scheme dict if found:
            {"found": True, "scheme_code": ..., "scheme_name": ...,
             "nav": ..., "date": ...}
        Or, if not found:
            {"found": False, "scheme_code": "<what was searched>"}
    """
    wanted = scheme_code.strip()

    for scheme in _get_all_schemes():
        if scheme["scheme_code"] == wanted:
            return {"found": True, **scheme}

    return {"found": False, "scheme_code": scheme_code}


if __name__ == "__main__":
    # Quick manual check (needs internet access to www.amfiindia.com).
    print("Fetching AMFI data ...")
    all_schemes = _get_all_schemes()
    print(f"Parsed {len(all_schemes)} schemes.\n")

    print("Sample search for 'hdfc small cap':")
    for s in search_schemes("hdfc small cap", limit=5):
        print(f"  {s['scheme_code']}  {s['scheme_name']}  NAV={s['nav']} ({s['date']})")
