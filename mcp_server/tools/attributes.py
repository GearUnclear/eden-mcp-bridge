from pydantic import TypeAdapter

from ..server import mcp, bridge
from ..bridge_client import BridgeCommandError
from ..models import EntityID, SetAttributeParams, GetAttributeParams, AttributeResult, AttributeWriteResult


def _pairs(pairs: list) -> dict:
    """Decode only a known SQF record; attribute array values remain untouched."""
    if not isinstance(pairs, list):
        raise ValueError("Invalid attribute record from bridge")
    result = {}
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
            raise ValueError("Invalid attribute record from bridge")
        if pair[0] in result:
            raise ValueError("Duplicate attribute record key from bridge")
        result[pair[0]] = pair[1]
    return result


def _identity(result: dict, entity_id: int) -> None:
    if result.get("ok") is not True:
        raise ValueError(result.get("error", "Attribute command failed"))
    actual = TypeAdapter(EntityID).validate_python(result.get("entity_id"))
    if actual != entity_id or not isinstance(result.get("entity_kind"), str) or not result["entity_kind"]:
        raise ValueError("Attribute response has mismatched or missing entity identity")


@mcp.tool()
async def set_attribute(params: SetAttributeParams) -> AttributeWriteResult:
    """Set a configured Eden property and return engine acceptance and readback.

    Infantry player/playable properties are ControlSP/ControlMP (bool); isPlayer
    and isPlayable are aliases. Name is the editor variable, Init is a string,
    rotation is [pitch,roll,yaw] degrees, and skill is a number in 0..1.
    Legacy azimut reads/sets yaw while preserving pitch and roll.
    Use get_supported_attributes to discover class-specific mod properties.
    ok means the engine accepted the write; verified means readback matched.
    """
    try:
        result = await bridge.send_command({
            "cmd": "set_attribute", "entity_id": params.entity_id,
            "attribute": params.attribute, "value": params.value,
        })
    except BridgeCommandError as exc:
        # Preserve an engine rejection with readback; validation errors remain
        # tool errors instead of inventing a mutation result that did not occur.
        if "engine_accepted" not in exc.result:
            raise
        result = exc.result
    if TypeAdapter(EntityID).validate_python(result.get("entity_id")) != params.entity_id:
        raise ValueError("Attribute write response has mismatched entity identity")
    for name in ("requested_value", "effective_value", "engine_accepted", "verified", "canonical_attribute"):
        if name not in result:
            raise ValueError(f"Attribute write response missing {name}")
    return AttributeWriteResult.model_validate(result)


@mcp.tool()
async def get_attribute(params: GetAttributeParams) -> AttributeResult:
    """Read one property; unwrap Eden's envelope but retain nested array values.

    Unknown names and properties unavailable for the resolved entity are errors.
    The result identifies the actual entity kind and canonical property.
    """
    result = await bridge.send_command({
        "cmd": "get_attribute", "entity_id": params.entity_id, "attribute": params.attribute,
    })
    _identity(result, params.entity_id)
    if "value" not in result or result.get("attribute") != params.attribute:
        raise ValueError("Attribute response missing value or requested attribute")
    return AttributeResult.model_validate(result)


@mcp.tool()
async def get_supported_attributes(entity_id: EntityID) -> dict:
    """Discover configured attribute properties/types for this entity kind/class.

    Includes inherited Cfg3DEN and class-specific mod attributes. Entries are
    configured candidates: UI conditions can make a property unavailable for
    this particular entity. UNKNOWN type requires a focused engine read.
    """
    entity_id = TypeAdapter(EntityID).validate_python(entity_id)
    result = await bridge.send_command({"cmd": "get_supported_attributes", "entity_id": entity_id})
    _identity(result, entity_id)
    entries = result.get("attributes")
    if not isinstance(entries, list):
        raise ValueError("Attribute discovery response missing attributes")
    return {
        **result, "attributes": [_pairs(entry) for entry in entries],
        "aliases": _pairs(result.get("aliases", [])),
    }


@mcp.tool()
async def get_all_attributes(entity_id: EntityID) -> dict:
    """Read configured attributes individually with explicit partial errors.

    Preserves false, zero, empty strings and empty arrays. Does not require the
    newer native bulk-attribute command. Discovery is bounded at 512 properties;
    conditional/mod attributes may report unavailable errors in a partial result.
    """
    entity_id = TypeAdapter(EntityID).validate_python(entity_id)
    result = await bridge.send_command({"cmd": "get_all_attributes", "entity_id": entity_id})
    _identity(result, entity_id)
    raw = result.get("attributes")
    if not isinstance(raw, list):
        raise ValueError("Attribute response missing attributes")
    attrs = _pairs(raw)
    return {**result, "count": len(attrs), "attributes": attrs,
            "errors": [_pairs(error) for error in result.get("errors", [])]}
