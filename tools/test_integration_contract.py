"""Offline integration checks; never import server.py or open a named pipe.

SQF checks below are source invariants/lexical validation, not engine execution.
"""
import asyncio
import importlib.util
import json
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mcp_server.models import CreateEntityParams, MoveEntityParams, GroupEntitiesParams, GetAttributeParams
from mcp_server.bridge_client import BridgeClient, BridgeCommandError

FUNCTIONS = ROOT / 'arma3_addon/addons/bridge/functions'


def sqf_tokens(source):
    """Ignore SQF comments and doubled-quote strings for delimiter checking."""
    pattern = r'//[^\n]*|/\*[\s\S]*?\*/|"(?:""|[^"])*"|\x27(?:\x27\x27|[^\x27])*\x27|[{}\[\]()]'
    for match in re.finditer(pattern, source):
        value = match.group()
        if len(value) == 1:
            yield value


class ModelContractTests(unittest.TestCase):
    def test_exact_id_validation_rejects_aliasing(self):
        for bad in [True, -1, 16777216, '1garbage', '1.0000000000000001', ' 1', float('nan'), float('inf')]:
            with self.subTest(value=bad), self.assertRaises(ValueError):
                GetAttributeParams(entity_id=bad, attribute='Name')
        for good in [0, 1, 1.0, '1', '1e0', '+1.0']:
            expected = 0 if good == 0 else 1
            self.assertEqual(GetAttributeParams(entity_id=good, attribute='Name').entity_id, expected)

    def test_placement_modes_and_coordinates(self):
        for mode in ['ATL', 'ASL', 'terrain', 'water']:
            p = MoveEntityParams(entity_id=1, position=[200, 300, 12], placement_mode=mode)
            self.assertEqual(p.position[2], 12)
        for coords in [[1], [1, 2, 3, 4], [True, 2], [1, float('nan')], [1, '2junk']]:
            with self.subTest(position=coords), self.assertRaises(ValueError):
                MoveEntityParams(entity_id=1, position=coords)
        self.assertEqual(CreateEntityParams(entity_type='Object', classname='x', position=[1,2]).placement_mode, 'ATL')


class EntityWrapperTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bridge = types.SimpleNamespace(send_command=AsyncMock())
        server = types.ModuleType('mcp_server.server')
        server.mcp = types.SimpleNamespace(tool=lambda: lambda fn: fn)
        server.bridge = self.bridge
        spec = importlib.util.spec_from_file_location('mcp_server.tools._entities_integration', ROOT / 'mcp_server/tools/entities.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'mcp_server.server': server}):
            spec.loader.exec_module(self.module)

    async def test_create_preserves_placement_readback_and_omits_unspecified_side(self):
        self.bridge.send_command.return_value = dict(ok=True, entity_id=42, classname='x', entity_kind='Object',
            position_atl=[1,2,12], position_asl=[1,2,112], placement_mode='ASL', engine_accepted=True, verified=True)
        result = await self.module.create_entity(CreateEntityParams(entity_type='Object', classname='x', position=[1,2,112], placement_mode='ASL'))
        sent = self.bridge.send_command.call_args.args[0]
        self.assertEqual(sent['position'], [1,2,112])
        self.assertNotIn('side', sent)
        self.assertEqual(sent['placement_mode'], 'ASL')
        self.assertEqual(result.position_atl, [1,2,12])
        self.assertTrue(result.verified)

    async def test_two_component_move_uses_explicit_zero_and_preserves_failure(self):
        self.bridge.send_command.side_effect = BridgeCommandError(dict(ok=False, entity_id=42, verified=False,
            engine_accepted=False, message='engine rejected', position_atl=[1,2,5], position_asl=[1,2,105], placement_mode='ATL'))
        result = await self.module.move_entity(MoveEntityParams(entity_id=42, position=[1,2]))
        self.assertEqual(self.bridge.send_command.call_args.args[0]['position'], [1,2,0])
        self.assertFalse(result.ok)
        self.assertEqual(result.position_atl[2], 5)
        self.bridge.send_command.assert_awaited_once()

    async def test_grouping_partial_verification_is_not_success(self):
        self.bridge.send_command.side_effect = BridgeCommandError(dict(ok=False, status='grouping_unconfirmed',
            group_id=9, leader_id=1, member_ids=[1], count=1, editor_verified=False, persistence_verified=False))
        result = await self.module.group_entities(GroupEntitiesParams(entity_ids=[1,2]))
        self.assertFalse(result.ok)
        self.assertEqual(result.member_ids, [1])
        self.assertFalse(result.persistence_verified)
        self.bridge.send_command.assert_awaited_once()

    async def test_validation_errors_are_not_converted_to_partial_success(self):
        self.bridge.send_command.side_effect = BridgeCommandError(dict(ok=False, error='entity_id invalid'))
        with self.assertRaises(BridgeCommandError):
            await self.module.group_entities(GroupEntitiesParams(entity_ids=[1,2]))


class ResponseContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_malformed_correlated_responses_fail_without_waiting(self):
        bodies = [[], [["value", 1]], [["ok", "true"]], [[[], 1]], [["ok",True],["ok",False]]]
        envelopes = [['offline-invalid','respond', body] for body in bodies]
        envelopes += [['offline-invalid'], ['offline-invalid', 'respond'], ['offline-invalid', 'wrong', [['ok',True]]]]
        for envelope in envelopes:
            with self.subTest(envelope=envelope):
                client = BridgeClient()
                handle = object()
                client._handle = handle
                future = asyncio.get_running_loop().create_future()
                client._pending['offline-invalid'] = future
                await client._dispatch(json.dumps(envelope), handle)
                self.assertTrue(future.done())
                with self.assertRaises(BridgeCommandError):
                    await future

    async def test_json_controls_nil_and_exponents_dispatch_without_io(self):
        client = BridgeClient()  # No __aenter__, connect or transport function.
        handle = object()
        client._handle = handle
        future = asyncio.get_running_loop().create_future()
        client._pending['offline-fixture'] = future
        value = ['\\\\host\\path', '""', '\n\r\t\x00', 'Œ😀', None, [], [True, 12500000000.0]]
        await client._dispatch(json.dumps(['offline-fixture','respond', [['ok',True],['value',value]]]), handle)
        self.assertEqual((await future)['value'], value)


class SQFIntegrationSourceTests(unittest.TestCase):
    def test_all_function_files_have_balanced_delimiters(self):
        for path in FUNCTIONS.glob('*.sqf'):
            with self.subTest(file=path.name):
                stack = []
                for token in sqf_tokens(path.read_text(encoding='utf-8-sig')):
                    if token in '{[(':
                        stack.append(token)
                    else:
                        self.assertTrue(stack, f'{path.name}: unmatched {token}')
                        self.assertEqual(stack.pop(), {'}':'{',']':'[',')':'('}[token])
                self.assertFalse(stack)

    def test_every_called_helper_survives_lifecycle_recovery(self):
        init = (FUNCTIONS / 'fn_init.sqf').read_text()
        config = (FUNCTIONS.parent / 'config.cpp').read_text()
        referenced = set()
        for path in FUNCTIONS.glob('*.sqf'):
            referenced.update(re.findall(r'ArmaDevBridge_bridge_fnc_(\w+)', path.read_text()))
        for name in referenced:
            with self.subTest(helper=name):
                self.assertTrue((FUNCTIONS / f'fn_{name}.sqf').is_file())
                self.assertIn(f'fn_{name}.sqf', init)
                self.assertRegex(init, rf'ArmaDevBridge_bridge_fnc_{name}\s*=\s*uiNamespace')
                self.assertRegex(config, rf'class\s+{name}\s*\{{')

    def test_request_guard_and_no_response_fallback(self):
        source = (FUNCTIONS / 'fn_processQueue.sqf').read_text()
        self.assertIn('parseSimpleArray _raw', source)
        self.assertNotIn('compile _raw', source)
        self.assertLess(source.index('private _abandoned'), source.index('callExtension "poll"'))
        self.assertIn('duplicate parameter', source)
        self.assertIn('handler_no_response', source)
        self.assertIn('if (_dup) exitWith', source)
        sender = (FUNCTIONS / 'fn_sendResponse.sqf').read_text()
        self.assertIn('262144', sender)
        self.assertIn('response_too_large', sender)
        encoder = (FUNCTIONS / 'fn_toJSON.sqf').read_text()
        self.assertNotIn('splitString', encoder)
        self.assertNotIn('while', encoder)  # No exponent-zero stripping.
        self.assertIn('isNil { _v select _i }', encoder)

    def test_eden_categories_match_official_array_order(self):
        source = (FUNCTIONS / 'fn_listEntities.sqf').read_text()
        for kind, index in [('Logic',3),('Waypoint',4),('Marker',5),('Layer',6)]:
            self.assertRegex(source, rf'case "{kind}":\s*\{{ {index} \}}')
        self.assertIn('count (_all select 4)', (FUNCTIONS / 'fn_getMissionInfo.sqf').read_text())
        grouping = (FUNCTIONS / 'fn_groupEntities.sqf').read_text()
        self.assertNotIn('param [3,', grouping)
        self.assertIn('param [4,', grouping)


if __name__ == '__main__':
    unittest.main(verbosity=2)
