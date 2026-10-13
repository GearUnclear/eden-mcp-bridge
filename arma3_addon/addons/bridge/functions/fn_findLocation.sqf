/*
 * fn_findLocation.sqf
 * Handles the "find_location" MCP command.
 * Searches all named map locations by name (case-insensitive substring).
 *
 * Params:
 *   query : String - substring to search for in location names (empty = return all)
 */

params ["_id", "_params"];

private _fnGetParam = {
    params ["_key", "_default"];
    private _pair = _params select { (_x select 0) isEqualTo _key };
    if (count _pair > 0) then { (_pair select 0) select 1 } else { _default }
};

private _query = ["query", ""] call _fnGetParam;
if !(_query isEqualType "") then { throw "query must be a string"; };
_query = toLower _query;

private _center = [worldSize / 2, worldSize / 2, 0];
private _types  = [
    "NameCity", "NameCityCapital", "NameVillage", "NameLocal",
    "Name", "Hill", "Mount", "Airport"
];
private _all = nearestLocations [_center, _types, worldSize];

private _result = [];
{
    private _name = text _x;
    if (_query isEqualTo "" || { (toLower _name) find _query >= 0 }) then {
        _result pushBack [
            ["name",     _name],
            ["type",     type _x],
            ["position", locationPosition _x]
        ];
    };
} forEach _all;

[_id, [["ok", true], ["count", count _result], ["locations", _result]]] call ArmaDevBridge_bridge_fnc_sendResponse;
