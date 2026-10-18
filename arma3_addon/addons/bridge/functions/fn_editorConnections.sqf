/* [entity] -> [[kind, target],...] native Eden connections (shared by grouping
 * and group reads). Older engines return bare Group entities; newer versions
 * use [kind,entity]. Only unambiguous bare membership/waypoint types are
 * normalised; anything else throws instead of guessing.
 */
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
