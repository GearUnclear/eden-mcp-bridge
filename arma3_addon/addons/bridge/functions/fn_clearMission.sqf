/*
 * fn_clearMission.sqf
 * Elimina todos los objetos del Eden Editor.
 * Usa delete3DENEntities para que la acción sea deshacible con Ctrl+Z.
 *
 * Params: [_id, _params] via processQueue
 */

if (!is3DEN) exitWith {
    [(_this select 0), [["ok", false], ["error", "Not in Eden Editor"]]] call ArmaDevBridge_bridge_fnc_sendResponse;
};

private _id = _this select 0;

// all3DENEntities returns [objects, groups, triggers, waypoints, markers, layers, logic, effects]
private _allObjects = all3DENEntities select 0;
private _count = count _allObjects;

if (_count == 0) exitWith {
    [_id, [["ok", true], ["message", "Nothing to clear"], ["removed", 0]]] call ArmaDevBridge_bridge_fnc_sendResponse;
};

delete3DENEntities _allObjects;

diag_log format ["[ArmaDevBridge] clear_mission: removed %1 entities", _count];

[_id, [["ok", true], ["removed", _count]]] call ArmaDevBridge_bridge_fnc_sendResponse;
