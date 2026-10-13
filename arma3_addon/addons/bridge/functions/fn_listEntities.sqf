/*
 * fn_listEntities.sqf
 * Handles the "list_entities" MCP command.
 * Returns all entities of the given type in the current mission.
 *
 * Expected params:
 *   entity_type : STRING  "Object" (default), "Group", "Trigger", "Waypoint", "Marker"
 */

params ["_id", "_params"];

private _typeIdx = _params findIf { (_x select 0) isEqualTo "entity_type" };
private _type    = if (_typeIdx < 0) then { "Object" } else { _params select _typeIdx select 1 };

// all3DENEntities returns all entities of the given category in the editor
private _all = all3DENEntities;

// Official order: [objects, groups, triggers, systems, waypoints, markers, layers, comments]
private _typeIndex = switch (_type) do {
    case "Object":    { 0 };
    case "Vehicle":   { 0 };
    case "Unit":      { 0 };
    case "Group":     { 1 };
    case "Trigger":   { 2 };
    case "Waypoint":  { 4 };
    case "Marker":    { 5 };
    case "Layer":     { 6 };
    case "Logic":     { 3 };
    default           { -1 };
};

if (_typeIndex < 0) then { throw "Unsupported entity_type; use Object, Unit, Vehicle, Group, Trigger, Logic, Waypoint, Marker or Layer"; };
private _entities = if (count _all > _typeIndex) then { _all select _typeIndex } else { [] };

private _list = [];
{
    // typeOf only accepts Objects; Groups (and other non-object categories)
    // throw "Type Group, expected Object". Guard so listing Groups works.
    private _classname = if (_x isEqualType objNull) then { typeOf _x } else { "" };
    private _eid = if (_type isEqualTo "Layer") then {_x} else {get3DENEntityID _x};
    _list pushBack [["entity_id", _eid], ["classname", _classname], ["entity_kind", ["Object","Group","Trigger","Logic","Waypoint","Marker","Layer"] select _typeIndex]];
} forEach _entities;

[_id, [["ok", true], ["entities", _list], ["count", count _list]]] call ArmaDevBridge_bridge_fnc_sendResponse;
