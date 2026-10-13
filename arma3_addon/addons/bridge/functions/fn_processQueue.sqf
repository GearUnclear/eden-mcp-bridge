/*
 * fn_processQueue.sqf
 * Called every editor frame via EachFrame event handler.
 *
 * Polls the DLL for the next pending command from the Python MCP server.
 * Each call processes at most one command to keep frame time impact minimal.
 *
 * The DLL returns "" when the queue is empty.
 *
 * Message format from Python (SQF array notation, also valid JSON):
 *   ["id", "cmd", "key1", val1, "key2", val2, ...]
 *
 * e.g. ["uuid-1234", "create_entity", "entity_type", "Vehicle",
 *        "classname", "B_MRAP_01_F", "position", [3000,3000,0], "side", "WEST"]
 */

// Never dispatch editor commands into a running Preview mission.
if (!is3DEN) exitWith {};

// Synchronous handlers must finish in their dispatch frame. If a native SQF
// runtime error aborted that frame (try/catch only catches explicit throws),
// fail its request on the next frame. Never repeat the command or its edits.
private _abandoned = missionNamespace getVariable ["ArmaDevBridge_pendingResponse", []];
if (count _abandoned > 0) then {
    [_abandoned select 0, [["ok",false], ["error","handler_no_response: editor handler aborted; edits may be partial"],
        ["command",_abandoned select 1], ["stage",missionNamespace getVariable ["ArmaDevBridge_responseStage","dispatch"]]]]
        call ArmaDevBridge_bridge_fnc_sendResponse;
};

// Commands are delivered by polling only.
params [["_raw", ""]];
if (_raw isEqualTo "") then {
    _raw = "arma3_mcp_bridge" callExtension "poll";
};
if (_raw isEqualTo "") exitWith {};

// Parse the payload as a DATA-ONLY simple array. parseSimpleArray accepts only
// numbers/strings/bools/nested arrays and executes NOTHING, so a crafted or
// prompt-injected payload can never become live SQF (unlike `call compile`).
// On malformed input it returns [], which the count guard below rejects.
private _msg = parseSimpleArray _raw;
if (isNil "_msg" || !(_msg isEqualType []) || count _msg < 2) exitWith {};

private _id  = _msg select 0;
private _cmd = _msg select 1;
if (isNil "_id" || {isNil "_cmd"} || {!(_id isEqualType "")} || {!(_cmd isEqualType "")} || {_id isEqualTo ""} || {count _id > 128}) exitWith {};

// Retain a defensive request-id guard for old DLLs or repeated delivery.
// Track recently-seen request ids and
// skip repeats. Empty ids (shouldn't happen for queued cmds) are not deduped.
// NB: a bare `if (..) exitWith {}` inside the then-block would only exit that
// block, not the script, so flag the duplicate and exit at the top scope.
private _dup = false;
if (!(_id isEqualTo "")) then {
    private _seen = missionNamespace getVariable ["ArmaDevBridge_seenIds", []];
    if (_id in _seen) then {
        _dup = true;
    } else {
        _seen pushBack _id;
        if (count _seen > 64) then { _seen deleteAt 0; };
        missionNamespace setVariable ["ArmaDevBridge_seenIds", _seen];
    };
};
if (_dup) exitWith {};

missionNamespace setVariable ["ArmaDevBridge_pendingResponse", [_id,_cmd]];
missionNamespace setVariable ["ArmaDevBridge_responseStage", "validation"];
try {
if ((count _msg) mod 2 != 0) then { throw "request: expected alternating parameter keys and values" };

// Increment command counter and flash the status indicator
private _count = (missionNamespace getVariable ["ArmaDevBridge_commandCount", 0]) + 1;
missionNamespace setVariable ["ArmaDevBridge_commandCount", _count];
[true, true] call ArmaDevBridge_bridge_fnc_updateBridgeStatus;

// Build a flat array of [key, value] pairs from alternating key/value pairs.
// Using an array instead of a HashMap avoids a SQF HashMap bug where
// getOrDefault returns the wrong value for certain key combinations.
private _params = [];
private _i = 2;
while { _i < count _msg - 1 } do {
    if (isNil {_msg select _i} || {isNil {_msg select (_i + 1)}}) then { throw "request: nil parameter" };
    private _key = _msg select _i;
    if (!(_key isEqualType "") || {_key isEqualTo ""}) then { throw "request: parameter name must be a nonempty string" };
    if ((_params findIf {(_x select 0) isEqualTo _key}) >= 0) then { throw format ["request: duplicate parameter %1", _key] };
    _params pushBack [(_msg select _i), (_msg select (_i + 1))];
    _i = _i + 2;
};

// Dispatch
missionNamespace setVariable ["ArmaDevBridge_responseStage", "dispatch"];
diag_log format ["[ArmaDevBridge] dispatch command=%1", _cmd];
switch (_cmd) do {
    case "ping": {
        [_id, [["ok", true], ["editor_open", true], ["version", "1.2.0-rc.1"]]] call ArmaDevBridge_bridge_fnc_sendResponse;
    };
    case "create_entity": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_createEntity;
    };
    case "delete_entity": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_deleteEntity;
    };
    case "move_entity": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_moveEntity;
    };
    case "group_entities": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_groupEntities;
    };
    case "set_attribute": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_setAttribute;
    };
    case "get_attribute": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_getAttribute;
    };
    case "get_selected": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_getSelected;
    };
    case "list_entities": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_listEntities;
    };
    case "get_all_objects": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_getAllObjects;
    };
    case "get_placeable_objects": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_getPlaceableObjects;
    };
    case "get_placeable_categories": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_getPlaceableCategories;
    };
    case "get_mission_info": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_getMissionInfo;
    };
    case "save_mission": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_saveMission;
    };
    case "clear_mission": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_clearMission;
    };
    case "get_terrain_info": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_getTerrainInfo;
    };
    case "get_roads": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_getRoads;
    };
    case "get_map_objects": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_getMapObjects;
    };
    case "find_location": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_findLocation;
    };
    case "get_supported_attributes": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_getSupportedAttributes;
    };
    case "get_all_attributes": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_getAllAttributes;
    };
    case "undo": {
        [_id, _params] call ArmaDevBridge_bridge_fnc_undo;
    };
    default {
        [_id, [["ok", false], ["error", format ["Unknown command: %1", _cmd]]]] call ArmaDevBridge_bridge_fnc_sendResponse;
    };
};
} catch {
    [_id, [["ok",false], ["error",str _exception], ["command",_cmd],
        ["stage",missionNamespace getVariable ["ArmaDevBridge_responseStage","dispatch"]]]]
        call ArmaDevBridge_bridge_fnc_sendResponse;
};
// Also catch a normal handler return with no response; the next-frame guard
// above covers runtime failures which prevent this postcondition from running.
private _remaining = missionNamespace getVariable ["ArmaDevBridge_pendingResponse", []];
if (count _remaining > 0 && {(_remaining select 0) isEqualTo _id}) then {
    [_id, [["ok",false], ["error","handler_no_response: handler returned without a result; edits may be partial"],
        ["command",_cmd], ["stage",missionNamespace getVariable ["ArmaDevBridge_responseStage","dispatch"]]]]
        call ArmaDevBridge_bridge_fnc_sendResponse;
};
