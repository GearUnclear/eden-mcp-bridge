/* Read one canonical property, with deliberate compatibility aliases. */
params ["_id", "_params"];
private _eidIdx = _params findIf { (_x select 0) isEqualTo "entity_id" };
private _attrIdx = _params findIf { (_x select 0) isEqualTo "attribute" };
if (_eidIdx < 0 || _attrIdx < 0) then { throw "entity_id and attribute are required"; };
private _attribute = _params select _attrIdx select 1;
if !(_attribute isEqualType "" && { !(_attribute isEqualTo "") }) then { throw "attribute must be a nonempty string"; };
([_params select _eidIdx select 1] call ArmaDevBridge_bridge_fnc_resolveEntity) params ["_entity", "_entityId", "_kind"];
([_entity, _kind, _attribute] call ArmaDevBridge_bridge_fnc_attributeInfo) params ["_canonical", "_expected", "_configPath"];
([_entity, _canonical] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_available", "_value", "_valueType", "_error"];
if (!_available) then { throw format ["Cannot read %1 on %2 %3: %4", _canonical, _kind, _entityId, _error]; };
// Legacy azimut represents yaw; rotation retains pitch/roll/yaw as an array.
if (toLower _attribute isEqualTo "azimut") then {
    if !(_value isEqualType [] && { count _value isEqualTo 3 }) then { throw "rotation did not return [pitch,roll,yaw]"; };
    _value = _value select 2;
};
[_id, [["ok",true],["entity_id",_entityId],["entity_kind",_kind],
    ["classname",if (_kind in ["Object","Logic","Trigger"]) then {typeOf _entity} else {""}],
    ["attribute",_attribute],["canonical_attribute",_canonical],["value",_value]]]
    call ArmaDevBridge_bridge_fnc_sendResponse;
