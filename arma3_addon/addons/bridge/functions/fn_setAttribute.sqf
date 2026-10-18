/* Validate, capture engine acceptance, and immediately read the effective value.
 * An accepted but transformed/unreadable value is explicitly unverified.
 */
params ["_id", "_params"];
private _eidIdx = _params findIf { (_x select 0) isEqualTo "entity_id" };
private _attrIdx = _params findIf { (_x select 0) isEqualTo "attribute" };
private _valIdx = _params findIf { (_x select 0) isEqualTo "value" };
if (_eidIdx < 0 || _attrIdx < 0 || _valIdx < 0) then { throw "entity_id, attribute and value are required"; };
private _attribute = _params select _attrIdx select 1;
if !(_attribute isEqualType "" && { !(_attribute isEqualTo "") }) then { throw "attribute must be a nonempty string"; };
private _requested = _params select _valIdx select 1;
([_params select _eidIdx select 1] call ArmaDevBridge_bridge_fnc_resolveEntity) params ["_entity", "_entityId", "_kind"];
([_entity, _entityId, _kind, _attribute, _requested] call ArmaDevBridge_bridge_fnc_writeAttribute)
    params ["_canonical", "_value", "_accepted", "_afterAvailable", "_effective", "_matches", "_unchanged", "_readError"];
private _verified = _accepted && {_matches};
private _message = if (!_accepted) then {"Engine rejected attribute write"} else {
    if (_verified) then {if (_unchanged) then {"Verified unchanged value"} else {"Verified effective value"}} else {
        if (_afterAvailable) then {"Engine accepted write but effective value differs; inspect effective_value"} else {format ["Engine accepted write; readback unavailable: %1",_readError]}
    }
};
private _valuePair = if (_afterAvailable) then {["effective_value",_effective]} else {["effective_value",nil]};
[_id, [["ok",_accepted],["error",if (_accepted) then {""} else {_message}],
    ["message",_message],["entity_id",_entityId],["entity_kind",_kind],
    ["classname",if (_kind in ["Object","Logic","Trigger"]) then {typeOf _entity} else {""}],
    ["attribute",_attribute],["canonical_attribute",_canonical],
    ["requested_value",_requested],_valuePair,
    ["engine_accepted",_accepted],["verified",_verified]]]
    call ArmaDevBridge_bridge_fnc_sendResponse;
