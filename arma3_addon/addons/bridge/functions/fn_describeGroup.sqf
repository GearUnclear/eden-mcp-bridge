/* Read-only group summary from a group or member/vehicle ID. Members and
 * leader are engine state; editor_membership_verified compares them with
 * native Eden Group links. Waypoints follow runtime order: index 0 is normally
 * the implicit start waypoint (waypoint_id -1, runtime AGL position); editor
 * waypoints report their Eden ATL position attribute.
 */
params ["_id", "_params"];
private _eidIdx = _params findIf { (_x select 0) isEqualTo "entity_id" };
if (_eidIdx < 0) then { throw "entity_id is required"; };
([_params select _eidIdx select 1] call ArmaDevBridge_bridge_fnc_resolveGroup) params ["_group", "_groupId"];
missionNamespace setVariable ["ArmaDevBridge_responseStage", "group_read"];
private _errors = [];
private _side = switch (side _group) do { case west: {"WEST"}; case east: {"EAST"}; case resistance: {"GUER"}; case civilian: {"CIV"}; default {"UNKNOWN"}; };
private _leader = leader _group;
private _leaderId = if (isNull _leader) then { -1 } else { get3DENEntityID _leader };
private _units = units _group;
private _members = _units apply {
    private _unit = _x;
    private _unitId = get3DENEntityID _unit;
    private _variable = "";
    ([_unit, "Name"] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_nameAvailable", "_name", "_nameType", "_nameError"];
    if (_nameAvailable && {_name isEqualType ""}) then { _variable = _name; } else {
        _errors pushBack [["entity_id", _unitId], ["attribute", "Name"], ["stage", "attribute_read"],
            ["error", if (_nameAvailable) then {"Unexpected value type"} else {_nameError}]];
    };
    private _vehicle = vehicle _unit;
    private _vehicleId = -1;
    private _role = "";
    if !(_vehicle isEqualTo _unit) then {
        _vehicleId = get3DENEntityID _vehicle;
        private _seat = (fullCrew _vehicle) select { (_x select 0) isEqualTo _unit };
        if (count _seat > 0) then { _role = toLower ((_seat select 0) select 1); };
    };
    [["entity_id", _unitId], ["classname", typeOf _unit], ["variable", _variable], ["vehicle_id", _vehicleId], ["role", _role]]
};
missionNamespace setVariable ["ArmaDevBridge_responseStage", "group_links"];
private _membershipVerified = false;
try {
    private _native = ([_group] call ArmaDevBridge_bridge_fnc_editorConnections) select { (_x select 0) isEqualTo "Group" };
    _membershipVerified = count _native == count _units && {_native findIf { !((_x select 1) in _units) } < 0};
} catch {
    _errors pushBack [["entity_id", _groupId], ["stage", "group_links"], ["error", format ["%1", _exception]]];
};
missionNamespace setVariable ["ArmaDevBridge_responseStage", "group_waypoints"];
private _editorWaypoints = (all3DENEntities param [4, []]) select { (_x select 0) isEqualTo _group };
// In Eden the runtime list can be empty even when editor waypoints exist
// (observed live), so merge the Eden list in and order by index.
private _source = +(waypoints _group);
{ if !(_x in _source) then { _source pushBack _x; }; } forEach _editorWaypoints;
_source = [_source, [], { _x select 1 }, "ASCEND"] call BIS_fnc_sortBy;
private _waypoints = _source apply {
    private _waypoint = _x;
    private _waypointId = get3DENEntityID _waypoint;
    if (isNil "_waypointId") then { _waypointId = -1; };
    private _type = waypointType _waypoint;
    if (_type isEqualTo "" && {_waypointId >= 0}) then {
        ([_waypoint, "itemClass"] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_classAvailable", "_class"];
        if (_classAvailable && {_class isEqualType ""}) then {
            private _classes = ["move","seekanddestroy","destroy","getin","getout","hold","guard","sentry","loiter","cycle","unload","transportunload","load","dismiss","support","join","leader"];
            private _types = ["MOVE","SAD","DESTROY","GETIN","GETOUT","HOLD","GUARD","SENTRY","LOITER","CYCLE","UNLOAD","TR_UNLOAD","LOAD","DISMISS","SUPPORT","JOIN","LEADER"];
            private _at = _classes find (toLower _class);
            _type = if (_at >= 0) then { _types select _at } else { _class };
        };
    };
    if (_type isEqualTo "TR UNLOAD") then { _type = "TR_UNLOAD"; };
    private _position = waypointPosition _waypoint;
    if (_waypointId >= 0) then {
        ([_waypoint, "position"] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_posAvailable", "_editorPosition", "_posType", "_posError"];
        if (_posAvailable && {_editorPosition isEqualType []} && {count _editorPosition == 3}) then { _position = _editorPosition; } else {
            _errors pushBack [["entity_id", _waypointId], ["attribute", "position"], ["stage", "attribute_read"],
                ["error", if (_posAvailable) then {"Unexpected value type"} else {_posError}]];
        };
    };
    _position = _position apply { [_x, "waypoint position"] call ArmaDevBridge_bridge_fnc_readNumber };
    [["waypoint_id", _waypointId], ["index", _waypoint select 1], ["waypoint_type", _type], ["position", _position]]
};
if (({ ((_x select 0) select 1) >= 0 } count _waypoints) != count _editorWaypoints) then {
    _errors pushBack [["entity_id", _groupId], ["stage", "group_waypoints"],
        ["error", format ["Runtime waypoints list %1 editor waypoints; Eden has %2", { ((_x select 0) select 1) >= 0 } count _waypoints, count _editorWaypoints]]];
};
[_id, [["ok", true], ["group_id", _groupId], ["side", _side], ["leader_id", _leaderId],
    ["members", _members], ["waypoints", _waypoints], ["editor_membership_verified", _membershipVerified],
    ["errors", _errors]]] call ArmaDevBridge_bridge_fnc_sendResponse;
