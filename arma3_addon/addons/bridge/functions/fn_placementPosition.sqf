/* [position, mode] -> [ATL, ASL, normalizedMode]. Shared create/move contract.
 * Two coordinates imply z=0; snapping is explicit and uses z as surface offset.
 * Water means the sea surface at ASL=0; building/obstacle snapping is not done.
 */
params ["_position", ["_mode", "ATL"]];
if !(_position isEqualType [] && { count _position in [2,3] }) then {
    throw "position must contain exactly two or three finite numbers";
};
if !(_mode isEqualType "") then { throw "placement_mode must be ATL, ASL, terrain or water"; };
private _modeKey = toLower _mode;
if !(_modeKey in ["atl","asl","terrain","water"]) then { throw "placement_mode must be ATL, ASL, terrain or water"; };
private _xPos = [_position select 0, "position.x"] call ArmaDevBridge_bridge_fnc_readNumber;
private _yPos = [_position select 1, "position.y"] call ArmaDevBridge_bridge_fnc_readNumber;
private _zPos = [if (count _position isEqualTo 3) then { _position select 2 } else { 0 }, "position.z"] call ArmaDevBridge_bridge_fnc_readNumber;
private _terrain = getTerrainHeightASL [_xPos, _yPos];
if (_modeKey isEqualTo "water" && { !surfaceIsWater [_xPos, _yPos] }) then { throw "water placement requires a water surface at x/y"; };
private _zATL = switch (_modeKey) do {
    case "asl": { _zPos - _terrain };
    case "water": { _zPos - _terrain };
    default { _zPos };
};
private _atl = [_xPos, _yPos, _zATL];
[_atl, [_xPos, _yPos, _zATL + _terrain], switch (_modeKey) do { case "atl": {"ATL"}; case "asl": {"ASL"}; default {_modeKey}; }]
