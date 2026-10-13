"""
wiki.py — Tools for looking up Arma 3 scripting commands and functions
         from the scraped BI Wiki markdown files.

Files live in: wiki_scraper/output/markdown/{name}.md
"""

from __future__ import annotations
from pathlib import Path

from ..server import mcp

_WIKI_DIR = (Path(__file__).parent.parent / "wiki").resolve()


def _safe_filename(name: str) -> str:
    import re
    # NOTE: this regex does NOT reliably strip path separators (on Windows a
    # backslash survives), so it must NOT be relied on for sandboxing. The hard
    # containment guarantee is enforced by _resolve_in_wiki() below.
    safe = re.sub(r'[\\/:*?"<>|]', "_", name.strip())
    safe = re.sub(r" {2,}", " ", safe)
    return safe[:120] or "unknown"


def _resolve_in_wiki(name: str) -> Path | None:
    """Resolve <name>.md inside the wiki dir, or None if it would escape it.

    Defends against path traversal (e.g. ``..\\..\\secret``): we resolve the
    final absolute path and confirm it is still under _WIKI_DIR. This holds no
    matter what _safe_filename let through.
    """
    candidate = (_WIKI_DIR / (_safe_filename(name) + ".md")).resolve()
    if candidate == _WIKI_DIR or _WIKI_DIR not in candidate.parents:
        return None
    return candidate


def _all_names() -> list[str]:
    return sorted(p.stem for p in _WIKI_DIR.glob("*.md"))


@mcp.tool()
def wiki_lookup(name: str) -> str:
    """
    Return the full documentation for an Arma 3 scripting command, function,
    or concept by its exact name.

    Examples: "forEach", "BIS_fnc_taskCreate", "addMissionEventHandler", "waitUntil"

    Returns the Markdown content of the wiki page, including syntax, parameters,
    return value, examples, and see-also links.
    If the page is not found, suggests similar names.
    """
    path = _resolve_in_wiki(name)
    if path is not None and path.exists():
        return path.read_text(encoding="utf-8")

    # Try case-insensitive match
    name_lower = name.lower()
    for p in _WIKI_DIR.glob("*.md"):
        if p.stem.lower() == name_lower:
            return p.read_text(encoding="utf-8")

    # Suggest similar names
    similar = [n for n in _all_names() if name_lower in n.lower()][:10]
    if similar:
        return f"Page '{name}' not found. Similar names:\n" + "\n".join(f"- {n}" for n in similar)
    return f"Page '{name}' not found and no similar names found."


@mcp.tool()
def wiki_search(query: str) -> list[str]:
    """
    Search Arma 3 wiki pages by name. Returns a list of matching command/function names.

    Use this to discover commands when you don't know the exact name.
    Then call wiki_lookup(name) to get the full documentation.

    Examples:
    - wiki_search("event")     → all commands with "event" in the name
    - wiki_search("BIS_fnc")   → all BIS functions
    - wiki_search("addWeapon") → addWeapon and variants
    - wiki_search("trigger")   → trigger-related commands
    """
    q = query.lower()
    return [n for n in _all_names() if q in n.lower()]
