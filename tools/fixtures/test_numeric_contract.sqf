/* Deferred engine fixture. Authored offline; never executed by Python tests.
 * Requires the updated registered readNumber helper. No entity writes or pipe I/O.
 */
private _acceptedIDs = [
    [0,0], [1,1], [1.0,1], [16777215,16777215],
    ["0",0], ["1",1], ["001",1], ["+1",1], ["1.0",1],
    [".1e1",1], ["1e0",1], ["10e-1",1], ["1.6777215e7",16777215]
];
{
    _x params ["_raw", "_expected"];
    private _actual = [_raw, "entity_id", true, 0, 16777215] call ArmaDevBridge_bridge_fnc_readNumber;
    if (_actual != _expected) then { throw format ["Expected %1 from %2; got %3", _expected, _raw, _actual]; };
} forEach _acceptedIDs;
private _rejectedIDs = [
    true, false, [], -1, 16777216, 1.5,
    "", " ", " 1", "1 ", "abc", "1abc", "0x10", "true",
    "1+2", "[1]", "1;call code", ".", "+", "1e", "1e+", "1e-",
    "NaN", "Inf", "1e100", "-1", "16777216", "1.5", "1.000000001",
    "-1e-99", "16777215.00000001"
];
{
    private _rejected = false;
    try { [_x, "entity_id", true, 0, 16777215] call ArmaDevBridge_bridge_fnc_readNumber; }
    catch { _rejected = true; };
    if (!_rejected) then { throw format ["Invalid ID accepted: %1", _x]; };
} forEach _rejectedIDs;
private _coordinates = [["-1.25",-1.25], ["1e3",1000], ["1E-3",0.001], [".5",0.5], ["1.",1]];
{
    _x params ["_raw", "_expected"];
    private _actual = [_raw, "position[0]"] call ArmaDevBridge_bridge_fnc_readNumber;
    if (abs (_actual - _expected) > 0.00001) then { throw format ["Coordinate %1 parsed as %2", _raw, _actual]; };
} forEach _coordinates;
format ["Numeric contract fixture passed %1 cases", count _acceptedIDs + count _rejectedIDs + count _coordinates]
