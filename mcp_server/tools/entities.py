from ..server import mcp, bridge
from ..bridge_client import BridgeCommandError
from ..models import (
    CreateEntityParams, EntityRef, DeleteEntityParams, MoveEntityParams,
    GroupEntitiesParams, OperationResult, PlacementResult, GroupEntitiesResult,
)


@mcp.tool()
async def create_entity(params: CreateEntityParams) -> EntityRef:
    """
    Create a new entity in the Arma 3 Eden Editor.

    Examples:
    - Place a BLUFOR MRAP at position [3000, 3000, 0]:
      entity_type='Vehicle', classname='B_MRAP_01_F', position=[3000,3000,0], side='WEST'
    - Place an OPFOR soldier:
      entity_type='Unit', classname='O_Soldier_F', position=[3100,3000,0], side='EAST'
    - Place a static object (no side needed):
      entity_type='Object', classname='Land_Cargo20_white_F', position=[2900,3000,0]
    """
    position = params.position if len(params.position) == 3 else [*params.position, 0.0]
    result = await bridge.send_command({
        "cmd": "create_entity",
        "entity_type": params.entity_type,
        "classname": params.classname,
        "position": position,
        "placement_mode": params.placement_mode,
        **({"side": params.side} if params.side is not None else {}),
    })
    return EntityRef(**{**result, "classname": result.get("classname", params.classname)})


@mcp.tool()
async def delete_entity(params: DeleteEntityParams) -> OperationResult:
    """Delete an entity from the Eden Editor by its entity ID."""
    result = await bridge.send_command({
        "cmd": "delete_entity",
        "entity_id": params.entity_id,
    })
    return OperationResult(ok=result.get("ok", False), message=result.get("message", ""))


@mcp.tool()
async def move_entity(params: MoveEntityParams) -> PlacementResult:
    """Move in explicit ATL/ASL coordinates, or snap to terrain/water with a z offset. Returns verified final ATL and ASL positions."""
    position = params.position if len(params.position) == 3 else [*params.position, 0.0]
    try:
        result = await bridge.send_command({
            "cmd": "move_entity",
            "entity_id": params.entity_id,
            "position": position,
            "placement_mode": params.placement_mode,
        })
    except BridgeCommandError as exc:
        if "verified" not in exc.result:
            raise
        result = exc.result
    return PlacementResult(**result)


@mcp.tool()
async def group_entities(params: GroupEntitiesParams) -> GroupEntitiesResult:
    """Merge same-side on-foot infantry into the requested leader's Eden group.

    The requested leader (default first ID) must already lead its source group.
    Include every member of source groups; source routes and external connections
    are rejected to avoid losing editor state. The target group's routes remain.
    Returns observed membership/leader IDs; save/reload persistence needs engine
    acceptance. Vehicle/crew grouping is currently unsupported.
    """
    cmd = {
        "cmd": "group_entities",
        "entity_ids": params.entity_ids,
    }
    if params.leader is not None:
        cmd["leader"] = params.leader
    try:
        result = await bridge.send_command(cmd)
    except BridgeCommandError as exc:
        if "status" not in exc.result:
            raise
        result = exc.result
    return GroupEntitiesResult(**result)
