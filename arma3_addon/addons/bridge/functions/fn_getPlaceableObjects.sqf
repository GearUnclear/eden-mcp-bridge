/*
 * fn_getPlaceableObjects.sqf
 * Handles the "get_placeable_objects" MCP command.
 *
 * Reads the game config database (CfgVehicles) and returns all classes
 * that are placeable in the Eden Editor (scope >= 2), with their display
 * name, side, faction, vehicle class, and editor categories.
 *
 * This covers: units, vehicles, tanks, aircraft, ships, boats, static
 * weapons, buildings, signs, decorative objects, animals, and more.
 *
 * Results are CACHED in missionNamespace after the first build (can be
 * slow with many mods). Pass refresh=true to force a rebuild.
 *
 * Expected params:
 *   page              : NUMBER   0-based page index (default 0)
 *   page_size         : NUMBER   entries per page (default 30, max 100)
 *   filter_side       : STRING named CONFIG affiliation (default ALL).
 *                       Legacy NUMBER -1=ALL,0=NEUTRAL,1=EAST,2=WEST,3=GUER,4=CIV,5=AMBIENT.
 *   filter_vehicle_class : STRING  ""=all, e.g. "Air","Car","Tank","Man","Sea","StaticWeapon" (default "")
 *   filter_faction    : STRING   ""=all, faction class name e.g. "BLU_F" (default "")
 *   search            : STRING   ""=no filter, substring match on displayName or classname (default "")
 *   refresh           : BOOL     force cache rebuild (default false)
 *
 * Response fields per object:
 *   classname         : classname used with create3DENEntity
 *   display_name      : human-readable name shown in Eden Editor
 *   side              : named config affiliation; UNKNOWN for unsupported config codes.
 *   config_side       : raw config side number. Empty placement is independent.
 *   faction           : faction class name (e.g. "BLU_F", "OPF_F")
 *   vehicle_class     : "Air","Car","Tank","Man","Sea","StaticWeapon","Ship", etc.
 *   editor_category   : main Eden Editor category
 *   editor_subcategory: Eden Editor subcategory
 */

params ["_id", "_params"];

private _pageIdx     = _params findIf { (_x select 0) isEqualTo "page" };
private _page        = [if (_pageIdx < 0) then { 0 } else { _params select _pageIdx select 1 }, "page", true, 0, 16777215] call ArmaDevBridge_bridge_fnc_readNumber;

private _psIdx       = _params findIf { (_x select 0) isEqualTo "page_size" };
private _pageSize    = ([if (_psIdx < 0) then { 30 } else { _params select _psIdx select 1 }, "page_size", true, 1, 16777215] call ArmaDevBridge_bridge_fnc_readNumber) min 100;

private _fsIdx       = _params findIf { (_x select 0) isEqualTo "filter_side" };
private _filterSide  = if (_fsIdx < 0) then { "ALL" } else { _params select _fsIdx select 1 };
private _namedSides = ["ALL", "EAST", "WEST", "GUER", "CIV", "NEUTRAL", "ENEMY", "FRIENDLY", "LOGIC", "EMPTY", "AMBIENT", "UNKNOWN"];
if (_filterSide isEqualType "") then { _filterSide = toUpper _filterSide; };
if !(_filterSide in _namedSides) then {
    private _legacy = [_filterSide, "filter_side legacy integer", true, -1, 5] call ArmaDevBridge_bridge_fnc_readNumber;
    _filterSide = ["ALL", "NEUTRAL", "EAST", "WEST", "GUER", "CIV", "AMBIENT"] select (_legacy + 1);
};

private _fcIdx       = _params findIf { (_x select 0) isEqualTo "filter_vehicle_class" };
private _filterClass = if (_fcIdx < 0) then { "" } else { _params select _fcIdx select 1 };

private _ffIdx       = _params findIf { (_x select 0) isEqualTo "filter_faction" };
private _filterFact  = if (_ffIdx < 0) then { "" } else { _params select _ffIdx select 1 };

private _srIdx       = _params findIf { (_x select 0) isEqualTo "search" };
private _search      = if (_srIdx < 0) then { "" } else { _params select _srIdx select 1 };

private _refIdx      = _params findIf { (_x select 0) isEqualTo "refresh" };
private _refresh     = if (_refIdx < 0) then { false } else { _params select _refIdx select 1 };
if !(_refresh isEqualType true) then { throw "refresh must be boolean"; };
{ if !(_x isEqualType "") then { throw "search, filter_vehicle_class and filter_faction must be strings"; }; } forEach [_search, _filterClass, _filterFact];

// ---------------------------------------------------------------------------
// 1. Build or retrieve the full catalogue cache
// ---------------------------------------------------------------------------

private _cacheKey = "ArmaDevBridge_placeableCache";
private _cache = missionNamespace getVariable [_cacheKey, []];
private _schemaKey = "ArmaDevBridge_placeableCacheSchema";
private _schemaVersion = 2;

if (_refresh || count _cache == 0 || {(missionNamespace getVariable [_schemaKey, 0]) != _schemaVersion}) then {
    // Query all CfgVehicles with scope >= 2 (editorPlaceable)
    // Using the conditioned configClasses form for better performance
    private _allClasses = "getNumber (_x >> 'scope') >= 2" configClasses (configFile >> "CfgVehicles");

    private _built = [];
    {
        private _cls      = _x;
        private _name     = configName _cls;
        private _dispName = getText (_cls >> "displayName");
        private _sideNum  = if (isNumber (_cls >> "side")) then { getNumber (_cls >> "side") } else { 4 };
        private _faction  = getText (_cls >> "faction");
        private _vehClass = getText (_cls >> "vehicleClass");
        private _edCat    = getText (_cls >> "editorCategory");
        private _edSub    = getText (_cls >> "editorSubcategory");

        // Map side number to string
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

        // Skip classes with empty classname or display name (abstract/base classes)
        if !(_name isEqualTo "" || _dispName isEqualTo "") then {
            _built pushBack [
                _name,       // 0 classname
                _dispName,   // 1 display_name
                _sideNum,    // 2 side number (for filtering)
                _sideStr,    // 3 side string
                _faction,    // 4 faction
                _vehClass,   // 5 vehicle_class
                _edCat,      // 6 editor_category
                _edSub       // 7 editor_subcategory
            ];
        };
    } forEach _allClasses;

    missionNamespace setVariable [_cacheKey, _built];
    missionNamespace setVariable [_schemaKey, _schemaVersion];
    _cache = _built;
};

// ---------------------------------------------------------------------------
// 2. Apply filters
// ---------------------------------------------------------------------------

private _filtered = _cache;

// Side filter
if !(_filterSide isEqualTo "ALL") then {
    _filtered = _filtered select { (_x select 3) isEqualTo _filterSide };
};

// Vehicle class filter (case-insensitive contains)
if !(_filterClass isEqualTo "") then {
    private _lowerClass = toLower _filterClass;
    _filtered = _filtered select { toLower (_x select 5) == _lowerClass };
};

// Faction filter (case-insensitive contains)
if !(_filterFact isEqualTo "") then {
    private _lowerFact = toLower _filterFact;
    _filtered = _filtered select { toLower (_x select 4) == _lowerFact };
};

// Text search (substring match on classname or displayName)
if !(_search isEqualTo "") then {
    private _lowerSearch = toLower _search;
    _filtered = _filtered select {
        (toLower (_x select 0) find _lowerSearch) >= 0 ||
        (toLower (_x select 1) find _lowerSearch) >= 0
    };
};

// ---------------------------------------------------------------------------
// 3. Paginate
// ---------------------------------------------------------------------------

private _total      = count _filtered;
private _totalPages = if (_pageSize > 0) then { (ceil (_total / _pageSize)) max 1 } else { 1 };
private _start      = _page * _pageSize;
private _end        = (_start + _pageSize - 1) min (_total - 1);

private _list = [];

if (_total > 0 && _start < _total) then {
    for "_i" from _start to _end do {
        private _e = _filtered select _i;
        _list pushBack [
            ["classname",          _e select 0],
            ["display_name",       _e select 1],
            ["side",               _e select 3],
            ["config_side",        _e select 2],
            ["faction",            _e select 4],
            ["vehicle_class",      _e select 5],
            ["editor_category",    _e select 6],
            ["editor_subcategory", _e select 7]
        ];
    };
};

[
    _id,
    [
        ["ok",          true],
        ["objects",     _list],
        ["page",        _page],
        ["page_size",   _pageSize],
        ["total",       _total],
        ["total_pages", _totalPages],
        ["has_more",    (_page + 1 < _totalPages)],
        ["cache_size",  count _cache]
    ]
] call ArmaDevBridge_bridge_fnc_sendResponse;
