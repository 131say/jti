"""
Шестерни: упрощённая геометрия (low LOD) — многоугольник по наружному диаметру + отверстие под вал.
high_lod=true — зарезервировано под эвольвентный профиль (будущие инкременты).
"""

from __future__ import annotations

from typing import Any

import cadquery as cq

from worker.core.exceptions import BlueprintGenerationError


def make_gear_solid(parameters: dict[str, Any]) -> cq.Shape:
    m = float(parameters.get("module") or 0.0)
    z = int(parameters.get("teeth") or 0)
    h = float(parameters.get("thickness") or 0.0)
    bore = float(parameters.get("bore_diameter") or 0.0)
    high_lod = bool(parameters.get("high_lod", False))

    if high_lod:
        raise BlueprintGenerationError(
            "gear: high_lod=true (эвольвентный профиль) пока не реализовано — используйте high_lod=false"
        )
    if m <= 0:
        raise BlueprintGenerationError("gear: module должен быть > 0")
    if z < 4:
        raise BlueprintGenerationError("gear: teeth должно быть >= 4")
    if h <= 0:
        raise BlueprintGenerationError("gear: thickness должен быть > 0")
    if bore <= 0:
        raise BlueprintGenerationError("gear: bore_diameter должен быть > 0")

    d_outer = m * (z + 2)
    r_outer = d_outer / 2.0
    r_bore = bore / 2.0
    if r_bore >= r_outer - 1e-3:
        raise BlueprintGenerationError("gear: посадочное отверстие слишком велико для венца")

    # n-угольник «звёздочка»: число вершин = teeth, радиус до вершины = наружный
    rv = cq.Workplane("XY").polygon(z, r_outer).extrude(h)
    return rv.faces("<Z").workplane().circle(r_bore).cutThruAll().val()


def gear_catalog_label(parameters: dict[str, Any]) -> str:
    m = float(parameters.get("module") or 0)
    z = int(parameters.get("teeth") or 0)
    lod = "высокая детализация" if parameters.get("high_lod") else "упрощённая (preview)"
    return f"Шестерня m={m:g}, z={z} ({lod})"
