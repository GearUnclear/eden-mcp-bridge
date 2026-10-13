/* Undo operates on the editor global history, including manual user edits. */
params ["_id", "_params"];
missionNamespace setVariable ["ArmaDevBridge_undoObserved", false];
private _handler = add3DENEventHandler ["OnUndo", {
    missionNamespace setVariable ["ArmaDevBridge_undoObserved", true];
}];
try {
    do3DENAction "Undo";
} catch {
    remove3DENEventHandler ["OnUndo", _handler];
    missionNamespace setVariable ["ArmaDevBridge_undoObserved", nil];
    throw _exception;
};
private _observed = (missionNamespace getVariable ["ArmaDevBridge_undoObserved", false]) isEqualTo true;
remove3DENEventHandler ["OnUndo", _handler];
missionNamespace setVariable ["ArmaDevBridge_undoObserved", nil];
[_id, [
    ["ok", _observed], ["status", if (_observed) then {"undo_observed"} else {"undo_unconfirmed"}],
    ["undo_requested", true], ["undo_observed", _observed],
    ["action_scope", "editor_global"], ["action_identity", "unknown"],
    ["message", if (_observed) then {"Eden emitted OnUndo; inspect affected editor state. The reverted operation may include manual edits"} else {"Undo requested but no immediate OnUndo event was observed; history may be empty or unavailable. Inspect Eden before retrying"}]
]] call ArmaDevBridge_bridge_fnc_sendResponse;
