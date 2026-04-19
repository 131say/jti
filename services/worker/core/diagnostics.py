"""
Инженерная диагностика (DFM MVP): эвристики на базе CadQuery.

Interference — приоритет #1 (критично). Остальные — WARNING.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import cadquery as cq

from worker.core.diagnostics_status import aggregate_diagnostics_status
from worker.generator import build_part_solid

logger = logging.getLogger(__name__)

# Минимальный объём пересечения двух тел (мм³), считающийся коллизией.
INTERFERENCE_EPS_MM3 = 1e-2
# Порог «тонкой» стенки (мм) — эвристика, не wall-thickness solver.
THIN_FEATURE_MM = 1.0
# Игнорировать нижние грани у подошвы (мм над z_min).
BUILD_PLATE_TOLERANCE_MM = 0.5

CheckSeverity = str  # "pass" | "warning" | "fail"
CheckType = str


def _base_shape_by_part_id(blueprint: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in (blueprint.get("geometry") or {}).get("parts") or []:
        pid = p.get("part_id")
        if pid is None:
            continue
        bs = p.get("base_shape")
        if isinstance(bs, str):
            out[str(pid)] = bs
    return out


def _pairwise_interference(
    solids_by_id: dict[str, cq.Shape],
    blueprint: dict[str, Any],
) -> list[dict[str, Any]]:
    """Проверка всех пар деталей на пересечение (объём > epsilon)."""
    shapes = _base_shape_by_part_id(blueprint)
    out: list[dict[str, Any]] = []
    ids = sorted(solids_by_id.keys())
    for i, a_id in enumerate(ids):
        sa = solids_by_id[a_id]
        for b_id in ids[i + 1 :]:
            sb = solids_by_id[b_id]
            try:
                inter = sa.intersect(sb)
                vol = float(inter.val().Volume())
            except Exception as e:
                logger.warning(
                    "interference %s vs %s: %s", a_id, b_id, e, exc_info=False
                )
                continue
            if vol > INTERFERENCE_EPS_MM3:
                both_gear = (
                    shapes.get(a_id) == "gear" and shapes.get(b_id) == "gear"
                )
                severity: CheckSeverity = "warning" if both_gear else "fail"
                msg_extra = (
                    " (пара шестерён: процедурный профиль даёт микропересечения — WARNING до meshing-проверок)."
                    if both_gear
                    else ""
                )
                out.append(
                    {
                        "type": "interference",
                        "severity": severity,
                        "message": (
                            f"Детали '{a_id}' и '{b_id}' пересекаются "
                            f"(эвристика объёма пересечения).{msg_extra}"
                        ),
                        "part_ids": [a_id, b_id],
                        "metrics": {"interference_volume_mm3": round(vol, 6)},
                    }
                )
    return out


def _thin_feature_heuristic(
    solids_by_id: dict[str, cq.Shape],
) -> list[dict[str, Any]]:
    """Минимальный размер габарита < THIN_FEATURE_MM → WARNING."""
    out: list[dict[str, Any]] = []
    for pid, solid in solids_by_id.items():
        try:
            bb = solid.BoundingBox()
            min_dim = min(bb.xlen, bb.ylen, bb.zlen)
        except Exception as e:
            logger.warning("thin_feature %s: bbox: %s", pid, e)
            continue
        if min_dim < THIN_FEATURE_MM:
            out.append(
                {
                    "type": "thin_feature",
                    "severity": "warning",
                    "message": (
                        f"Эвристика: у детали '{pid}' минимальный размер габарита "
                        f"{min_dim:.3f} мм < {THIN_FEATURE_MM} мм (потенциально хрупкая зона)."
                    ),
                    "part_ids": [pid],
                    "metrics": {"min_feature_mm": round(min_dim, 6)},
                }
            )
    return out


def _overhang_heuristic(solid: cq.Shape, part_id: str) -> dict[str, Any] | None:
    """
    Эвристика FDM: грани выше подошвы, у которых нормаль «устойчивая» к +Z
    под углом > 45° (к вертикали).
    """
    try:
        bb = solid.BoundingBox()
        z_min = bb.zmin
    except Exception:
        return None

    flagged = False
    max_angle_from_z = 0.0
    try:
        faces = solid.faces()
        for face in faces.vals():
            try:
                c = face.Center()
                n = face.normalAt(0.5, 0.5)
                nz = float(n.z)
            except Exception:
                continue
            if c.z <= z_min + BUILD_PLATE_TOLERANCE_MM:
                continue
            # Эвристика: «нормаль смотрит вниз» (nz < 0) — типичные зоны поддержки FDM;
            # не классифицируем отдельные грани (MVP).
            if nz >= -0.02:
                continue
            ang = math.degrees(math.acos(max(-1.0, min(1.0, abs(nz)))))
            flagged = True
            max_angle_from_z = max(max_angle_from_z, ang)
    except Exception as e:
        logger.warning("overhang %s: %s", part_id, e)
        return None

    if not flagged:
        return None
    return {
        "type": "overhang",
        "severity": "warning",
        "message": (
            f"Эвристика FDM: у детали '{part_id}' есть грани с направлением нормали "
            f"вниз (nz < 0) выше плоскости подошвы — возможны нависания при печати."
        ),
        "part_ids": [part_id],
        "metrics": {"max_overhang_deg": round(max_angle_from_z, 2)},
    }


def _proportion_fillet_chamfer(
    blueprint: dict[str, Any],
    solids_by_id: dict[str, cq.Shape],
) -> list[dict[str, Any]]:
    """Сравнение радиуса fillet / длины chamfer с минимальным ребром bbox."""
    out: list[dict[str, Any]] = []
    parts = (blueprint.get("geometry") or {}).get("parts") or []
    for part in parts:
        pid = part.get("part_id")
        if not pid or str(pid) not in solids_by_id:
            continue
        pid_s = str(pid)
        solid = solids_by_id[pid_s]
        try:
            bb = solid.BoundingBox()
            min_edge = min(bb.xlen, bb.ylen, bb.zlen)
        except Exception:
            continue
        if min_edge <= 1e-9:
            continue
        for op in part.get("operations") or []:
            t = op.get("type")
            if t == "fillet":
                r = float(op.get("radius") or 0)
                if r > 0.5 * min_edge:
                    out.append(
                        {
                            "type": "proportion",
                            "severity": "warning",
                            "message": (
                                f"Эвристика: fillet r={r:.3f} мм у '{pid_s}' "
                                f"сопоставим с минимальным габаритом {min_edge:.3f} мм."
                            ),
                            "part_ids": [pid_s],
                            "metrics": {
                                "fillet_radius_mm": round(r, 6),
                                "min_bbox_edge_mm": round(min_edge, 6),
                            },
                        }
                    )
            elif t == "chamfer":
                ln = float(op.get("length") or 0)
                if ln > 0.5 * min_edge:
                    out.append(
                        {
                            "type": "proportion",
                            "severity": "warning",
                            "message": (
                                f"Эвристика: chamfer length={ln:.3f} мм у '{pid_s}' "
                                f"сопоставим с минимальным габаритом {min_edge:.3f} мм."
                            ),
                            "part_ids": [pid_s],
                            "metrics": {
                                "chamfer_length_mm": round(ln, 6),
                                "min_bbox_edge_mm": round(min_edge, 6),
                            },
                        }
                    )
    return out


def _build_solids_map(
    blueprint: dict[str, Any],
    warnings: list[str] | None,
) -> dict[str, cq.Shape]:
    w = warnings if warnings is not None else []
    out: dict[str, cq.Shape] = {}
    for part in (blueprint.get("geometry") or {}).get("parts") or []:
        pid = part.get("part_id")
        if not pid:
            continue
        pid_s = str(pid)
        try:
            out[pid_s] = build_part_solid(part)
        except Exception as e:
            w.append(f"diagnostics: деталь {pid_s}: построение тела: {e!s}")
    return out


def run_engineering_diagnostics(
    blueprint: dict[str, Any],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """
    Запуск всех проверок. Возвращает словарь для API/Redis:
    ``{ "status": "pass"|"warning"|"fail", "checks": [...] }``.
    """
    checks: list[dict[str, Any]] = []
    solids_by_id = _build_solids_map(blueprint, warnings)

    if len(solids_by_id) < 1:
        return {"status": "pass", "checks": []}

    # 1) Interference (высший приоритет)
    checks.extend(_pairwise_interference(solids_by_id, blueprint))

    # 2) Thin features
    checks.extend(_thin_feature_heuristic(solids_by_id))

    # 3) Overhangs (по каждой детали, максимум одно предупреждение на part)
    seen_oh: set[str] = set()
    for pid, solid in solids_by_id.items():
        oh = _overhang_heuristic(solid, pid)
        if oh is not None and pid not in seen_oh:
            checks.append(oh)
            seen_oh.add(pid)

    # 4) Proportion (fillet/chamfer vs bbox)
    checks.extend(_proportion_fillet_chamfer(blueprint, solids_by_id))

    status = aggregate_diagnostics_status(checks)
    return {"status": status, "checks": checks}
