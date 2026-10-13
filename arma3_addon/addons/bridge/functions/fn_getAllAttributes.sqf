/* Read configured attributes individually; no 2.18-only native bulk command.
 * Preserve false, zero, empty strings, arrays and explicit null values.
 */
params ["_id", "_params"];
private _eidIdx = _params findIf { (_x select 0) isEqualTo "entity_id" };
if (_eidIdx < 0) then { throw "entity_id is required"; };
([_params select _eidIdx select 1] call ArmaDevBridge_bridge_fnc_resolveEntity) params ["_entity", "_entityId", "_kind"];
missionNamespace setVariable ["ArmaDevBridge_responseStage", "attribute_discovery"];
private _schemas = [_entity, _kind] call ArmaDevBridge_bridge_fnc_attributeInfo;
if (count _schemas > 512) then { throw "More than 512 configured attributes; use focused get_attribute reads with known property names"; };
private _attrs = [];
private _errors = [];
{
    _x params ["_name", "_expected", "_configPath"];
    try {
        ([_entity, _name] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_available", "_value", "_valueType", "_error"];
        if (_available) then { _attrs pushBack [_name, _value]; } else {
            _errors pushBack [["attribute",_name],["error",_error]];
        };
    } catch { _errors pushBack [["attribute",_name],["error",_exception]]; };
} forEach _schemas;
[_id, [["ok",true],["entity_id",_entityId],["entity_kind",_kind],
    ["classname",if (_kind in ["Object","Logic","Trigger"]) then {typeOf _entity} else {""}],
    ["count",count _attrs],["attributes",_attrs],["errors",_errors],
    ["partial",count _errors > 0],["discovery_source","Cfg3DEN and entity-specific config; conditional candidates checked by engine"]]]
    call ArmaDevBridge_bridge_fnc_sendResponse;
