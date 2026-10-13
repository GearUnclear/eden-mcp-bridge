/* Native editor grouping: complete same-side on-foot infantry groups only.
 * The requested leader must already lead the destination. No runtime grouping
 * or explicit deletion; target settings/routes survive, source routes reject.
 */
params ["_id", "_params"];
private _idx = _params findIf { (_x select 0) isEqualTo "entity_ids" };
if (_idx < 0) then { throw "entity_ids is required"; };
private _rawIds = _params select _idx select 1;
if (!(_rawIds isEqualType []) || {count _rawIds < 2}) then { throw "entity_ids must contain at least two distinct infantry IDs"; };
private _members = [];
private _memberIds = [];
{
    private _resolved = [_x, ["Object"]] call ArmaDevBridge_bridge_fnc_resolveEntity;
    _resolved params ["_object", "_eid"];
    if (_eid in _memberIds) then { throw "entity_ids contains duplicate IDs"; };
    if (!(_object isKindOf "CAManBase") || {vehicle _object != _object}) then {
        throw format ["Entity %1 is not on-foot infantry; vehicles and mounted crew are unsupported", _eid];
    };
    _members pushBack _object;
    _memberIds pushBack _eid;
} forEach _rawIds;
private _leader = _members select 0;
_idx = _params findIf { (_x select 0) isEqualTo "leader" };
if (_idx >= 0) then {
    _leader = ([_params select _idx select 1, ["Object"]] call ArmaDevBridge_bridge_fnc_resolveEntity) select 0;
};
if (!(_leader in _members)) then { throw "leader must be one of entity_ids"; };
private _target = group _leader;
if (isNull _target || {get3DENEntityID _target < 0}) then { throw "Leader has no editor group"; };
if (leader _target != _leader) then {
    throw "Requested leader must already lead its editor group; choose that leader or change leadership in Eden first";
};
private _side = side _target;
private _groups = [];
{
    private _group = group _x;
    if (isNull _group || {get3DENEntityID _group < 0} || {side _group != _side}) then {
        throw "All infantry must belong to valid editor groups of the same side";
    };
    _groups pushBackUnique _group;
} forEach _members;
// Older engines return bare Group entities; newer versions use [kind,entity].
// Only unambiguous bare membership/waypoint types are normalised.
private _connections = {
    params ["_entity"];
    private _result = [];
    {
        private _link = _x;
        if (_link isEqualType [] && {count _link == 2} && {(_link select 0) isEqualType ""}) then {
            _result pushBack _link;
        } else {
            if ((_entity isEqualType objNull && {_link isEqualType grpNull} && {_link isEqualTo group _entity}) ||
                {_entity isEqualType grpNull && {_link isEqualType objNull} && {_link in units _entity}}) then {
                _result pushBack ["Group", _link];
            } else {
                if (_link isEqualType [] && {count _link == 2} && {(_link select 0) isEqualType grpNull} && {(_link select 1) isEqualType 0}) then {
                    _result pushBack ["Waypoint", _link];
                } else { throw "Unrecognised Eden connection format; grouping was not verified"; };
            };
        };
    } forEach get3DENConnections _entity;
    _result
};
// all3DENEntities: objects, groups, triggers, systems, waypoints, markers, layers, comments.
private _waypoints = all3DENEntities param [4, []];
private _targetRoutes = _waypoints select { (_x select 0) isEqualTo _target };
private _targetOtherLinks = ([_target] call _connections) select { (_x select 0) != "Group" };
{
    private _source = _x;
    if ((units _source) findIf { !(_x in _members) } >= 0) then {
        throw format ["Include every member of source group %1; partial-group merges are unsupported", get3DENEntityID _source];
    };
    if (_source != _target) then {
        if (_waypoints findIf { (_x select 0) isEqualTo _source } >= 0) then { throw "A source group has editor waypoints; remove or transfer its routes in Eden first"; };
        if (([_source] call _connections) findIf { (_x select 0) != "Group" } >= 0) then { throw "A source group has non-group connections; transfer them in Eden first"; };
    };
} forEach _groups;
{
    private _source = _x;
    private _nativeMembers = ([_source] call _connections) select { (_x select 0) isEqualTo "Group" };
    if (count _nativeMembers != count units _source ||
        {_nativeMembers findIf { !((_x select 1) in units _source) } >= 0}) then {
        throw "Source group editor membership disagrees with engine membership; inspect Eden before grouping";
    };
} forEach _groups;
{
    if (!( ["Group", group _x] in ([_x] call _connections) )) then {
        throw "Infantry editor group connection could not be verified before grouping";
    };
} forEach _members;
private _unitOtherLinks = _members apply { ([_x] call _connections) select { (_x select 0) != "Group" } };
private _unrelated = (all3DENEntities param [1, []]) select { !(_x in _groups) };
private _accepted = count _groups == 1;
if (!_accepted) then {
    collect3DENHistory {
        private _connectionResult = add3DENConnection ["Group", _members - [_leader], _target];
        // Some builds perform this action but return nil, despite the documented
        // Boolean result. Do not propagate nil through &&/if or emit JSON null.
        // A missing return still requires all native readback checks below;
        // explicit false or any unexpected non-Boolean return stays unconfirmed.
        _accepted = isNil "_connectionResult" || {_connectionResult isEqualTo true};
    };
};
// Native link readback in both directions plus runtime membership. A failure
// after dispatch may leave partial changes; never guess at rollback.
private _verified = (_accepted isEqualTo true) && {group _leader isEqualTo _target} && {leader _target isEqualTo _leader};
private _actualMembers = units _target;
_verified = _verified && {count _actualMembers == count _members} && {_actualMembers findIf { !(_x in _members) } < 0};
private _targetLinks = [_target] call _connections;
private _nativeMembers = _targetLinks select { (_x select 0) isEqualTo "Group" };
_verified = _verified && {count _nativeMembers == count _members} && {_nativeMembers findIf { !((_x select 1) in _members) } < 0};
{
    private _unitLinks = [_x] call _connections;
    _verified = _verified && {group _x isEqualTo _target} && {["Group", _target] in _unitLinks} && {["Group", _x] in _targetLinks};
    private _other = _unitLinks select { (_x select 0) != "Group" };
    private _beforeOther = _unitOtherLinks select _forEachIndex;
    _verified = _verified && {(_other - _beforeOther) isEqualTo []} && {(_beforeOther - _other) isEqualTo []};
} forEach _members;
private _afterOther = _targetLinks select { (_x select 0) != "Group" };
private _afterRoutes = (all3DENEntities param [4, []]) select { (_x select 0) isEqualTo _target };
_verified = _verified && {(_afterOther - _targetOtherLinks) isEqualTo []} && {(_targetOtherLinks - _afterOther) isEqualTo []};
_verified = _verified && {(_afterRoutes - _targetRoutes) isEqualTo []} && {(_targetRoutes - _afterRoutes) isEqualTo []};
_verified = _verified && {_unrelated findIf { get3DENEntityID _x < 0 } < 0};
// Keep the wire contract explicit even if a future native readback returns nil.
if (isNil "_verified") then { _verified = false; };
_verified = _verified isEqualTo true;
[_id, [
    ["ok", _verified], ["status", if (_verified) then {"editor_group_verified"} else {"grouping_unconfirmed"}],
    ["group_id", get3DENEntityID _target], ["leader_id", get3DENEntityID (leader _target)],
    ["count", count _actualMembers], ["member_ids", _actualMembers apply {get3DENEntityID _x}],
    ["editor_verified", _verified], ["persistence_verified", false],
    ["message", if (_verified) then {"Editor membership and leader verified; save/reload persistence is not verified"} else {"Native grouping was not fully verified; inspect Eden before retrying or undoing. Partial changes may remain"}]
]] call ArmaDevBridge_bridge_fnc_sendResponse;
