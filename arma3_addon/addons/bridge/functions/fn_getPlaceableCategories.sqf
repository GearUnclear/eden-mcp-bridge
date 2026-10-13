/*
 * fn_getPlaceableCategories.sqf
 * Handles the "get_placeable_categories" MCP command.
 *
 * Returns a summary of all available vehicle classes, factions, sides,
 * and editor categories found in the placeable-objects catalogue.
 *
 * Includes objects from ALL loaded mods — configFile is the fully merged
 * config that already contains every addon loaded at game startup.
 *
 * If the cache is empty this function builds it inline (same as
 * fn_getPlaceableObjects does). The first call may take a few seconds
 * on heavily modded installs; subsequent calls are instant.
 *
 * Expected params: none
 *
 * Response:
 *   vehicle_classes     : ARRAY of unique vehicle class strings  (Air, Car, Tank, Man, Sea, ...)
 *   factions            : ARRAY of unique faction class names     (BLU_F, OPF_F, IND_F, ...)
 *   sides               : ARRAY of unique side strings            (WEST, EAST, GUER, CIV, EMPTY)
 *   editor_categories   : ARRAY of unique editor category strings
 *   total_placeable     : NUMBER total placeable objects (vanilla + all mods)
 */

params ["_id", "_params"];

// ---------------------------------------------------------------------------
// 1. Ensure cache is populated
//    We build it here directly — never delegate to fn_getPlaceableObjects,
//    which would send a response with this same _id before we can.
// ---------------------------------------------------------------------------

private _cacheKey = "ArmaDevBridge_placeableCache";
private _cache = missionNamespace getVariable [_cacheKey, []];
private _schemaKey = "ArmaDevBridge_placeableCacheSchema";
private _schemaVersion = 2;

if (count _cache == 0 || {(missionNamespace getVariable [_schemaKey, 0]) != _schemaVersion}) then {
    // configFile is the fully merged game config (vanilla + all loaded mods).
    // "getNumber (_x >> 'scope') >= 2" = visible and placeable in Eden Editor.
    private _allClasses = "getNumber (_x >> 'scope') >= 2" configClasses (configFile >> "CfgVehicles");

    private _built = [];
    {
        private _cls      = _x;
        private _name     = configName _cls;
        private _dispName = getText (_cls >> "displayName");

        // Skip abstract base classes (no classname or no display name)
        if !(_name isEqualTo "" || _dispName isEqualTo "") then {
            private _sideNum = if (isNumber (_cls >> "side")) then { getNumber (_cls >> "side") } else { 4 };
            private _sideStr = switch (_sideNum) do {
                case -1: { "AMBIENT" };
                case 0: { "EAST" };
                case 1: { "WEST" };
                case 2: { "GUER" };
                case 3: { "CIV" };
                case 4: { "NEUTRAL" };
                case 5: { "ENEMY" };
                case 6: { "FRIENDLY" };
                case 7: { "LOGIC" };
                case 8: { "EMPTY" };
                case 9: { "AMBIENT" };
                default { "UNKNOWN" };
            };

            _built pushBack [
                _name,                              // 0 classname
                _dispName,                          // 1 display_name
                _sideNum,                           // 2 side number (for filtering)
                _sideStr,                           // 3 side string
                getText (_cls >> "faction"),         // 4 faction
                getText (_cls >> "vehicleClass"),    // 5 vehicle_class
                getText (_cls >> "editorCategory"),  // 6 editor_category
                getText (_cls >> "editorSubcategory") // 7 editor_subcategory
            ];
        };
    } forEach _allClasses;

    missionNamespace setVariable [_cacheKey, _built];
    missionNamespace setVariable [_schemaKey, _schemaVersion];
    _cache = _built;
};

// ---------------------------------------------------------------------------
// 2. Collect unique values across ALL entries (vanilla + mods)
// ---------------------------------------------------------------------------

private _vehicleClasses   = [];
private _factions         = [];
private _sides            = [];
private _editorCategories = [];

{
    private _vc   = _x select 5;
    private _fact = _x select 4;
    private _side = _x select 3;
    private _cat  = _x select 6;

    if (!(_vc   isEqualTo "") && !(_vc   in _vehicleClasses))    then { _vehicleClasses   pushBack _vc;   };
    if (!(_fact  isEqualTo "") && !(_fact  in _factions))         then { _factions          pushBack _fact; };
    if (!(_side  isEqualTo "") && !(_side  in _sides))            then { _sides             pushBack _side; };
    if (!(_cat   isEqualTo "") && !(_cat   in _editorCategories)) then { _editorCategories  pushBack _cat;  };
} forEach _cache;

_vehicleClasses   sort true;
_factions         sort true;
_sides            sort true;
_editorCategories sort true;

[
    _id,
    [
        ["ok",                true],
        ["vehicle_classes",   _vehicleClasses],
        ["factions",          _factions],
        ["sides",             _sides],
        ["editor_categories", _editorCategories],
        ["total_placeable",   count _cache]
    ]
] call ArmaDevBridge_bridge_fnc_sendResponse;
