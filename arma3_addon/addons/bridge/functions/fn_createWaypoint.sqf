/* Data-only editor waypoint for one group. Parameters are an explicit
 * allowlist: script-bearing fields (statements, conditions, activation code)
 * are rejected, never applied. Each requested attribute is read back; any
 * mismatch deletes the waypoint. Classes and stored values follow 3den.pbo:
 * formation/speedMode save lowercase strings, while BIS export reads indices,
 * so an index is tried when the string is not stored; either form verifies.
 */
params ["_id", "_params"];
private _allowed = ["entity_id","position","placement_mode","waypoint_type","behaviour","combat_mode","speed","formation","completion_radius"];
{
    if !((_x select 0) in _allowed) then { throw format ["create_waypoint does not accept parameter %1; waypoint code fields are unsupported", _x select 0]; };
} forEach _params;
private _get = {
    params ["_key"];
    private _idx = _params findIf { (_x select 0) isEqualTo _key };
    if (_idx < 0) then { nil } else { _params select _idx select 1 }
};
private _types = [["MOVE","Move"],["SAD","SeekAndDestroy"],["DESTROY","Destroy"],["GETIN","GetIn"],["GETOUT","GetOut"],
    ["HOLD","Hold"],["GUARD","Guard"],["SENTRY","Sentry"],["LOITER","Loiter"],["CYCLE","Cycle"],["UNLOAD","Unload"],
    ["TR_UNLOAD","TransportUnload"],["LOAD","Load"],["DISMISS","Dismiss"],["SUPPORT","Support"],["JOIN","Join"],["LEADER","Leader"]];
private _behaviours = ["UNCHANGED","CARELESS","SAFE","AWARE","COMBAT","STEALTH"];
private _combatModes = ["NO CHANGE","BLUE","GREEN","WHITE","YELLOW","RED"];
private _speeds = ["UNCHANGED","LIMITED","NORMAL","FULL"];
private _speedSaved = ["unchanged","limited","normal","full"];
private _formations = ["NO CHANGE","WEDGE","VEE","LINE","COLUMN","FILE","STAG COLUMN","ECH LEFT","ECH RIGHT","DIAMOND"];
private _formationSaved = ["no change","wedge","vee","line","column","file","stag_column","ech_left","ech_right","diamond"];
// Exact, case-sensitive enum match; -1 when the optional key is absent.
private _enum = {
    params ["_key", "_values"];
    private _raw = [_key] call _get;
    if (isNil "_raw") exitWith { -1 };
    private _index = _values findIf { _x isEqualTo _raw };
    if (_index < 0) then { throw format ["%1 must be one of %2", _key, _values joinString ", "]; };
    _index
};
private _typeIdx = ["waypoint_type", _types apply { _x select 0 }] call _enum;
if (_typeIdx < 0) then { throw "waypoint_type is required"; };
(_types select _typeIdx) params ["_type", "_class"];
private _behaviourIdx = ["behaviour", _behaviours] call _enum;
private _combatIdx = ["combat_mode", _combatModes] call _enum;
private _speedIdx = ["speed", _speeds] call _enum;
private _formationIdx = ["formation", _formations] call _enum;
private _radiusRaw = ["completion_radius"] call _get;
private _hasRadius = !isNil "_radiusRaw";
private _radius = if (_hasRadius) then { [_radiusRaw, "completion_radius", false, 0] call ArmaDevBridge_bridge_fnc_readNumber } else { 0 };
private _positionRaw = ["position"] call _get;
if (isNil "_positionRaw") then { throw "position is required"; };
private _modeRaw = ["placement_mode"] call _get;
if (isNil "_modeRaw") then { _modeRaw = "ATL"; };
([_positionRaw, _modeRaw] call ArmaDevBridge_bridge_fnc_placementPosition) params ["_posATL", "_posASL", "_placementMode"];
private _entityRaw = ["entity_id"] call _get;
if (isNil "_entityRaw") then { throw "entity_id is required"; };
([_entityRaw] call ArmaDevBridge_bridge_fnc_resolveGroup) params ["_group", "_groupId"];

// [response key, Eden attribute, values to try in order, accepted readbacks, requested]
private _requests = [];
if (_behaviourIdx >= 0) then {
    private _value = _behaviours select _behaviourIdx;
    _requests pushBack ["behaviour", "behaviour", [_value], [_value], _value];
};
if (_combatIdx >= 0) then {
    private _value = _combatModes select _combatIdx;
    _requests pushBack ["combat_mode", "combatMode", [_value], [_value], _value];
};
if (_speedIdx >= 0) then {
    private _saved = _speedSaved select _speedIdx;
    _requests pushBack ["speed", "speedMode", [_saved, _speedIdx], [_saved, _speedIdx], _speeds select _speedIdx];
};
if (_formationIdx >= 0) then {
    private _saved = _formationSaved select _formationIdx;
    _requests pushBack ["formation", "formation", [_saved, _formationIdx], [_saved, _formationIdx], _formations select _formationIdx];
};
if (_hasRadius) then {
    _requests pushBack ["completion_radius", "completionRadius", [_radius], [_radius], _radius];
};

missionNamespace setVariable ["ArmaDevBridge_responseStage", "waypoint_create"];
private _waypoint = _group create3DENEntity ["Waypoint", _class, _posATL];
if (isNil "_waypoint" || {!(_waypoint isEqualType [])} || {count _waypoint != 2} || {!((_waypoint select 0) isEqualTo _group)}) then {
    throw format ["Engine did not create a %1 waypoint for group %2", _type, _groupId];
};
private _waypointId = get3DENEntityID _waypoint;
if (isNil "_waypointId") then { _waypointId = -1; };
if (_waypointId < 0) then {
    delete3DENEntities [_waypoint];
    throw format ["Engine did not return an editor ID for the %1 waypoint; it was deleted", _type];
};

private _attributes = [];
private _failure = "";
try {
    {
        _x params ["_key", "_attribute", "_candidates", "_acceptable", "_requested"];
        if (_failure isEqualTo "") then {
            missionNamespace setVariable ["ArmaDevBridge_responseStage", format ["waypoint_attribute:%1", _attribute]];
            private _accepted = false;
            private _available = false;
            private _effective = [];
            private _verified = false;
            private _readError = "";
            {
                if (!_verified) then {
                    private _set = _waypoint set3DENAttribute [_attribute, _x];
                    if (isNil "_set") then { _set = false; };
                    _accepted = _set isEqualTo true;
                    ([_waypoint, _attribute] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_readOk", "_readValue", "_readType", "_error"];
                    _available = _readOk;
                    _readError = _error;
                    if (_readOk) then {
                        _effective = _readValue;
                        // Readback is authoritative; a false return alone is not failure.
                        _verified = (_acceptable findIf { [_readValue, _x] call ArmaDevBridge_bridge_fnc_attributeValuesMatch }) >= 0;
                    };
                };
            } forEach _candidates;
            _attributes pushBack [["attribute", _key], ["canonical_attribute", _attribute], ["requested_value", _requested],
                if (_available) then { ["effective_value", _effective] } else { ["effective_value", nil] },
                ["engine_accepted", _accepted], ["verified", _verified]];
            if (!_verified) then {
                _failure = if (_available) then { format ["%1 readback did not match %2", _key, _requested] } else { format ["%1 readback unavailable: %2", _key, _readError] };
            };
        };
    } forEach _requests;
} catch {
    _failure = format ["%1", _exception];
};

private _result = [];
if !(_failure isEqualTo "") then {
    missionNamespace setVariable ["ArmaDevBridge_responseStage", "waypoint_rollback"];
    delete3DENEntities [_waypoint];
    private _found = get3DENEntity _waypointId;
    private _rolledBack = isNil "_found" || {_found isEqualTo -1};
    _result = [["ok", false], ["stage", "waypoint_rollback"],
        ["error", if (_rolledBack) then { format ["Waypoint removed: %1", _failure] } else { format ["%1; waypoint %2 could not be removed, inspect Eden", _failure, _waypointId] }],
        ["waypoint_id", _waypointId], ["group_id", _groupId], ["waypoint_type", _type],
        ["rolled_back", _rolledBack], ["attributes", _attributes]];
} else {
    _result = [["ok", true], ["waypoint_id", _waypointId], ["group_id", _groupId], ["entity_kind", "Waypoint"],
        ["waypoint_type", _type], ["waypoint_class", _class], ["placement_mode", _placementMode],
        ["engine_accepted", true], ["attributes", _attributes]];
    ([_waypoint, "position"] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_available", "_finalATL", "_valueType", "_readError"];
    if (!_available || {!(_finalATL isEqualType [] && {count _finalATL isEqualTo 3})}) then {
        _result append [["verified", false], ["message", format ["Waypoint created; position readback unavailable: %1", _readError]]];
    } else {
        _finalATL = _finalATL apply { [_x, "final position"] call ArmaDevBridge_bridge_fnc_readNumber };
        private _verified = [_finalATL, _posATL, 0.001] call ArmaDevBridge_bridge_fnc_attributeValuesMatch;
        _result append [["position_atl", _finalATL],
            ["position_asl", [_finalATL select 0, _finalATL select 1, (_finalATL select 2) + getTerrainHeightASL _finalATL]],
            ["verified", _verified],
            ["message", if (_verified) then { "Verified waypoint position and attributes" } else { "Waypoint attributes verified; engine position differs from requested ATL position" }]];
    };
};
[_id, _result] call ArmaDevBridge_bridge_fnc_sendResponse;
