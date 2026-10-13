/* Data-only JSON encoding: preserve repeated delimiters, controls, exponent
 * digits and nil array slots. Never compile incoming values. */
if (isNil { _this select 0 }) exitWith { "null" };
params ["_v"];
switch (typeName _v) do {
    case "BOOL": { if (_v) then { "true" } else { "false" } };
    case "SCALAR": {
        if (!finite _v) then { throw "serialization: non-finite number" };
        // Trimming trailing zeroes corrupts exponents: 1.25e+10 -> 1.25e+1.
        str _v
    };
    case "STRING": {
        private _parts = [];
        private _hex = "0123456789abcdef";
        {
            private _c = _x;
            _parts pushBack (switch (_c) do {
                case 34: { toString [92,34] };
                case 92: { toString [92,92] };
                default {
                    if (_c < 32 || {_c > 126}) then {
                        // toArray exposes UTF-16 units. Escape non-ASCII too so
                        // surrogate pairs survive without converting halves.
                        (toString [92]) + "u" + (_hex select [floor (_c / 4096),1]) +
                            (_hex select [(floor (_c / 256)) mod 16,1]) +
                            (_hex select [(floor (_c / 16)) mod 16,1]) + (_hex select [_c mod 16,1])
                    } else { toString [_c] }
                };
            });
        } forEach toArray _v;
        (toString [34]) + (_parts joinString "") + (toString [34])
    };
    case "ARRAY": {
        private _parts = [];
        for "_i" from 0 to (count _v - 1) do {
            _parts pushBack (if (isNil { _v select _i }) then { "null" } else {
                [_v select _i] call ArmaDevBridge_bridge_fnc_toJSON
            });
        };
        "[" + (_parts joinString ",") + "]"
    };
    default { throw format ["serialization: unsupported value type %1", typeName _v] };
};
