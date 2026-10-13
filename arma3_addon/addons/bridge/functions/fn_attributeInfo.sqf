/* Config-backed attribute metadata. No config expressions are executed here.
 * [entity, kind] -> [[property,type,configPath],...]
 * [entity, kind, requested] -> [canonicalProperty,type,configPath] or throws.
 * Entries are configured candidates; conditional applicability is checked by
 * readAttribute/the engine, rather than guessed from UI condition expressions.
 */
params ["_entity", "_kind", ["_requested", ""]];
private _schemas = [];
private _add = {
    params ["_cfg"];
    private _name = getText (_cfg >> "property");
    if (_name isEqualTo "") then { _name = getText (_cfg >> "data"); };
    if !(_name isEqualTo "") then {
        private _type = toUpper getText (_cfg >> "typeName");
        private _control = toLower getText (_cfg >> "control");
        if (_type isEqualTo "") then {
            _type = switch (_control) do {
                case "checkbox": { "BOOL" };
                case "checkboxnumber";
                case "slider": { "SCALAR" };
                case "editxyz";
                case "editxy": { "ARRAY" };
                default { "UNKNOWN" };
            };
        };
        if (_type isEqualTo "NUMBER") then { _type = "SCALAR"; };
        private _idx = _schemas findIf { toLower (_x select 0) isEqualTo toLower _name };
        private _entry = [_name, _type, str _cfg];
        if (_idx < 0) then { _schemas pushBack _entry; } else { _schemas set [_idx, _entry]; };
    };
};
{
    { [_x] call _add; } forEach (configProperties [_x >> "Attributes", "isClass _x", true]);
} forEach (configProperties [configFile >> "Cfg3DEN" >> _kind >> "AttributeCategories", "isClass _x", true]);

// Entity-specific mod attributes inherit through the vehicle's config class.
if (_kind in ["Object", "Logic"]) then {
    { [_x] call _add; } forEach (configProperties [configFile >> "CfgVehicles" >> typeOf _entity >> "Attributes", "isClass _x", true]);
};

// Stable engine properties, including ones not represented by a custom control.
// Discovery remains open to mod properties above; this is not a custom allowlist.
private _core = switch (_kind) do {
    case "Object": { [["Name","STRING"],["Init","STRING"],["position","ARRAY"],["rotation","ARRAY"],["description","STRING"]] };
    case "Logic": { [["Name","STRING"],["Init","STRING"],["position","ARRAY"],["rotation","ARRAY"]] };
    case "Trigger": { [["Name","STRING"],["position","ARRAY"],["rotation","ARRAY"]] };
    case "Marker": { [["Name","STRING"],["position","ARRAY"]] };
    case "Waypoint": { [["position","ARRAY"]] };
    case "Layer": { [["Name","STRING"]] };
    default { [] };
};
if (_kind isEqualTo "Object" && { _entity isKindOf "CAManBase" }) then {
    _core append [["ControlSP","BOOL"],["ControlMP","BOOL"],["skill","SCALAR"]];
};
{
    private _name = _x select 0;
    private _idx = _schemas findIf { toLower (_x select 0) isEqualTo toLower _name };
    if (_idx < 0) then { _schemas pushBack [_name, _x select 1, "engine"]; };
} forEach _core;
if (_requested isEqualTo "") exitWith { _schemas };
if !(_requested isEqualType "") then { throw "attribute must be a nonempty string"; };
private _canonical = switch (toLower _requested) do {
    case "isplayer": { "ControlSP" };
    case "isplayable": { "ControlMP" };
    case "variable": { "Name" };
    case "azimut": { "rotation" };
    default { _requested };
};
if (toLower _canonical in ["controlsp", "controlmp"] && { !(_kind isEqualTo "Object" && { _entity isKindOf "CAManBase" }) }) then {
    throw format ["Attribute %1 requires an infantry Object", _canonical];
};
private _idx = _schemas findIf { toLower (_x select 0) isEqualTo toLower _canonical };
if (_idx < 0) then {
    throw format ["Unsupported attribute '%1' for %2; use get_supported_attributes(entity_id) to discover configured properties", _requested, _kind];
};
_schemas select _idx
