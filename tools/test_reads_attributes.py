"""Offline wrapper fixtures only: no server, pipe, editor, or engine imports.

Run from repository root: python -m unittest discover -s tools -p test_reads_attributes.py
The fake server decorator registers nothing. Fixtures verify response contracts,
not the correctness of Eden's SQF commands or the cause of historical timeouts.
"""
import asyncio
import importlib
import math
from pathlib import Path
import sys
import types
import unittest
from typing import get_type_hints
from pydantic import TypeAdapter
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeMCP:
    def tool(self):
        return lambda fn: fn


class FixtureBridgeError(RuntimeError):
    def __init__(self, result):
        self.result = result
        super().__init__(result.get("error", "rejected"))


# Load tools with inert server/bridge modules; never import the real server.
fixture_package = types.ModuleType("_reads_fixture")
fixture_package.__path__ = [str(ROOT / "mcp_server")]
fixture_tools = types.ModuleType("_reads_fixture.tools")
fixture_tools.__path__ = [str(ROOT / "mcp_server/tools")]
fixture_server = types.ModuleType("_reads_fixture.server")
fixture_server.mcp = FakeMCP()
fixture_server.bridge = types.SimpleNamespace(send_command=AsyncMock())
fixture_client = types.ModuleType("_reads_fixture.bridge_client")
fixture_client.BridgeCommandError = FixtureBridgeError
with patch.dict(sys.modules, {"_reads_fixture": fixture_package,
                             "_reads_fixture.tools": fixture_tools,
                             "_reads_fixture.server": fixture_server,
                             "_reads_fixture.bridge_client": fixture_client}):
    attrs = importlib.import_module("_reads_fixture.tools.attributes")
    selection = importlib.import_module("_reads_fixture.tools.selection")
    fixture_models = sys.modules["_reads_fixture.models"]
GetAttributeParams = fixture_models.GetAttributeParams
SetAttributeParams = fixture_models.SetAttributeParams


def pairs(record):
    return [[key, value] for key, value in record.items()]


def object_fixture(entity_id=1, **changes):
    value = dict(entity_id=entity_id, classname="B_Soldier_F",
                 position=[20.0, 30.0, 2.0], position_asl=[20.0, 30.0, 52.0],
                 direction=125.0, side="WEST", group_id=0,
                 description="Leader", variable="leader_one", init='this setVariable ["note", "quote\\line\nnext"]',
                 is_playable=False, is_player=False, is_leader=True, skill=0.6)
    value.update(changes)
    return pairs(value)


def page_fixture(objects, total=None, page=0, errors=None, page_size=50):
    total = len(objects) if total is None else total
    total_pages = math.ceil(total / page_size)
    return dict(ok=True, objects=objects, page=page, page_size=page_size, total=total,
                total_pages=total_pages, has_more=page + 1 < total_pages,
                errors=errors or [], diagnostics=pairs(dict(stage="object_page_completed", handler_ms=2.5)))


class ReadFixtures(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bridge = fixture_server.bridge.send_command
        self.bridge.reset_mock(side_effect=True, return_value=True)

    async def test_original_28_unit_page_keeps_flags_and_positions(self):
        self.bridge.return_value = page_fixture([object_fixture(i, is_player=(i == 1), is_playable=(i == 1)) for i in range(1, 29)], page_size=30)
        page = await selection.get_all_editor_objects(page=0, page_size=30)
        self.assertEqual(len(page.objects), 28)
        self.assertTrue(page.objects[0].is_player)
        self.assertFalse(page.objects[1].is_playable)
        self.assertEqual(page.objects[0].position_asl[2] - page.objects[0].position[2], 50)
        self.assertIn("\\line\nnext", page.objects[0].init)
        self.assertEqual(page.diagnostics["stage"], "object_page_completed")

    def test_public_annotations_reject_bool_before_tool_coercion(self):
        for function, parameter in [(attrs.get_all_attributes, 'entity_id'),
                                    (attrs.get_supported_attributes, 'entity_id'),
                                    (selection.get_all_editor_objects, 'page'),
                                    (selection.get_all_editor_objects, 'page_size'),
                                    (selection.get_all_editor_objects_full, 'max_pages')]:
            with self.subTest(function=function.__name__, parameter=parameter):
                annotation = get_type_hints(function, include_extras=True)[parameter]
                with self.assertRaises(ValueError):
                    TypeAdapter(annotation).validate_python(True)

    async def test_empty_mission_has_zero_pages(self):
        self.bridge.return_value = page_fixture([])
        result = await selection.get_all_editor_objects()
        self.assertEqual(result.total_pages, 0)
        self.assertEqual(await selection.get_all_editor_objects_full(), [])

    async def test_bad_page_values_fail_before_sending(self):
        for args in [(-1, 50), (0, 0), (0, 101), (0.5, 50), (True, 50), (0, False)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                await selection.get_all_editor_objects(*args)
        self.bridge.assert_not_called()

    async def test_partial_page_is_visible_but_full_does_not_claim_completion(self):
        self.bridge.return_value = page_fixture([object_fixture()], total=2,
            errors=[pairs(dict(entity_id=2, attribute="position", stage="attribute_read", error="unavailable"))])
        result = await selection.get_all_editor_objects()
        self.assertEqual(result.errors[0]["entity_id"], 2)
        with self.assertRaisesRegex(ValueError, "per-entity errors"):
            await selection.get_all_editor_objects_full()

    async def test_missing_required_coordinates_are_not_fabricated(self):
        for change in [dict(position=[1, 2]), dict(position_asl=None), dict(direction=float("nan")),
                       dict(is_playable="false"), dict(entity_id=True)]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                selection._parse_editor_object(object_fixture(**change))

    async def test_inconsistent_page_identity_and_totals_fail(self):
        for change in [dict(page=1), dict(page_size=20), dict(total_pages=100), dict(has_more=True)]:
            self.bridge.return_value = {**page_fixture([object_fixture()]), **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                await selection.get_all_editor_objects()

    async def test_repeated_ids_and_changing_mission_fail_explicitly(self):
        first = page_fixture([object_fixture(i) for i in range(1, 51)], total=51)
        for second, error in [(page_fixture([object_fixture(1)], total=51, page=1), "Repeated entity"),
                              (page_fixture([object_fixture(51), object_fixture(52)], total=52, page=1), "entity count changed")]:
            self.bridge.side_effect = [first, second]
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                await selection.get_all_editor_objects_full()

    async def test_page_budget_is_finite(self):
        self.bridge.return_value = page_fixture([object_fixture(i) for i in range(1, 51)], total=51)
        with self.assertRaisesRegex(ValueError, "exceeded 1 pages"):
            await selection.get_all_editor_objects_full(max_pages=1)
        self.assertEqual(self.bridge.call_count, 1)

    async def test_false_zero_empty_and_nested_values_survive(self):
        values = {"ControlMP": False, "skill": 0, "Init": "", "cargo": [],
                  "modArray": [[1, "number string 2", None, True], [], ""]}
        self.bridge.return_value = dict(ok=True, entity_id=9, entity_kind="Object", classname="B_Soldier_F",
                                       attributes=pairs(values), errors=[], partial=False)
        result = await attrs.get_all_attributes(9)
        self.assertEqual(result["attributes"], values)
        self.assertEqual(result["count"], 5)

    async def test_attribute_value_is_unwrapped_only_by_engine_handler(self):
        value = [[1, "2", False], []]
        self.bridge.return_value = dict(ok=True, entity_id=9, entity_kind="Object", classname="B_Soldier_F",
                                       attribute="custom", canonical_attribute="custom", value=value)
        result = await attrs.get_attribute(GetAttributeParams(entity_id=9, attribute="custom"))
        self.assertEqual(result.value, value)

    async def test_attribute_response_cannot_silently_change_identity(self):
        self.bridge.return_value = dict(ok=True, entity_id=0, entity_kind="Group", attribute="isPlayer", value=False)
        with self.assertRaisesRegex(ValueError, "identity"):
            await attrs.get_attribute(GetAttributeParams(entity_id=9, attribute="isPlayer"))

    async def test_bad_entity_ids_fail_before_attribute_discovery(self):
        for entity_id in [True, -1, 1.5, "broken", 16777216]:
            with self.subTest(entity_id=entity_id), self.assertRaises(ValueError):
                await attrs.get_supported_attributes(entity_id)
        self.bridge.assert_not_called()

    async def test_discovery_keeps_metadata_and_deliberate_aliases(self):
        self.bridge.return_value = dict(ok=True, entity_id=9, entity_kind="Object", classname="B_Soldier_F",
            attributes=[pairs(dict(name="ControlSP", value_type="BOOL", config_path="engine")),
                        pairs(dict(name="ModProperty", value_type="UNKNOWN", config_path="CfgVehicles/mod/Attributes"))],
            aliases=[["isPlayer", "ControlSP"], ["isPlayable", "ControlMP"]])
        result = await attrs.get_supported_attributes(9)
        self.assertEqual(result["attributes"][1]["name"], "ModProperty")
        self.assertEqual(result["aliases"]["isPlayer"], "ControlSP")

    async def test_engine_rejection_retains_actual_value(self):
        rejected = dict(ok=False, error="Engine rejected attribute write", message="rejected",
                        entity_id=9, entity_kind="Object", classname="B_Soldier_F", attribute="skill",
                        canonical_attribute="skill", requested_value=0.5, effective_value=0.2,
                        engine_accepted=False, verified=False)
        self.bridge.side_effect = FixtureBridgeError(rejected)
        result = await attrs.set_attribute(SetAttributeParams(entity_id=9, attribute="skill", value=0.5))
        self.assertFalse(result.ok)
        self.assertEqual(result.effective_value, 0.2)

    async def test_accepted_but_transformed_write_is_unverified(self):
        self.bridge.return_value = dict(ok=True, message="effective value differs", entity_id=9,
            entity_kind="Object", classname="B_Soldier_F", attribute="Name", canonical_attribute="Name",
            requested_value="Bad Name", effective_value="Bad_Name", engine_accepted=True, verified=False)
        result = await attrs.set_attribute(SetAttributeParams(entity_id=9, attribute="Name", value="Bad Name"))
        self.assertTrue(result.engine_accepted)
        self.assertFalse(result.verified)
        self.assertEqual(result.requested_value, "Bad Name")

    async def test_validation_rejection_remains_tool_error(self):
        self.bridge.side_effect = FixtureBridgeError(dict(ok=False, error="unsupported attribute"))
        with self.assertRaisesRegex(FixtureBridgeError, "unsupported"):
            await attrs.set_attribute(SetAttributeParams(entity_id=9, attribute="invalid", value=True))


class SQFContractChecks(unittest.TestCase):
    """Source guards complement fixtures; they do not execute SQF or prove Eden behavior."""
    def source(self, name):
        return (ROOT / "arma3_addon/addons/bridge/functions" / f"fn_{name}.sqf").read_text(encoding="utf-8-sig")

    def test_reads_use_canonical_properties_and_guard_pagination(self):
        source = self.source("getAllObjects")
        self.assertIn('["ControlSP",false]', source)
        self.assertIn('["ControlMP",false]', source)
        self.assertIn('["Name",""]', source)
        self.assertIn('[_obj,"rotation"]', source)
        self.assertIn('"page_size",true,1,100', source)
        self.assertIn('ArmaDevBridge_responseStage', source)
        self.assertNotIn('get3DENAttribute "isPlayable"', source)

    def test_discovery_does_not_compile_mod_expressions_or_require_218(self):
        source = self.source("attributeInfo")
        self.assertIn('"Cfg3DEN"', source)
        self.assertIn('"CfgVehicles"', source)
        self.assertIn('"property"', source)
        self.assertIn('"data"', source)
        self.assertNotIn("compile", source)
        self.assertNotIn("get3DENAttributes", self.source("getAllAttributes"))

    def test_placement_shares_explicit_converter_and_persistent_engine_write(self):
        for name in ("createEntity", "moveEntity"):
            source = self.source(name)
            self.assertIn("ArmaDevBridge_bridge_fnc_placementPosition", source)
            self.assertIn('"position_asl"', source)
            self.assertIn('"verified"', source)
            self.assertNotIn("_posZ <=", source)
            self.assertNotIn("setPos", source)
        self.assertIn('set3DENAttribute ["position",_posATL]', self.source("moveEntity"))
        self.assertIn('"atl","asl","terrain","water"', self.source("placementPosition"))
        self.assertIn("surfaceIsWater", self.source("placementPosition"))

    def test_setter_uses_engine_result_and_readback(self):
        source = self.source("setAttribute")
        self.assertIn("private _accepted = _entity set3DENAttribute", source)
        self.assertIn("[_effective, _value, _verificationTolerance] call ArmaDevBridge_bridge_fnc_attributeValuesMatch", source)
        self.assertIn('["requested_value",_requested]', source)
        self.assertIn('["ok",_accepted]', source)

    def test_readback_comparator_is_registered_and_type_strict(self):
        source = self.source("attributeValuesMatch")
        self.assertIn("_actual isEqualType _expected", source)
        self.assertIn("!finite _actual", source)
        self.assertIn("!finite _expected", source)
        self.assertIn("count _actual isEqualTo count _expected", source)
        self.assertIn("_actual isEqualTo _expected", source)
        self.assertNotIn("parseNumber", source)
        self.assertNotIn("toLower", source)
        self.assertIn("class attributeValuesMatch", (ROOT / "arma3_addon/addons/bridge/config.cpp").read_text())
        init = self.source("init")
        self.assertIn('"fn_attributeValuesMatch.sqf"', init)
        self.assertIn('ArmaDevBridge_bridge_fnc_attributeValuesMatch = uiNamespace getVariable "ArmaDevBridge_fnc_attributeValuesMatch"', init)

    def test_created_marker_position_is_explicit_and_readback_stays_atl(self):
        source = self.source("createEntity")
        self.assertIn('_kind isEqualTo "Marker"', source)
        self.assertIn('_resolved set3DENAttribute ["position",_posATL]', source)
        self.assertIn('_placementAccepted && {[_finalATL,_posATL,0.001]', source)
        self.assertIn('[_finalATL,_posATL,0.001]', self.source("moveEntity"))
        self.assertNotIn('_finalATL select 2) - getTerrainHeightASL', source)


if __name__ == "__main__":
    unittest.main()
