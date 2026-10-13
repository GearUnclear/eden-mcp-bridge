/*
 * fn_getRoads.sqf
 * Handles the "get_roads" MCP command.
 * Returns road segments near a given position within a radius.
 *
 * Params (from _params array):
 *   position : Array  - [x, y] or [x, y, z] center of search
 *   radius   : Number - search radius in metres (default 500)
 *   max      : Number - max segments to return (default 100)
 */

params ["_id", "_params"];

private _fnGetParam = {
    params ["_key", "_default"];
    private _pair = _params select { (_x select 0) isEqualTo _key };
    if (count _pair > 0) then { (_pair select 0) select 1 } else { _default }
};

private _pos    = ["position", [0,0,0]] call _fnGetParam;
private _radius = ["radius",   500]     call _fnGetParam;
private _max    = [["max", 100] call _fnGetParam, "max", true, 0, 16777215] call ArmaDevBridge_bridge_fnc_readNumber;
if !(_pos isEqualType [] && {count _pos in [2,3]}) then { throw "position must be [x,y] or [x,y,z]"; };
_pos = _pos apply { [_x, format ["position[%1]", _forEachIndex]] call ArmaDevBridge_bridge_fnc_readNumber };
_radius = [_radius, "radius", false, 0] call ArmaDevBridge_bridge_fnc_readNumber;

private _roads = _pos nearRoads _radius;
if (count _roads > _max) then { _roads resize _max; };

private _result = [];
{
    private _info = getRoadInfo _x;
    if (count _info >= 9) then {
        _info params [
            "_mapType", "_width", "_isPedestrian",
            "_texture", "_textureEnd", "_material",
            "_begPos",  "_endPos",    "_isBridge"
        ];
        _result pushBack [
            ["map_type",     _mapType],
            ["width",        _width],
            ["is_pedestrian",_isPedestrian],
            ["is_bridge",    _isBridge],
            ["beg_pos",      _begPos],
            ["end_pos",      _endPos]
        ];
    };
} forEach _roads;

[
    _id,
    [
        ["ok",    true],
        ["count", count _result],
        ["roads", _result]
    ]
] call ArmaDevBridge_bridge_fnc_sendResponse;
