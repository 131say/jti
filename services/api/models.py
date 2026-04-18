"""Pydantic v2 модели Blueprint v1.0–v2.0 (v2.0: опционально global_variables после резолвера)."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Metadata & global ---


class BlueprintMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    schema_version: Literal["1.0", "1.1", "1.2", "1.3", "1.4", "2.0"]


class GlobalSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    units: Literal["mm", "m", "in"]
    up_axis: Literal["X", "Y", "Z"]


# --- Geometry: operations ---

HoleDepth = Union[Annotated[float, Field(gt=0)], Literal["through_all"]]


class PartOperationHole(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["hole"]
    diameter: float = Field(gt=0)
    depth: HoleDepth
    position: tuple[float, float, float]
    direction: tuple[float, float, float]


class PartOperationFillet(BaseModel):
    """Скругление рёбер (CadQuery `edges(...).fillet`)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["fillet"]
    radius: float = Field(gt=0)
    selector: str = Field(default="ALL", min_length=1)


class PartOperationChamfer(BaseModel):
    """Фаска на рёбрах (CadQuery `edges(...).chamfer`)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["chamfer"]
    length: float = Field(gt=0)
    selector: str = Field(default="ALL", min_length=1)


class PartOperationLinearHolePattern(BaseModel):
    """Линейный массив отверстий (сетка в плоскости XY от базовой position дочернего hole)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["linear_pattern"]
    operation: PartOperationHole
    count_x: int = Field(ge=1)
    count_y: int = Field(ge=1)
    spacing_x: float
    spacing_y: float


class PartOperationCircularHolePattern(BaseModel):
    """Круговой массив отверстий; поле position у дочернего hole игнорируется."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["circular_pattern"]
    center: tuple[float, float, float]
    radius: float = Field(gt=0)
    count: int = Field(ge=1)
    angle: float = Field(gt=0, description="Полный угол разворота в градусах (например 360).")
    operation: PartOperationHole


PartOperation = Annotated[
    Union[
        PartOperationHole,
        PartOperationFillet,
        PartOperationChamfer,
        PartOperationLinearHolePattern,
        PartOperationCircularHolePattern,
    ],
    Field(discriminator="type"),
]


class MaterialVisual(BaseModel):
    """Переопределение внешнего вида поверх пресета ``material``."""

    model_config = ConfigDict(extra="forbid")

    color: str | None = Field(
        default=None,
        description="Цвет #RRGGBB (опционально).",
    )
    roughness: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Шероховатость 0..1 (для согласования с рендером; STEP использует цвет).",
    )


class GeometryPartMaterialFields(BaseModel):
    """Общие поля детали: пресет материала и визуал (Blueprint v1.1+)."""

    model_config = ConfigDict(extra="forbid")

    material: str | None = Field(
        default=None,
        description="Ключ пресета (steel, aluminum_6061, abs_plastic, rubber) — плотность/трение/цвет.",
    )
    visual: MaterialVisual | None = None


# --- Geometry: parts (discriminated by base_shape) ---


class CylinderParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radius: float = Field(gt=0)
    height: float = Field(gt=0)


class BoxParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length: float = Field(gt=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class SphereParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radius: float = Field(gt=0)


class GeometryPartCylinder(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["cylinder"]
    parameters: CylinderParams
    operations: list[PartOperation]


class GeometryPartBox(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["box"]
    parameters: BoxParams
    operations: list[PartOperation]


class GeometryPartSphere(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["sphere"]
    parameters: SphereParams
    operations: list[PartOperation]


class ExtrudedProfileParams(BaseModel):
    """2D-контур в XY, экструзия вдоль +Z; точки по порядку, контур замыкается автоматически."""

    model_config = ConfigDict(extra="forbid")

    points: Annotated[list[tuple[float, float]], Field(min_length=3)]
    height: float = Field(gt=0)


class GeometryPartExtrudedProfile(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["extruded_profile"]
    parameters: ExtrudedProfileParams
    operations: list[PartOperation]


class RevolvedProfileParams(BaseModel):
    """
    Сечение в плоскости XZ: первая координата — расстояние от оси вращения Y (>= 0),
    вторая — координата Z; вращение вокруг Y на angle градусов.
    """

    model_config = ConfigDict(extra="forbid")

    points: Annotated[list[tuple[float, float]], Field(min_length=3)]
    angle: float = Field(gt=0, le=360, description="Угол в градусах, (0, 360].")


class GeometryPartRevolvedProfile(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["revolved_profile"]
    parameters: RevolvedProfileParams
    operations: list[PartOperation]


class GeometryPartCustomProfile(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["custom_profile"]
    parameters: dict[str, Any]
    operations: list[PartOperation]

    @field_validator("parameters")
    @classmethod
    def at_least_one_key(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) < 1:
            raise ValueError("custom_profile.parameters must contain at least one key")
        return v


GeometryPart = Annotated[
    Union[
        GeometryPartCylinder,
        GeometryPartBox,
        GeometryPartSphere,
        GeometryPartExtrudedProfile,
        GeometryPartRevolvedProfile,
        GeometryPartCustomProfile,
    ],
    Field(discriminator="base_shape"),
]


class GeometrySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parts: Annotated[list[GeometryPart], Field(min_length=1)]


# --- Simulation ---


class SimulationMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mat_id: str = Field(min_length=1)
    density: float = Field(gt=0)
    friction: float = Field(ge=0)


class SimulationNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    mat_id: str = Field(min_length=1)
    mass_override: float | None = Field(default=None, gt=0)


class SimulationJoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    joint_id: str = Field(min_length=1)
    type: Literal["hinge", "slider", "fixed", "ball"]
    parent_part: str = Field(min_length=1)
    child_part: str = Field(min_length=1)
    anchor_point: tuple[float, float, float]
    axis: tuple[float, float, float]
    limits: tuple[float, float] | None = None


class SimulationSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    materials: list[SimulationMaterial]
    nodes: list[SimulationNode]
    joints: list[SimulationJoint]


# --- Root payload ---


class ResolvedBlueprintPayload(BaseModel):
    """
    Строго числовой Blueprint после ``resolve_blueprint_variables`` —
    для воркера (CadQuery, MJCF, экспорт Python).
    """

    model_config = ConfigDict(extra="forbid")

    metadata: BlueprintMetadata
    global_variables: dict[str, float] | None = Field(
        default=None,
        description="Числовые константы (после resolve); геометрия — только числа.",
    )
    global_settings: GlobalSettings
    geometry: GeometrySection
    simulation: SimulationSection


# Обратная совместимость с кодом и тестами, ожидающими имя BlueprintPayload
BlueprintPayload = ResolvedBlueprintPayload


# --- Job API ---
# JobCreateWithPrompt см. models_raw.py (current_blueprint: RawBlueprintPayload)


class JobCreateResponse(BaseModel):
    job_id: str
    status: Literal["queued"]


class JobArtifacts(BaseModel):
    glb_url: str
    step_url: str
    mjcf_url: str | None = None
    zip_url: str | None = None
    video_url: str | None = Field(default=None)
    script_url: str | None = Field(default=None)


class JobBomPart(BaseModel):
    """Одна строка BOM (сырьё / геометрия), без парсинга CSV на клиенте."""

    part_id: str
    material: str | None = None
    mass_g: float
    volume_cm3: float
    cost_usd: float


class JobBom(BaseModel):
    parts: list[JobBomPart]
    total_mass_g: float
    total_cost_usd: float


class JobDiagnosticCheck(BaseModel):
    """Одна проверка DFM (интерференция, тонкие стенки, …)."""

    model_config = ConfigDict(extra="forbid")

    type: str
    severity: Literal["pass", "warning", "fail"]
    message: str
    part_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] | None = None


class JobDiagnostics(BaseModel):
    """Результат инженерной диагностики воркера (эвристики)."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["pass", "warning", "fail"]
    checks: list[JobDiagnosticCheck]


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "in_progress", "completed", "failed"]
    artifacts: JobArtifacts | None = None
    error: str | None = None
    warnings: list[str] | None = None
    blueprint: dict[str, Any] | None = None
    bom: JobBom | None = None
    diagnostics: JobDiagnostics | None = None


# --- Cloud projects (persistence / share links) ---


class ProjectLastArtifacts(BaseModel):
    """Кэш presigned URL + BOM для мгновенного показа 3D без повторного воркера."""

    model_config = ConfigDict(extra="forbid")

    glb_url: str | None = None
    step_url: str | None = None
    mjcf_url: str | None = None
    zip_url: str | None = None
    video_url: str | None = None
    script_url: str | None = None
    bom: JobBom | None = None


class ProjectRecord(BaseModel):
    """Сущность Project в Redis (version 2.0 — миграции в будущем)."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str
    version: Literal["2.0"] = "2.0"
    blueprint: dict[str, Any]
    last_artifacts: ProjectLastArtifacts | None = None
    created_at: str
    updated_at: str


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="Untitled Project", min_length=1, max_length=256)
    blueprint: dict[str, Any]
    last_artifacts: ProjectLastArtifacts | None = None


class ProjectCreateResponse(BaseModel):
    project_id: str


class ProjectUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=256)
    blueprint: dict[str, Any] | None = None
    last_artifacts: ProjectLastArtifacts | None = None
