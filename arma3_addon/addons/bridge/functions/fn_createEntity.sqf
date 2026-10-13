/* Create using explicit ATL/ASL/terrain/water placement; report engine position.
 * Group creation and group-owned waypoints need dedicated tools/parameters.
 */
params ["_id", "_params"];
private _typeIdx = _params findIf { (_x select 0) isEqualTo "entity_type" };
private _type = if (_typeIdx < 0) then {"Object"} else {_params select _typeIdx select 1};
if !(_type isEqualType "") then {throw "entity_type must be a string";};
private _3denType = switch (toLower _type) do {
    case "object"; case "unit"; case "vehicle": {"Object"};
    case "trigger": {"Trigger"}; case "logic": {"Logic"}; case "marker": {"Marker"};
    default {""};
};
if (_3denType isEqualTo "") then {throw "create_entity supports Object, Unit, Vehicle, Trigger, Logic and Marker; groups and waypoints require a group-aware tool";};
private _cnIdx = _params findIf { (_x select 0) isEqualTo "classname" };
private _classname = if (_cnIdx < 0) then {""} else {_params select _cnIdx select 1};
if !(_classname isEqualType "") then {throw "classname must be a string";};
if (_classname isEqualTo "" && {!(_3denType isEqualTo "Marker")}) then {throw "classname is required";};
private _posIdx = _params findIf { (_x select 0) isEqualTo "position" };
if (_posIdx < 0) then {throw "position is required";};
private _modeIdx = _params findIf { (_x select 0) isEqualTo "placement_mode" };
private _mode = if (_modeIdx < 0) then {"ATL"} else {_params select _modeIdx select 1};
([_params select _posIdx select 1,_mode] call ArmaDevBridge_bridge_fnc_placementPosition) params ["_posATL","_posASL","_placementMode"];
private _configRoot = switch (_3denType) do {case "Marker":{"CfgMarkers"}; case "Trigger":{"CfgNonAIVehicles"}; default {"CfgVehicles"};};
if (!(_classname isEqualTo "") && {!isClass (configFile >> _configRoot >> _classname)}) then {throw format ["Unknown %1 classname: %2",_3denType,_classname];};
private _sideIdx = _params findIf { (_x select 0) isEqualTo "side" };
if (_sideIdx >= 0 && {!((_params select _sideIdx select 1) isEqualTo "")}) then {
    private _requestedSide = _params select _sideIdx select 1;
    if !(_requestedSide isEqualType "") then {throw "side must be WEST, EAST, GUER or CIV";};
    _requestedSide = toUpper _requestedSide;
    if !(_requestedSide in ["WEST","EAST","GUER","CIV"]) then {throw "side must be WEST, EAST, GUER or CIV";};
    if !(_3denType isEqualTo "Object") then {throw "side is only supported for Object, Unit or Vehicle classes";};
    private _configSide = getNumber (configFile >> "CfgVehicles" >> _classname >> "side");
    private _classSide = switch (_configSide) do {case 0:{"EAST"};case 1:{"WEST"};case 2:{"GUER"};case 3:{"CIV"};default {"EMPTY"};};
    if !(_classSide isEqualTo _requestedSide) then {throw format ["Class %1 has side %2; choose a classname matching requested side %3",_classname,_classSide,_requestedSide];};
};
missionNamespace setVariable ["ArmaDevBridge_responseStage","entity_create"];
// Documented isEmpty avoids spawning crew only to delete them afterward.
private _entity = create3DENEntity [_3denType,_classname,_posATL,true];
if (isNil "_entity") then {throw format ["Failed to create %1 %2",_3denType,_classname];};
private _entityId = get3DENEntityID _entity;
if (_entityId < 0) then {throw format ["Engine did not return an editor entity ID for %1",_classname];};
([_entityId,[_3denType]] call ArmaDevBridge_bridge_fnc_resolveEntity) params ["_resolved","_resolvedId","_kind"];
// Marker creation can offset Z to terrain even when its position attribute
// accepts/returns ATL. Apply the requested persistent attribute explicitly;
// never reinterpret that readback as ASL or fabricate requested coordinates.
private _placementAccepted = true;
if (_kind isEqualTo "Marker") then {
    missionNamespace setVariable ["ArmaDevBridge_responseStage","created_marker_position_write"];
    _placementAccepted = (_resolved set3DENAttribute ["position",_posATL]) isEqualTo true;
};
([_resolved,"position"] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_available","_finalATL","_valueType","_readError"];
if (!_available || {!(_finalATL isEqualType [] && {count _finalATL isEqualTo 3})}) exitWith {
    [_id,[["ok",true],["entity_id",_entityId],["entity_kind",_kind],["classname",_classname],
        ["placement_mode",_placementMode],["engine_accepted",true],["verified",false],
        ["message",format ["Entity created; position readback unavailable: %1",_readError]]]]
        call ArmaDevBridge_bridge_fnc_sendResponse;
};
_finalATL = _finalATL apply {[_x,"final position"] call ArmaDevBridge_bridge_fnc_readNumber};
private _finalASL = [_finalATL select 0,_finalATL select 1,(_finalATL select 2) + getTerrainHeightASL _finalATL];
private _verified = _placementAccepted && {[_finalATL,_posATL,0.001] call ArmaDevBridge_bridge_fnc_attributeValuesMatch};
private _message = if (!_placementAccepted) then {"Entity created; engine rejected explicit marker position"} else {
    if (_verified) then {"Verified created position"} else {"Entity created; engine position differs from requested ATL position"}
};
[_id,[["ok",true],["entity_id",_entityId],["entity_kind",_kind],["classname",_classname],
    ["position_atl",_finalATL],["position_asl",_finalASL],["placement_mode",_placementMode],
    ["engine_accepted",true],["verified",_verified],["message",_message]]]
    call ArmaDevBridge_bridge_fnc_sendResponse;
