/* Pure readback comparison: finite numbers tolerate float32 round-trip noise.
 * Strings/booleans/types, array lengths/order, nil slots, and differing integer
 * leaves remain exact. No numeric string conversion or angle wrapping is done.
 * Default abs tolerance 1e-5; relative 1e-6 (roughly eight float32 ULPs).
 * Position callers use a 1mm absolute floor for ATL/ASL cancellation noise.
 */
params ["_actual", "_expected", ["_absoluteTolerance", 1e-5], ["_relativeTolerance", 1e-6]];
if !(_absoluteTolerance isEqualType 0 && {_relativeTolerance isEqualType 0}
    && {finite _absoluteTolerance} && {finite _relativeTolerance}
    && {_absoluteTolerance >= 0} && {_relativeTolerance >= 0}) then {throw "Comparison tolerances must be finite nonnegative scalars";};
if (isNil "_actual" || {isNil "_expected"}) exitWith {
    isNil "_actual" && {isNil "_expected"}
};
private _compare = {
    params ["_actual", "_expected"];
    if (isNil "_actual" || {isNil "_expected"}) exitWith {
        isNil "_actual" && {isNil "_expected"}
    };
    if (typeName _actual isEqualTo "NaN" || {typeName _expected isEqualTo "NaN"}) exitWith {false};
    if !(_actual isEqualType _expected) exitWith {false};
    if (_actual isEqualType 0) exitWith {
        if (!finite _actual || {!finite _expected}) exitWith {false};
        if (_actual isEqualTo _expected) exitWith {true};
        // Array counts/indices are scalar in SQF too; do not forgive off-by-one
        // integer changes at large magnitudes where relative tolerance grows.
        if (floor _actual isEqualTo _actual && {floor _expected isEqualTo _expected}) exitWith {false};
        private _tolerance = _absoluteTolerance max (_relativeTolerance * (abs _actual max abs _expected));
        abs (_actual - _expected) <= _tolerance
    };
    if (_actual isEqualType []) exitWith {
        if !(count _actual isEqualTo count _expected) exitWith {false};
        private _matches = true;
        for "_i" from 0 to (count _actual - 1) do {
            private _actualNil = isNil {_actual select _i};
            private _expectedNil = isNil {_expected select _i};
            if (_actualNil || _expectedNil) then {
                if !(_actualNil && _expectedNil) then {_matches = false;};
            } else {
                if !([_actual select _i, _expected select _i] call _compare) then {_matches = false;};
            };
            if (!_matches) exitWith {};
        };
        _matches
    };
    _actual isEqualTo _expected
};
[_actual, _expected] call _compare
