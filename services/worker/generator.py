"""Оркестрация: Blueprint JSON → Assembly → экспорт STEP/STL (ADR v1.0)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cadquery as cq
from cadquery import Color

from worker.core.exceptions import BlueprintGenerationError
from worker.zip_packaging import create_project_zip
from worker.core.materials import resolve_part_material
from worker.core.geometry import (
    apply_chamfer,
    apply_fillet,
    apply_hole,
    clamp_hole_diameter_to_solid,
    expand_circular_pattern_to_hole_dicts,
    expand_linear_pattern_to_hole_dicts,
)
from worker.core.primitives import (
    make_box,
    make_cylinder,
    make_extruded_profile,
    make_revolved_profile,
)

logger = logging.getLogger(__name__)

__all__ = [
    "BlueprintGenerationError",
    "build_assembly_from_blueprint",
    "build_part_solid",
    "build_shape_from_blueprint",
    "export_artifacts",
    "export_individual_parts_to_dir",
    "export_part_meshes",
    "create_project_zip",
]


def _apply_operation_dict(
    solid: cq.Shape,
    op: dict[str, Any],
    *,
    part_id: str,
    warnings: list[str] | None,
) -> cq.Shape:
    op_type = op.get("type")
    if op_type == "hole":
        pos = op["position"]
        if len(pos) != 3:
            raise BlueprintGenerationError("position должен быть из трёх чисел")
        position = (float(pos[0]), float(pos[1]), float(pos[2]))

        direction = (
            float(op["direction"][0]),
            float(op["direction"][1]),
            float(op["direction"][2]),
        )

        raw_d = float(op["diameter"])
        diameter = clamp_hole_diameter_to_solid(
            solid,
            raw_d,
            part_id=part_id,
            warnings=warnings,
        )

        try:
            wp = cq.Workplane().add(solid)
            wp = apply_hole(
                wp,
                diameter,
                position,
                direction,
                op["depth"],
            )
            return wp.val()
        except Exception as e:
            msg = f"Part '{part_id}': hole skipped ({e!s})"
            logger.warning(msg)
            if warnings is not None:
                warnings.append(msg)
            return solid

    if op_type == "fillet":
        radius = float(op["radius"])
        selector = str(op.get("selector") or "ALL")
        try:
            wp = cq.Workplane().add(solid)
            wp = apply_fillet(wp, radius, selector)
            return wp.val()
        except Exception as e:
            msg = f"Part '{part_id}': fillet skipped ({e!s})"
            logger.warning(msg)
            if warnings is not None:
                warnings.append(msg)
            return solid

    if op_type == "chamfer":
        length = float(op["length"])
        selector = str(op.get("selector") or "ALL")
        try:
            wp = cq.Workplane().add(solid)
            wp = apply_chamfer(wp, length, selector)
            return wp.val()
        except Exception as e:
            msg = f"Part '{part_id}': chamfer skipped ({e!s})"
            logger.warning(msg)
            if warnings is not None:
                warnings.append(msg)
            return solid

    if op_type == "linear_pattern":
        try:
            holes = expand_linear_pattern_to_hole_dicts(op)
        except Exception as e:
            raise BlueprintGenerationError(f"linear_pattern: {e!s}") from e
        s2 = solid
        for h in holes:
            s2 = _apply_operation_dict(s2, h, part_id=part_id, warnings=warnings)
        return s2

    if op_type == "circular_pattern":
        try:
            holes = expand_circular_pattern_to_hole_dicts(op)
        except Exception as e:
            raise BlueprintGenerationError(f"circular_pattern: {e!s}") from e
        s2 = solid
        for h in holes:
            s2 = _apply_operation_dict(s2, h, part_id=part_id, warnings=warnings)
        return s2

    raise BlueprintGenerationError(f"Неизвестный type операции: {op.get('type')!r}")


def _apply_operations(
    solid: cq.Shape,
    part: dict[str, Any],
    *,
    warnings: list[str] | None,
) -> cq.Shape:
    pid = str(part.get("part_id") or "?")
    for op in part.get("operations") or []:
        solid = _apply_operation_dict(solid, op, part_id=pid, warnings=warnings)
    return solid


def _build_cylinder(part: dict[str, Any], warnings: list[str] | None) -> cq.Shape:
    p = part["parameters"]
    r = float(p["radius"])
    h = float(p["height"])
    wp = make_cylinder(r, h)
    solid = wp.val()
    return _apply_operations(solid, part, warnings=warnings)


def _build_box(part: dict[str, Any], warnings: list[str] | None) -> cq.Shape:
    p = part["parameters"]
    length = float(p["length"])
    width = float(p["width"])
    height = float(p["height"])
    wp = make_box(length, width, height)
    solid = wp.val()
    return _apply_operations(solid, part, warnings=warnings)


def _build_extruded_profile(
    part: dict[str, Any], warnings: list[str] | None
) -> cq.Shape:
    p = part["parameters"]
    wp = make_extruded_profile(p["points"], float(p["height"]))
    solid = wp.val()
    return _apply_operations(solid, part, warnings=warnings)


def _build_revolved_profile(
    part: dict[str, Any], warnings: list[str] | None
) -> cq.Shape:
    p = part["parameters"]
    wp = make_revolved_profile(p["points"], float(p["angle"]))
    solid = wp.val()
    return _apply_operations(solid, part, warnings=warnings)


def build_part_solid(
    part: dict[str, Any],
    warnings: list[str] | None = None,
) -> cq.Shape:
    """Одна деталь из Blueprint (для per-part STL и массы в MJCF)."""
    kind = part.get("base_shape")
    if kind == "cylinder":
        return _build_cylinder(part, warnings)
    if kind == "box":
        return _build_box(part, warnings)
    if kind == "extruded_profile":
        return _build_extruded_profile(part, warnings)
    if kind == "revolved_profile":
        return _build_revolved_profile(part, warnings)
    if kind in ("sphere", "custom_profile"):
        raise BlueprintGenerationError(
            f"base_shape {kind!r} не поддерживается воркером (используйте cylinder, box, "
            "extruded_profile, revolved_profile)"
        )
    raise BlueprintGenerationError(f"Неизвестный base_shape: {kind!r}")


def export_individual_parts_to_dir(
    payload: dict[str, Any],
    parts_dir: Path,
    warnings: list[str] | None,
) -> None:
    """
    STEP + STL на каждую деталь в ``parts_dir``. Ошибка по одной детали не прерывает
    остальные (warnings дополняются).
    """
    parts_dir.mkdir(parents=True, exist_ok=True)
    w = warnings if warnings is not None else []
    for part in (payload.get("geometry") or {}).get("parts") or []:
        pid = part.get("part_id")
        if not pid:
            w.append("geometry.parts: пропущена деталь без part_id (экспорт parts/)")
            continue
        pid_s = str(pid)
        try:
            solid = build_part_solid(part)
        except Exception as e:
            w.append(f"parts/{pid_s}: построение тела: {e!s}")
            continue
        stl_path = parts_dir / f"{pid_s}.stl"
        step_path = parts_dir / f"{pid_s}.step"
        try:
            cq.exporters.export(solid, str(stl_path), exportType="STL")
        except Exception as e:
            w.append(f"parts/{pid_s}.stl: {e!s}")
        try:
            cq.exporters.export(solid, str(step_path), exportType="STEP")
        except Exception as e:
            w.append(f"parts/{pid_s}.step: {e!s}")


def export_part_meshes(payload: dict[str, Any], mesh_dir: Path) -> None:
    """Обратная совместимость: только STL в каталог (без fallback по деталям)."""
    export_individual_parts_to_dir(payload, mesh_dir, None)


def build_assembly_from_blueprint(
    payload: dict[str, Any],
    warnings: list[str] | None = None,
) -> cq.Assembly:
    """Собирает `cq.Assembly`: каждая запись `geometry.parts` — отдельное тело с именем `part_id`."""
    parts = (payload.get("geometry") or {}).get("parts") or []
    if not parts:
        raise BlueprintGenerationError("geometry.parts должен содержать хотя бы одну деталь")

    root = cq.Assembly(None, name="AI_Forge_Project")
    for part in parts:
        solid = build_part_solid(part, warnings)

        pid = part.get("part_id")
        if not pid:
            raise BlueprintGenerationError("part_id обязателен для каждой детали")
        try:
            resolved = resolve_part_material(part)
            if resolved is not None:
                col = Color(resolved.color_r, resolved.color_g, resolved.color_b)
                root.add(solid, name=pid, color=col)
            else:
                root.add(solid, name=pid)
        except ValueError as e:
            raise BlueprintGenerationError(str(e)) from e

    return root


def build_shape_from_blueprint(
    payload: dict[str, Any],
    warnings: list[str] | None = None,
) -> cq.Shape:
    """Обратная совместимость: compound всех тел (без булева union)."""
    return build_assembly_from_blueprint(payload, warnings).toCompound()


def export_artifacts(assembly: cq.Assembly, assembly_dir: Path) -> tuple[Path, Path]:
    """
    Экспорт общей сборки: ``assembly/assembly.step``, ``assembly/model.glb``
    (иерархия GLB, имена узлов = ``part_id`` для веба).
    """
    assembly_dir.mkdir(parents=True, exist_ok=True)
    step_path = assembly_dir / "assembly.step"
    glb_path = assembly_dir / "model.glb"

    assembly.export(str(step_path), exportType="STEP")
    assembly.export(str(glb_path), exportType="GLB")

    return step_path, glb_path
