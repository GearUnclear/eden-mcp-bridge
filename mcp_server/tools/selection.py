import math
from typing import Annotated

from pydantic import Field, TypeAdapter
from ..server import mcp, bridge
from ..models import EntityID, GetSelectedParams, SelectedEntities, EntityRef, EditorObject, EditorObjectsPage

PageNumber = Annotated[int, Field(strict=True, ge=0, le=16777215)]
PageSize = Annotated[int, Field(strict=True, ge=1, le=100)]
PageBudget = Annotated[int, Field(strict=True, ge=1, le=200)]


def _pairs_to_dict(pairs: list) -> dict:
    """Decode a known SQF record without modifying nested array values."""
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


@mcp.tool()
async def get_selected_entities(params: GetSelectedParams) -> SelectedEntities:
    """Return Eden entities currently selected by the user."""
    result = await bridge.send_command({"cmd": "get_selected", "entity_type": params.entity_type})
    return SelectedEntities(entities=[EntityRef.model_validate(_pairs_to_dict(e)) for e in result.get("entities", [])])


@mcp.tool()
async def list_all_entities(entity_type: str = "Object") -> SelectedEntities:
    """List entity IDs and classnames; use object pages for full details."""
    result = await bridge.send_command({"cmd": "list_entities", "entity_type": entity_type})
    return SelectedEntities(entities=[EntityRef.model_validate(_pairs_to_dict(e)) for e in result.get("entities", [])])


def _parse_editor_object(raw: list) -> EditorObject:
    """Reject malformed required fields rather than inventing IDs/coordinates."""
    data = _pairs_to_dict(raw)
    for field in ("position", "position_asl"):
        values = data.get(field)
        if (not isinstance(values, list) or len(values) != 3
                or any(isinstance(v, bool) or not isinstance(v, (float, int))
                       or not math.isfinite(v) for v in values)):
            raise ValueError(f"Object response has invalid {field}")
    data["entity_id"] = TypeAdapter(EntityID).validate_python(data.get("entity_id"))
    if data.get("group_id") != -1:
        data["group_id"] = TypeAdapter(EntityID).validate_python(data.get("group_id"))
    for field in ("direction", "skill"):
        value = data.get(field)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError(f"Object response has invalid {field}")
    for field in ("is_player", "is_playable", "is_leader"):
        if not isinstance(data.get(field), bool):
            raise ValueError(f"Object response has invalid {field}")
    return EditorObject.model_validate(data, strict=True)


def _page_bounds(page: int, page_size: int) -> tuple[int, int]:
    page = TypeAdapter(Annotated[int, Field(strict=True, ge=0, le=16777215)]).validate_python(page)
    page_size = TypeAdapter(Annotated[int, Field(strict=True, ge=1, le=100)]).validate_python(page_size)
    return page, page_size


@mcp.tool()
async def get_all_editor_objects(page: PageNumber = 0, page_size: PageSize = 50) -> EditorObjectsPage:
    """Read one bounded object page with ATL and ASL positions and error details.

    page must be >=0 and page_size in 1..100. Includes canonical player/playable,
    Name, Init and rotation yaw. errors identify unsupported optional fields or
    failed rows; diagnostics report handler completion/timing. An oversized
    response is an explicit error: retry a smaller page or a focused read.
    """
    page, page_size = _page_bounds(page, page_size)
    result = await bridge.send_command({"cmd": "get_all_objects", "page": page, "page_size": page_size})
    if result.get("ok") is not True:
        raise ValueError(result.get("error", "Object page failed"))
    if result.get("page") != page or result.get("page_size") != page_size:
        raise ValueError("Object response has mismatched page identity")
    objects = result.get("objects")
    if not isinstance(objects, list) or len(objects) > page_size:
        raise ValueError("Object response has invalid page contents")
    errors = [_pairs_to_dict(error) for error in result.get("errors", [])]
    parsed = EditorObjectsPage.model_validate({
        **result, "objects": [_parse_editor_object(raw) for raw in objects],
        "errors": errors, "diagnostics": _pairs_to_dict(result.get("diagnostics", [])),
    }, strict=True)
    expected_pages = math.ceil(parsed.total / page_size)
    if (parsed.total < 0 or parsed.total_pages != expected_pages
            or parsed.has_more != (page + 1 < expected_pages)):
        raise ValueError("Object response has inconsistent pagination")
    return parsed


@mcp.tool()
async def get_all_editor_objects_full(max_pages: PageBudget = 200) -> list[EditorObject]:
    """Read up to max_pages (default 200) and fail explicitly on partial results.

    This convenience helper has a finite page budget, detects duplicate IDs and
    changes in total count, and never returns a partial list as complete. Pages
    are not an atomic editor snapshot; keep the mission unchanged during reads.
    Prefer manual pages when inspecting a large mission or per-entity errors.
    """
    max_pages = TypeAdapter(Annotated[int, Field(strict=True, ge=1, le=200)]).validate_python(max_pages)
    all_objects: list[EditorObject] = []
    seen: set[int] = set()
    total = None
    for page in range(max_pages):
        result = await get_all_editor_objects(page=page, page_size=50)
        if result.errors:
            raise ValueError(f"Object page {page} has per-entity errors; use get_all_editor_objects to inspect them")
        if total is not None and result.total != total:
            raise ValueError("Mission entity count changed during paginated read; retry with the editor unchanged")
        total = result.total
        for obj in result.objects:
            if obj.entity_id in seen:
                raise ValueError("Repeated entity ID across object pages; retry with the editor unchanged")
            seen.add(obj.entity_id)
        all_objects.extend(result.objects)
        if not result.has_more:
            if len(all_objects) != total:
                raise ValueError("Incomplete object read; use manual pages to inspect failures")
            return all_objects
        if not result.objects:
            raise ValueError("Object pagination made no progress")
    raise ValueError(f"Object read exceeded {max_pages} pages; use manual pagination")
