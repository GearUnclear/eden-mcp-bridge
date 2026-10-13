"""Offline regression fixtures: no server, game, extension, or pipe is opened.

SQF source checks enforce wiring and catalogue tables, not engine behavior.
The numeric fixtures exercise the Python boundary; the deferred SQF fixture
tools/fixtures/test_numeric_contract.sqf exercises the engine helper separately.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch
from typing import get_type_hints

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mcp_server.protocol import CONFIG_SIDES, build_sqf_payload, normalize_catalog_side, normalize_number, sqf_value

FIXTURES = json.loads((ROOT / "tools/fixtures/numeric-contract.json").read_text())
SQF = ROOT / "arma3_addon/addons/bridge/functions"


def load_module(name, path, stubs):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


def load_client():
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline tests must never open or operate a pipe")
    win32 = types.ModuleType("win32file")
    for name in ("CreateFile", "WriteFile", "ReadFile", "CloseHandle"):
        setattr(win32, name, forbidden)
    pipe = types.ModuleType("win32pipe")
    pipe.PeekNamedPipe = forbidden
    pywin = types.ModuleType("pywintypes")
    pywin.error = OSError
    return load_module("mcp_server._offline_client", "mcp_server/bridge_client.py", {
        "win32file": win32, "win32pipe": pipe, "pywintypes": pywin,
    })


class ProtocolTests(unittest.TestCase):
    def test_numeric_id_forms_preserve_exact_identity(self):
        for raw, expected in FIXTURES["accepted_ids"]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_number(raw, "entity_id", True, 0, 16777215), expected)

    def test_invalid_ids_are_rejected_with_parameter_name(self):
        for raw in FIXTURES["rejected_ids"] + [float("nan"), float("inf"), float("-inf")]:
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, "entity_id"):
                    normalize_number(raw, "entity_id", True, 0, 16777215)

    def test_coordinate_decimal_forms(self):
        for raw, expected in FIXTURES["accepted_coordinates"]:
            self.assertEqual(normalize_number(raw, "position[0]"), expected)
        for raw in (True, "1abc", "-1e-99", -1):
            with self.assertRaisesRegex(ValueError, "radius"):
                normalize_number(raw, "radius", minimum=0)

    def test_wire_numeric_and_attribute_types(self):
        wire = build_sqf_payload({"cmd": "set_attribute", "entity_id": 1,
                                  "value": [0, 90.0, [1, "1", True, False]]}, "req")
        self.assertEqual(json.loads(wire), ["req", "set_attribute", "entity_id", 1,
                                           "value", [0, 90.0, [1, "1", True, False]]])
        self.assertEqual(sqf_value([0, 90, 180]), "[0,90,180]")
        self.assertEqual(sqf_value([0.0, 90.0, 180.0]), "[0.0,90.0,180.0]")

    def test_wire_rejects_nonfinite_out_of_range_and_unsupported_values(self):
        for value in (float("nan"), float("inf"), 1e39, 10**100, [1, float("nan")]):
            with self.assertRaises(ValueError):
                sqf_value(value)
        for value in (None, {}, (1, 2)):
            with self.assertRaises(TypeError):
                sqf_value(value)

    def test_framing_and_quotes_remain_inert(self):
        for value in ['1\n', '1\r', '\x00', 'first\nsecond', ['1\n']]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                sqf_value(value)
        wire = build_sqf_payload({"cmd": 'ping";call danger', "value": '";call danger\t'}, 'req"')
        self.assertEqual(wire.count(b"\n"), 1)
        self.assertNotIn(b"\r", wire)
        self.assertNotIn(b"\x00", wire)
        self.assertEqual(wire, b'["req""","ping"";call danger","value",""";call danger\t"]\n')


class CatalogTests(unittest.TestCase):
    def test_changed_sqf_delimiters_are_balanced(self):
        for name in ("readNumber", "resolveEntity", "deleteEntity", "findLocation", "getMapObjects",
                     "getPlaceableObjects", "getPlaceableCategories", "getRoads", "getTerrainInfo"):
            source = (SQF / f"fn_{name}.sqf").read_text()
            stack = []
            for match in re.finditer(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:[^"]|"")*"|[{}\[\]()]', source):
                token = match.group()
                if token in ("(", "[", "{"):
                    stack.append(token)
                elif token in (")", "]", "}"):
                    self.assertTrue(stack, f"{name}: unmatched {token} at {match.start()}")
                    self.assertEqual(stack.pop(), {")": "(", "]": "[", "}": "{"}[token], name)
            self.assertEqual(stack, [], name)

    def test_names_and_legacy_aliases(self):
        for raw, expected in FIXTURES["legacy_sides"]:
            self.assertEqual(normalize_catalog_side(raw), expected)
            self.assertEqual(normalize_catalog_side(str(raw)), expected)
        for name in set(CONFIG_SIDES.values()) | {"ALL", "UNKNOWN"}:
            self.assertEqual(normalize_catalog_side(name.lower()), name)
        for raw in (True, False, 6, 1.5, "6", "1junk", "1 ", "1.00000001", "BLUFOR"):
            with self.assertRaises(ValueError):
                normalize_catalog_side(raw)

    def test_both_cache_builders_match_config_fixture_sides(self):
        for name in ("fn_getPlaceableObjects.sqf", "fn_getPlaceableCategories.sqf"):
            source = (SQF / name).read_text()
            mapping = {int(code): side for code, side in re.findall(r'case (-?\d+):\s*\{ "([A-Z]+)" \}', source)}
            self.assertEqual(mapping, CONFIG_SIDES, name)
            for row in FIXTURES["config_classes"]:
                self.assertEqual(mapping[row["config_side"]], row["side"], row["classname"])
            self.assertIn('default { "UNKNOWN" }', source)
            self.assertIn('else { 4 }', source)  # Missing config side cannot become EAST=0.
            self.assertIn('private _schemaVersion = 2;', source)
            self.assertIn('(missionNamespace getVariable [_schemaKey, 0]) != _schemaVersion', source)
            self.assertIn('missionNamespace setVariable [_schemaKey, _schemaVersion]', source)

    def test_config_affiliation_filter_is_separate_from_empty_placement(self):
        source = (SQF / "fn_getPlaceableObjects.sqf").read_text()
        self.assertIn('(_x select 3) isEqualTo _filterSide', source)
        self.assertIn('["config_side",        _e select 2]', source)
        self.assertNotIn('(_x select 2) == _filterSide', source)

    def test_legacy_handlers_no_longer_parse_number_prefixes(self):
        for name in ("fn_deleteEntity.sqf", "fn_getPlaceableObjects.sqf", "fn_getTerrainInfo.sqf", "fn_getRoads.sqf", "fn_getMapObjects.sqf"):
            source = (SQF / name).read_text()
            self.assertNotIn("parseNumber", source, name)
        resolver = (SQF / "fn_resolveEntity.sqf").read_text()
        self.assertIn('true, 0, 16777215', resolver)
        self.assertIn('(get3DENEntityID _entity) != _id', resolver)
        self.assertIn('[[0, "Object"], [2, "Trigger"], [3, "Logic"]]', resolver)
        self.assertIn('_id in (_all select 6)', resolver)
        terrain = (SQF / "fn_getTerrainInfo.sqf").read_text()
        self.assertIn('count _x in [2,3]', terrain)
        self.assertIn('["entity_kind", _kind]', (SQF / "fn_deleteEntity.sqf").read_text())


class BridgeDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_response_retains_complete_diagnostic_result(self):
        module = load_client()
        client = module.BridgeClient()
        future = asyncio.get_running_loop().create_future()
        client._pending["req"] = future
        result = {"ok": False, "message": "save requested; unconfirmed", "save_requested": True,
                  "status": "unconfirmed", "editor_verified": False}
        await client._dispatch(json.dumps(["req", "respond", list(map(list, result.items()))]))
        with self.assertRaises(module.BridgeCommandError) as caught:
            await future
        self.assertEqual(caught.exception.result, result)
        self.assertEqual(str(caught.exception), result["message"])

    async def test_stale_reader_cannot_complete_current_request(self):
        module = load_client()
        client = module.BridgeClient()
        old_handle, current_handle = object(), object()
        client._handle = current_handle
        future = asyncio.get_running_loop().create_future()
        client._pending["req"] = future
        await client._dispatch('["req","respond",[["ok",true]]]', old_handle)
        self.assertFalse(future.done())
        self.assertIs(client._handle, current_handle)
        await client._dispatch('["req","respond",[["ok",true]]]', current_handle)
        self.assertEqual(await future, {"ok": True})


class ToolBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from pydantic import TypeAdapter
        self.TypeAdapter = TypeAdapter
        self.commands = []

        async def send_command(command):
            self.commands.append(command)
            return {"objects": [[["classname", "B_Soldier_F"], ["side", "WEST"], ["config_side", 1]]],
                    "page": command.get("page", 0), "page_size": command.get("page_size", 30)}

        server = types.ModuleType("mcp_server.server")
        server.mcp = types.SimpleNamespace(tool=lambda: lambda function: function)
        server.bridge = types.SimpleNamespace(send_command=send_command)
        models = types.ModuleType("mcp_server.models")
        for name in ("PlaceableObject", "PlaceableObjectsPage", "PlaceableCategories"):
            setattr(models, name, types.SimpleNamespace)
        self.catalog = load_module("mcp_server.tools._offline_catalog", "mcp_server/tools/catalog.py",
                                   {"mcp_server.server": server, "mcp_server.models": models})
        self.terrain = load_module("mcp_server.tools._offline_terrain", "mcp_server/tools/terrain.py",
                                   {"mcp_server.server": server})

    async def test_catalog_request_and_raw_config_side_are_preserved(self):
        result = await self.catalog.search_placeable_objects(filter_side=2, page="1", page_size=500)
        self.assertEqual(self.commands[0]["filter_side"], "WEST")
        self.assertEqual(self.commands[0]["page"], 1)
        self.assertEqual(self.commands[0]["page_size"], 100)
        self.assertEqual(result.objects[0].side, "WEST")
        self.assertEqual(result.objects[0].config_side, 1)
        self.assertNotIn("mcp_server.server", sys.modules)

    def test_catalog_pydantic_boundary_rejects_bool_and_fractional_pages(self):
        hints = get_type_hints(self.catalog.search_placeable_objects, include_extras=True)
        for name, values in {"page": [True, -1, "1.01", "1tail"],
                             "page_size": [False, 0, "1.5"],
                             "filter_side": [True, "1tail", 1.0]}.items():
            adapter = self.TypeAdapter(hints[name])
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    adapter.validate_python(value)

    def test_terrain_pydantic_boundary_rejects_coercible_bool(self):
        hints = get_type_hints(self.terrain.get_roads, include_extras=True)
        for name, values in {"position": [[True, 0], ["1tail", 0]],
                             "radius": [False, -1, "-1e-99"],
                             "max_segments": [True, -1, "1.5", 16777216]}.items():
            adapter = self.TypeAdapter(hints[name])
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    adapter.validate_python(value)


if __name__ == "__main__":
    unittest.main()
