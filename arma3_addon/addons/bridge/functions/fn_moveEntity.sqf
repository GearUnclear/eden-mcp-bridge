/* Move through Eden's persistent position attribute; verify actual placement. */
params ["_id","_params"];
private _eidIdx = _params findIf {(_x select 0) isEqualTo "entity_id"};
private _posIdx = _params findIf {(_x select 0) isEqualTo "position"};
if (_eidIdx < 0 || _posIdx < 0) then {throw "entity_id and position are required";};
([_params select _eidIdx select 1,["Object","Trigger","Logic","Waypoint","Marker"]] call ArmaDevBridge_bridge_fnc_resolveEntity) params ["_entity","_entityId","_kind"];
private _modeIdx = _params findIf {(_x select 0) isEqualTo "placement_mode"};
private _mode = if (_modeIdx < 0) then {"ATL"} else {_params select _modeIdx select 1};
([_params select _posIdx select 1,_mode] call ArmaDevBridge_bridge_fnc_placementPosition) params ["_posATL","_posASL","_placementMode"];
missionNamespace setVariable ["ArmaDevBridge_responseStage","position_write"];
private _accepted = _entity set3DENAttribute ["position",_posATL];
if (isNil "_accepted") then {_accepted = false;};
_accepted = _accepted isEqualTo true;
([_entity,"position"] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_available","_finalATL","_valueType","_readError"];
private _hasPosition = _available && {_finalATL isEqualType [] && {count _finalATL isEqualTo 3}};
private _verified = _accepted && {_hasPosition} && {[_finalATL,_posATL,0.001] call ArmaDevBridge_bridge_fnc_attributeValuesMatch};
private _message = if (!_accepted) then {"Engine rejected position write"} else {
    if (_verified) then {"Verified moved position"} else {
        if (_hasPosition) then {"Engine accepted move; actual position differs"} else {format ["Engine accepted move; readback unavailable: %1",_readError]}
    }
};
private _result = [["ok",_accepted],["entity_id",_entityId],["entity_kind",_kind],
    ["placement_mode",_placementMode],["engine_accepted",_accepted],["verified",_verified],
    ["message",_message],["error",if (_accepted) then {""} else {_message}]];
if (_hasPosition) then {
    _finalATL = _finalATL apply {[_x,"final position"] call ArmaDevBridge_bridge_fnc_readNumber};
    _result append [["position",_finalATL],["position_atl",_finalATL],
        ["position_asl",[_finalATL select 0,_finalATL select 1,(_finalATL select 2) + getTerrainHeightASL _finalATL]]];
};
[_id,_result] call ArmaDevBridge_bridge_fnc_sendResponse;
