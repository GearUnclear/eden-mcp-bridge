/*
 * fn_init.sqf
 * Called via preInit = 1 during any mission start (introExp, etc.)
 *
 * Compiles all bridge functions and stores them in uiNamespace,
 * which persists across missions and into the Eden Editor session.
 *
 * The Cfg3DEN Init event then calls ArmaDevBridge_fnc_startBridge
 * from uiNamespace when the Eden Editor display is created.
 */

diag_log "[ArmaDevBridge] fn_init preInit running";

if (!hasInterface) exitWith {
    diag_log "[ArmaDevBridge] no interface - skipping";
};

// Compile and store all functions in uiNamespace (persists across missions)
private _base = "ArmaDevBridge\bridge\functions\";

uiNamespace setVariable ["ArmaDevBridge_fnc_toJSON",             compile preprocessFileLineNumbers (_base + "fn_toJSON.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_sendResponse",       compile preprocessFileLineNumbers (_base + "fn_sendResponse.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_attributeValuesMatch", compile preprocessFileLineNumbers (_base + "fn_attributeValuesMatch.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_processQueue",       compile preprocessFileLineNumbers (_base + "fn_processQueue.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_createEntity",       compile preprocessFileLineNumbers (_base + "fn_createEntity.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_deleteEntity",       compile preprocessFileLineNumbers (_base + "fn_deleteEntity.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_moveEntity",         compile preprocessFileLineNumbers (_base + "fn_moveEntity.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_groupEntities",      compile preprocessFileLineNumbers (_base + "fn_groupEntities.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_createWaypoint",     compile preprocessFileLineNumbers (_base + "fn_createWaypoint.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_describeGroup",      compile preprocessFileLineNumbers (_base + "fn_describeGroup.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_setAttribute",       compile preprocessFileLineNumbers (_base + "fn_setAttribute.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_getAttribute",       compile preprocessFileLineNumbers (_base + "fn_getAttribute.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_getSelected",        compile preprocessFileLineNumbers (_base + "fn_getSelected.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_listEntities",       compile preprocessFileLineNumbers (_base + "fn_listEntities.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_getAllObjects",       compile preprocessFileLineNumbers (_base + "fn_getAllObjects.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_getPlaceableObjects",    compile preprocessFileLineNumbers (_base + "fn_getPlaceableObjects.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_getPlaceableCategories", compile preprocessFileLineNumbers (_base + "fn_getPlaceableCategories.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_getMissionInfo",     compile preprocessFileLineNumbers (_base + "fn_getMissionInfo.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_saveMission",        compile preprocessFileLineNumbers (_base + "fn_saveMission.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_clearMission",         compile preprocessFileLineNumbers (_base + "fn_clearMission.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_getTerrainInfo",       compile preprocessFileLineNumbers (_base + "fn_getTerrainInfo.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_getRoads",             compile preprocessFileLineNumbers (_base + "fn_getRoads.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_getMapObjects",        compile preprocessFileLineNumbers (_base + "fn_getMapObjects.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_findLocation",         compile preprocessFileLineNumbers (_base + "fn_findLocation.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_updateBridgeStatus",   compile preprocessFileLineNumbers (_base + "fn_updateBridgeStatus.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_getAllAttributes",      compile preprocessFileLineNumbers (_base + "fn_getAllAttributes.sqf")];

uiNamespace setVariable ["ArmaDevBridge_fnc_readNumber", compile preprocessFileLineNumbers (_base + "fn_readNumber.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_resolveEntity", compile preprocessFileLineNumbers (_base + "fn_resolveEntity.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_resolveGroup", compile preprocessFileLineNumbers (_base + "fn_resolveGroup.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_editorConnections", compile preprocessFileLineNumbers (_base + "fn_editorConnections.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_writeAttribute", compile preprocessFileLineNumbers (_base + "fn_writeAttribute.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_attributeInfo", compile preprocessFileLineNumbers (_base + "fn_attributeInfo.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_readAttribute", compile preprocessFileLineNumbers (_base + "fn_readAttribute.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_placementPosition", compile preprocessFileLineNumbers (_base + "fn_placementPosition.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_getSupportedAttributes", compile preprocessFileLineNumbers (_base + "fn_getSupportedAttributes.sqf")];
uiNamespace setVariable ["ArmaDevBridge_fnc_undo", compile preprocessFileLineNumbers (_base + "fn_undo.sqf")];

// Mission handlers are lost/replaced across Preview. Editor lifecycle handlers
// (Cfg3DEN) survive it; use them to reinstall only our own polling handler.
uiNamespace setVariable ["ArmaDevBridge_fnc_stopBridge", {
    "arma3_mcp_bridge" callExtension "editor_paused";
    // Handler IDs can be reused by other addons when a mission is recreated.
    // Invalidate our generation instead; surviving handlers remove themselves
    // by their own _thisEventHandler, never by a potentially stale stored ID.
    uiNamespace setVariable ["ArmaDevBridge_generation", (uiNamespace getVariable ["ArmaDevBridge_generation", 0]) + 1];
    missionNamespace setVariable ["ArmaDevBridge_frameEH", -1];
    missionNamespace setVariable ["ArmaDevBridge_initialized", false];
    missionNamespace setVariable ["ArmaDevBridge_pendingResponse", []];
}];

// Schedule recovery after Eden has restored its world and displays. Coalesce
// overlapping Init/New/Load events so only one restart task is pending.
uiNamespace setVariable ["ArmaDevBridge_fnc_scheduleBridge", {
    private _previous = uiNamespace getVariable ["ArmaDevBridge_restartTask", scriptNull];
    if (!scriptDone _previous) then { terminate _previous; };
    private _task = [] spawn {
        uiSleep 0.1;
        if (is3DEN) then {
            [] call (uiNamespace getVariable ["ArmaDevBridge_fnc_startBridge", {}]);
        };
    };
    uiNamespace setVariable ["ArmaDevBridge_restartTask", _task];
}];

// Re-entrant: a stale initialization flag is never evidence that handlers exist.
uiNamespace setVariable ["ArmaDevBridge_fnc_startBridge", {
    if (!is3DEN) exitWith {};
    [] call (uiNamespace getVariable ["ArmaDevBridge_fnc_stopBridge", {}]);

    // Retrieve compiled functions from uiNamespace into missionNamespace
    ArmaDevBridge_bridge_fnc_toJSON             = uiNamespace getVariable "ArmaDevBridge_fnc_toJSON";
    ArmaDevBridge_bridge_fnc_sendResponse       = uiNamespace getVariable "ArmaDevBridge_fnc_sendResponse";
    ArmaDevBridge_bridge_fnc_attributeValuesMatch = uiNamespace getVariable "ArmaDevBridge_fnc_attributeValuesMatch";
    ArmaDevBridge_bridge_fnc_processQueue       = uiNamespace getVariable "ArmaDevBridge_fnc_processQueue";
    ArmaDevBridge_bridge_fnc_createEntity       = uiNamespace getVariable "ArmaDevBridge_fnc_createEntity";
    ArmaDevBridge_bridge_fnc_deleteEntity       = uiNamespace getVariable "ArmaDevBridge_fnc_deleteEntity";
    ArmaDevBridge_bridge_fnc_moveEntity         = uiNamespace getVariable "ArmaDevBridge_fnc_moveEntity";
    ArmaDevBridge_bridge_fnc_groupEntities      = uiNamespace getVariable "ArmaDevBridge_fnc_groupEntities";
    ArmaDevBridge_bridge_fnc_createWaypoint     = uiNamespace getVariable "ArmaDevBridge_fnc_createWaypoint";
    ArmaDevBridge_bridge_fnc_describeGroup      = uiNamespace getVariable "ArmaDevBridge_fnc_describeGroup";
    ArmaDevBridge_bridge_fnc_setAttribute       = uiNamespace getVariable "ArmaDevBridge_fnc_setAttribute";
    ArmaDevBridge_bridge_fnc_getAttribute       = uiNamespace getVariable "ArmaDevBridge_fnc_getAttribute";
    ArmaDevBridge_bridge_fnc_getSelected        = uiNamespace getVariable "ArmaDevBridge_fnc_getSelected";
    ArmaDevBridge_bridge_fnc_listEntities       = uiNamespace getVariable "ArmaDevBridge_fnc_listEntities";
    ArmaDevBridge_bridge_fnc_getAllObjects      = uiNamespace getVariable "ArmaDevBridge_fnc_getAllObjects";
    ArmaDevBridge_bridge_fnc_getPlaceableObjects    = uiNamespace getVariable "ArmaDevBridge_fnc_getPlaceableObjects";
    ArmaDevBridge_bridge_fnc_getPlaceableCategories = uiNamespace getVariable "ArmaDevBridge_fnc_getPlaceableCategories";
    ArmaDevBridge_bridge_fnc_getMissionInfo     = uiNamespace getVariable "ArmaDevBridge_fnc_getMissionInfo";
    ArmaDevBridge_bridge_fnc_saveMission        = uiNamespace getVariable "ArmaDevBridge_fnc_saveMission";
    ArmaDevBridge_bridge_fnc_clearMission         = uiNamespace getVariable "ArmaDevBridge_fnc_clearMission";
    ArmaDevBridge_bridge_fnc_getTerrainInfo       = uiNamespace getVariable "ArmaDevBridge_fnc_getTerrainInfo";
    ArmaDevBridge_bridge_fnc_getRoads             = uiNamespace getVariable "ArmaDevBridge_fnc_getRoads";
    ArmaDevBridge_bridge_fnc_getMapObjects        = uiNamespace getVariable "ArmaDevBridge_fnc_getMapObjects";
    ArmaDevBridge_bridge_fnc_findLocation         = uiNamespace getVariable "ArmaDevBridge_fnc_findLocation";
    ArmaDevBridge_bridge_fnc_updateBridgeStatus   = uiNamespace getVariable "ArmaDevBridge_fnc_updateBridgeStatus";
    ArmaDevBridge_bridge_fnc_getAllAttributes      = uiNamespace getVariable "ArmaDevBridge_fnc_getAllAttributes";

    ArmaDevBridge_bridge_fnc_readNumber = uiNamespace getVariable "ArmaDevBridge_fnc_readNumber";
    ArmaDevBridge_bridge_fnc_resolveEntity = uiNamespace getVariable "ArmaDevBridge_fnc_resolveEntity";
    ArmaDevBridge_bridge_fnc_resolveGroup = uiNamespace getVariable "ArmaDevBridge_fnc_resolveGroup";
    ArmaDevBridge_bridge_fnc_editorConnections = uiNamespace getVariable "ArmaDevBridge_fnc_editorConnections";
    ArmaDevBridge_bridge_fnc_writeAttribute = uiNamespace getVariable "ArmaDevBridge_fnc_writeAttribute";
    ArmaDevBridge_bridge_fnc_attributeInfo = uiNamespace getVariable "ArmaDevBridge_fnc_attributeInfo";
    ArmaDevBridge_bridge_fnc_readAttribute = uiNamespace getVariable "ArmaDevBridge_fnc_readAttribute";
    ArmaDevBridge_bridge_fnc_placementPosition = uiNamespace getVariable "ArmaDevBridge_fnc_placementPosition";
    ArmaDevBridge_bridge_fnc_getSupportedAttributes = uiNamespace getVariable "ArmaDevBridge_fnc_getSupportedAttributes";
    ArmaDevBridge_bridge_fnc_undo = uiNamespace getVariable "ArmaDevBridge_fnc_undo";

    diag_log "[ArmaDevBridge] Eden Editor detected - pinging DLL";

    // Use "arma3_mcp_bridge" — Arma 3 x64 auto-appends _x64 when loading the DLL
    private _ping = "arma3_mcp_bridge" callExtension "ping";
    diag_log format ["[ArmaDevBridge] ping response: %1", _ping];

    if (_ping != "{""ok"":true}") then {
        diag_log "[ArmaDevBridge] ERROR: DLL not found. Make sure arma3_mcp_bridge_x64.dll is in the Arma 3 root folder.";
        [] spawn {
            uiSleep 0.5;
            [false] call ArmaDevBridge_bridge_fnc_updateBridgeStatus;
            uiSleep 1.5;
            ["ArmaDevBridge: DLL not found. Put arma3_mcp_bridge_x64.dll in the Arma 3 root folder."] call BIS_fnc_3DENNotification;
        };
    } else {
        // One delivery path. Callback + polling previously executed every edit
        // twice; polling is sufficient and does not depend on callback survival.
        private _ehHandle = addMissionEventHandler ["EachFrame", {
            if ((_thisArgs select 0) != (uiNamespace getVariable ["ArmaDevBridge_generation", -1])) exitWith {
                removeMissionEventHandler ["EachFrame", _thisEventHandler];
            };
            if (is3DEN) then {
                [] call (uiNamespace getVariable ["ArmaDevBridge_fnc_processQueue", {}]);
            };
        }, [uiNamespace getVariable ["ArmaDevBridge_generation", 0]]];
        diag_log format ["[ArmaDevBridge] EachFrame handle: %1", _ehHandle];
        missionNamespace setVariable ["ArmaDevBridge_frameEH", _ehHandle];
        missionNamespace setVariable ["ArmaDevBridge_initialized", true];
        disableSerialization;
        private _display = findDisplay 313;
        if (!isNull _display && !(_display getVariable ["ArmaDevBridge_unloadInstalled", false])) then {
            _display displayAddEventHandler ["Unload", {
                [] call (uiNamespace getVariable ["ArmaDevBridge_fnc_stopBridge", {}]);
            }];
            _display setVariable ["ArmaDevBridge_unloadInstalled", true];
        };
        "arma3_mcp_bridge" callExtension "editor_ready";
        // Delay indicator creation: display 313 needs a frame or two to be fully ready
        [] spawn {
            uiSleep 0.5;
            [true] call ArmaDevBridge_bridge_fnc_updateBridgeStatus;
            diag_log "[ArmaDevBridge] updateBridgeStatus called";
            uiSleep 1.5;
            ["ArmaDevBridge: MCP bridge active."] call BIS_fnc_3DENNotification;
        };
    };
}];

diag_log "[ArmaDevBridge] functions stored in uiNamespace - ready for editor";
