/* Encode the full envelope. Bound responses independently of the extension's
 * DLL-to-engine output buffer, which is not the outgoing response limit. */
params ["_id", "_result"];
private _pending = missionNamespace getVariable ["ArmaDevBridge_pendingResponse", []];
private _command = if (count _pending > 1) then { _pending select 1 } else { "unknown" };
private _stage = missionNamespace getVariable ["ArmaDevBridge_responseStage", "response"];
private _payload = "";
try {
    _payload = [[_id, "respond", _result]] call ArmaDevBridge_bridge_fnc_toJSON;
} catch {
    _payload = [[_id, "respond", [["ok",false], ["error",str _exception],
        ["command",_command], ["stage","serialization"]]]] call ArmaDevBridge_bridge_fnc_toJSON;
};
// Four bytes per character conservatively bounds UTF-8, also if toArray exposes
// UTF-8 bytes. Oversized responses return a small actionable error.
if ((count toArray _payload) * 4 > 262144) then {
    _payload = [[_id, "respond", [["ok",false], ["error","response_too_large: reduce page_size or request one attribute"],
        ["command",_command], ["stage",_stage]]]] call ArmaDevBridge_bridge_fnc_toJSON;
};
private _delivery = "arma3_mcp_bridge" callExtension _payload;
if (count _pending > 0 && {(_pending select 0) isEqualTo _id}) then {
    missionNamespace setVariable ["ArmaDevBridge_pendingResponse", []];
};
diag_log format ["[ArmaDevBridge] response command=%1 stage=%2 chars=%3 delivery=%4", _command, _stage, count _payload, _delivery];
