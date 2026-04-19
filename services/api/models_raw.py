"""
Исходный (source-of-truth) Blueprint: числовые поля геометрии могут быть строками с $-выражениями.

После ``finalize_resolved_blueprint`` (variables + assembly_mates) JSON приводится к ``ResolvedBlueprintPayload``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

try:
    from models import (
        BlueprintMetadata,
        GeometryPartMaterialFields,
        GlobalSettings,
        SimulationSection,
    )
except ModuleNotFoundError:  # тесты: PYTHONPATH=services → пакет api
    from api.models import (
        BlueprintMetadata,
        GeometryPartMaterialFields,
        GlobalSettings,
        SimulationSection,
    )

# --- Выражения и сырые операции ---

NumExpr = Union[float, int, str]
Tuple3Expr = tuple[NumExpr, NumExpr, NumExpr]
Points2DRaw = Annotated[list[tuple[NumExpr, NumExpr]], Field(min_length=3)]

RawHoleDepth = Union[Literal["through_all"], NumExpr]


class RawPartOperationHole(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["hole"]
    diameter: NumExpr
    depth: RawHoleDepth
    position: Tuple3Expr
    direction: Tuple3Expr


class RawPartOperationFillet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["fillet"]
    radius: NumExpr
    selector: str = Field(default="ALL", min_length=1)


class RawPartOperationChamfer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["chamfer"]
    length: NumExpr
    selector: str = Field(default="ALL", min_length=1)


class RawPartOperationLinearHolePattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["linear_pattern"]
    operation: RawPartOperationHole
    count_x: int = Field(ge=1)
    count_y: int = Field(ge=1)
    spacing_x: NumExpr
    spacing_y: NumExpr


class RawPartOperationCircularHolePattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["circular_pattern"]
    center: Tuple3Expr
    radius: NumExpr
    count: int = Field(ge=1)
    angle: NumExpr
    operation: RawPartOperationHole


RawPartOperation = Annotated[
    Union[
        RawPartOperationHole,
        RawPartOperationFillet,
        RawPartOperationChamfer,
        RawPartOperationLinearHolePattern,
        RawPartOperationCircularHolePattern,
    ],
    Field(discriminator="type"),
]


class RawGeometryPartMaterialFields(GeometryPartMaterialFields):
    """Как GeometryPartMaterialFields, но position/rotation допускают $-выражения."""

    model_config = ConfigDict(extra="forbid")

    position: Tuple3Expr | None = None
    rotation: Tuple3Expr | None = None


# --- Параметры деталей ---


class RawCylinderParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radius: NumExpr
    height: NumExpr


class RawBoxParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length: NumExpr
    width: NumExpr
    height: NumExpr


class RawSphereParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radius: NumExpr


class RawExtrudedProfileParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: Points2DRaw
    height: NumExpr


class RawRevolvedProfileParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: Points2DRaw
    angle: NumExpr


class RawFastenerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["bolt_hex", "nut_hex", "washer"]
    size: Literal["M6", "M8", "M10", "M12"]
    length: NumExpr | None = None
    fit: Literal["clearance", "tight"] = "clearance"


class RawBearingParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: str = Field(min_length=1)


class RawGearParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: NumExpr
    teeth: NumExpr
    thickness: NumExpr
    bore_diameter: NumExpr
    high_lod: bool = False


class RawGeometryPartCylinder(RawGeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["cylinder"]
    parameters: RawCylinderParams
    operations: list[RawPartOperation]


class RawGeometryPartBox(RawGeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["box"]
    parameters: RawBoxParams
    operations: list[RawPartOperation]


class RawGeometryPartSphere(RawGeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["sphere"]
    parameters: RawSphereParams
    operations: list[RawPartOperation]


class RawGeometryPartExtrudedProfile(RawGeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["extruded_profile"]
    parameters: RawExtrudedProfileParams
    operations: list[RawPartOperation]


class RawGeometryPartRevolvedProfile(RawGeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["revolved_profile"]
    parameters: RawRevolvedProfileParams
    operations: list[RawPartOperation]


class RawGeometryPartFastener(RawGeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["fastener"]
    parameters: RawFastenerParams
    operations: list[RawPartOperation]


class RawGeometryPartBearing(RawGeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["bearing"]
    parameters: RawBearingParams
    operations: list[RawPartOperation]


class RawGeometryPartGear(RawGeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["gear"]
    parameters: RawGearParams
    operations: list[RawPartOperation]


class RawGeometryPartCustomProfile(RawGeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["custom_profile"]
    parameters: dict[str, Any]
    operations: list[RawPartOperation]

    @field_validator("parameters")
    @classmethod
    def at_least_one_key(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) < 1:
            raise ValueError("custom_profile.parameters must contain at least one key")
        return v


RawGeometryPart = Annotated[
    Union[
        RawGeometryPartCylinder,
        RawGeometryPartBox,
        RawGeometryPartSphere,
        RawGeometryPartExtrudedProfile,
        RawGeometryPartRevolvedProfile,
        RawGeometryPartFastener,
        RawGeometryPartBearing,
        RawGeometryPartGear,
        RawGeometryPartCustomProfile,
    ],
    Field(discriminator="base_shape"),
]


# --- Assembly mates (raw: offset/value допускают $-строки до finalize) ---


class RawAssemblyMateSnapToOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["snap_to_operation"]
    source_part: str = Field(min_length=1)
    target_part: str = Field(min_length=1)
    target_operation_index: int = Field(ge=0)
    reverse_direction: bool = False


class RawAssemblyMateConcentric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["concentric"]
    source_part: str = Field(min_length=1)
    target_part: str = Field(min_length=1)
    target_operation_index: int = Field(ge=0)
    reverse_direction: bool = False


class RawAssemblyMateCoincident(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["coincident"]
    source_part: str = Field(min_length=1)
    target_part: str = Field(min_length=1)
    offset: NumExpr = 0.0
    flip: bool = False


class RawAssemblyMateDistance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["distance"]
    source_part: str = Field(min_length=1)
    target_part: str = Field(min_length=1)
    value: NumExpr


RawAssemblyMate = Annotated[
    Union[
        RawAssemblyMateSnapToOperation,
        RawAssemblyMateConcentric,
        RawAssemblyMateCoincident,
        RawAssemblyMateDistance,
    ],
    Field(discriminator="type"),
]


class RawGeometrySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parts: Annotated[list[RawGeometryPart], Field(min_length=0)]


GearboxCenterDistance = Union[Literal["auto"], NumExpr]


class RawGeneratorGearbox(BaseModel):
    """Высокоуровневый одноступенчатый редуктор (2 шестерни, 2 вала, mates)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["gearbox"]
    ratio: NumExpr
    module: NumExpr
    thickness: NumExpr
    bore_diameter: NumExpr
    center_distance: GearboxCenterDistance = "auto"
    high_lod: bool = False


class RawBlueprintPayload(BaseModel):
    """Source of truth: формулы в строках сохраняются при model_dump."""

    model_config = ConfigDict(extra="forbid")

    metadata: BlueprintMetadata
    global_variables: dict[str, float] | None = Field(
        default=None,
        description="Числовые константы (MVP); без ссылок между ключами.",
    )
    global_settings: GlobalSettings
    geometry: RawGeometrySection
    simulation: SimulationSection
    assembly_mates: list[RawAssemblyMate] | None = Field(
        default=None,
        description="Сборочные привязки (snap + v3.5 constraints); после резолва — числовой ResolvedBlueprintPayload.",
    )
    generators: list[RawGeneratorGearbox] | None = Field(
        default=None,
        description="Высокоуровневые генераторы (v4.3); expand до resolve.",
    )

    @model_validator(mode="after")
    def _parts_or_generators(self) -> RawBlueprintPayload:
        if self.generators and len(self.generators) > 0:
            return self
        if len(self.geometry.parts) < 1:
            raise ValueError(
                "geometry.parts: укажите хотя бы одну деталь или непустой generators (gearbox)"
            )
        return self


class JobCreateWithPrompt(BaseModel):
    """Тело POST /jobs при генерации из текста."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    current_blueprint: RawBlueprintPayload | None = None
