"""
Async named-pipe client that communicates with the Arma 3 bridge DLL.

Protocol: newline-delimited over a Windows named pipe.
- Requests:  SQF array notation  ["id","cmd","key1",val1,...]   (also valid JSON)
- Responses: SQF array notation  ["id","respond",[["key",val],...]]

Uses win32file for reliable named-pipe I/O on Windows.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from collections.abc import Callable, Awaitable
from typing import Any

import time

from .protocol import build_sqf_payload, sqf_value

import win32file
import win32pipe
import pywintypes

log = logging.getLogger(__name__)
_dbg = log.debug  # lightweight alias used throughout

PIPE_NAME = os.environ.get("ARMA3_BRIDGE_PIPE", r"\\.\pipe\arma3_mcp_bridge")
TIMEOUT = float(os.environ.get("ARMA3_BRIDGE_TIMEOUT", "30"))
RECONNECT_INTERVAL = 2.0


class BridgeNotConnectedError(RuntimeError):
    pass


class BridgeCommandError(RuntimeError):
    """Rejected command with its complete diagnostic response retained."""

    def __init__(self, result: dict) -> None:
        self.result = result
        super().__init__(result.get("error") or result.get("message") or "Command rejected by Arma 3")


class BridgeClient:
    def __init__(self) -> None:
        self._handle: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: dict[str, asyncio.Future[dict]] = {}
        self._event_handlers: dict[str, list[Callable[[dict], Awaitable[None]]]] = {}
        self._connected = False
        self._last_error: str = ""
        self._reconnect_task: asyncio.Task | None = None
        self._write_lock = threading.Lock()
        self._connect_lock: asyncio.Lock | None = None  # initialised in __aenter__
        self._ready = asyncio.Event()
        self._closing = False
        self._read_thread: threading.Thread | None = None

    async def __aenter__(self) -> "BridgeClient":
        self._closing = False
        self._connect_lock = asyncio.Lock()
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        return self

    async def __aexit__(self, *_: Any) -> None:
        self._closing = True
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        await self._disconnect()
        if self._read_thread:
            await asyncio.to_thread(self._read_thread.join, 1.0)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def last_error(self) -> str:
        return self._last_error

    async def reconnect(self) -> bool:
        """Release our own pipe and reconnect; never replay an editor command."""
        await self._disconnect()
        await self._try_connect()
        if not self.is_connected and self._reconnect_task and not self._closing:
            try:
                await asyncio.wait_for(self._ready.wait(), RECONNECT_INTERVAL + 0.5)
            except asyncio.TimeoutError:
                pass
        return self.is_connected

    async def send_command(self, cmd: dict) -> dict:
        if not self._connected and not self._closing and self._reconnect_task:
            try:
                await asyncio.wait_for(self._ready.wait(), RECONNECT_INTERVAL + 0.5)
            except asyncio.TimeoutError:
                pass
        if not self._connected or self._handle is None:
            raise BridgeNotConnectedError(
                "No connection to Arma 3 bridge. Is Arma 3 running with @ArmaDevBridge loaded?"
            )
        request_id = str(uuid.uuid4())
        future: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        handle = self._handle
        try:
            payload = self._build_sqf_payload(cmd, request_id)
            _dbg(f"send_command: writing payload {payload!r}")
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, self._win32_write, payload, handle)
            except (pywintypes.error, BridgeNotConnectedError) as exc:
                self._last_error = str(exc)
                await self._disconnect(handle)
                raise BridgeNotConnectedError("Bridge disconnected while sending; command was not retried") from exc
            _dbg(f"send_command: write done, awaiting future for {request_id[:8]}")
            return await asyncio.wait_for(future, timeout=TIMEOUT)
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"No response for {cmd.get('cmd', 'unknown')} from Arma 3 after {TIMEOUT}s. "
                "The command may have partially applied; inspect editor state before retrying. "
                "Check Eden's bridge diagnostics for the command and stage."
            )
        finally:
            self._pending.pop(request_id, None)
            if future.done() and not future.cancelled():
                future.exception()  # consume a disconnect error after a failed write

    def on_event(self, event_name: str, handler: Callable[[dict], Awaitable[None]]) -> None:
        self._event_handlers.setdefault(event_name, []).append(handler)

    # ------------------------------------------------------------------
    # SQF serialisation
    # ------------------------------------------------------------------

    def _sqf_val(self, val: Any) -> str:
        return sqf_value(val)

    def _build_sqf_payload(self, cmd: dict, request_id: str) -> bytes:
        return build_sqf_payload(cmd, request_id)

    # ------------------------------------------------------------------
    # win32file I/O
    # ------------------------------------------------------------------

    def _win32_write(self, data: bytes, handle: Any) -> None:
        with self._write_lock:
            if handle is None or self._handle is not handle:
                raise BridgeNotConnectedError("Pipe changed before write")
            win32file.WriteFile(handle, data)

    def _win32_read_loop(self, handle: Any, loop: asyncio.AbstractEventLoop) -> None:
        # Use PeekNamedPipe to avoid blocking ReadFile while WriteFile may be
        # pending on the same synchronous handle (Windows serialises per-handle).
        buf = b""
        _dbg("read_loop: started")
        try:
            while self._connected and self._handle is handle:
                try:
                    _, avail, _ = win32pipe.PeekNamedPipe(handle, 0)
                    if avail == 0:
                        time.sleep(0.01)
                        continue
                    _dbg(f"read_loop: {avail} bytes available, reading...")
                    _, data = win32file.ReadFile(handle, min(avail, 4096))
                    _dbg(f"read_loop: ReadFile returned {len(data)} bytes: {data!r}")
                    if not data:
                        break
                    buf += data
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.strip()
                        if line:
                            decoded = line.decode("utf-8", errors="replace")
                            _dbg(f"read_loop: dispatching {decoded!r}")
                            asyncio.run_coroutine_threadsafe(self._dispatch(decoded, handle), loop)
                except pywintypes.error as e:
                    _dbg(f"read_loop: pywintypes error {e}")
                    log.warning("Arma 3 bridge read error: %s", e)
                    if self._handle is handle:
                        self._last_error = str(e)
                    break
        finally:
            _dbg("read_loop: exiting, calling disconnect")
            asyncio.run_coroutine_threadsafe(self._disconnect(handle), loop)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def _reconnect_loop(self) -> None:
        while not self._closing:
            if not self._connected:
                await self._try_connect()
            await asyncio.sleep(RECONNECT_INTERVAL)

    async def _try_connect(self) -> None:
        if self._connect_lock is None:
            return
        async with self._connect_lock:
            if self._connected or self._closing:
                return
            try:
                loop = asyncio.get_running_loop()
                opening = loop.run_in_executor(None, self._win32_open)
                try:
                    handle = await asyncio.shield(opening)
                except asyncio.CancelledError:
                    # Opening happens on a worker thread. Cancellation must not
                    # leave its eventual handle holding the DLL's only slot.
                    try:
                        handle = await opening
                        win32file.CloseHandle(handle)
                    except Exception:
                        pass
                    raise
                self._handle = handle
                self._loop = loop
                self._connected = True
                self._last_error = ""
                self._ready.set()
                _dbg(f"_try_connect: connected, handle={handle}")
                log.info("Connected to Arma 3 bridge at %s", PIPE_NAME)
                t = threading.Thread(target=self._win32_read_loop, args=(handle, loop), daemon=True)
                t.start()
                self._read_thread = t
            except pywintypes.error as exc:
                self._last_error = str(exc)
                log.debug("Pipe not available yet: %s", exc)
            except Exception as exc:
                self._last_error = str(exc)
                log.debug("Connect failed: %s", exc)

    def _win32_open(self) -> Any:
        return win32file.CreateFile(
            PIPE_NAME,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0, None,
            win32file.OPEN_EXISTING,
            0, None
        )

    async def _disconnect(self, expected_handle: Any = None) -> None:
        # An old reader can finish after a replacement connection is installed.
        # It must never close that new connection or fail its pending requests.
        if expected_handle is not None and self._handle is not expected_handle:
            return
        self._connected = False
        self._ready.clear()
        handle = self._handle
        self._handle = None
        self._loop = None
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(BridgeNotConnectedError("Bridge disconnected"))
        self._pending.clear()
        if handle is not None:
            await asyncio.to_thread(self._close_handle, handle)

    def _close_handle(self, handle: Any) -> None:
        # Waiting on a writer must not block the asyncio event loop.
        with self._write_lock:
            try:
                win32file.CloseHandle(handle)
            except Exception:
                pass

    async def _dispatch(self, raw: str, expected_handle: Any = None) -> None:
        if expected_handle is not None and self._handle is not expected_handle:
            return
        _dbg(f"_dispatch called with: {raw!r}")
        if not raw:
            return
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            _dbg(f"_dispatch: JSON parse error for {raw!r}")
            log.warning("Non-JSON from bridge: %r", raw)
            return

        # SQF array response: ["id", "respond", [["key", val], ...]]
        if not isinstance(msg, list) or not msg:
            _dbg(f"_dispatch: bad format: {msg}")
            log.debug("Unhandled bridge message: %s", msg)
            return

        msg_id = msg[0]
        _dbg(f"_dispatch: msg_id={msg_id!r}, pending keys={list(self._pending.keys())}")
        if not isinstance(msg_id, str) or msg_id not in self._pending:
            _dbg(f"_dispatch: unmatched id {msg_id!r}")
            log.debug("Unmatched response id: %s", msg_id)
            return

        fut = self._pending.pop(msg_id)
        if fut.done():
            return
        if len(msg) != 3 or msg[1] != "respond" or not isinstance(msg[2], list):
            fut.set_exception(BridgeCommandError({"ok": False, "error": "Malformed bridge response envelope"}))
            return
        result: dict = {}
        result_pairs = msg[2]
        for pair in result_pairs:
            if (not isinstance(pair, list) or len(pair) != 2
                    or not isinstance(pair[0], str) or pair[0] in result):
                fut.set_exception(BridgeCommandError({"ok": False, "error": "Malformed or duplicate bridge response field"}))
                return
            result[pair[0]] = pair[1]
        if not isinstance(result.get("ok"), bool):
            fut.set_exception(BridgeCommandError({"ok": False, "error": "Bridge response requires explicit boolean ok"}))
        elif result["ok"]:
            fut.set_result(result)
        else:
            fut.set_exception(BridgeCommandError(result))
