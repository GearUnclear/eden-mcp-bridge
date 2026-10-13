from __future__ import annotations
from typing import Annotated
from pydantic import BeforeValidator
from ..server import mcp, bridge
from ..protocol import normalize_number


Coordinate = Annotated[float, BeforeValidator(lambda value: normalize_number(value, "coordinate"))]
Radius = Annotated[float, BeforeValidator(lambda value: normalize_number(value, "radius", minimum=0))]
ResultLimit = Annotated[int, BeforeValidator(lambda value: normalize_number(value, "max", True, 0, 16777215))]


@mcp.tool()
async def get_terrain_info(positions: list[list[Coordinate]]) -> list[dict]:
    """
    Query terrain data for one or more world positions.

    Returns for each position:
    - x, y          : the queried coordinates
    - terrain_height : height above sea level in metres (negative = below sea)
    - is_water       : true if the position is over water (lake, sea, river)
    - surface_type   : short surface class name (e.g. "grass_green", "dirt", "concrete")

    Use this BEFORE placing objects to:
    - Avoid putting vehicles in water (is_water == true)
    - Check if terrain is flat enough for a building
    - Find the ground level for correct Z placement

    Example:
      get_terrain_info([[3000, 3000], [3100, 3000], [3200, 3000]])

    A single position is also accepted:
      get_terrain_info([[3000, 3000]])
    """
    result = await bridge.send_command({
        "cmd": "get_terrain_info",
        "positions": positions,
    })

    raw = result.get("results", [])
    output = []
    for item in raw:
        if isinstance(item, list):
            d = {p[0]: p[1] for p in item if isinstance(p, list) and len(p) == 2}
        elif isinstance(item, dict):
            d = item
        else:
            continue
        output.append({
            "x":              d.get("x", 0.0),
            "y":              d.get("y", 0.0),
            "terrain_height": d.get("terrain_height", 0.0),
            "is_water":       d.get("is_water", False),
            "surface_type":   d.get("surface_type", ""),
        })
    return output


@mcp.tool()
async def get_roads(
    position: list[Coordinate],
    radius: Radius = 500.0,
    max_segments: ResultLimit = 100,
) -> dict:
    """
    Return road segments near a position within the given radius.

    Each segment includes:
    - map_type      : "ROAD", "MAIN ROAD", "TRACK", "TRAIL", "HIDE"
    - width         : road width in metres
    - is_pedestrian : true for footpaths/trails
    - is_bridge     : true for bridge segments
    - beg_pos       : [x, y, z] start of segment
    - end_pos       : [x, y, z] end of segment

    Parameters:
    - position     : [x, y] or [x, y, z] center of search
    - radius       : search radius in metres (default 500)
    - max_segments : cap on returned segments to avoid huge payloads (default 100)

    Examples:
    - get_roads([3000, 3000], radius=200)
    - get_roads([5000, 5000], radius=1000, max_segments=200)
    """
    result = await bridge.send_command({
        "cmd": "get_roads",
        "position": position,
        "radius": radius,
        "max": max_segments,
    })

    raw_roads = result.get("roads", [])
    roads = []
    for item in raw_roads:
        if isinstance(item, list):
            d = {p[0]: p[1] for p in item if isinstance(p, list) and len(p) == 2}
        elif isinstance(item, dict):
            d = item
        else:
            continue
        roads.append({
            "map_type":      d.get("map_type", ""),
            "width":         d.get("width", 0.0),
            "is_pedestrian": d.get("is_pedestrian", False),
            "is_bridge":     d.get("is_bridge", False),
            "beg_pos":       d.get("beg_pos", []),
            "end_pos":       d.get("end_pos", []),
        })

    return {"count": len(roads), "roads": roads}


@mcp.tool()
async def get_map_objects(
    position: list[Coordinate],
    radius: Radius = 200.0,
    types: list[str] | None = None,
    max_objects: ResultLimit = 100,
) -> dict:
    """
    Return terrain objects (buildings, trees, roads, fences, etc.) near a position.

    Types filter — pass a list to get only specific object kinds (case-insensitive):
      Structures : "HOUSE", "BUILDING", "BUNKER", "CHURCH", "CHAPEL", "HOSPITAL",
                   "FUELSTATION", "FORTRESS", "FOUNTAIN", "RUIN", "SHIPWRECK",
                   "TOURISM", "VIEW-TOWER", "WATERTOWER", "LIGHTHOUSE", "STACK",
                   "CROSS", "BUSSTOP", "QUAY"
      Vegetation : "TREE", "SMALL TREE", "BUSH", "FOREST", "FOREST BORDER",
                   "FOREST SQUARE", "FOREST TRIANGLE"
      Terrain    : "ROCK", "ROCKS", "HIDE"
      Roads      : "ROAD", "MAIN ROAD", "TRACK", "TRAIL"
      Infra      : "FENCE", "WALL", "POWER LINES", "TRANSMITTER", "RAILWAY",
                   "POWERSOLAR", "POWERWAVE", "POWERWIND"
    Not all types exist on every map. Pass [] or omit to return ALL types.

    Each object includes:
    - class    : config class name (e.g. "Land_HouseV_1t_F"), empty for terrain objects
    - model    : model filename (e.g. "t_pinus2s_b_f.p3d") when class is empty
    - position : [x, y, z]
    - dir      : heading in degrees (0-360)

    Parameters:
    - position    : [x, y] or [x, y, z] center
    - radius      : search radius in metres (default 200)
    - types       : list of type strings to filter, [] = all
    - max_objects : cap on returned objects (default 100)

    Examples:
    - get_map_objects([3000, 3000], radius=300, types=["HOUSE","CHURCH"])
    - get_map_objects([5000, 5000], radius=100, types=["ROAD","MAIN ROAD","TRACK"])
    - get_map_objects([3000, 3000], radius=50)  # everything nearby
    """
    result = await bridge.send_command({
        "cmd": "get_map_objects",
        "position": position,
        "radius": radius,
        "types": types or [],
        "max": max_objects,
    })

    raw = result.get("objects", [])
    objects = []
    for item in raw:
        if isinstance(item, list):
            d = {p[0]: p[1] for p in item if isinstance(p, list) and len(p) == 2}
        elif isinstance(item, dict):
            d = item
        else:
            continue
        objects.append({
            "class":    d.get("class", ""),
            "model":    d.get("model", ""),
            "position": d.get("position", []),
            "dir":      d.get("dir", 0.0),
        })

    return {"count": len(objects), "objects": objects}


@mcp.tool()
async def find_location(query: str) -> dict:
    """
    Search for named map locations by name (case-insensitive substring match).

    Searches all location types: cities, villages, hills, peaks, airports, local names.

    Returns matching locations with:
    - name     : display name (e.g. "LZ Connor", "Agia Marina")
    - type     : location type ("NameCity", "NameVillage", "Hill", "Airport", etc.)
    - position : [x, y, z] world coordinates

    Examples:
    - find_location("connor")   # finds "LZ Connor"
    - find_location("agia")     # finds "Agia Marina"
    - find_location("airport")  # finds airports
    - find_location("")         # returns ALL named locations on the map
    """
    result = await bridge.send_command({
        "cmd": "find_location",
        "query": query,
    })

    raw = result.get("locations", [])
    locations = []
    for item in raw:
        if isinstance(item, list):
            d = {p[0]: p[1] for p in item if isinstance(p, list) and len(p) == 2}
        elif isinstance(item, dict):
            d = item
        else:
            continue
        locations.append({
            "name":     d.get("name", ""),
            "type":     d.get("type", ""),
            "position": d.get("position", []),
        })

    return {"count": len(locations), "locations": locations}
