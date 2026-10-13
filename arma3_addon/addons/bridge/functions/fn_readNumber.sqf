/* Strict full decimal/exponent parser. Never compile incoming input. */
params ["_raw", "_label", ["_integerOnly", false], ["_minimum", -1e30], ["_maximum", 1e30]];
private _value = _raw;
if (_raw isEqualType "") then {
    private _chars = toArray _raw;
    private _n = count _chars;
    private _i = 0;
    if (_n > 0 && {(_chars select 0) in [43,45]}) then { _i = 1; };
    private _digits = 0;
    private _mantissa = [];
    private _fractionDigits = 0;
    private _exponent = 0;
    while {_i < _n && {(_chars select _i) >= 48 && {(_chars select _i) <= 57}}} do {
        _mantissa pushBack (_chars select _i);
        _i = _i + 1; _digits = _digits + 1;
    };
    if (_i < _n && {(_chars select _i) == 46}) then {
        _i = _i + 1;
        while {_i < _n && {(_chars select _i) >= 48 && {(_chars select _i) <= 57}}} do {
            _mantissa pushBack (_chars select _i);
            _i = _i + 1; _digits = _digits + 1; _fractionDigits = _fractionDigits + 1;
        };
    };
    if (_digits == 0) then { throw format ["%1 must be a complete numeric value", _label]; };
    if (_i < _n && {(_chars select _i) in [69,101]}) then {
        _i = _i + 1;
        private _exponentValueStart = _i;
        if (_i < _n && {(_chars select _i) in [43,45]}) then { _i = _i + 1; };
        private _exponentStart = _i;
        while {_i < _n && {(_chars select _i) >= 48 && {(_chars select _i) <= 57}}} do { _i = _i + 1; };
        if (_i == _exponentStart) then { throw format ["%1 has an invalid exponent", _label]; };
        _exponent = parseNumber (_raw select [_exponentValueStart, _i - _exponentValueStart]);
        if !(finite _exponent) then { throw format ["%1 exponent is out of range", _label]; };
    };
    if (_i != _n) then { throw format ["%1 must be a complete numeric value", _label]; };
    // Validate exact decimal integrality BEFORE SQF single precision rounds it.
    // For example, "1.000000001" must never silently resolve entity 1.
    if (_integerOnly) then {
        private _fractionCount = (_fractionDigits - _exponent) max 0;
        private _fractionStart = ((count _mantissa) - _fractionCount) max 0;
        if ((_mantissa select [_fractionStart]) findIf { _x != 48 } >= 0) then {
            throw format ["%1 must be an integer", _label];
        };
    };
    if (_minimum >= 0 && {(_chars select 0) == 45} && {_mantissa findIf { _x != 48 } >= 0}) then {
        throw format ["%1 must be nonnegative", _label];
    };
    _value = parseNumber _raw;
};
if !(_value isEqualType 0) then { throw format ["%1 must be a number or numeric string", _label]; };
if !(finite _value) then { throw format ["%1 must be finite", _label]; };
if (_value < _minimum || {_value > _maximum}) then { throw format ["%1 must be in [%2,%3]", _label, _minimum, _maximum]; };
if (_integerOnly && {_value != floor _value}) then { throw format ["%1 must be an integer", _label]; };
_value
