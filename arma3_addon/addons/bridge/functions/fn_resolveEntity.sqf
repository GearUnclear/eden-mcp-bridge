/* Validate the ID before resolving, then verify native identity. */
params ["_raw", ["_allowedKinds", []]];
private _id = [_raw, "entity_id", true, 0, 16777215] call ArmaDevBridge_bridge_fnc_readNumber;
private _entity = get3DENEntity _id;
private _kind = "";
// Official array order: Object, Group, Trigger, Logic, Waypoint, Marker,
// Layer, Comment. Native type plus bucket membership identifies custom classes
// too, without assuming trigger or module class ancestry.
private _all = all3DENEntities;
if (_entity isEqualType objNull) then {
    if !(isNull _entity) then {
        {
            _x params ["_index", "_bucketKind"];
            if (count _all > _index && {_entity in (_all select _index)}) then { _kind = _bucketKind; };
        } forEach [[0, "Object"], [2, "Trigger"], [3, "Logic"]];
    };
};
if (_entity isEqualType grpNull && {!isNull _entity} && {count _all > 1} && {_entity in (_all select 1)}) then { _kind = "Group"; };
if (_entity isEqualType []) then {
    if (count _entity == 2 && {(_entity select 0) isEqualType grpNull} && {!isNull (_entity select 0)} && {count _all > 4} && {_entity in (_all select 4)}) then {
        _kind = "Waypoint";
    };
};
if (_entity isEqualType "" && {!(_entity isEqualTo "")} && {count _all > 5} && {_entity in (_all select 5)}) then { _kind = "Marker"; };
// Layer and Comment both resolve as scalar IDs. Only classify a scalar as a
// layer when Eden's layer list proves its kind; never accept -1 or Comment IDs.
if (_entity isEqualType 0 && {_entity == _id}) then {
    if (count _all > 6 && {_id in (_all select 6)}) then { _kind = "Layer"; };
};
if (_kind isEqualTo "") then { throw format ["Entity %1 not found or unsupported kind", _id]; };
// Scalar layer identity is already proved by ID equality and layer membership.
if (_kind != "Layer" && {(get3DENEntityID _entity) != _id}) then { throw format ["Entity %1 identity mismatch", _id]; };
if (count _allowedKinds > 0 && {!(_kind in _allowedKinds)}) then { throw format ["Entity %1 is %2; expected %3", _id, _kind, _allowedKinds]; };
[_entity, _id, _kind]
