/* Selection returns typed identities without applying Object-only commands to
 * groups, markers, waypoints or layers. */
params ["_id", "_params"];
private _typeIdx = _params findIf { (_x select 0) isEqualTo "entity_type" };
private _type = if (_typeIdx < 0) then {"Object"} else {_params select _typeIdx select 1};
if (_type in ["Unit","Vehicle"]) then {_type = "Object";};
if !(_type in ["Object","Group","Trigger","Logic","Waypoint","Marker","Layer"]) then {
    throw "Unsupported entity_type for selection";
};
private _selected = get3DENSelected _type;
private _list = [];
{
    private _eid = if (_type isEqualTo "Layer") then {_x} else {get3DENEntityID _x};
    ([_eid,[_type]] call ArmaDevBridge_bridge_fnc_resolveEntity) params ["_entity","_entityId","_kind"];
    private _classname = if (_entity isEqualType objNull) then {typeOf _entity} else {""};
    _list pushBack [["entity_id",_entityId],["entity_kind",_kind],["classname",_classname]];
} forEach _selected;
[_id,[["ok",true],["entities",_list]]] call ArmaDevBridge_bridge_fnc_sendResponse;
