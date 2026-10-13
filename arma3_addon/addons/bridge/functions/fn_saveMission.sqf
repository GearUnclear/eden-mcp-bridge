/* MissionSave is an editor request, not proof that mission.sqm reached disk. */
params ["_id", "_params"];
if ((_params findIf { (_x select 0) isEqualTo "display_name" }) >= 0) then {
    throw "display_name updates are unsupported; edit the scenario title in Eden before saving";
};
missionNamespace setVariable ["ArmaDevBridge_saveAsObserved", false];
private _handler = add3DENEventHandler ["OnMissionSaveAs", {
    missionNamespace setVariable ["ArmaDevBridge_saveAsObserved", true];
}];
try {
    do3DENAction "MissionSave";
} catch {
    remove3DENEventHandler ["OnMissionSaveAs", _handler];
    missionNamespace setVariable ["ArmaDevBridge_saveAsObserved", nil];
    throw _exception;
};
private _saveAs = (missionNamespace getVariable ["ArmaDevBridge_saveAsObserved", false]) isEqualTo true;
remove3DENEventHandler ["OnMissionSaveAs", _handler];
missionNamespace setVariable ["ArmaDevBridge_saveAsObserved", nil];
[_id, [
    ["ok", false], ["status", if (_saveAs) then {"save_as_required"} else {"save_requested"}],
    ["save_requested", true], ["persistence_verified", false], ["manual_action_required", true],
    ["message", if (_saveAs) then {"Save As opened; choose a scenario name/location and complete the dialog. Disk persistence is not verified"} else {"Scenario save requested. If Save As opens, complete it; verify the saved scenario in Eden. Disk persistence is not verified"}]
]] call ArmaDevBridge_bridge_fnc_sendResponse;
