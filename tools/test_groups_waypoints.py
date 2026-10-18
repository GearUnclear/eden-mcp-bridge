"""Offline crew/group/waypoint contract checks; no server, pipe, or SQF execution.

The real entity tool module is loaded with an inert server/decorator and canned
bridge replies. SQF checks are source invariants that keep Python and the
handlers in agreement; they do not prove Eden behavior (see docs/validation.md).
"""
import importlib.util
import json
from pathlib import Path
import re
import sys
import types
import typing
import unittest
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Real error type, but no operational win32 API: accidental pipe use fails.
inert = {name: types.ModuleType(name) for name in ("win32file", "win32pipe", "pywintypes")}
with patch.dict(sys.modules, inert):
    from mcp_server.bridge_client import BridgeCommandError
from mcp_server.models import (
    CreateEntityParams, CreateWaypointParams, DescribeGroupParams,
    WaypointBehaviour, WaypointCombatMode, WaypointFormation, WaypointSpeed, WaypointType,
)
from mcp_server.protocol import build_sqf_payload

FUNCTIONS = ROOT / "arma3_addon/addons/bridge/functions"
WAYPOINT_CLASSES = {
    "MOVE": "Move", "SAD": "SeekAndDestroy", "DESTROY": "Destroy", "GETIN": "GetIn", "GETOUT": "GetOut",
    "HOLD": "Hold", "GUARD": "Guard", "SENTRY": "Sentry", "LOITER": "Loiter", "CYCLE": "Cycle",
    "UNLOAD": "Unload", "TR_UNLOAD": "TransportUnload", "LOAD": "Load", "DISMISS": "Dismiss",
    "SUPPORT": "Support", "JOIN": "Join", "LEADER": "Leader",
}


def pairs(record):
    return [[key, value] for key, value in record.items()]


def source(name):
    return (FUNCTIONS / f"fn_{name}.sqf").read_text(encoding="utf-8-sig")


def sqf_strings(text):
    return re.findall(r'"((?:[^"]|"")*)"', text)


def sqf_list(text, variable):
    match = re.search(rf'private {variable} = \[([^\]]*)\];', text)
    assert match, variable
    return sqf_strings(match.group(1))


def unit(**changes):
    base = dict(entity_type="Unit", classname="B_Soldier_F", position=[1, 2])
    base.update(changes)
    return CreateEntityParams(**base)


def waypoint(**changes):
    base = dict(entity_id=45, position=[100, 200], waypoint_type="MOVE")
    base.update(changes)
    return CreateWaypointParams(**base)


class ModelValidationTests(unittest.TestCase):
    def test_create_options_reject_lossy_coercion(self):
        for bad in ("true", 1, "yes", None):
            with self.subTest(keep_crew=bad), self.assertRaises(ValidationError):
                unit(keep_crew=bad)
        for bad in (True, -1, 1.5, "1x", " 1", 16777216):
            with self.subTest(group_id=bad), self.assertRaises(ValidationError):
                unit(group_id=bad)
        self.assertEqual(unit(group_id="45").group_id, 45)
        self.assertIs(unit().keep_crew, False)

    def test_variable_names_are_identifiers_only(self):
        for bad in ("", "1abc", "a b", "x;y", 'x"y', "a-b", "abc\n", "\u00e9t\u00e9", "a.b", 7):
            with self.subTest(name=bad), self.assertRaises(ValidationError):
                unit(name=bad)
        for good in ("Alpha_A1", "_x", "a", "A9_"):
            self.assertEqual(unit(name=good).name, good)

    def test_azimuth_is_finite_and_half_open(self):
        for bad in (-1, 360, 360.0, "360", float("nan"), float("inf"), "nan", True, "90deg", "1e999", "-1e-99"):
            with self.subTest(azimuth=bad), self.assertRaises(ValidationError):
                unit(azimuth=bad)
        for good, expected in ((0, 0.0), ("359.5", 359.5), (90, 90.0)):
            value = unit(azimuth=good).azimuth
            self.assertEqual(value, expected)
            self.assertIsInstance(value, float)

    def test_waypoint_enums_are_exact(self):
        for name in typing.get_args(WaypointType):
            self.assertEqual(waypoint(waypoint_type=name).waypoint_type, name)
        bad = [{"waypoint_type": "move"}, {"waypoint_type": "TR UNLOAD"}, {"waypoint_type": "SCRIPTED"},
               {"waypoint_type": "MOVE;hint 1"}, {"behaviour": "safe"}, {"behaviour": "AGGRESSIVE"},
               {"combat_mode": "NO_CHANGE"}, {"combat_mode": "ORANGE"}, {"speed": "FAST"},
               {"formation": "STAG_COLUMN"}, {"formation": "BOX"}, {"placement_mode": "agl"}]
        for change in bad:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                waypoint(**change)

    def test_waypoint_rejects_code_fields_and_unknown_keys(self):
        for key in ("statements", "condition", "on_activation", "onActivation", "script", "expression", "timeout"):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                waypoint(**{key: "hint 'x'"})

    def test_waypoint_numbers_are_finite(self):
        for bad in (-1, "-1e-99", float("inf"), float("nan"), True, "1e31", "25m"):
            with self.subTest(completion_radius=bad), self.assertRaises(ValidationError):
                waypoint(completion_radius=bad)
        self.assertEqual(waypoint(completion_radius="25").completion_radius, 25.0)
        self.assertEqual(waypoint(completion_radius=0).completion_radius, 0.0)
        for bad in ([1], [1, 2, 3, 4], [float("nan"), 2], [True, 2], ["1tail", 2]):
            with self.subTest(position=bad), self.assertRaises(ValidationError):
                waypoint(position=bad)
        for bad in (True, -1, "4.5"):
            with self.subTest(entity_id=bad), self.assertRaises(ValidationError):
                DescribeGroupParams(entity_id=bad)


class WrapperTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bridge = types.SimpleNamespace(send_command=AsyncMock())
        server = types.ModuleType("mcp_server.server")
        server.mcp = types.SimpleNamespace(tool=lambda: lambda fn: fn)
        server.bridge = self.bridge
        spec = importlib.util.spec_from_file_location("mcp_server.tools._groups_waypoints", ROOT / "mcp_server/tools/entities.py")
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"mcp_server.server": server, **inert}):
            spec.loader.exec_module(self.module)

    def sent(self):
        self.bridge.send_command.assert_awaited_once()
        return self.bridge.send_command.call_args.args[0]

    async def test_default_create_payload_is_unchanged(self):
        self.bridge.send_command.return_value = dict(ok=True, entity_id=5, classname="B_MRAP_01_F", entity_kind="Object")
        result = await self.module.create_entity(CreateEntityParams(entity_type="Vehicle", classname="B_MRAP_01_F", position=[1, 2]))
        self.assertEqual(self.sent(), {"cmd": "create_entity", "entity_type": "Vehicle", "classname": "B_MRAP_01_F",
                                       "position": [1.0, 2.0, 0.0], "placement_mode": "ATL"})
        self.assertEqual((result.group_id, result.crew, result.attributes), (-1, [], []))

    async def test_create_options_payload_and_crew_readback(self):
        self.bridge.send_command.return_value = dict(
            ok=True, entity_id=101, entity_kind="Object", classname="B_MRAP_01_hmg_F", group_id=7,
            position_atl=[1, 2, 0], position_asl=[1, 2, 50], placement_mode="ATL", engine_accepted=True, verified=True,
            crew=[pairs(dict(entity_id=102, classname="B_Soldier_F", role="driver")),
                  pairs(dict(entity_id=103, classname="B_Soldier_F", role="turret"))],
            attributes=[pairs(dict(attribute="name", canonical_attribute="Name", requested_value="mrap_1",
                                   effective_value="mrap_1", engine_accepted=True, verified=True)),
                        pairs(dict(attribute="azimuth", canonical_attribute="rotation", requested_value=90.0,
                                   effective_value=[0, 0, 90], engine_accepted=False, verified=True))])
        params = CreateEntityParams(entity_type="Vehicle", classname="B_MRAP_01_hmg_F", position=[1, 2], side="WEST",
                                    keep_crew=True, name="mrap_1", azimuth="90")
        result = await self.module.create_entity(params)
        sent = self.sent()
        self.assertEqual(sent, {"cmd": "create_entity", "entity_type": "Vehicle", "classname": "B_MRAP_01_hmg_F",
                                "position": [1.0, 2.0, 0.0], "placement_mode": "ATL", "side": "WEST",
                                "keep_crew": True, "name": "mrap_1", "azimuth": 90.0})
        self.assertEqual(build_sqf_payload(sent, "r"),
                         b'["r","create_entity","entity_type","Vehicle","classname","B_MRAP_01_hmg_F",'
                         b'"position",[1.0,2.0,0.0],"placement_mode","ATL","side","WEST","keep_crew",true,'
                         b'"name","mrap_1","azimuth",90.0]\n')
        self.assertEqual([(c.entity_id, c.role) for c in result.crew], [(102, "driver"), (103, "turret")])
        self.assertEqual(result.group_id, 7)
        self.assertFalse(result.attributes[1].engine_accepted)
        self.assertTrue(result.attributes[1].verified)

    async def test_group_id_payload_for_infantry(self):
        self.bridge.send_command.return_value = dict(ok=True, entity_id=50, entity_kind="Object", classname="B_Soldier_F",
                                                     group_id=45, crew=[], attributes=[])
        result = await self.module.create_entity(unit(group_id=12))
        self.assertEqual(self.sent()["group_id"], 12)
        self.assertNotIn("keep_crew", self.sent())
        self.assertEqual(result.group_id, 45)

    async def test_older_addon_that_ignores_options_is_an_error(self):
        self.bridge.send_command.return_value = dict(ok=True, entity_id=9, entity_kind="Object", classname="B_Soldier_F")
        with self.assertRaisesRegex(ValueError, "ignored group_id.*entity 9"):
            await self.module.create_entity(unit(group_id=3))

    async def test_unverified_or_missing_attribute_readback_is_an_error(self):
        for attributes in ([], [pairs(dict(attribute="name", verified=False))]):
            self.bridge.send_command.reset_mock()
            self.bridge.send_command.return_value = dict(ok=True, entity_id=9, entity_kind="Object",
                                                         classname="B_Soldier_F", group_id=1, crew=[], attributes=attributes)
            with self.subTest(attributes=attributes), self.assertRaisesRegex(ValueError, "readback for name"):
                await self.module.create_entity(unit(name="alpha"))

    async def test_malformed_crew_records_are_rejected(self):
        for crew in ([[["entity_id", 1], ["entity_id", 2]]], [pairs(dict(entity_id=-1, classname="x", role="driver"))],
                     "not records", [pairs(dict(entity_id=True, classname="x", role="driver"))]):
            self.bridge.send_command.reset_mock()
            self.bridge.send_command.return_value = dict(ok=True, entity_id=9, entity_kind="Object", classname="x",
                                                         group_id=-1, crew=crew, attributes=[])
            with self.subTest(crew=crew), self.assertRaises(ValueError):
                await self.module.create_entity(CreateEntityParams(entity_type="Vehicle", classname="x", position=[1, 2], keep_crew=True))

    async def test_rollback_and_validation_rejections_remain_tool_errors(self):
        self.bridge.send_command.side_effect = BridgeCommandError(dict(ok=False, stage="create_rollback", rolled_back=True,
            error="create_entity failed after creation (name readback did not match); removed entities [9]. Nothing remains"))
        with self.assertRaisesRegex(BridgeCommandError, "Nothing remains"):
            await self.module.create_entity(unit(name="alpha"))
        self.bridge.send_command.side_effect = BridgeCommandError(dict(ok=False, error="Waypoint removed: formation readback did not match WEDGE"))
        with self.assertRaisesRegex(BridgeCommandError, "Waypoint removed"):
            await self.module.create_waypoint(waypoint(formation="WEDGE"))

    async def test_minimal_waypoint_payload(self):
        self.bridge.send_command.return_value = dict(ok=True, waypoint_id=300, group_id=45, entity_kind="Waypoint",
            waypoint_type="MOVE", waypoint_class="Move", placement_mode="ATL", engine_accepted=True, attributes=[],
            position_atl=[100, 200, 0], position_asl=[100, 200, 12], verified=True)
        result = await self.module.create_waypoint(waypoint())
        self.assertEqual(self.sent(), {"cmd": "create_waypoint", "entity_id": 45, "position": [100.0, 200.0, 0.0],
                                       "placement_mode": "ATL", "waypoint_type": "MOVE"})
        self.assertEqual((result.waypoint_id, result.group_id, result.waypoint_class), (300, 45, "Move"))
        self.assertTrue(result.ok)

    async def test_full_waypoint_payload_and_string_or_index_readback(self):
        attributes = [pairs(dict(attribute=key, canonical_attribute=canonical, requested_value=requested,
                                 effective_value=effective, engine_accepted=True, verified=True))
                      for key, canonical, requested, effective in [
                          ("behaviour", "behaviour", "COMBAT", "COMBAT"), ("combat_mode", "combatMode", "NO CHANGE", "NO CHANGE"),
                          ("speed", "speedMode", "FULL", "full"), ("formation", "formation", "STAG COLUMN", 6),
                          ("completion_radius", "completionRadius", 25.0, 25)]]
        self.bridge.send_command.return_value = dict(ok=True, waypoint_id=301, group_id=45, waypoint_type="TR_UNLOAD",
                                                     attributes=attributes, verified=False, message="position differs")
        params = waypoint(waypoint_type="TR_UNLOAD", position=[1, 2, 3], placement_mode="ASL", behaviour="COMBAT",
                          combat_mode="NO CHANGE", speed="FULL", formation="STAG COLUMN", completion_radius=25)
        result = await self.module.create_waypoint(params)
        sent = self.sent()
        self.assertEqual(build_sqf_payload(sent, "req-1"),
                         b'["req-1","create_waypoint","entity_id",45,"position",[1.0,2.0,3.0],"placement_mode","ASL",'
                         b'"waypoint_type","TR_UNLOAD","behaviour","COMBAT","combat_mode","NO CHANGE","speed","FULL",'
                         b'"formation","STAG COLUMN","completion_radius",25.0]\n')
        self.assertEqual(json.loads(build_sqf_payload(sent, "req-1"))[2::2],
                         ["entity_id", "position", "placement_mode", "waypoint_type", "behaviour", "combat_mode",
                          "speed", "formation", "completion_radius"])
        self.assertEqual(result.attributes[3].effective_value, 6)
        self.assertFalse(result.verified)

    async def test_waypoint_identity_and_readback_are_required(self):
        base = dict(ok=True, waypoint_id=1, group_id=45, waypoint_type="MOVE", attributes=[])
        cases = [(waypoint(), {**base, "waypoint_type": "SAD"}),
                 (waypoint(), {k: v for k, v in base.items() if k != "attributes"}),
                 (waypoint(speed="LIMITED"), base),
                 (waypoint(speed="LIMITED"), {**base, "attributes": [pairs(dict(attribute="speed", verified=False))]}),
                 (waypoint(), {**base, "waypoint_id": -1}),
                 (waypoint(), {**base, "group_id": True})]
        for params, reply in cases:
            self.bridge.send_command.reset_mock()
            self.bridge.send_command.return_value = reply
            with self.subTest(reply=reply), self.assertRaises(ValueError):
                await self.module.create_waypoint(params)

    async def test_describe_group_parses_implicit_waypoint_and_errors(self):
        self.bridge.send_command.return_value = dict(
            ok=True, group_id=9, side="WEST", leader_id=12, editor_membership_verified=True,
            members=[pairs(dict(entity_id=12, classname="B_Soldier_SL_F", variable="alpha_1", vehicle_id=-1, role="")),
                     pairs(dict(entity_id=13, classname="B_crew_F", variable="", vehicle_id=20, role="driver"))],
            waypoints=[pairs(dict(waypoint_id=-1, index=0, waypoint_type="MOVE", position=[1, 2, 0])),
                       pairs(dict(waypoint_id=30, index=1, waypoint_type="TR_UNLOAD", position=[4, 5, 0.5]))],
            errors=[pairs(dict(entity_id=13, attribute="Name", stage="attribute_read", error="unavailable"))])
        result = await self.module.describe_group(DescribeGroupParams(entity_id="13"))
        self.assertEqual(self.sent(), {"cmd": "describe_group", "entity_id": 13})
        self.assertEqual([(m.entity_id, m.vehicle_id, m.role) for m in result.members], [(12, -1, ""), (13, 20, "driver")])
        self.assertEqual([(w.waypoint_id, w.index, w.waypoint_type) for w in result.waypoints],
                         [(-1, 0, "MOVE"), (30, 1, "TR_UNLOAD")])
        self.assertEqual(result.errors[0]["attribute"], "Name")
        self.assertTrue(result.editor_membership_verified)

    async def test_describe_group_defaults_and_malformed_replies(self):
        self.bridge.send_command.return_value = dict(ok=True, group_id=9, side="EAST", leader_id=-1, members=[], waypoints=[])
        result = await self.module.describe_group(DescribeGroupParams(entity_id=9))
        self.assertEqual((result.leader_id, result.errors, result.editor_membership_verified), (-1, [], False))
        for change in (dict(members=None), dict(waypoints="x"), dict(group_id=-1),
                       dict(waypoints=[pairs(dict(waypoint_id=1, index=1, waypoint_type="MOVE", position=[1, 2]))]),
                       dict(members=[pairs(dict(entity_id=1, classname="x", variable="", vehicle_id=-2, role=""))])):
            self.bridge.send_command.reset_mock()
            self.bridge.send_command.return_value = {**dict(ok=True, group_id=9, side="EAST", leader_id=-1,
                                                           members=[], waypoints=[]), **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                await self.module.describe_group(DescribeGroupParams(entity_id=9))


class SQFContractTests(unittest.TestCase):
    """Source guards only; live Eden acceptance is tracked in docs/validation.md."""

    def test_python_commands_are_dispatched(self):
        cases = set(re.findall(r'case "(\w+)":', source("processQueue")))
        commands = set()
        for path in (ROOT / "mcp_server/tools").glob("*.py"):
            commands.update(re.findall(r'"cmd":\s*"(\w+)"', path.read_text(encoding="utf-8")))
        self.assertTrue({"create_waypoint", "describe_group", "create_entity"} <= commands)
        self.assertEqual(commands - cases, set())
        queue = source("processQueue")
        self.assertIn('case "create_waypoint": {\n        [_id, _params] call ArmaDevBridge_bridge_fnc_createWaypoint;', queue.replace("\r\n", "\n"))
        self.assertIn('case "describe_group": {\n        [_id, _params] call ArmaDevBridge_bridge_fnc_describeGroup;', queue.replace("\r\n", "\n"))

    def test_new_functions_are_registered_for_lifecycle_recovery(self):
        config = (FUNCTIONS.parent / "config.cpp").read_text()
        init = source("init")
        for name in ("createWaypoint", "describeGroup", "resolveGroup", "editorConnections", "writeAttribute"):
            with self.subTest(function=name):
                self.assertRegex(config, rf"class\s+{name}\s*\{{")
                self.assertIn(f'"ArmaDevBridge_fnc_{name}"', init)
                self.assertIn(f'(_base + "fn_{name}.sqf")', init)
                self.assertRegex(init, rf'ArmaDevBridge_bridge_fnc_{name}\s*=\s*uiNamespace getVariable "ArmaDevBridge_fnc_{name}"')

    def test_new_handlers_are_data_only_and_respond_once(self):
        for name in ("createWaypoint", "describeGroup", "createEntity", "resolveGroup", "editorConnections", "writeAttribute"):
            text = source(name)
            with self.subTest(function=name):
                for forbidden in ("compile", "execVM", "setWaypointStatements", "setWaypointScript",
                                  "setWaypointCondition", "onActivation"):
                    self.assertNotIn(forbidden, text)
        for name in ("createWaypoint", "describeGroup", "createEntity"):
            with self.subTest(handler=name):
                self.assertEqual(source(name).count("ArmaDevBridge_bridge_fnc_sendResponse"), 1)
        reader = source("describeGroup")
        for mutation in ("set3DENAttribute", "create3DENEntity", "delete3DENEntities", "add3DENConnection"):
            self.assertNotIn(mutation, reader)

    def test_waypoint_parameter_allowlist_matches_model(self):
        allowed = sqf_list(source("createWaypoint"), "_allowed")
        self.assertEqual(set(allowed), set(CreateWaypointParams.model_fields))
        self.assertIn("forEach _params", source("createWaypoint"))

    def test_waypoint_tables_match_python_and_3den_classes(self):
        text = source("createWaypoint")
        table = dict(re.findall(r'\["([A-Z_]+)","(\w+)"\]', text))
        self.assertEqual(table, WAYPOINT_CLASSES)
        self.assertEqual(set(table), set(typing.get_args(WaypointType)))
        self.assertEqual(set(sqf_list(text, "_behaviours")), set(typing.get_args(WaypointBehaviour)))
        self.assertEqual(set(sqf_list(text, "_combatModes")), set(typing.get_args(WaypointCombatMode)))
        self.assertEqual(sqf_list(text, "_speeds"), ["UNCHANGED", "LIMITED", "NORMAL", "FULL"])
        self.assertEqual(set(sqf_list(text, "_speeds")), set(typing.get_args(WaypointSpeed)))
        self.assertEqual(sqf_list(text, "_speedSaved"), ["unchanged", "limited", "normal", "full"])
        formations = sqf_list(text, "_formations")
        self.assertEqual(set(formations), set(typing.get_args(WaypointFormation)))
        self.assertEqual(sqf_list(text, "_formationSaved"),
                         ["no change", "wedge", "vee", "line", "column", "file", "stag_column", "ech_left", "ech_right", "diamond"])
        self.assertEqual([f.lower().replace(" ", "_") for f in formations][1:], sqf_list(text, "_formationSaved")[1:])
        for attribute in ('"behaviour"', '"combatMode"', '"speedMode"', '"formation"', '"completionRadius"'):
            self.assertIn(attribute, text)
        # String first, index fallback; readback accepts either form.
        self.assertIn('[_saved, _formationIdx], [_saved, _formationIdx]', text)
        self.assertIn('[_saved, _speedIdx], [_saved, _speedIdx]', text)
        self.assertIn('_group create3DENEntity ["Waypoint", _class, _posATL]', text)
        self.assertIn('delete3DENEntities [_waypoint]', text)
        self.assertIn('"completion_radius", false, 0] call ArmaDevBridge_bridge_fnc_readNumber', text)

    def test_create_entity_crew_group_and_rollback_contract(self):
        text = source("createEntity")
        self.assertIn("create3DENEntity [_3denType,_classname,_posATL,!_keepCrew]", text)
        self.assertIn('_targetGroup create3DENEntity ["Object",_classname,_posATL]', text)
        self.assertIn('if !(_keepCrew isEqualType true) then {throw "keep_crew must be a boolean";};', text)
        self.assertIn("group_id requires an infantry (CAManBase) class", text)
        self.assertIn("private _isVehicle = _kind isEqualTo \"Object\" && {!(_resolved isKindOf \"CAManBase\")};", text)
        self.assertIn("if (!_keepCrew && {_isVehicle}", text)
        self.assertIn("toLower _role", text)
        self.assertIn("} forEach [0,1,2,3,4];", text)
        self.assertIn("_existingName == _name", text)
        # Validation precedes creation; rollback removes only groups new to this request.
        self.assertLess(text.index("name_uniqueness"), text.index("entity_create"))
        self.assertLess(text.index('"azimuth must be in [0,360)"'), text.index("entity_create"))
        self.assertIn("select {!(_x in _groupsBefore)}", text)
        self.assertNotIn("delete3DENEntities [_targetGroup", text)
        self.assertIn('["name","Name",_name,_nameIdx >= 0],["azimuth","azimut",_azimuth,_azIdx >= 0]', text)
        self.assertIn("call ArmaDevBridge_bridge_fnc_writeAttribute", text)

    def test_group_reads_reuse_shared_resolution_and_links(self):
        self.assertIn("effectiveCommander _source", source("resolveGroup"))
        self.assertIn('[_raw, ["Object", "Group"]] call ArmaDevBridge_bridge_fnc_resolveEntity', source("resolveGroup"))
        for name in ("createWaypoint", "describeGroup", "createEntity"):
            self.assertIn("ArmaDevBridge_bridge_fnc_resolveGroup", source(name))
        self.assertIn("private _connections = ArmaDevBridge_bridge_fnc_editorConnections;", source("groupEntities"))
        reader = source("describeGroup")
        self.assertIn("call ArmaDevBridge_bridge_fnc_editorConnections", reader)
        self.assertIn('if (_type isEqualTo "TR UNLOAD") then { _type = "TR_UNLOAD"; };', reader)
        self.assertIn("waypoints _group", reader)


if __name__ == "__main__":
    unittest.main()
