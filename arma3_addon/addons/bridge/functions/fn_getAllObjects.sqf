/* Bounded object page. Unsupported optional fields are reported per entity;
 * invalid required positions/rotations omit a row and add an explicit error.
 * Source defects here are not proof of the historical timeout's root cause.
 */
params ["_id","_params"];
private _started = diag_tickTime;
private _pageIdx = _params findIf {(_x select 0) isEqualTo "page"};
private _psIdx = _params findIf {(_x select 0) isEqualTo "page_size"};
private _page = [if (_pageIdx < 0) then {0} else {_params select _pageIdx select 1},"page",true,0,16777215] call ArmaDevBridge_bridge_fnc_readNumber;
private _pageSize = [if (_psIdx < 0) then {50} else {_params select _psIdx select 1},"page_size",true,1,100] call ArmaDevBridge_bridge_fnc_readNumber;
missionNamespace setVariable ["ArmaDevBridge_responseStage","object_listing"];
private _objects = all3DENEntities select 0;
private _total = count _objects;
private _totalPages = ceil (_total / _pageSize);
private _start = _page * _pageSize;
private _end = (_start + _pageSize - 1) min (_total - 1);
private _list = [];
private _errors = [];
if (_start < _total) then {
    for "_i" from _start to _end do {
        private _obj = _objects select _i;
        private _eid = get3DENEntityID _obj;
        try {
            ([_eid,["Object"]] call ArmaDevBridge_bridge_fnc_resolveEntity) params ["_resolved","_resolvedId","_kind"];
            if !(_resolved isEqualTo _obj) then {throw "Object identity changed while reading page";};
            // Defaults on optional fields are always accompanied by page.errors.
            private _fetch = {
                params ["_attribute","_default"];
                private _result = [_obj,_attribute] call ArmaDevBridge_bridge_fnc_readAttribute;
                if (!(_result select 0) || {!((_result select 1) isEqualType _default)}) exitWith {
                    _errors pushBack [["entity_id",_eid],["attribute",_attribute],["stage","attribute_read"],
                        ["error",if (_result select 0) then {"Unexpected value type"} else {_result select 3}]];
                    _default
                };
                _result select 1
            };
            private _posResult = [_obj,"position"] call ArmaDevBridge_bridge_fnc_readAttribute;
            if !(_posResult select 0) then {throw format ["position: %1",_posResult select 3];};
            private _pos = _posResult select 1;
            if !(_pos isEqualType [] && {count _pos isEqualTo 3}) then {throw "position must be [x,y,z]";};
            _pos = _pos apply {[_x,"object position"] call ArmaDevBridge_bridge_fnc_readNumber};
            private _rotationResult = [_obj,"rotation"] call ArmaDevBridge_bridge_fnc_readAttribute;
            if !(_rotationResult select 0) then {throw format ["rotation: %1",_rotationResult select 3];};
            private _rotation = _rotationResult select 1;
            if !(_rotation isEqualType [] && {count _rotation isEqualTo 3}) then {throw "rotation must be [pitch,roll,yaw]";};
            private _yaw = [_rotation select 2,"rotation.yaw"] call ArmaDevBridge_bridge_fnc_readNumber;
            private _dir = ((_yaw % 360) + 360) % 360;
            private _grp = group _obj;
            private _groupId = if (isNull _grp) then {-1} else {get3DENEntityID _grp};
            private _sideStr = switch (side _obj) do {case west:{"WEST"};case east:{"EAST"};case resistance:{"GUER"};case civilian:{"CIV"};default {"UNKNOWN"};};
            private _isMan = _obj isKindOf "CAManBase";
            private _isPlayable = false;
            private _isPlayer = false;
            private _skill = -1;
            if (_isMan) then {
                _isPlayable = ["ControlMP",false] call _fetch;
                _isPlayer = ["ControlSP",false] call _fetch;
                _skill = ["skill",-1] call _fetch;
                _skill = [_skill,"skill"] call ArmaDevBridge_bridge_fnc_readNumber;
            };
            private _desc = ["description",""] call _fetch;
            private _name = ["Name",""] call _fetch;
            private _init = ["Init",""] call _fetch;
            _list pushBack [["entity_id",_eid],["classname",typeOf _obj],
                ["position",_pos],["position_asl",[_pos select 0,_pos select 1,(_pos select 2) + getTerrainHeightASL _pos]],
                ["direction",_dir],["side",_sideStr],["group_id",_groupId],
                ["description",_desc],["variable",_name],["init",_init],
                ["is_playable",_isPlayable],["is_player",_isPlayer],
                ["is_leader",!isNull _grp && {_obj isEqualTo leader _grp}],["skill",_skill]];
        } catch {
            _errors pushBack [["entity_id",_eid],["stage",missionNamespace getVariable ["ArmaDevBridge_responseStage","object_read"]],["error",_exception]];
        };
    };
};
missionNamespace setVariable ["ArmaDevBridge_responseStage","object_page_completed"];
[_id,[["ok",true],["objects",_list],["page",_page],["page_size",_pageSize],
    ["total",_total],["total_pages",_totalPages],["has_more",_page + 1 < _totalPages],
    ["errors",_errors],["diagnostics",[["stage","object_page_completed"],
        ["handler_ms",(diag_tickTime - _started) * 1000],["returned",count _list],["error_count",count _errors]]]]]
    call ArmaDevBridge_bridge_fnc_sendResponse;
