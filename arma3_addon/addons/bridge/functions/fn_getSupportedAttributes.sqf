/* Discover configured properties for this resolved entity kind/class.
 * UI condition expressions are never compiled/evaluated by the bridge.
 */
params ["_id", "_params"];
private _eidIdx = _params findIf { (_x select 0) isEqualTo "entity_id" };
if (_eidIdx < 0) then { throw "entity_id is required"; };
([_params select _eidIdx select 1] call ArmaDevBridge_bridge_fnc_resolveEntity) params ["_entity", "_entityId", "_kind"];
missionNamespace setVariable ["ArmaDevBridge_responseStage", "attribute_discovery"];
private _schemas = [_entity, _kind] call ArmaDevBridge_bridge_fnc_attributeInfo;
if (count _schemas > 512) then { throw "Attribute discovery exceeds 512 configured properties"; };
private _attributes = _schemas apply {
    [["name",_x select 0],["value_type",_x select 1],["config_path",_x select 2]]
};
[_id, [["ok",true],["entity_id",_entityId],["entity_kind",_kind],
    ["classname",if (_kind in ["Object","Logic","Trigger"]) then {typeOf _entity} else {""}],
    ["attributes",_attributes],["count",count _attributes],
    ["scope","configured candidates; conditional applicability and UNKNOWN types require an engine read"],
    ["aliases",[["isPlayer","ControlSP"],["isPlayable","ControlMP"],["variable","Name"],["azimut","rotation yaw"]]]]]
    call ArmaDevBridge_bridge_fnc_sendResponse;
