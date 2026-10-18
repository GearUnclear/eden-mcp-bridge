/* Create using explicit ATL/ASL/terrain/water placement; report engine position.
 * Options: keep_crew (vehicle default crew), group_id (infantry joins an
 * existing editor group), name and azimuth (set_attribute's validated write).
 * Every option is validated before creation. A failed group/name/azimuth
 * readback deletes what this request created (never a pre-existing group).
 * Group creation and group-owned waypoints need dedicated tools.
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
private _sideName = {
    params ["_side"];
    switch (_side) do {case west:{"WEST"};case east:{"EAST"};case resistance:{"GUER"};case civilian:{"CIV"};default {"UNKNOWN"};}
};
private _classSide = if (_3denType isEqualTo "Object") then {
    switch (getNumber (configFile >> "CfgVehicles" >> _classname >> "side")) do {case 0:{"EAST"};case 1:{"WEST"};case 2:{"GUER"};case 3:{"CIV"};default {"EMPTY"};}
} else {"EMPTY"};
private _sideIdx = _params findIf { (_x select 0) isEqualTo "side" };
if (_sideIdx >= 0 && {!((_params select _sideIdx select 1) isEqualTo "")}) then {
    private _requestedSide = _params select _sideIdx select 1;
    if !(_requestedSide isEqualType "") then {throw "side must be WEST, EAST, GUER or CIV";};
    _requestedSide = toUpper _requestedSide;
    if !(_requestedSide in ["WEST","EAST","GUER","CIV"]) then {throw "side must be WEST, EAST, GUER or CIV";};
    if !(_3denType isEqualTo "Object") then {throw "side is only supported for Object, Unit or Vehicle classes";};
    if !(_classSide isEqualTo _requestedSide) then {throw format ["Class %1 has side %2; choose a classname matching requested side %3",_classname,_classSide,_requestedSide];};
};
private _isManClass = _3denType isEqualTo "Object" && {_classname isKindOf "CAManBase"};
private _kcIdx = _params findIf { (_x select 0) isEqualTo "keep_crew" };
private _keepCrew = if (_kcIdx < 0) then {false} else {_params select _kcIdx select 1};
if !(_keepCrew isEqualType true) then {throw "keep_crew must be a boolean";};
if (_keepCrew && {!(_3denType isEqualTo "Object") || {_isManClass}}) then {throw "keep_crew applies only to vehicle classes";};
// Existing groups are resolved before creation; an invalid target creates nothing.
private _targetGroup = grpNull;
private _gidIdx = _params findIf { (_x select 0) isEqualTo "group_id" };
if (_gidIdx >= 0) then {
    if (!_isManClass) then {throw format ["group_id requires an infantry (CAManBase) class; %1 is not one. Nothing was created",_classname];};
    ([_params select _gidIdx select 1] call ArmaDevBridge_bridge_fnc_resolveGroup) params ["_resolvedGroup","_resolvedGroupId"];
    private _groupSide = [side _resolvedGroup] call _sideName;
    if !(_classSide isEqualTo _groupSide) then {throw format ["Class %1 has side %2; group %3 is %4",_classname,_classSide,_resolvedGroupId,_groupSide];};
    _targetGroup = _resolvedGroup;
};
private _nameIdx = _params findIf { (_x select 0) isEqualTo "name" };
private _name = if (_nameIdx < 0) then {""} else {_params select _nameIdx select 1};
if (_nameIdx >= 0) then {
    // Identifier only: ^[A-Za-z_][A-Za-z0-9_]*$
    private _validName = _name isEqualType "" && {!(_name isEqualTo "")};
    if (_validName) then {
        {
            private _letter = (_x >= 65 && _x <= 90) || (_x >= 97 && _x <= 122) || _x == 95;
            private _digit = _x >= 48 && _x <= 57;
            if (!_letter && {_forEachIndex == 0 || {!_digit}}) then {_validName = false;};
        } forEach toArray _name;
    };
    if (!_validName) then {throw "name must match ^[A-Za-z_][A-Za-z0-9_]*$";};
};
private _azIdx = _params findIf { (_x select 0) isEqualTo "azimuth" };
private _azimuth = 0;
if (_azIdx >= 0) then {
    _azimuth = [_params select _azIdx select 1,"azimuth",false,0,360] call ArmaDevBridge_bridge_fnc_readNumber;
    if (_azimuth >= 360) then {throw "azimuth must be in [0,360)";};
};
if ((_nameIdx >= 0 || _azIdx >= 0) && {_3denType isEqualTo "Marker"}) then {throw "name and azimuth are supported for Object, Unit, Vehicle, Trigger and Logic";};
if (_nameIdx >= 0) then {
    // SQF string == is case-insensitive, like mission variable names.
    missionNamespace setVariable ["ArmaDevBridge_responseStage","name_uniqueness"];
    private _all = all3DENEntities;
    {
        {
            ([_x,"Name"] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_nameAvailable","_existingName"];
            if (_nameAvailable && {_existingName isEqualType ""} && {_existingName == _name}) then {
                throw format ["name %1 is already used by Eden entity %2 (%3); nothing was created",_name,get3DENEntityID _x,_existingName];
            };
        } forEach (_all param [_x, []]);
    } forEach [0,1,2,3,4];
};
private _groupsBefore = +(all3DENEntities param [1, []]);
missionNamespace setVariable ["ArmaDevBridge_responseStage","entity_create"];
// Documented isEmpty avoids spawning crew only to delete them afterward;
// keep_crew opts into the class's default crew.
private _entity = if (isNull _targetGroup) then {
    create3DENEntity [_3denType,_classname,_posATL,!_keepCrew]
} else {
    _targetGroup create3DENEntity ["Object",_classname,_posATL]
};
if (isNil "_entity") then {throw format ["Failed to create %1 %2",_3denType,_classname];};
private _entityId = get3DENEntityID _entity;
if (_entityId < 0) then {throw format ["Engine did not return an editor entity ID for %1",_classname];};
([_entityId,[_3denType]] call ArmaDevBridge_bridge_fnc_resolveEntity) params ["_resolved","_resolvedId","_kind"];
private _isVehicle = _kind isEqualTo "Object" && {!(_resolved isKindOf "CAManBase")};
// Safeguard for the empty default: never strip a man (he is his own crew).
private _strippedCrew = 0;
if (!_keepCrew && {_isVehicle} && {count crew _resolved > 0}) then {
    missionNamespace setVariable ["ArmaDevBridge_responseStage","empty_vehicle_crew_strip"];
    _strippedCrew = count crew _resolved;
    delete3DENEntities (crew _resolved);
    private _emptyNewGroups = (all3DENEntities param [1, []]) select {!(_x in _groupsBefore) && {units _x isEqualTo []}};
    if (count _emptyNewGroups > 0) then {delete3DENEntities _emptyNewGroups;};
};
private _exists = {
    params ["_eid"];
    private _found = get3DENEntity _eid;
    !(isNil "_found") && {!(_found isEqualTo -1)}
};
private _attributes = [];
private _failure = "";
if (!isNull _targetGroup && {!(group _resolved isEqualTo _targetGroup)}) then {
    _failure = format ["entity did not join group %1",get3DENEntityID _targetGroup];
};
{
    _x params ["_key","_attribute","_requested","_enabled"];
    if (_enabled && {_failure isEqualTo ""}) then {
        try {
            ([_resolved,_entityId,_kind,_attribute,_requested] call ArmaDevBridge_bridge_fnc_writeAttribute)
                params ["_canonical","_written","_accepted","_available","_effective","_matches"];
            // Readback is authoritative: a false engine return only fails
            // when the effective value also disagrees.
            _attributes pushBack [["attribute",_key],["canonical_attribute",_canonical],["requested_value",_requested],
                if (_available) then {["effective_value",_effective]} else {["effective_value",nil]},
                ["engine_accepted",_accepted],["verified",_matches]];
            if (!_matches) then {_failure = format ["%1 readback did not match the requested value",_key];};
        } catch {
            _failure = format ["%1: %2",_key,_exception];
        };
    };
} forEach [["name","Name",_name,_nameIdx >= 0],["azimuth","azimut",_azimuth,_azIdx >= 0]];
private _result = [];
if !(_failure isEqualTo "") then {
    missionNamespace setVariable ["ArmaDevBridge_responseStage","create_rollback"];
    private _createdObjects = [_resolved];
    if (_kind isEqualTo "Object") then {_createdObjects append ((crew _resolved) - [_resolved]);};
    private _createdIds = _createdObjects apply {get3DENEntityID _x};
    // Only groups that did not exist before this request; group_id targets survive.
    private _newGroups = (all3DENEntities param [1, []]) select {!(_x in _groupsBefore)};
    private _groupIds = _newGroups apply {get3DENEntityID _x};
    delete3DENEntities _createdObjects;
    private _leftGroups = _groupIds select {[_x] call _exists};
    if (count _leftGroups > 0) then {delete3DENEntities _leftGroups;};
    private _remaining = (_createdIds + _groupIds) select {[_x] call _exists};
    private _rolledBack = count _remaining == 0;
    private _error = if (_rolledBack) then {
        format ["create_entity failed after creation (%1); removed entities %2. Nothing remains",_failure,_createdIds + _groupIds]
    } else {
        format ["create_entity failed after creation (%1); rollback incomplete, entities %2 remain. Inspect Eden",_failure,_remaining]
    };
    _result = [["ok",false],["error",_error],["stage","create_rollback"],["entity_id",_entityId],["classname",_classname],
        ["rolled_back",_rolledBack],["remaining_ids",_remaining],["attributes",_attributes]];
} else {
    // Marker creation can offset Z to terrain even when its position attribute
    // accepts/returns ATL. Apply the requested persistent attribute explicitly;
    // never reinterpret that readback as ASL or fabricate requested coordinates.
    private _placementAccepted = true;
    if (_kind isEqualTo "Marker") then {
        missionNamespace setVariable ["ArmaDevBridge_responseStage","created_marker_position_write"];
        _placementAccepted = (_resolved set3DENAttribute ["position",_posATL]) isEqualTo true;
    };
    private _groupId = -1;
    if (_kind isEqualTo "Object") then {
        try { _groupId = ([_entityId] call ArmaDevBridge_bridge_fnc_resolveGroup) select 1; } catch { _groupId = -1; };
    };
    private _crew = [];
    if (_isVehicle) then {
        {
            _x params ["_unit","_role"];
            if (!isNull _unit) then {
                _crew pushBack [["entity_id",get3DENEntityID _unit],["classname",typeOf _unit],["role",toLower _role]];
            };
        } forEach (fullCrew _resolved);
    };
    _result = [["ok",true],["entity_id",_entityId],["entity_kind",_kind],["classname",_classname],
        ["placement_mode",_placementMode],["engine_accepted",true],["group_id",_groupId],
        ["crew",_crew],["attributes",_attributes]];
    ([_resolved,"position"] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_available","_finalATL","_valueType","_readError"];
    private _suffix = if (_strippedCrew > 0) then {format ["; removed %1 unrequested crew",_strippedCrew]} else {""};
    if (!_available || {!(_finalATL isEqualType [] && {count _finalATL isEqualTo 3})}) then {
        _result append [["verified",false],["message",format ["Entity created; position readback unavailable: %1%2",_readError,_suffix]]];
    } else {
        _finalATL = _finalATL apply {[_x,"final position"] call ArmaDevBridge_bridge_fnc_readNumber};
        private _finalASL = [_finalATL select 0,_finalATL select 1,(_finalATL select 2) + getTerrainHeightASL _finalATL];
        private _verified = _placementAccepted && {[_finalATL,_posATL,0.001] call ArmaDevBridge_bridge_fnc_attributeValuesMatch};
        private _message = if (!_placementAccepted) then {"Entity created; engine rejected explicit marker position"} else {
            if (_verified) then {"Verified created position"} else {"Entity created; engine position differs from requested ATL position"}
        };
        _result append [["position_atl",_finalATL],["position_asl",_finalASL],["verified",_verified],["message",_message + _suffix]];
    };
};
[_id,_result] call ArmaDevBridge_bridge_fnc_sendResponse;
