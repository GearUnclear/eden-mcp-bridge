/* Pure comparator regression cases: run in an SQF runtime, never mutates Eden.
 * _match must be the actual compiled fn_attributeValuesMatch.sqf implementation.
 * Example in an authorized editor debug console with the repaired addon loaded:
 * [ArmaDevBridge_bridge_fnc_attributeValuesMatch] call compile
 *     preprocessFileLineNumbers "C:\\path\\to\\tools\\test_attribute_values_match.sqf";
 * Throws on a failure and returns the count on success. Not run by Python tests.
 */
params ["_match"];
private _cases = [
    ["observed yaw and next float32 value",[0,0,123.50000762939453],[0,0,123.5],true],
    ["negative adjacent yaw",[0,0,-123.50000762939453],[0,0,-123.5],true],
    ["near-zero rotation noise",[0.000001,0,123.5],[0,0,123.5],true],
    ["material yaw change",[0,0,123.51],[0,0,123.5],false],
    ["no angle wrapping",[0,0,360],[0,0,0],false],
    ["large integer cargo count",[10000001],[10000000],false],
    ["number versus numeric string",[123.5],["123.5"],false],
    ["number versus boolean",[0],[false],false],
    ["boolean change",[true],[false],false],
    ["case-sensitive string",["Alpha"],["alpha"],false],
    ["nested mixed array preserves tag",[[123.50000762939453,"tag",true],[]],[[123.5,"tag",true],[]],true],
    ["nested mixed array changed tag",[[123.50000762939453,"TAG",true]],[[123.5,"tag",true]],false],
    ["array size mismatch",[0,0,123.5],[0,123.5],false],
    ["array nesting mismatch",[[123.5]],[123.5],false],
    ["nil slot unchanged",[nil,123.50000762939453],[nil,123.5],true],
    ["nil versus scalar",[nil,123.5],[0,123.5],false],
    ["empty arrays",[],[],true],
    ["nonfinite values are not verified",[1e39],[1e39],false],
    ["trigger ATL cancellation noise",[105,100,0.0000610352],[105,100,0],true,0.001],
    ["material placement delta",[105,100,0.01],[105,100,0],false,0.001],
    ["marker terrain offset is not float noise",[100,100,588.154],[100,100,0],false,0.001]
];
{
    _x params ["_label","_actual","_expected","_wanted",["_absTolerance",1e-5]];
    private _matched = [_actual,_expected,_absTolerance] call _match;
    if !(_matched isEqualTo _wanted) then {
        throw format ["attributeValuesMatch regression failed: %1 (expected %2, got %3)",_label,_wanted,_matched];
    };
} forEach _cases;
count _cases
