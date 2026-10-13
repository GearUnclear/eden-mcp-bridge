from __future__ import annotations
from typing import Annotated, Any, Literal, Optional
from pydantic import BaseModel, BeforeValidator, Field
from .protocol import normalize_number


def _finite_number(value: Any) -> float:
    return float(normalize_number(value, "number"))


def _entity_id(value: Any) -> int:
    return normalize_number(value, "entity_id", integer_only=True, minimum=0, maximum=16777215)


EntityID = Annotated[int, BeforeValidator(_entity_id)]
FiniteNumber = Annotated[float, BeforeValidator(_finite_number)]
PlacementMode = Literal["ATL", "ASL", "terrain", "water"]


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class Position(BaseModel):
    x: float
    y: float
    z: float = 0.0

    def to_list(self) -> list[float]:
        return [self.x, self.y, self.z]


# ---------------------------------------------------------------------------
# Entity tools
# ---------------------------------------------------------------------------

class CreateEntityParams(BaseModel):
    entity_type: str = Field(
        description="Type of entity: 'Object', 'Vehicle', 'Unit', 'Group', 'Trigger', 'Waypoint', 'Logic', 'Marker'"
    )
    classname: str = Field(description="Arma 3 config class name, e.g. 'B_MRAP_01_F'")
    position: list[FiniteNumber] = Field(
        description="[x,y,z] in placement_mode; missing z is 0. ATL preserves height above terrain, ASL above sea level. Snapping is explicit.",
        min_length=2,
        max_length=3,
    )
    placement_mode: PlacementMode = "ATL"
    side: Optional[str] = Field(
        default=None,
        description="Side for units/vehicles: 'WEST', 'EAST', 'GUER', 'CIV'. Not needed for objects."
    )


class EntityRef(BaseModel):
    entity_id: EntityID = Field(description="3DEN internal entity ID")
    classname: str
    entity_kind: str | None = None
    position_atl: list[float] | None = None
    position_asl: list[float] | None = None
    placement_mode: str | None = None
    engine_accepted: bool | None = None
    verified: bool | None = None
    message: str = ""


class DeleteEntityParams(BaseModel):
    entity_id: EntityID = Field(description="3DEN entity ID to delete")


class MoveEntityParams(BaseModel):
    entity_id: EntityID
    position: list[FiniteNumber] = Field(min_length=2, max_length=3)
    placement_mode: PlacementMode = "ATL"


class GroupEntitiesParams(BaseModel):
    entity_ids: list[EntityID] = Field(
        description="Same-side on-foot infantry IDs to merge into one persistent Eden group (>=2). "
                    "The first id becomes the group leader unless 'leader' is set.",
        min_length=2,
    )
    leader: Optional[EntityID] = Field(
        default=None,
        description="Entity ID to force as the group leader. Defaults to the first id."
    )


# ---------------------------------------------------------------------------
# Attribute tools
# ---------------------------------------------------------------------------

class SetAttributeParams(BaseModel):
    entity_id: EntityID
    attribute: str = Field(description="3DEN attribute name, e.g. 'skill', 'health', 'fuel'")
    value: str | int | float | bool | list


class GetAttributeParams(BaseModel):
    entity_id: EntityID
    attribute: str


class AttributeResult(BaseModel):
    entity_id: int
    attribute: str
    value: str | int | float | bool | list | None
    canonical_attribute: str = ""
    entity_kind: str = ""
    classname: str = ""


# ---------------------------------------------------------------------------
# Selection tools
# ---------------------------------------------------------------------------

class GetSelectedParams(BaseModel):
    entity_type: str = Field(
        default="Object",
        description="Filter by type: 'Object', 'Group', 'Trigger', 'Waypoint', 'Marker', 'Layer'"
    )


class SelectedEntities(BaseModel):
    entities: list[EntityRef]


class EditorObject(BaseModel):
    """Full details of a single object placed in the Eden Editor."""
    entity_id: int
    classname: str = Field(description="Arma 3 config class, e.g. 'B_MRAP_01_F'.")
    position: list[float] = Field(description="ATL position [x, y, z]")
    position_asl: list[float] = Field(default_factory=list)
    direction: float = Field(description="Azimuth in degrees (0–360)")
    side: str = Field(description="'WEST', 'EAST', 'GUER', 'CIV', or 'UNKNOWN'")
    group_id: int = Field(description="Entity ID of the group this object belongs to. -1 if none.")
    description: str = Field(description="Editor label / description attribute")
    variable: str = Field(description="SQF variable name assigned in the editor")
    init: str = Field(description="Init code field")
    is_playable: bool
    is_player: bool = False
    is_leader: bool = Field(description="True if this unit is the group leader")
    skill: float = Field(description="Skill value 0–1. -1 if not applicable (vehicles, objects).")


class EditorObjectsPage(BaseModel):
    """Paginated response for get_all_editor_objects."""
    objects: list[EditorObject]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_more: bool
    errors: list[dict] = Field(default_factory=list)
    diagnostics: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Placeable-objects catalogue (CfgVehicles config database)
# ---------------------------------------------------------------------------

class PlaceableObject(BaseModel):
    """An object class available in the Eden Editor object browser."""
    classname: str = Field(description="Class name for create3DENEntity, e.g. 'B_MRAP_01_F'")
    display_name: str = Field(description="Human-readable name shown in Eden Editor")
    side: str = Field(description="CfgVehicles affiliation: EAST, WEST, GUER, CIV, NEUTRAL, ENEMY, FRIENDLY, LOGIC, EMPTY, AMBIENT, UNKNOWN; independent of empty placement")
    config_side: int | None = None
    faction: str = Field(description="Faction class, e.g. 'BLU_F', 'OPF_F'. Empty for buildings/objects.")
    vehicle_class: str = Field(description="Engine category: 'Air','Car','Tank','Man','Sea','Ship','StaticWeapon','Animal', or '' for buildings")
    editor_category: str = Field(description="Eden Editor main tab, e.g. 'EdCat_Side_BLUFOR'")
    editor_subcategory: str = Field(description="Eden Editor subcategory, e.g. 'EdSubcat_Wheeled'")


class PlaceableObjectsPage(BaseModel):
    objects: list[PlaceableObject]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_more: bool
    cache_size: int = Field(description="Total entries in the full unfiltered catalogue")


class PlaceableCategories(BaseModel):
    """Summary of available filter values for the placeable-objects catalogue."""
    vehicle_classes: list[str] = Field(description="All unique vehicle class values (Air, Car, Tank, Man, Sea, ...)")
    factions: list[str] = Field(description="All unique faction class names")
    sides: list[str] = Field(description="All unique side strings")
    editor_categories: list[str] = Field(description="All unique Eden Editor main categories")
    total_placeable: int = Field(description="Total number of placeable entries in the catalogue")


# ---------------------------------------------------------------------------
# Mission tools
# ---------------------------------------------------------------------------

class MissionInfo(BaseModel):
    name: str
    author: str
    terrain: str
    entity_count: int
    groups: int
    triggers: int
    waypoints: int


class SaveMissionParams(BaseModel):
    display_name: Optional[str] = Field(
        default=None,
        description="Display-name changes are unsupported; omit this field to request a scenario save"
    )


class OperationResult(BaseModel):
    ok: bool
    message: str = ""


class AttributeWriteResult(OperationResult):
    entity_id: int
    attribute: str
    canonical_attribute: str = ""
    entity_kind: str = ""
    classname: str = ""
    requested_value: Any = None
    effective_value: Any = None
    engine_accepted: bool = False
    verified: bool = False
    error: str | None = None


class PlacementResult(OperationResult):
    entity_id: int
    entity_kind: str = ""
    position_atl: list[float] = Field(default_factory=list)
    position_asl: list[float] = Field(default_factory=list)
    placement_mode: str = "ATL"
    engine_accepted: bool = False
    verified: bool = False


class GroupEntitiesResult(OperationResult):
    status: str = ""
    group_id: int = -1
    leader_id: int = -1
    member_ids: list[int] = Field(default_factory=list)
    count: int = 0
    editor_verified: bool = False
    persistence_verified: bool = False


class SaveMissionResult(OperationResult):
    status: str
    save_requested: bool = False
    persistence_verified: bool = False
    manual_action_required: bool = True


class UndoResult(OperationResult):
    status: str
    undo_requested: bool = False
    undo_observed: bool = False
    action_scope: str = "editor_global"
    action_identity: str = "unknown"
