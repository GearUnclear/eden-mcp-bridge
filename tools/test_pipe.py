"""
test_pipe.py – Named pipe smoke test.

Simulates the Arma 3 bridge DLL by acting as the pipe SERVER,
then tests the Python MCP bridge_client against it.

Run:  python tools/test_pipe.py
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

PIPE_NAME = r"\\.\pipe\arma3_mcp_bridge"

# ---------------------------------------------------------------------------
# Fake DLL: pipe server that handles a few known commands
# ---------------------------------------------------------------------------

def make_sqf_response(request_id: str, pairs: list) -> str:
    """Build the SQF array notation that the real DLL would return to Python."""
    # The DLL converts outbound messages to JSON for the Python side
    result = {k: v for k, v in pairs}
    return json.dumps({"id": request_id, "ok": result.get("ok", True), "result": result})


async def fake_dll_server():
    """Listens on the named pipe and returns canned responses."""
    import win32pipe  # type: ignore
    import win32file  # type: ignore
    import pywintypes  # type: ignore

    print(f"[fake DLL] Creating pipe at {PIPE_NAME}")
    pipe = win32pipe.CreateNamedPipe(
        PIPE_NAME,
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
        1, 65536, 65536, 0, None
    )

    print("[fake DLL] Waiting for client...")
    win32pipe.ConnectNamedPipe(pipe, None)
    print("[fake DLL] Client connected!")

    buf = b""
    while True:
        try:
            _, data = win32file.ReadFile(pipe, 65536)
            buf += data
        except pywintypes.error:
            break

        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            req_id = msg.get("id", str(uuid.uuid4()))
            cmd = msg.get("cmd", "")

            print(f"[fake DLL] Received: cmd={cmd!r} id={req_id!r}")

            # Build response
            if cmd == "ping":
                resp = {"id": req_id, "ok": True, "result": {"editor_open": True, "version": "test"}}
            elif cmd == "create_entity":
                resp = {"id": req_id, "ok": True, "result": {"entity_id": 9001, "classname": msg.get("classname", "")}}
            elif cmd == "get_mission_info":
                resp = {"id": req_id, "ok": True, "result": {
                    "name": "Test Mission", "author": "Test",
                    "terrain": "Altis", "entity_count": 5,
                    "groups": 2, "triggers": 1, "waypoints": 3
                }}
            elif cmd == "poll":
                resp = None  # poll is handled inline in the DLL; not sent over pipe
            else:
                resp = {"id": req_id, "ok": True, "result": {"message": f"ack:{cmd}"}}

            if resp:
                payload = json.dumps(resp) + "\n"
                win32file.WriteFile(pipe, payload.encode())
                print(f"[fake DLL] Sent response for {cmd!r}")

    win32file.CloseHandle(pipe)
    print("[fake DLL] Closed.")


# ---------------------------------------------------------------------------
# Client side: use the real BridgeClient
# ---------------------------------------------------------------------------

async def run_tests():
    from mcp_server.bridge_client import BridgeClient

    client = BridgeClient()
    async with client:
        # Give the reconnect loop a moment to connect
        for _ in range(20):
            if client.is_connected:
                break
            await asyncio.sleep(0.2)

        if not client.is_connected:
            print("FAIL: BridgeClient did not connect within 4 seconds")
            return False

        print("\n[test] Connected to fake DLL")

        # Test 1: ping
        result = await client.send_command({"cmd": "ping"})
        assert result.get("editor_open") is True, f"ping failed: {result}"
        print("[test] PASS: ping")

        # Test 2: create_entity
        result = await client.send_command({
            "cmd": "create_entity",
            "entity_type": "Vehicle",
            "classname": "B_MRAP_01_F",
            "position": [3000, 3000, 0],
            "side": "WEST",
        })
        assert result.get("entity_id") == 9001, f"create_entity failed: {result}"
        print("[test] PASS: create_entity")

        # Test 3: get_mission_info
        result = await client.send_command({"cmd": "get_mission_info"})
        assert result.get("terrain") == "Altis", f"get_mission_info failed: {result}"
        print("[test] PASS: get_mission_info")

        print("\nAll tests passed!")
        return True


async def main():
    # Run the fake DLL server and test client concurrently
    # (We need pywin32 for the server side; if not installed, skip)
    try:
        import win32pipe  # noqa: F401
    except ImportError:
        print("pywin32 not installed. Install with: pip install pywin32")
        print("Testing with a simple asyncio pipe echo server instead...")
        await run_simple_test()
        return

    server_task = asyncio.create_task(fake_dll_server())
    await asyncio.sleep(0.3)  # give server time to create pipe

    success = await run_tests()
    server_task.cancel()
    sys.exit(0 if success else 1)


async def run_simple_test():
    """Minimal connectivity test without pywin32."""
    from mcp_server.bridge_client import BridgeClient, BridgeNotConnectedError
    client = BridgeClient()
    async with client:
        await asyncio.sleep(0.5)
        if client.is_connected:
            print("Unexpectedly connected (is Arma 3 running?). Running live tests...")
            result = await client.send_command({"cmd": "ping"})
            print(f"Live ping result: {result}")
        else:
            try:
                await client.send_command({"cmd": "ping"})
            except BridgeNotConnectedError as e:
                print(f"PASS: Got expected BridgeNotConnectedError: {e}")


if __name__ == "__main__":
    asyncio.run(main())
