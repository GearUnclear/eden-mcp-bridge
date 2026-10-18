/* Shared validated write with immediate readback (set_attribute and
 * create_entity name/azimuth). Validation errors throw before any write.
 * [entity, entityId, kind, attribute, value] ->
 *   [canonical, writtenValue, engineAccepted, readbackAvailable, effective,
 *    readbackMatches, unchangedValue, readError]
 * Callers decide how engine acceptance and readback combine into verification.
 */
params ["_entity", "_entityId", "_kind", "_attribute", "_requested"];
if !(_attribute isEqualType "" && { !(_attribute isEqualTo "") }) then { throw "attribute must be a nonempty string"; };
private _value = _requested;
([_entity, _kind, _attribute] call ArmaDevBridge_bridge_fnc_attributeInfo) params ["_canonical", "_expected", "_configPath"];
([_entity, _canonical] call ArmaDevBridge_bridge_fnc_readAttribute) params ["_beforeAvailable", "_before", "_beforeType", "_beforeError"];
if (!_beforeAvailable) then { throw format ["Cannot validate %1 on %2 %3: %4", _canonical, _kind, _entityId, _beforeError]; };
// Current engine type wins over UI control metadata (including mod controls).
if !(_beforeType isEqualTo "NOTHING") then { _expected = _beforeType; };
if (toLower _attribute isEqualTo "azimut") then {
    if !(_before isEqualType [] && {count _before isEqualTo 3}) then { throw "rotation must be [pitch,roll,yaw] to set azimut"; };
    private _yaw = [_value,"azimut"] call ArmaDevBridge_bridge_fnc_readNumber;
    _value = +_before;
    _value set [2, _yaw];
};
switch (_expected) do {
    case "SCALAR": { _value = [_value, _canonical] call ArmaDevBridge_bridge_fnc_readNumber; };
    case "BOOL": { if !(_value isEqualType true) then { throw format ["%1 requires a boolean",_canonical]; }; };
    case "STRING": { if !(_value isEqualType "") then { throw format ["%1 requires a string",_canonical]; }; };
    case "ARRAY": { if !(_value isEqualType []) then { throw format ["%1 requires an array",_canonical]; }; };
    default { throw format ["Cannot safely validate type %1 for %2",_expected,_canonical]; };
};
if (toLower _canonical in ["position","rotation"]) then {
    if !(_value isEqualType [] && {count _value isEqualTo 3}) then { throw format ["%1 requires three numbers",_canonical]; };
    _value = _value apply { [_x,_canonical] call ArmaDevBridge_bridge_fnc_readNumber };
};
if (toLower _canonical in ["skill","health","fuel","ammo"] && {_value isEqualType 0}) then {
    if (_value < 0 || _value > 1) then { throw format ["%1 must be in 0..1",_canonical]; };
};
missionNamespace setVariable ["ArmaDevBridge_responseStage", format ["attribute_write:%1",_canonical]];
private _accepted = _entity set3DENAttribute [_canonical, _value];
if (isNil "_accepted") then { _accepted = false; };
_accepted = _accepted isEqualTo true;
private _afterAvailable = false;
private _effective = [];
private _readError = "";
try {
    private _after = [_entity,_canonical] call ArmaDevBridge_bridge_fnc_readAttribute;
    _afterAvailable = _after select 0;
    _effective = _after select 1;
    _readError = _after select 3;
} catch { _readError = _exception; };
private _verificationTolerance = if (toLower _canonical isEqualTo "position") then {0.001} else {1e-5};
private _matches = _afterAvailable && {[_effective, _value, _verificationTolerance] call ArmaDevBridge_bridge_fnc_attributeValuesMatch};
private _unchanged = _afterAvailable && {[_before, _effective, _verificationTolerance] call ArmaDevBridge_bridge_fnc_attributeValuesMatch};
[_canonical, _value, _accepted, _afterAvailable, _effective, _matches, _unchanged, _readError]
