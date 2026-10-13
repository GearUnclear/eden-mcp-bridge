/*
 * fn_updateBridgeStatus.sqf
 *
 * Updates the ADB_StatusIndicator control (IDC 8888) in the Eden Editor top bar.
 * The control is defined in config.cpp (RscDisplay3DEN::Controls::ADB_StatusIndicator).
 *
 * Parameters:
 *   _status  : BOOL   - true = connected/green, false = disconnected/red  (default: true)
 *   _isPulse : BOOL   - true = flash white briefly on data receive         (default: false)
 */

params [["_status", true, [true]], ["_isPulse", false, [false]]];

disableSerialization;
private _display = findDisplay 313;
if (isNull _display) exitWith {};

private _ctrl = _display displayCtrl 8888;
if (isNull _ctrl) then {
    _ctrl = _display ctrlCreate ["RscStructuredText", 8888];
    _ctrl ctrlSetPosition [(safezoneX + safezoneW) - 0.52, safezoneY, 0.35, 0.04];
    _ctrl ctrlSetBackgroundColor [0, 0, 0, 0.7];
    _ctrl ctrlCommit 0;
};

private _count = missionNamespace getVariable ["ArmaDevBridge_commandCount", 0];

private _color = if (_status) then { "#2ECC71" } else { "#E74C3C" };
private _text  = if (_status) then { "MCP BRIDGE ACTIVE" } else { "MCP BRIDGE DISCONNECTED" };

if (_isPulse) then {
    _color = "#FFFFFF";
    _text  = "[ RECEIVING DATA ]";
};

_ctrl ctrlSetStructuredText parseText format [
    "<t align='right' font='RobotoCondensedBold' color='%1'>%2 [Cmds: %3]</t>",
    _color, _text, _count
];
_ctrl ctrlSetBackgroundColor (if (_status) then { [0, 0, 0, 0.5] } else { [0.2, 0, 0, 0.8] });

if (_isPulse) then {
    [_ctrl, _count] spawn {
        uiSleep 0.1;
        (_this select 0) ctrlSetStructuredText parseText format [
            "<t align='right' font='RobotoCondensedBold' color='#2ECC71'>MCP BRIDGE ACTIVE [Cmds: %1]</t>",
            _this select 1
        ];
        (_this select 0) ctrlSetBackgroundColor [0, 0, 0, 0.5];
    };
};
