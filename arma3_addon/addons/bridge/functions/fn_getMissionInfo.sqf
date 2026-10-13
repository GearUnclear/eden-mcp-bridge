/*
 * fn_getMissionInfo.sqf
 * Handles the "get_mission_info" MCP command.
 * Returns general info about the open mission.
 */

params ["_id", "_params"];

private _all = all3DENEntities;
// Indices: 0=objects, 1=groups, 2=triggers, 3=logic, 4=waypoints, 5=markers, 6=layers
private _objects   = if (count _all > 0) then { count (_all select 0) } else { 0 };
private _groups    = if (count _all > 1) then { count (_all select 1) } else { 0 };
private _triggers  = if (count _all > 2) then { count (_all select 2) } else { 0 };
private _waypoints = if (count _all > 4) then { count (_all select 4) } else { 0 };

private _missionName = briefingName;
if (isNil "_missionName" || !(_missionName isEqualType "")) then { _missionName = ""; };
private _author  = "";
private _terrain = worldName;

[
    _id,
    [
        ["ok", true],
        ["name", _missionName],
        ["author", _author],
        ["terrain", _terrain],
        ["entity_count", _objects],
        ["groups", _groups],
        ["triggers", _triggers],
        ["waypoints", _waypoints]
    ]
] call ArmaDevBridge_bridge_fnc_sendResponse;
