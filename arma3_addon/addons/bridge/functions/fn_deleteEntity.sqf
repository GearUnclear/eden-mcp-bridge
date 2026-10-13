/*
 * fn_deleteEntity.sqf
 * Handles the "delete_entity" MCP command.
 *
 * Expected params:
 *   entity_id : NUMBER  3DEN entity ID
 */

params ["_id", "_params"];

private _eidIdx   = _params findIf { (_x select 0) isEqualTo "entity_id" };
if (_eidIdx < 0) then { throw "entity_id is required"; };
// Layers retain their historical unsupported status in this deletion tool.
private _resolved = [_params select _eidIdx select 1, ["Object", "Group", "Trigger", "Waypoint", "Logic", "Marker"]] call ArmaDevBridge_bridge_fnc_resolveEntity;
_resolved params ["_entity", "_entityId", "_kind"];

delete3DENEntities [_entity];

[_id, [["ok", true], ["entity_id", _entityId], ["entity_kind", _kind]]] call ArmaDevBridge_bridge_fnc_sendResponse;
