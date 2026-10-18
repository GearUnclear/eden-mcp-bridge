from ..server import mcp, bridge
from ..bridge_client import BridgeCommandError
from ..models import (
    CreateEntityParams, CreateEntityResult, DeleteEntityParams, MoveEntityParams,
    GroupEntitiesParams, OperationResult, PlacementResult, GroupEntitiesResult,
    CreateWaypointParams, WaypointResult, DescribeGroupParams, GroupDescription,
)

CREATE_OPTIONS = ("keep_crew", "group_id", "name", "azimuth")
WAYPOINT_OPTIONS = ("behaviour", "combat_mode", "speed", "formation", "completion_radius")


def _record(pairs: list) -> dict:
    """Decode one known SQF record; nested values remain untouched."""
    if not isinstance(pairs, list):
        raise ValueError("Invalid record from bridge")
    result = {}
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
            raise ValueError("Invalid record from bridge")
        if pair[0] in result:
            raise ValueError("Duplicate record key from bridge")
        result[pair[0]] = pair[1]
    return result


def _records(result: dict, key: str, required: bool = False) -> list[dict]:
    raw = result.get(key, None if required else [])
    if not isinstance(raw, list):
        raise ValueError(f"Bridge response missing {key} records")
    return [_record(item) for item in raw]


def _require_verified(attributes: list[dict], requested: list[str], what: str) -> None:
    verified = {a.get("attribute") for a in attributes if a.get("verified") is True}
    missing = [name for name in requested if name not in verified]
    if missing:
        raise ValueError(f"{what} response lacks verified readback for {', '.join(missing)}; inspect Eden")


@mcp.tool()
async def create_entity(params: CreateEntityParams) -> CreateEntityResult:
    """
    Create a new entity in the Arma 3 Eden Editor.

    Vehicles are created empty unless keep_crew=True; the response lists crew
    (entity_id, classname, role). group_id creates a man inside an existing
    group (group ID, or a member/vehicle ID); other classes are rejected and
    nothing is created. name and azimuth use set_attribute's validated write;
    a duplicate name is refused before creating, and a failed readback deletes
    everything the request created. group_id is the entity's editor group.

    Examples:
    - Place a BLUFOR MRAP at position [3000, 3000, 0]:
      entity_type='Vehicle', classname='B_MRAP_01_F', position=[3000,3000,0], side='WEST'
    - Place an OPFOR soldier:
      entity_type='Unit', classname='O_Soldier_F', position=[3100,3000,0], side='EAST'
    - Place a static object (no side needed):
      entity_type='Object', classname='Land_Cargo20_white_F', position=[2900,3000,0]
    - Crewed vehicle facing east: classname='B_MRAP_01_hmg_F', side='WEST', keep_crew=True, azimuth=90
    - Add a rifleman to group 45: entity_type='Unit', classname='B_Soldier_F', group_id=45, name='alpha_2'
    """
    position = params.position if len(params.position) == 3 else [*params.position, 0.0]
    cmd = {
        "cmd": "create_entity",
        "entity_type": params.entity_type,
        "classname": params.classname,
        "position": position,
        "placement_mode": params.placement_mode,
        **({"side": params.side} if params.side is not None else {}),
    }
    if params.keep_crew:
        cmd["keep_crew"] = True
    for key in ("group_id", "name", "azimuth"):
        if getattr(params, key) is not None:
            cmd[key] = getattr(params, key)
    result = await bridge.send_command(cmd)
    options = [key for key in CREATE_OPTIONS if key in cmd]
    if options and any(key not in result for key in ("group_id", "crew", "attributes")):
        raise ValueError(f"The installed addon ignored {', '.join(options)}; entity {result.get('entity_id')} "
                         "was created without them. Update the addon, then fix or delete that entity")
    attributes = _records(result, "attributes")
    _require_verified(attributes, [key for key in ("name", "azimuth") if key in cmd], "create_entity")
    return CreateEntityResult.model_validate({
        **result, "classname": result.get("classname", params.classname),
        "crew": _records(result, "crew"), "attributes": attributes,
    })


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


@mcp.tool()
async def create_waypoint(params: CreateWaypointParams) -> WaypointResult:
    """Append a data-only Eden waypoint to one group.

    entity_id is a group ID or a member/crewed-vehicle ID. Optional behaviour,
    combat_mode, speed, formation and completion_radius are written and read
    back; a mismatch deletes the waypoint and returns an error. Waypoint code
    (conditions, activation statements) is deliberately unsupported. verified
    refers to the created position; each attribute entry has its own flag.
    Use describe_group to read the resulting route.
    """
    position = params.position if len(params.position) == 3 else [*params.position, 0.0]
    cmd = {
        "cmd": "create_waypoint",
        "entity_id": params.entity_id,
        "position": position,
        "placement_mode": params.placement_mode,
        "waypoint_type": params.waypoint_type,
    }
    for key in WAYPOINT_OPTIONS:
        if getattr(params, key) is not None:
            cmd[key] = getattr(params, key)
    result = await bridge.send_command(cmd)
    if result.get("waypoint_type") != params.waypoint_type:
        raise ValueError("Waypoint response has mismatched or missing waypoint_type")
    attributes = _records(result, "attributes", required=True)
    _require_verified(attributes, [key for key in WAYPOINT_OPTIONS if key in cmd], "create_waypoint")
    return WaypointResult.model_validate({**result, "attributes": attributes})


@mcp.tool()
async def describe_group(params: DescribeGroupParams) -> GroupDescription:
    """Read a group's side, leader, members and waypoints without changing it.

    entity_id is a group ID or a member/crewed-vehicle ID. Members report
    variable name, vehicle_id (-1 on foot) and lowercase crew role. Waypoints
    are in runtime order; index 0 is usually the implicit start waypoint with
    waypoint_id -1. editor_membership_verified compares members with native
    Eden group links; errors lists fields that could not be read.
    """
    result = await bridge.send_command({"cmd": "describe_group", "entity_id": params.entity_id})
    return GroupDescription.model_validate({
        **result,
        "members": _records(result, "members", required=True),
        "waypoints": _records(result, "waypoints", required=True),
        "errors": _records(result, "errors"),
    })
