"""
Разрешение assembly_mates (Blueprint v3.0): привязка метизов к hole-операциям по индексу.

Выполняется после resolve_blueprint_variables, до Pydantic-валидации и CadQuery.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

logger = logging.getLogger(__name__)


class MateResolutionError(ValueError):
    """Ошибка резолва assembly_mates (цикл, неверная операция, отсутствующая деталь)."""


def _vec3(v: Any, *, ctx: str) -> np.ndarray:
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise MateResolutionError(f"{ctx}: ожидался массив из 3 чисел")
    return np.array([float(v[0]), float(v[1]), float(v[2])], dtype=float)


def _normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        raise MateResolutionError("нулевой вектор направления")
    return v / n


def _pose_to_RT(part: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Матрица поворота 3x3 и смещение из part (градусы, cq.Rot / scipy ``xyz``)."""
    pos = part.get("position")
    rot = part.get("rotation")
    if pos is None:
        t = np.zeros(3, dtype=float)
    else:
        t = _vec3(pos, ctx="position")
    if rot is None:
        rx = ry = rz = 0.0
    else:
        p = _vec3(rot, ctx="rotation")
        rx, ry, rz = float(p[0]), float(p[1]), float(p[2])
    r = Rotation.from_euler("xyz", [rx, ry, rz], degrees=True)
    return r.as_matrix(), t


def _RT_apply_point(R: np.ndarray, t: np.ndarray, p: np.ndarray) -> np.ndarray:
    return R @ p + t


def _RT_apply_dir(R: np.ndarray, d: np.ndarray) -> np.ndarray:
    return R @ d


def _align_plus_z_to_direction(dir_world: np.ndarray) -> tuple[float, float, float]:
    """Эйлер [rx, ry, rz] в градусах: локальная +Z → dir_world (единичный)."""
    d = _normalize(dir_world.reshape(3))
    ez = np.array([0.0, 0.0, 1.0], dtype=float)
    rot, _ = Rotation.align_vectors(d.reshape(1, 3), ez.reshape(1, 3))
    euler = rot.as_euler("xyz", degrees=True)
    return float(euler[0]), float(euler[1]), float(euler[2])


def _gather_last_mate_by_source(
    mates_raw: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    last: dict[str, dict[str, Any]] = {}
    for raw in mates_raw:
        if not isinstance(raw, dict):
            raise MateResolutionError("Элемент assembly_mates должен быть объектом")
        t = raw.get("type")
        if t != "snap_to_operation":
            raise MateResolutionError(f"assembly_mates: неизвестный type {t!r}")
        s = raw.get("source_part")
        if not isinstance(s, str) or not s:
            raise MateResolutionError("snap_to_operation: source_part должен быть непустой строкой")
        tgt = raw.get("target_part")
        if not isinstance(tgt, str) or not tgt:
            raise MateResolutionError("snap_to_operation: target_part должен быть непустой строкой")
        last[s] = raw
    return last


def _hole_from_operation(
    op: dict[str, Any],
    *,
    part_id: str,
    idx: int,
) -> tuple[np.ndarray, np.ndarray]:
    ot = op.get("type")
    if ot != "hole":
        raise MateResolutionError(
            f"snap_to_operation: part {part_id!r}, operation[{idx}] имеет type={ot!r}; "
            "для привязки допускается только hole (MVP)."
        )
    pos = op.get("position")
    direction = op.get("direction")
    p = _vec3(pos, ctx=f"{part_id} hole.position")
    d = _vec3(direction, ctx=f"{part_id} hole.direction")
    return p, _normalize(d)


def _apply_snap_mate(
    src_part: dict[str, Any],
    mate: dict[str, Any],
    tgt_part: dict[str, Any],
    *,
    part_id: str,
    tgt_id: str,
    warnings: list[str],
) -> None:
    idx = mate.get("target_operation_index")
    if not isinstance(idx, int) or idx < 0:
        raise MateResolutionError(
            f"snap_to_operation {part_id!r}: target_operation_index должен быть int >= 0"
        )
    rev = bool(mate.get("reverse_direction", False))
    ops = tgt_part.get("operations")
    if not isinstance(ops, list) or idx >= len(ops):
        raise MateResolutionError(f"snap_to_operation: у детали {tgt_id!r} нет operations[{idx}]")
    op = ops[idx]
    if not isinstance(op, dict):
        raise MateResolutionError(f"operations[{idx}] у {tgt_id!r} должен быть объектом")

    p_loc, d_loc = _hole_from_operation(op, part_id=tgt_id, idx=idx)
    R_t, T_t = _pose_to_RT(tgt_part)
    p_world = _RT_apply_point(R_t, T_t, p_loc)
    d_world = _RT_apply_dir(R_t, d_loc)
    if rev:
        d_world = -d_world

    had_pos = src_part.get("position") is not None
    had_rot = src_part.get("rotation") is not None
    if had_pos or had_rot:
        warnings.append(
            f"assembly_mates: mate snap_to_operation перезаписывает явные "
            f"position/rotation у {part_id!r} (приоритет сборки)"
        )

    rx, ry, rz = _align_plus_z_to_direction(d_world)
    src_part["position"] = (float(p_world[0]), float(p_world[1]), float(p_world[2]))
    src_part["rotation"] = (rx, ry, rz)


def resolve_assembly_mates(
    blueprint: dict[str, Any],
    *,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """
    Копирует blueprint, для assembly_mates типа snap_to_operation задаёт
    position/rotation у source_part. Mate имеет приоритет над явными pose (с предупреждением).

    Вызывать на dict уже после ``resolve_blueprint_variables``.
    """
    out = copy.deepcopy(blueprint)
    w = warnings if warnings is not None else []
    mates_raw = out.get("assembly_mates")
    if not mates_raw:
        return out
    if not isinstance(mates_raw, list):
        raise MateResolutionError("assembly_mates должен быть массивом")

    geo = out.get("geometry")
    if not isinstance(geo, dict):
        raise MateResolutionError("geometry отсутствует")
    parts_list = geo.get("parts")
    if not isinstance(parts_list, list):
        raise MateResolutionError("geometry.parts должен быть массивом")

    by_id: dict[str, dict[str, Any]] = {}
    for p in parts_list:
        if isinstance(p, dict) and p.get("part_id"):
            by_id[str(p["part_id"])] = p

    last_mate_by_source = _gather_last_mate_by_source(mates_raw)

    done: set[str] = set()

    def ensure_mated_pose(part_id: str, visiting: set[str]) -> None:
        if part_id in done:
            return
        if part_id not in by_id:
            raise MateResolutionError(f"assembly_mates: неизвестный part_id {part_id!r}")
        if part_id in visiting:
            raise MateResolutionError(
                "assembly_mates: обнаружена циклическая зависимость в графе привязок"
            )
        visiting.add(part_id)
        if part_id in last_mate_by_source:
            mate = last_mate_by_source[part_id]
            tgt_id = str(mate["target_part"])
            ensure_mated_pose(tgt_id, visiting)
            _apply_snap_mate(
                by_id[part_id],
                mate,
                by_id[tgt_id],
                part_id=part_id,
                tgt_id=tgt_id,
                warnings=w,
            )
        visiting.remove(part_id)
        done.add(part_id)

    for src in last_mate_by_source:
        ensure_mated_pose(src, set())

    return out
