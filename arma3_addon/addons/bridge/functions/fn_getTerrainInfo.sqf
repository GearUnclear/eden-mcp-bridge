/*
 * fn_getTerrainInfo.sqf
 * Handles the "get_terrain_info" MCP command.
 *
 * Returns terrain data at one or more positions:
 *   - terrain_height : height above sea level (meters)
 *   - is_water       : true if position is over water
 *   - surface_type   : surface class string (e.g. "grass_green", "dirt", "concrete")
 *
 * Expected params:
 *   positions : ARRAY  [[x,y], [x,y,z], ...] (z validated, terrain query uses x/y)
 *               A single [x,y] or [x,y,z] is also accepted (auto-wrapped).
 */

params ["_id", "_params"];

private _posIdx    = _params findIf { (_x select 0) isEqualTo "positions" };
private _positions = if (_posIdx < 0) then { [] } else { _params select _posIdx select 1 };
if !(_positions isEqualType []) then { throw "positions must be an array of [x,y] or [x,y,z] positions"; };

// Accept a single position (auto-wrap).
if (count _positions in [2,3] && {!(_positions select 0 isEqualType [])}) then {
    _positions = [_positions];
};

private _results = [];

// Validate the entire request before calling engine terrain commands.
_positions = _positions apply {
    private _positionIndex = _forEachIndex;
    if !(_x isEqualType [] && {count _x in [2,3]}) then { throw format ["positions[%1] must be [x,y] or [x,y,z]", _positionIndex]; };
    _x apply {
        [_x, format ["positions[%1][%2]", _positionIndex, _forEachIndex]] call ArmaDevBridge_bridge_fnc_readNumber
    }
};

{
    private _pos  = _x;
    private _x2d  = _pos select 0;
    private _y2d  = _pos select 1;

    private _height  = getTerrainHeightASL [_x2d, _y2d];
    private _isWater = surfaceIsWater [_x2d, _y2d];
    private _surface = surfaceType [_x2d, _y2d];

    // surfaceType returns e.g. "\A3\map_altis\data\layers\P_Altis_Grain.paa"
    // Split by backslash, take last segment, then strip extension.
    private _parts = _surface splitString "\";
    private _filename = if (count _parts > 0) then {
        _parts select (count _parts - 1)
    } else {
        _surface
    };
    private _dotParts  = _filename splitString ".";
    private _surfShort = if (count _dotParts > 0) then {
        _dotParts select 0
    } else {
        _filename
    };

    _results pushBack [
        ["x",              _x2d],
        ["y",              _y2d],
        ["terrain_height", _height],
        ["is_water",       _isWater],
        ["surface_type",   _surfShort]
    ];
} forEach _positions;

[_id, [["ok", true], ["results", _results]]] call ArmaDevBridge_bridge_fnc_sendResponse;
