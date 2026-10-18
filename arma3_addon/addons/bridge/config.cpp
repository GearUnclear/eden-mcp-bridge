class CfgPatches {
    class ArmaDevBridge_bridge {
        name = "Eden MCP Bridge";
        units[] = {};
        weapons[] = {};
        requiredVersion = 2.04;          // mission EH arguments (_thisArgs)
        requiredAddons[] = {"3DEN"};     // REQUIRED: this is a 3DEN addon
        author = "diaverso and contributors; maintained by GearUnclear";
        url = "https://github.com/GearUnclear/eden-mcp-bridge";
        version = "1.2.0-rc.1";
        is3DENmod = 1;                   // REQUIRED: marks addon as Eden Editor tool
    };
};

class CfgFunctions {
    class ArmaDevBridge {
        tag = "ArmaDevBridge";
        class bridge {
            file = "ArmaDevBridge\bridge\functions";
            class init                  { preInit = 1; description = "Initialise MCP bridge"; };
            class processQueue          { description = "Process pending MCP commands (called per frame)"; };
            class createEntity          { description = "Handle create_entity command"; };
            class deleteEntity          { description = "Handle delete_entity command"; };
            class moveEntity            { description = "Handle move_entity command"; };
            class groupEntities         { description = "Handle group_entities command"; };
            class createWaypoint        { description = "Handle create_waypoint command"; };
            class describeGroup         { description = "Handle describe_group command"; };
            class setAttribute          { description = "Handle set_attribute command"; };
            class getAttribute          { description = "Handle get_attribute command"; };
            class getSelected           { description = "Handle get_selected command"; };
            class listEntities          { description = "Handle list_entities command"; };
            class getAllObjects          { description = "Handle get_all_objects command"; };
            class getPlaceableObjects   { description = "Handle get_placeable_objects command"; };
            class getPlaceableCategories{ description = "Handle get_placeable_categories command"; };
            class getMissionInfo        { description = "Handle get_mission_info command"; };
            class saveMission           { description = "Handle save_mission command"; };
            class clearMission          { description = "Handle clear_mission command"; };
            class getTerrainInfo        { description = "Handle get_terrain_info command"; };
            class getRoads              { description = "Handle get_roads command"; };
            class getMapObjects         { description = "Handle get_map_objects command"; };
            class findLocation          { description = "Handle find_location command"; };
            class getAllAttributes {};
            class readNumber {};
            class resolveEntity {};
            class resolveGroup {};
            class editorConnections {};
            class writeAttribute {};
            class attributeInfo {};
            class readAttribute {};
            class placementPosition {};
            class getSupportedAttributes {};
            class undo {};
            class toJSON                { description = "Serialise a SQF value to a JSON string"; };
            class sendResponse          { description = "Encode and send a response back via callExtension"; };
            class attributeValuesMatch  { description = "Compare readback values with numeric precision tolerance"; };
            class updateBridgeStatus    { description = "Update the Eden Editor status indicator control"; };
        };
    };
};

// --- Status indicator injected into Eden Editor's top bar ---
class RscDisplay3DEN {
    class Controls {
        class ADB_StatusIndicator {
            idc = 8888;
            type = 13;  // CT_STRUCTURED_TEXT
            style = 0;
            x = "safezoneX + safezoneW - 0.52";
            y = "safezoneY";
            w = 0.35;
            h = 0.04;
            shadow = 0;
            colorBackground[] = {0, 0, 0, 0.5};
            text = "MCP BRIDGE ACTIVE";
            class Attributes {
                align = "right";
                color = "#F1C40F";
                font = "RobotoCondensedBold";
                size = "1";
            };
        };
    };
};

// Config editor handlers survive Preview; mission EachFrame handlers do not.
class Cfg3DEN {
    class EventHandlers {
        class ArmaDevBridge_Bridge {
            Init = "diag_log '[ArmaDevBridge] Cfg3DEN Init fired'; [] call compile preprocessFileLineNumbers 'ArmaDevBridge\bridge\functions\fn_init.sqf'; [] call (uiNamespace getVariable ['ArmaDevBridge_fnc_scheduleBridge', {}]);";
            OnMissionNew = "[] call (uiNamespace getVariable ['ArmaDevBridge_fnc_scheduleBridge', {}]);";
            OnMissionLoad = "[] call (uiNamespace getVariable ['ArmaDevBridge_fnc_scheduleBridge', {}]);";
            OnMissionPreview = "[] call (uiNamespace getVariable ['ArmaDevBridge_fnc_stopBridge', {}]);";
            OnMissionPreviewEnd = "[] call (uiNamespace getVariable ['ArmaDevBridge_fnc_scheduleBridge', {}]);";
            OnTerrainNew = "[] call (uiNamespace getVariable ['ArmaDevBridge_fnc_scheduleBridge', {}]);";
        };
    };
};
