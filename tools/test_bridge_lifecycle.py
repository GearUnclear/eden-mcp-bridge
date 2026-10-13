"""Windows regression tests against the real DLL on a unique, isolated pipe.

Build bridge_dll first, then run with the server's .venv Python. The extension
exports simulate the SQF side; no game, mission, or live bridge is touched.
"""
import asyncio
import ctypes
import json
import os
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["ARMA3_BRIDGE_PIPE"] = rf"\\.\pipe\arma3_bridge_test_{uuid.uuid4().hex}"

from mcp_server.bridge_client import BridgeClient, BridgeNotConnectedError
from mcp_server.bridge_client import PIPE_NAME
import win32file

# Fail closed if an earlier import cached the production/default pipe. Never
# load/start the test DLL until both sides demonstrably use this UUID test pipe.
if PIPE_NAME != os.environ["ARMA3_BRIDGE_PIPE"] or not PIPE_NAME.startswith(r"\\.\pipe\arma3_bridge_test_"):
    raise RuntimeError("Isolated lifecycle tests require a fresh unique test pipe")


class SplitClient(BridgeClient):
    def _win32_write(self, data, handle):
        # Force several ReadFile completions, including a cancelled idle read.
        for pos in range(0, len(data), 9):
            super()._win32_write(data[pos:pos + 9], handle)
            time.sleep(0.02)


class DLLLifecycleTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.dll = ctypes.WinDLL(str(ROOT / "bridge_dll/build/wsl/arma3_mcp_bridge.dll"))
        cls.dll.RVExtension.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]
        cls.dll.RVExtension.restype = None
        cls.ext("ping")

    @classmethod
    def ext(cls, command, size=10240):
        buffer = ctypes.create_string_buffer(size)
        cls.dll.RVExtension(buffer, size, command.encode())
        return buffer.value.decode()

    async def open_client(self, client_type=BridgeClient):
        client = client_type()
        await client.__aenter__()
        self.addAsyncCleanup(client.__aexit__)
        await asyncio.wait_for(client._ready.wait(), 4)
        return client

    async def asyncSetUp(self):
        self.ext("editor_paused")
        self.ext("editor_ready")

    async def pump(self, count, timeout=5):
        commands = []
        deadline = asyncio.get_running_loop().time() + timeout
        while len(commands) < count:
            raw = self.ext("poll")
            if raw:
                msg = json.loads(raw)
                commands.append(msg)
                self.ext(json.dumps([msg[0], "respond", [["ok", True], ["editor_open", True]]]))
            self.assertLess(asyncio.get_running_loop().time(), deadline, "SQF poll timed out")
            await asyncio.sleep(0.005)
        return commands

    async def test_fragmented_request_survives_multiple_reads(self):
        client = await self.open_client(SplitClient)
        call = asyncio.create_task(client.send_command({"cmd": "get_mission_info"}))
        commands = await self.pump(1)
        self.assertTrue((await call)["ok"])
        self.assertEqual(commands[0][1], "get_mission_info")
        self.assertEqual(self.ext("poll"), "")

    async def test_concurrent_commands_delivered_once(self):
        client = await self.open_client()
        calls = [asyncio.create_task(client.send_command({"cmd": "ping", "index": n})) for n in range(20)]
        commands = await self.pump(20)
        self.assertEqual(len({m[0] for m in commands}), 20)
        self.assertTrue(all(r["ok"] for r in await asyncio.gather(*calls)))
        self.assertEqual(self.ext("poll"), "")

    async def test_preview_rejects_edits_then_recovers_repeatedly(self):
        client = await self.open_client()
        for _ in range(5):
            self.ext("editor_paused")
            status = await client.send_command({"cmd": "ping"})
            self.assertFalse(status["editor_open"])
            with self.assertRaisesRegex(RuntimeError, "paused or closed"):
                await client.send_command({"cmd": "create_entity"})
            self.ext("editor_ready")
            self.assertEqual(self.ext("poll"), "", "Rejected edit was replayed")
            call = asyncio.create_task(client.send_command({"cmd": "ping"}))
            await self.pump(1)
            self.assertTrue((await call)["editor_open"])

    async def test_pending_edit_cancelled_on_preview(self):
        client = await self.open_client()
        written = threading.Event()
        original = client._win32_write
        def write(data, handle):
            original(data, handle)
            written.set()
        client._win32_write = write
        call = asyncio.create_task(client.send_command({"cmd": "create_entity"}))
        await asyncio.wait_for(asyncio.to_thread(written.wait), 2)
        await asyncio.sleep(0.15)  # allow DLL to enqueue; do not poll/execute it
        self.ext("editor_paused")
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            await call
        self.ext("editor_ready")
        self.assertEqual(self.ext("poll"), "")

    async def test_oversized_command_fails_instead_of_truncating(self):
        client = await self.open_client()
        call = asyncio.create_task(client.send_command({"cmd": "set_attribute", "value": "x" * 12000}))
        for _ in range(100):
            self.assertEqual(self.ext("poll"), "")
            if call.done():
                break
            await asyncio.sleep(0.01)
        with self.assertRaisesRegex(RuntimeError, "output buffer"):
            await asyncio.wait_for(call, 2)

    async def test_reconnect_releases_slot_and_restores_roundtrip(self):
        client = await self.open_client()
        for _ in range(5):
            await client.reconnect()
            await asyncio.wait_for(client._ready.wait(), 4)
            call = asyncio.create_task(client.send_command({"cmd": "ping"}))
            await self.pump(1)
            self.assertTrue((await call)["ok"])

    async def test_disconnect_discards_old_queued_commands(self):
        client = await self.open_client()
        await asyncio.to_thread(client._win32_write, b'["stale","create_entity"]\n', client._handle)
        await asyncio.sleep(0.15)
        await client.reconnect()
        await asyncio.wait_for(client._ready.wait(), 4)
        self.assertEqual(self.ext("poll"), "", "Old client command reached new session")


class ClientRaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_reader_cannot_close_replacement_connection(self):
        client = BridgeClient()
        old, new = object(), object()
        client._handle = new
        client._connected = True
        future = asyncio.get_running_loop().create_future()
        client._pending["new"] = future
        with patch("win32file.CloseHandle") as close:
            await client._disconnect(old)
            close.assert_not_called()
        self.assertIs(client._handle, new)
        self.assertTrue(client.is_connected)
        self.assertFalse(future.done())

    async def test_old_reader_response_cannot_complete_new_request(self):
        client = BridgeClient()
        old, new = object(), object()
        client._handle = new
        future = asyncio.get_running_loop().create_future()
        client._pending["new"] = future
        await client._dispatch('["new","respond",[["ok",true]]]', old)
        self.assertFalse(future.done())

    async def test_shutdown_during_open_closes_eventual_handle(self):
        client = BridgeClient()
        started, release = threading.Event(), threading.Event()
        handle = object()
        def opening():
            started.set()
            release.wait(2)
            return handle
        with patch.object(client, "_win32_open", opening), patch("win32file.CloseHandle") as close:
            await client.__aenter__()
            await asyncio.wait_for(asyncio.to_thread(started.wait), 2)
            closing = asyncio.create_task(client.__aexit__())
            await asyncio.sleep(0.05)
            release.set()
            await asyncio.wait_for(closing, 2)
            close.assert_called_once_with(handle)
            self.assertFalse(client.is_connected)

    async def test_failed_write_disconnects_without_retry(self):
        client = BridgeClient()
        client._handle = object()
        client._connected = True
        with patch.object(client, "_win32_write", side_effect=BridgeNotConnectedError("closed")) as write, patch("win32file.CloseHandle"):
            with self.assertRaisesRegex(BridgeNotConnectedError, "not retried"):
                await client.send_command({"cmd": "create_entity"})
            write.assert_called_once()
        self.assertFalse(client.is_connected)
        self.assertEqual(client._pending, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
