/* Resolve an editor group from a group ID or a member/vehicle ID.
 * Infantry -> its group; crewed vehicle -> effective commander's group, else
 * the first crew member's. Empty vehicles and other kinds throw.
 * [rawId] -> [group, groupId, sourceId, sourceKind]
 */
params ["_raw"];
([_raw, ["Object", "Group"]] call ArmaDevBridge_bridge_fnc_resolveEntity) params ["_source", "_sourceId", "_sourceKind"];
private _group = grpNull;
if (_sourceKind isEqualTo "Group") then {
    _group = _source;
} else {
    if (_source isKindOf "CAManBase") then {
        _group = group _source;
    } else {
        private _crew = crew _source;
        if (count _crew > 0) then {
            private _commander = effectiveCommander _source;
            _group = if (!isNull _commander && {_commander in _crew}) then { group _commander } else { group (_crew select 0) };
        };
    };
};
if (isNull _group) then { throw format ["Entity %1 is not a group and has no editor group (empty vehicle or object)", _sourceId]; };
private _groupId = get3DENEntityID _group;
if (isNil "_groupId") then { _groupId = -1; };
if (_groupId < 0 || {!(_group in (all3DENEntities param [1, []]))}) then {
    throw format ["Entity %1 does not belong to an editor group", _sourceId];
};
[_group, _groupId, _sourceId, _sourceKind]
