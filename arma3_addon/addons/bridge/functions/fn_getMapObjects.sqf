/*
 * fn_getMapObjects.sqf
 * Handles the "get_map_objects" MCP command.
 * Returns terrain objects (buildings, trees, roads, etc.) near a position.
 *
 * Params:
 *   position : Array  - [x, y] or [x, y, z]
 *   radius   : Number - search radius in metres (default 200)
 *   types    : Array  - filter by type strings, [] = all types (default [])
 *              e.g. ["HOUSE","TREE","ROAD","MAIN ROAD","TRACK","FENCE","WALL","ROCK"]
 *   max      : Number - max objects to return (default 100)
 */

params ["_id", "_params"];

private _fnGetParam = {
    params ["_key", "_default"];
    private _pair = _params select { (_x select 0) isEqualTo _key };
    if (count _pair > 0) then { (_pair select 0) select 1 } else { _default }
};

private _pos    = ["position", [0,0,0]] call _fnGetParam;
private _radius = ["radius",   200]     call _fnGetParam;
private _types  = ["types",    []]      call _fnGetParam;
private _max    = [["max", 100] call _fnGetParam, "max", true, 0, 16777215] call ArmaDevBridge_bridge_fnc_readNumber;
if !(_pos isEqualType [] && {count _pos in [2,3]}) then { throw "position must be [x,y] or [x,y,z]"; };
_pos = _pos apply { [_x, format ["position[%1]", _forEachIndex]] call ArmaDevBridge_bridge_fnc_readNumber };
_radius = [_radius, "radius", false, 0] call ArmaDevBridge_bridge_fnc_readNumber;
if !(_types isEqualType []) then { throw "types must be an array of strings"; };
{ if !(_x isEqualType "") then { throw "types must be an array of strings"; }; } forEach _types;

private _objects = nearestTerrainObjects [_pos, _types, _radius, false, true];
if (count _objects > _max) then { _objects resize _max; };

private _result = [];
{
    private _obj = _x;
    private _pos3 = getPosATL _obj;
    private _class = typeOf _obj;
    private _dir = getDir _obj;

    // typeOf is always "" for static terrain objects; use model filename as fallback.
    private _model = "";
    if (_class isEqualTo "") then {
        private _info = getModelInfo _obj;
        if (count _info > 0) then {
            private _modelPath = _info select 0;
            private _parts = _modelPath splitString "\/";
            _model = if (count _parts > 0) then { _parts select (count _parts - 1) } else { _modelPath };
        };
    };

    _result pushBack [
        ["class",    _class],
        ["model",    _model],
        ["position", _pos3],
        ["dir",      _dir]
    ];
} forEach _objects;

[
    _id,
    [
        ["ok",    true],
        ["count", count _result],
        ["objects", _result]
    ]
] call ArmaDevBridge_bridge_fnc_sendResponse;
