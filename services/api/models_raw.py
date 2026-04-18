"""
Исходный (source-of-truth) Blueprint: числовые поля геометрии могут быть строками с $-выражениями.

После ``resolve_blueprint_variables`` JSON приводится к ``ResolvedBlueprintPayload`` (только числа).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class RawGeometryPartCylinder(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["cylinder"]
    parameters: RawCylinderParams
    operations: list[RawPartOperation]


class RawGeometryPartBox(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["box"]
    parameters: RawBoxParams
    operations: list[RawPartOperation]


class RawGeometryPartSphere(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["sphere"]
    parameters: RawSphereParams
    operations: list[RawPartOperation]


class RawGeometryPartExtrudedProfile(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["extruded_profile"]
    parameters: RawExtrudedProfileParams
    operations: list[RawPartOperation]


class RawGeometryPartRevolvedProfile(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["revolved_profile"]
    parameters: RawRevolvedProfileParams
    operations: list[RawPartOperation]


class RawGeometryPartCustomProfile(GeometryPartMaterialFields):
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
        RawGeometryPartCustomProfile,
    ],
    Field(discriminator="base_shape"),
]


class RawGeometrySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parts: Annotated[list[RawGeometryPart], Field(min_length=1)]


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


class JobCreateWithPrompt(BaseModel):
    """Тело POST /jobs при генерации из текста."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    current_blueprint: RawBlueprintPayload | None = None
