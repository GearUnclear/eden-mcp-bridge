"""Offline Python response-contract checks; no MCP startup, pipe I/O, or SQF execution.

The real mission tool module is imported with an inert server/decorator and canned
bridge replies. These checks establish Python failure semantics only, not native
Eden grouping, save persistence, event timing, or undo behavior.
"""
import importlib
import asyncio
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp_server.models import SaveMissionParams

server = types.ModuleType("mcp_server.server")
server.mcp = types.SimpleNamespace(tool=lambda: lambda function: function)
server.bridge = types.SimpleNamespace(send_command=AsyncMock())
# Import the real error type without providing any operational win32 APIs.
# Accidental transport use therefore fails instead of contacting any game pipe.
inert_imports = {name: types.ModuleType(name) for name in ("win32file", "win32pipe", "pywintypes")}
inert_imports["mcp_server.server"] = server
with patch.dict(sys.modules, inert_imports):
    from mcp_server.bridge_client import BridgeClient, BridgeCommandError
    mission = importlib.import_module("mcp_server.tools.mission")


class PersistenceContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        server.bridge.send_command = AsyncMock()

    def test_native_route_guard_uses_official_waypoint_bucket(self):
        # Static contract guard only: systems occupy index3; waypoints index4.
        # This does not execute or establish correctness of the SQF handler.
        source = (ROOT / "arma3_addon/addons/bridge/functions/fn_groupEntities.sqf").read_text(encoding="utf-8-sig")
        self.assertEqual(source.count("all3DENEntities param [4, []]"), 2)
        self.assertNotIn("all3DENEntities param [3", source)

    def test_grouping_native_nil_is_guarded_before_wire_boolean_emission(self):
        # Source guard for the native-return regression. The decoder fixtures
        # below verify Python behavior; neither check runs SQF/native grouping.
        source = (ROOT / "arma3_addon/addons/bridge/functions/fn_groupEntities.sqf").read_text(encoding="utf-8-sig")
        self.assertIn('private _connectionResult = add3DENConnection', source)
        self.assertIn('isNil "_connectionResult" || {_connectionResult isEqualTo true}', source)
        self.assertIn('if (isNil "_verified") then { _verified = false; };', source)
        self.assertIn('_verified = _verified isEqualTo true;', source)
        self.assertNotIn('_accepted = add3DENConnection', source)

    async def test_grouping_null_fixture_matches_reported_length_and_fails_closed(self):
        request_id = "x" * 36
        fields = [["ok", None], ["status", None], ["group_id", 0], ["leader_id", 1],
                  ["count", 2], ["member_ids", [1, 3]], ["editor_verified", None],
                  ["persistence_verified", False], ["message", None]]
        wire = json.dumps([request_id, "respond", fields], separators=(",", ":"))
        self.assertEqual(len(wire), 217)
        client = BridgeClient()  # no connect/context entry or win32 operation
        future = asyncio.get_running_loop().create_future()
        client._pending[request_id] = future
        await client._dispatch(wire)
        with self.assertRaisesRegex(BridgeCommandError, "explicit boolean ok"):
            await future

    async def test_boolean_grouping_results_preserve_verification_and_partial_state(self):
        for verified in (True, False):
            with self.subTest(verified=verified):
                request_id = "group-readback"
                reply = dict(ok=verified,
                    status="editor_group_verified" if verified else "grouping_unconfirmed",
                    group_id=0, leader_id=1, count=2, member_ids=[1, 3],
                    editor_verified=verified, persistence_verified=False,
                    message="Editor readback verified" if verified else "Partial edits may remain")
                client = BridgeClient()
                future = asyncio.get_running_loop().create_future()
                client._pending[request_id] = future
                await client._dispatch(json.dumps([request_id, "respond", list(reply.items())]))
                if verified:
                    self.assertEqual(await future, reply)
                else:
                    with self.assertRaises(BridgeCommandError) as caught:
                        await future
                    self.assertEqual(caught.exception.result, reply)
                self.assertFalse(client.is_connected)

    async def test_save_omits_unsupported_title_and_preserves_request_only_state(self):
        reply = dict(ok=False, status="save_requested", save_requested=True,
                     persistence_verified=False, manual_action_required=True,
                     message="Save requested; verify manually")
        server.bridge.send_command.side_effect = BridgeCommandError(reply)
        result = await mission.save_mission(SaveMissionParams())
        server.bridge.send_command.assert_awaited_once_with({"cmd": "save_mission"})
        self.assertFalse(result.ok)
        self.assertTrue(result.save_requested)
        self.assertFalse(result.persistence_verified)
        self.assertTrue(result.manual_action_required)
        self.assertEqual(result.status, "save_requested")
        self.assertEqual(result.message, reply["message"])

    async def test_save_as_or_cancel_never_becomes_verified_success(self):
        reply = dict(ok=False, status="save_as_required", save_requested=True,
                     persistence_verified=False, manual_action_required=True,
                     message="Complete Save As; cancel means no save")
        server.bridge.send_command.side_effect = BridgeCommandError(reply)
        result = await mission.save_mission(SaveMissionParams())
        self.assertEqual(result.status, "save_as_required")
        self.assertFalse(result.ok)
        self.assertFalse(result.persistence_verified)

    async def test_any_supplied_display_name_is_rejected_before_dispatch(self):
        for title in ("", "My mission"):
            with self.subTest(title=title):
                result = await mission.save_mission(SaveMissionParams(display_name=title))
                self.assertFalse(result.ok)
                self.assertEqual(result.status, "unsupported_display_name")
                self.assertFalse(result.save_requested)
        server.bridge.send_command.assert_not_awaited()

    async def test_legacy_success_reply_does_not_claim_disk_persistence(self):
        server.bridge.send_command.return_value = {"ok": True, "message": "Mission saved"}
        result = await mission.save_mission(SaveMissionParams())
        self.assertFalse(result.ok)
        self.assertFalse(result.persistence_verified)
        self.assertFalse(result.save_requested)
        self.assertEqual(result.status, "save_unconfirmed")
        self.assertNotIn("Mission saved", result.message)

    async def test_undo_observed_event_preserves_global_unknown_scope(self):
        server.bridge.send_command.return_value = dict(ok=True, status="undo_observed",
            undo_requested=True, undo_observed=True, action_scope="editor_global", action_identity="unknown")
        result = await mission.undo_last_action()
        server.bridge.send_command.assert_awaited_once_with({"cmd": "undo"})
        self.assertTrue(result.ok)
        self.assertTrue(result.undo_observed)
        self.assertEqual(result.action_scope, "editor_global")
        self.assertEqual(result.action_identity, "unknown")

    async def test_undo_without_event_preserves_unconfirmed_failure(self):
        server.bridge.send_command.side_effect = BridgeCommandError(dict(ok=False,
            status="undo_unconfirmed", undo_requested=True, undo_observed=False,
            message="Empty history or unavailable action cannot be distinguished"))
        result = await mission.undo_last_action()
        self.assertFalse(result.ok)
        self.assertTrue(result.undo_requested)
        self.assertFalse(result.undo_observed)
        self.assertEqual(result.status, "undo_unconfirmed")

    async def test_legacy_noop_success_is_not_reported_as_undo(self):
        server.bridge.send_command.return_value = {"ok": True}
        result = await mission.undo_last_action()
        self.assertFalse(result.ok)
        self.assertFalse(result.undo_requested)
        self.assertFalse(result.undo_observed)
        self.assertEqual(result.status, "undo_unconfirmed")

    async def test_transport_failure_propagates_without_synthetic_confirmation(self):
        server.bridge.send_command.side_effect = TimeoutError("No response")
        with self.assertRaises(TimeoutError):
            await mission.save_mission(SaveMissionParams())
        with self.assertRaises(TimeoutError):
            await mission.undo_last_action()


if __name__ == "__main__":
    unittest.main()
