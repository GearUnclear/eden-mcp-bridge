/* [entity, canonicalName] -> [ok, unwrappedValue, SQFType, error].
 * [] is unavailable, [[]] is an available empty-array value; do not conflate.
 * Multiple returned elements are retained as an array. Never fabricate success.
 */
params ["_entity", "_attribute"];
missionNamespace setVariable ["ArmaDevBridge_responseStage", format ["attribute:%1", _attribute]];
private _raw = _entity get3DENAttribute _attribute;
if (isNil "_raw") exitWith { [false, [], "NOTHING", "Engine returned nil"] };
if !(_raw isEqualType []) exitWith { [false, [], typeName _raw, "Engine returned an invalid attribute envelope"] };
if (count _raw isEqualTo 0) exitWith { [false, [], "NOTHING", "Attribute unavailable on this entity"] };
if (count _raw isEqualTo 1 && {isNil { _raw select 0 }}) exitWith { [false, [], "NOTHING", "Engine returned nil attribute value"] };
private _value = if (count _raw isEqualTo 1) then { _raw select 0 } else { _raw };
[true, _value, typeName _value, ""]
