"""Pydantic v2 модели Blueprint v1.0–v3.5 (v3.5: constraint assembly_mates)."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --- Metadata & global ---


class BlueprintMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    schema_version: Literal[
        "1.0", "1.1", "1.2", "1.3", "1.4", "2.0", "2.1", "3.0", "3.2", "3.5"
    ]


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
    position: tuple[float, float, float] | None = Field(
        default=None,
        description="Смещение детали в сборке (мм); для v3.0 может вычисляться через assembly_mates.",
    )
    rotation: tuple[float, float, float] | None = Field(
        default=None,
        description="Поворот в сборке (градусы), как cq.Rot(x,y,z); для v3.0 может вычисляться через assembly_mates.",
    )


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


class FastenerParams(BaseModel):
    """Параметры стандартного метиза (без моделирования резьбы)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["bolt_hex", "nut_hex", "washer"]
    size: Literal["M6", "M8", "M10", "M12"]
    length: float | None = Field(
        default=None,
        description="Длина стержня болта (мм), только для bolt_hex.",
    )
    fit: Literal["clearance", "tight"] = "clearance"

    @model_validator(mode="after")
    def _validate_bolt_length(self) -> FastenerParams:
        if self.type == "bolt_hex":
            if self.length is None or self.length <= 0:
                raise ValueError("bolt_hex: parameters.length обязателен и > 0")
        return self


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


class GeometryPartFastener(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["fastener"]
    parameters: FastenerParams
    operations: list[PartOperation]


class BearingParams(BaseModel):
    """Каталожный подшипник (упрощённое кольцо по OD/ID/ширине)."""

    model_config = ConfigDict(extra="forbid")

    series: str = Field(
        min_length=1,
        description="Серия из каталога (608zz, 6200, 6201, …).",
    )


class GeometryPartBearing(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["bearing"]
    parameters: BearingParams
    operations: list[PartOperation]


class GearParams(BaseModel):
    """Шестерня: preview (high_lod=false) — многоугольник по Da; high_lod=true — процедурный трапециевидный зуб (прототип/печать)."""

    model_config = ConfigDict(extra="forbid")

    module: float = Field(gt=0, description="Модуль m (мм).")
    teeth: int = Field(ge=4, le=500, description="Число зубьев z.")
    thickness: float = Field(gt=0, description="Ширина венца (мм), экструзия +Z.")
    bore_diameter: float = Field(gt=0, description="Посадочное отверстие под вал (мм).")
    high_lod: bool = Field(
        default=False,
        description="false: упрощённая геометрия (быстро); true: процедурный spur high-LOD (не идеальная эвольвента).",
    )


class GeometryPartGear(GeometryPartMaterialFields):
    model_config = ConfigDict(extra="forbid")

    part_id: str = Field(min_length=1)
    base_shape: Literal["gear"]
    parameters: GearParams
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
        GeometryPartFastener,
        GeometryPartBearing,
        GeometryPartGear,
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


# --- Assembly mates (v3.0) ---


class AssemblyMateSnapToOperation(BaseModel):
    """Привязка детали-источника к центру и направлению hole-операции на целевой детали."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["snap_to_operation"]
    source_part: str = Field(min_length=1, description="Деталь, pose которой задаётся mate (часто fastener).")
    target_part: str = Field(min_length=1)
    target_operation_index: int = Field(ge=0, description="Индекс в operations целевой детали (hole).")
    reverse_direction: bool = Field(
        default=False,
        description="Перевернуть ось вставки на 180° (вход с противоположной стороны).",
    )


class AssemblyMateConcentric(BaseModel):
    """Совмещение локальной +Z source с осью hole на target (MVP: только rotation + axis для следующих шагов)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["concentric"]
    source_part: str = Field(min_length=1)
    target_part: str = Field(min_length=1)
    target_operation_index: int = Field(ge=0)
    reverse_direction: bool = Field(
        default=False,
        description="Развернуть ось совмещения на 180°.",
    )


class AssemblyMateCoincident(BaseModel):
    """Совмещение центров вдоль оси (после concentric — axis_u; иначе линия центров)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["coincident"]
    source_part: str = Field(min_length=1)
    target_part: str = Field(min_length=1)
    offset: float = Field(default=0.0, description="Смещение в мм вдоль оси прижима.")
    flip: bool = Field(default=False, description="Поворот на 180° вокруг оси ⟂ оси прижима.")


class AssemblyMateDistance(BaseModel):
    """Фиксированное расстояние центра source от центра target вдоль axis_u или линии центров."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["distance"]
    source_part: str = Field(min_length=1)
    target_part: str = Field(min_length=1)
    value: float = Field(description="Расстояние в мм (после resolve $-выражений).")


AssemblyMate = Annotated[
    Union[
        AssemblyMateSnapToOperation,
        AssemblyMateConcentric,
        AssemblyMateCoincident,
        AssemblyMateDistance,
    ],
    Field(discriminator="type"),
]


# --- Root payload ---


class ResolvedBlueprintPayload(BaseModel):
    """
    Строго числовой Blueprint после ``resolve_blueprint_variables`` и ``resolve_assembly_mates`` —
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
    assembly_mates: list[AssemblyMate] | None = Field(
        default=None,
        description="Логические привязки (v3.0 snap; v3.5 concentric/coincident/distance); резолвер заполняет pose у source.",
    )


# Обратная совместимость с кодом и тестами, ожидающими имя BlueprintPayload
BlueprintPayload = ResolvedBlueprintPayload


# --- Job API ---
# JobCreateWithPrompt см. models_raw.py (current_blueprint: RawBlueprintPayload)


class JobCreateResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
    resolved_transforms: dict[str, Any] | None = Field(
        default=None,
        description="Если в запросе debug_constraints=true — pose частей после mate_solver (для отладки).",
    )


class JobArtifacts(BaseModel):
    glb_url: str
    step_url: str
    mjcf_url: str | None = None
    zip_url: str | None = None
    video_url: str | None = Field(default=None)
    script_url: str | None = Field(default=None)
    drawings_urls: list[str] | None = Field(
        default=None,
        description="Presigned GET на SVG-превью (по одному на вид).",
    )
    pdf_url: str | None = Field(
        default=None,
        description="Presigned GET на PDF инструкции по сборке (assembly_instructions.pdf).",
    )


class JobBomPart(BaseModel):
    """Одна строка BOM (сырьё / геометрия), без парсинга CSV на клиенте."""

    part_id: str
    material: str | None = None
    mass_g: float
    volume_cm3: float
    cost_usd: float
    item_type: Literal["manufactured", "purchased"] = "manufactured"
    catalog_label: str | None = None


class JobBom(BaseModel):
    parts: list[JobBomPart]
    total_mass_g: float
    total_cost_usd: float


class JobDiagnosticCheck(BaseModel):
    """Одна проверка DFM (интерференция, тонкие стенки, …)."""

    model_config = ConfigDict(extra="forbid")

    type: str
    severity: Literal["pass", "warning", "fail", "info"]
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
    drawings_urls: list[str] | None = None
    pdf_url: str | None = None


class ProjectRecord(BaseModel):
    """Сущность Project в Redis (version 2.0 — миграции в будущем)."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    owner_id: str | None = None
    is_public: bool = False
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
    is_public: bool | None = None


class ProjectSummary(BaseModel):
    """Элемент списка «Мои проекты»."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str
    owner_id: str | None = None
    is_public: bool = False
    created_at: str
    updated_at: str


class ProjectListResponse(BaseModel):
    projects: list[ProjectSummary]


class ProjectForkResponse(BaseModel):
    project_id: str


class AuthUserPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    name: str
    avatar_url: str | None = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUserPublic


class GoogleAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential: str = Field(min_length=10, description="Google ID token (JWT string)")
