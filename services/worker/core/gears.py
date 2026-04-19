"""
Шестерни (spur, MVP):
- high_lod=false: многоугольник по наружному диаметру + отверстие (preview).
- high_lod=true: процедурный трапециевидный зуб + polar fuse (прототип / печать, не идеальная эвольвента).
"""

from __future__ import annotations

import math
from typing import Any

import cadquery as cq

from worker.core.exceptions import BlueprintGenerationError

# Телеметрия при сборке задачи (добавляется воркером при наличии high_lod gear).
HIGH_LOD_GEAR_JOB_WARNING = (
    "Внимание: генерация High-LOD шестерен может занять дополнительное время и "
    "увеличить размер экспортируемых файлов. Профиль зуба является процедурным "
    "приближением для прототипирования."
)


def _validate_gear_params(m: float, z: int, h: float, bore: float) -> None:
    if m <= 0:
        raise BlueprintGenerationError("gear: module должен быть > 0")
    if z < 4:
        raise BlueprintGenerationError("gear: teeth должно быть >= 4")
    if h <= 0:
        raise BlueprintGenerationError("gear: thickness должен быть > 0")
    if bore <= 0:
        raise BlueprintGenerationError("gear: bore_diameter должен быть > 0")


def build_procedural_gear(
    module: float,
    teeth: int,
    thickness: float,
    bore: float,
) -> cq.Shape:
    """
    Прямозубая цилиндрическая шестерня (MVP): корень d_f = m*(z-2.5), наружный d_a = m*(z+2),
    трапециевидный профиль зуба, z копий по окружности, вырез под вал.
    """
    m = float(module)
    z = int(teeth)
    h = float(thickness)
    bore_d = float(bore)
    _validate_gear_params(m, z, h, bore_d)

    d_outer = m * (z + 2)
    d_root = m * (z - 2.5)
    r_outer = d_outer / 2.0
    r_root = max(d_root / 2.0, 1e-6)
    r_bore = bore_d / 2.0

    if r_bore >= r_outer - 1e-3:
        raise BlueprintGenerationError("gear: посадочное отверстие слишком велико для венца")
    if r_root <= r_bore + 1e-3:
        raise BlueprintGenerationError(
            "gear high_lod: диаметр впадин слишком мал для указанного bore — уменьшите отверстие или модуль"
        )

    # Эвристика углов (радианы): корень шире, вершина уже.
    theta_root = 0.52 * math.pi / z
    theta_tip = 0.38 * math.pi / z

    pts: list[tuple[float, float]] = [
        (r_root * math.cos(-theta_root), r_root * math.sin(-theta_root)),
        (r_outer * math.cos(-theta_tip), r_outer * math.sin(-theta_tip)),
        (r_outer * math.cos(theta_tip), r_outer * math.sin(theta_tip)),
        (r_root * math.cos(theta_root), r_root * math.sin(theta_root)),
    ]

    tooth = cq.Workplane("XY").polyline(pts).close().extrude(h).val()

    root_cyl = cq.Workplane("XY").circle(r_root).extrude(h).val()
    merged = root_cyl
    for i in range(z):
        ang = i * 360.0 / z
        t_rot = tooth.rotate((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), ang)
        merged = merged.fuse(t_rot)

    gear_wp = cq.Workplane("XY").add(merged)
    return gear_wp.faces("<Z").workplane().circle(r_bore).cutThruAll().val()


def make_gear_solid(parameters: dict[str, Any]) -> cq.Shape:
    m = float(parameters.get("module") or 0.0)
    z = int(parameters.get("teeth") or 0)
    h = float(parameters.get("thickness") or 0.0)
    bore = float(parameters.get("bore_diameter") or 0.0)
    high_lod = bool(parameters.get("high_lod", False))

    if high_lod:
        return build_procedural_gear(m, z, h, bore)

    _validate_gear_params(m, z, h, bore)

    d_outer = m * (z + 2)
    r_outer = d_outer / 2.0
    r_bore = bore / 2.0
    if r_bore >= r_outer - 1e-3:
        raise BlueprintGenerationError("gear: посадочное отверстие слишком велико для венца")

    rv = cq.Workplane("XY").polygon(z, r_outer).extrude(h)
    return rv.faces("<Z").workplane().circle(r_bore).cutThruAll().val()


def build_gear_solid(parameters: dict[str, Any]) -> cq.Shape:
    """Алиас для generator / diagnostics."""
    return make_gear_solid(parameters)


def gear_catalog_label(parameters: dict[str, Any]) -> str:
    m = float(parameters.get("module") or 0)
    z = int(parameters.get("teeth") or 0)
    if parameters.get("high_lod"):
        lod = "процедурный профиль (прототип/печать)"
    else:
        lod = "упрощённая (preview)"
    return f"Шестерня m={m:g}, z={z} ({lod})"
