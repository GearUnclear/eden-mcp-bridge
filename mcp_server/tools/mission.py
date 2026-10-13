import asyncio
from ..server import mcp, bridge
from ..models import MissionInfo, SaveMissionParams, SaveMissionResult, UndoResult, OperationResult
from ..bridge_client import BridgeCommandError


@mcp.tool()
async def get_mission_info() -> MissionInfo:
    """
    Return general information about the current mission open in Eden Editor:
    name, author, terrain, entity counts, etc.
    """
    result = await bridge.send_command({"cmd": "get_mission_info"})
    return MissionInfo(
        name=result.get("name", ""),
        author=result.get("author", ""),
        terrain=result.get("terrain", ""),
        entity_count=result.get("entity_count", 0),
        groups=result.get("groups", 0),
        triggers=result.get("triggers", 0),
        waypoints=result.get("waypoints", 0),
    )


@mcp.tool()
async def save_mission(params: SaveMissionParams) -> SaveMissionResult:
    """Request Eden's scenario save; disk persistence requires manual verification.

    New scenarios may open Save As, which must be completed in Eden. A request
    alone returns ok=false and persistence_verified=false. Display-name changes
    are unsupported and rejected before requesting a save.
    """
    if params.display_name is not None:
        return SaveMissionResult(
            ok=False, status="unsupported_display_name",
            message="display_name updates are unsupported; edit the scenario title in Eden before saving",
        )
    try:
        result = await bridge.send_command({"cmd": "save_mission"})
    except BridgeCommandError as exc:
        result = exc.result
    verified = result.get("persistence_verified") is True
    message = result.get("error", "No disk persistence confirmation was returned; verify the scenario in Eden")
    if "status" in result:
        message = result.get("message", message)
    return SaveMissionResult(
        ok=result.get("ok") is True and verified,
        status=result.get("status", "save_unconfirmed"),
        save_requested=result.get("save_requested") is True,
        persistence_verified=verified,
        manual_action_required=result.get("manual_action_required", True),
        message=message,
    )


@mcp.tool()
async def clear_mission() -> OperationResult:
    """
    Delete ALL entities currently placed in the Eden Editor mission.
    This action is undoable with Ctrl+Z inside the editor.
    Returns the number of removed entities.
    """
    result = await bridge.send_command({"cmd": "clear_mission"})
    removed = result.get("removed", 0)
    return OperationResult(ok=result.get("ok", True), message=f"Removed {removed} entities")


@mcp.tool()
async def undo_last_action() -> UndoResult:
    """Request Undo on Eden's global history, which includes manual editor edits.

    ok=true means Eden emitted an immediate OnUndo event. Unobserved requests
    are unconfirmed, including empty or unavailable history. The bridge cannot
    identify the reverted operation or guarantee a rollback of an MCP edit.
    """
    try:
        result = await bridge.send_command({"cmd": "undo"})
    except BridgeCommandError as exc:
        result = exc.result
    observed = result.get("undo_observed") is True
    message = result.get("error", "No undo event confirmation was returned; inspect Eden before retrying")
    if "status" in result:
        message = result.get("message", message)
    return UndoResult(
        ok=result.get("ok") is True and observed,
        status=result.get("status", "undo_unconfirmed"),
        undo_requested=result.get("undo_requested") is True,
        undo_observed=observed,
        action_scope=result.get("action_scope", "editor_global"),
        action_identity=result.get("action_identity", "unknown"),
        message=message,
    )


@mcp.tool()
async def get_bridge_status() -> dict:
    """
    Check whether the Arma 3 bridge is connected and the Eden Editor is open.
    Use this first to confirm connectivity before issuing other commands.
    """
    if not bridge.is_connected:
        return {"connected": False, "pipe_open": False, "last_error": bridge.last_error,
                "message": "Pipe not connected. Open Eden with @ArmaDevBridge loaded. If the pipe is busy (Windows error 231), another MCP client owns it; disconnect that client first."}
    # Pipe is open â€” attempt a round-trip ping with short timeout
    try:
        result = await asyncio.wait_for(bridge.send_command({"cmd": "ping"}), timeout=3.0)
        return {"connected": True, "pipe_open": True, "editor_open": result.get("editor_open", False), "version": result.get("version", ""),
                "message": "Ready" if result.get("editor_open", False) else "Bridge is alive; return from Preview to Eden to resume editing."}
    except (TimeoutError, asyncio.TimeoutError):
        return {"connected": False, "pipe_open": True, "message": "Pipe connected but SQF not responding. Return to Eden; try reconnect_bridge if it stays unresponsive. Check Arma log for errors."}
    except Exception as exc:
        return {"connected": False, "pipe_open": True, "message": str(exc)}


@mcp.tool()
async def reconnect_bridge() -> dict:
    """Reconnect this MCP client's pipe without restarting Arma or replaying commands.

    Pending calls fail; inspect editor state before retrying any edit. This cannot
    take a pipe owned by another MCP client (such as another editor client session).
    """
    await bridge.reconnect()
    return await get_bridge_status()
