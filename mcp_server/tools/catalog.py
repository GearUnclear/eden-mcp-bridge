"""
catalog.py — Tools for browsing the Arma 3 placeable-objects catalogue.

These tools read the game's CfgVehicles config (not the current mission),
returning all classes that can be placed in the Eden Editor, with their
display names, sides, factions, and vehicle categories.

MOD SUPPORT: Arma 3's configFile is the fully merged config that includes
vanilla content AND all loaded mods. Objects from RHS, ACE, CUP, 3CB, RHSAFRF,
and any other loaded addon will appear automatically — no special handling needed.
The cache is built once from the live config at first request.

Typical workflow:
  1. get_placeable_categories()         → discover available filters + mod content totals
  2. search_placeable_objects(...)      → find specific classes by name/category/faction
  3. create_entity(classname=..., ...)  → place the found class in the editor
"""

from __future__ import annotations
from typing import Annotated
from pydantic import BeforeValidator
from ..server import mcp, bridge
from ..models import PlaceableObject, PlaceableObjectsPage, PlaceableCategories
from ..protocol import normalize_catalog_side, normalize_number


def _page_number(value: object) -> int:
    return normalize_number(value, "page", True, 0, 16777215)


def _page_size(value: object) -> int:
    return min(normalize_number(value, "page_size", True, 1, 16777215), 100)


def _parse_placeable(raw: list) -> PlaceableObject:
    d = {item[0]: item[1] for item in raw if isinstance(item, list) and len(item) == 2}
    return PlaceableObject(
        classname=str(d.get("classname", "")),
        display_name=str(d.get("display_name", "")),
        side=str(d.get("side", "UNKNOWN")),
        config_side=d.get("config_side"),
        faction=str(d.get("faction", "")),
        vehicle_class=str(d.get("vehicle_class", "")),
        editor_category=str(d.get("editor_category", "")),
        editor_subcategory=str(d.get("editor_subcategory", "")),
    )


@mcp.tool()
async def get_placeable_categories() -> PlaceableCategories:
    """
    Return all available filter values for the Eden Editor object catalogue:
    vehicle classes (Air, Car, Tank, Man, Sea...), factions, sides, and
    editor categories.

    Use this FIRST to discover what filters are available before calling
    search_placeable_objects. Also tells you how many total placeable objects
    exist (including mods if loaded).

    The first call builds a cache from CfgVehicles. Later calls reuse it until
    refresh_cache is requested or the catalogue schema changes.
    """
    result = await bridge.send_command({"cmd": "get_placeable_categories"})
    return PlaceableCategories(
        vehicle_classes=result.get("vehicle_classes", []),
        factions=result.get("factions", []),
        sides=result.get("sides", []),
        editor_categories=result.get("editor_categories", []),
        total_placeable=int(result.get("total_placeable", 0)),
    )


@mcp.tool()
async def search_placeable_objects(
    search: str = "",
    filter_side: Annotated[str | int, BeforeValidator(normalize_catalog_side)] = "ALL",
    filter_vehicle_class: str = "",
    filter_faction: str = "",
    page: Annotated[int, BeforeValidator(_page_number)] = 0,
    page_size: Annotated[int, BeforeValidator(_page_size)] = 30,
    refresh_cache: bool = False,
) -> PlaceableObjectsPage:
    """
    Search the Eden Editor placeable-objects catalogue (CfgVehicles).

    Returns classnames with display names, sides, factions, and categories.
    Use the returned classname with create_entity to place objects in the editor.

    Parameters:
    - search: substring to match against classname OR display name (case-insensitive).
      Example: "mrap", "tank", "building", "sign", "boat", "helicopter"
    - filter_side: named config affiliation: ALL, EAST, WEST, GUER, CIV,
      NEUTRAL, ENEMY, FRIENDLY, LOGIC, EMPTY, AMBIENT, UNKNOWN.
      Legacy integers: -1=ALL, 0=NEUTRAL, 1=EAST, 2=WEST, 3=GUER, 4=CIV, 5=AMBIENT.
      Legacy 0 deliberately targets neutral config objects; it no longer selects EAST
      classes due to the old mapping bug. EMPTY selects config side 8, not every
      vehicle that can be placed without crew. A WEST vehicle remains WEST in this
      catalogue even when create_entity places it empty.
    - filter_vehicle_class: exact match (case-insensitive).
      Common values: "Air", "Car", "Tank", "Man", "Sea", "Ship", "StaticWeapon", "Animal"
      Leave "" to include all vehicle classes (buildings, signs, etc. have empty class).
    - filter_faction: exact faction class name, e.g. "BLU_F", "OPF_F", "IND_F".
      Use get_placeable_categories() to see all available faction names.
    - page / page_size: pagination (max 100 per page).
    - refresh_cache: set True to force re-reading the config (needed after loading new mods).

    Examples:
    - All BLUFOR wheeled vehicles: filter_side="WEST", filter_vehicle_class="Car"
    - Search boats: search="boat"
    - All OPFOR aircraft: filter_side="EAST", filter_vehicle_class="Air"
    - All signs: search="sign"
    - Search buildings: search="building" (empty vehicle_class filter includes all).
    """
    result = await bridge.send_command({
        "cmd": "get_placeable_objects",
        "page": _page_number(page),
        "page_size": _page_size(page_size),
        "filter_side": normalize_catalog_side(filter_side),
        "filter_vehicle_class": filter_vehicle_class,
        "filter_faction": filter_faction,
        "search": search,
        "refresh": refresh_cache,
    })

    objects = [_parse_placeable(raw) for raw in result.get("objects", [])]

    return PlaceableObjectsPage(
        objects=objects,
        page=int(result.get("page", page)),
        page_size=int(result.get("page_size", page_size)),
        total=int(result.get("total", len(objects))),
        total_pages=int(result.get("total_pages", 1)),
        has_more=bool(result.get("has_more", False)),
        cache_size=int(result.get("cache_size", 0)),
    )


@mcp.tool()
async def find_classname(display_name_query: str) -> list[PlaceableObject]:
    """
    Find the exact classname(s) for an object when you only know its
    display name or a partial name.

    Searches across the full catalogue and returns the top 20 matches.
    Use the returned classname with create_entity.

    Examples:
    - find_classname("MRAP")         → finds B_MRAP_01_F and variants
    - find_classname("T-72")         → finds T-72 tank classnames
    - find_classname("container")    → finds shipping containers
    - find_classname("patrol boat")  → finds small boats
    """
    result = await bridge.send_command({
        "cmd": "get_placeable_objects",
        "page": 0,
        "page_size": 20,
        "filter_side": "ALL",
        "filter_vehicle_class": "",
        "filter_faction": "",
        "search": display_name_query,
        "refresh": False,
    })
    return [_parse_placeable(raw) for raw in result.get("objects", [])]
