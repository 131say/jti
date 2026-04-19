"""
Инженерная диагностика (DFM MVP): эвристики на базе CadQuery.

Interference — приоритет #1 (критично). gear_mesh: fail/warning/info по зацеплению.
Остальные эвристики — WARNING (или info только для gear_mesh «всё ок»).
"""

from __future__ import annotations

import logging
import math
from typing import Any

import cadquery as cq

from worker.core.diagnostics_status import aggregate_diagnostics_status
from worker.core.fasteners import assembly_pose
from worker.generator import build_part_solid

logger = logging.getLogger(__name__)

# Минимальный объём пересечения двух тел (мм³), считающийся коллизией.
INTERFERENCE_EPS_MM3 = 1e-2
# Порог «тонкой» стенки (мм) — эвристика, не wall-thickness solver.
THIN_FEATURE_MM = 1.0
# Игнорировать нижние грани у подошвы (мм над z_min).
BUILD_PLATE_TOLERANCE_MM = 0.5
# Зубчатые пары: коллинеарность осей (|dot|).
_GEAR_AXIS_PARALLEL_ABS_DOT_MIN = 0.985
# Допуск соосности по оси шестерни (мм): |Δ вдоль оси| ≤ max(h)·k + ε.
_GEAR_AXIAL_ALIGN_FACTOR = 0.65
_GEAR_AXIAL_PAD_MM = 0.6

CheckSeverity = str  # "pass" | "warning" | "fail" | "info"
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


def _vec_len(v: tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _vec_norm(v: tuple[float, float, float]) -> tuple[float, float, float]:
    L = _vec_len(v)
    if L < 1e-9:
        return (0.0, 0.0, 1.0)
    return (v[0] / L, v[1] / L, v[2] / L)


def _vec_sub(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec_dot(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vec_scale(v: tuple[float, float, float], s: float) -> tuple[float, float, float]:
    return (v[0] * s, v[1] * s, v[2] * s)


def _gear_axis_unit_from_part(part: dict[str, Any]) -> tuple[float, float, float]:
    """Локальная ось +Z шестерни в мировых координатах (только вращение из rotation)."""
    rot = part.get("rotation")
    rx = ry = rz = 0.0
    if rot is not None and len(rot) >= 3:
        rx, ry, rz = float(rot[0]), float(rot[1]), float(rot[2])
    try:
        rloc = cq.Location(cq.Rot(rx, ry, rz))
        v = rloc * cq.Vector(0.0, 0.0, 1.0)
        return _vec_norm((float(v.x), float(v.y), float(v.z)))
    except Exception:
        return (0.0, 0.0, 1.0)


def _placed_solid(part: dict[str, Any], warnings: list[str] | None) -> cq.Shape | None:
    try:
        raw = build_part_solid(part, warnings)
        loc = assembly_pose(part)
        if hasattr(raw, "moved"):
            return raw.moved(loc)
        t = loc.translation()
        return raw.translate((float(t.x), float(t.y), float(t.z)))
    except Exception as e:
        pid = part.get("part_id", "?")
        w = warnings if warnings is not None else []
        w.append(f"diagnostics gear_mesh: деталь {pid}: {e!s}")
        return None


def _bbox_center(shape: cq.Shape) -> tuple[float, float, float] | None:
    try:
        bb = shape.BoundingBox()
        return (
            (bb.xmin + bb.xmax) * 0.5,
            (bb.ymin + bb.ymax) * 0.5,
            (bb.zmin + bb.zmax) * 0.5,
        )
    except Exception:
        return None


def _parse_gear_row(part: dict[str, Any]) -> dict[str, Any] | None:
    if part.get("base_shape") != "gear":
        return None
    p = part.get("parameters") or {}
    try:
        m = float(p["module"])
        z = int(p["teeth"])
        h = float(p["thickness"])
    except (KeyError, TypeError, ValueError):
        return None
    if m <= 0 or z < 4 or h <= 0:
        return None
    pid = str(part.get("part_id") or "")
    if not pid:
        return None
    return {"part": part, "part_id": pid, "m": m, "z": z, "h": h}


def _ideal_center_distance(m: float, z1: int, z2: int) -> float:
    """Межосевое с микро-зазором: m(z1+z2)/2 + 0.05m."""
    return m * (z1 + z2) * 0.5 + 0.05 * m


def _mesh_tolerance(m: float) -> float:
    return 0.1 * m


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return abs(a)


def _gear_ratio_phrase(z1: int, z2: int) -> str:
    g = _gcd(z1, z2)
    n1, n2 = z1 // g, z2 // g
    return f"{n1}:{n2}"


def check_gear_meshes(
    blueprint: dict[str, Any],
    warnings: list[str] | None,
) -> list[dict[str, Any]]:
    """
    Пары шестерён: параллельные оси, одна плоскость зацепления, межосевое vs m(z1+z2)/2+backlash.
    FAIL при несовпадении модулей в зацеплении; WARNING при плохом расстоянии; INFO при успехе.
    """
    rows: list[dict[str, Any]] = []
    for part in (blueprint.get("geometry") or {}).get("parts") or []:
        if not isinstance(part, dict):
            continue
        row = _parse_gear_row(part)
        if row is not None:
            rows.append(row)
    if len(rows) < 2:
        return []

    placed: dict[str, tuple[cq.Shape, dict[str, Any], tuple[float, float, float], tuple[float, float, float]]] = {}
    for row in rows:
        part = row["part"]
        sh = _placed_solid(part, warnings)
        if sh is None:
            continue
        c = _bbox_center(sh)
        if c is None:
            continue
        u = _gear_axis_unit_from_part(part)
        placed[row["part_id"]] = (sh, row, c, u)

    ids = sorted(placed.keys())
    out: list[dict[str, Any]] = []
    for i, id_a in enumerate(ids):
        _, ra, ca, ua = placed[id_a]
        for id_b in ids[i + 1 :]:
            _, rb, cb, ub = placed[id_b]
            dot_ax = abs(_vec_dot(ua, ub))
            if dot_ax < _GEAR_AXIS_PARALLEL_ABS_DOT_MIN:
                continue

            # use ua as reference axis (flip ub if opposite for axial scalar)
            u_ref = ua if _vec_dot(ua, ub) >= 0.0 else _vec_scale(ub, -1.0)
            sep = _vec_sub(cb, ca)
            axial = abs(_vec_dot(sep, u_ref))
            h_max = max(float(ra["h"]), float(rb["h"]))
            axial_tol = h_max * _GEAR_AXIAL_ALIGN_FACTOR + _GEAR_AXIAL_PAD_MM
            if axial > axial_tol:
                continue

            # межосевое в плоскости зацепления
            along = _vec_scale(u_ref, _vec_dot(sep, u_ref))
            perp = _vec_sub(sep, along)
            L = _vec_len(perp)

            z1, z2 = int(ra["z"]), int(rb["z"])
            m1, m2 = float(ra["m"]), float(rb["m"])
            m_mid = 0.5 * (m1 + m2)
            a_nom = _ideal_center_distance(m_mid, z1, z2)
            tol = _mesh_tolerance(m_mid)

            meshing = abs(L - a_nom) <= tol

            id_lo, id_hi = (id_a, id_b) if id_a < id_b else (id_b, id_a)
            r_lo = ra if id_lo == id_a else rb
            r_hi = rb if id_hi == id_b else ra
            z_lo, z_hi = int(r_lo["z"]), int(r_hi["z"])

            if meshing and abs(m1 - m2) > 1e-5:
                out.append(
                    {
                        "type": "gear_mesh",
                        "severity": "fail",
                        "message": (
                            f"Несовпадение модулей в зацеплении: «{id_a}» m={m1:g}, "
                            f"«{id_b}» m={m2:g} (межосевое L≈{L:.3f} мм)."
                        ),
                        "part_ids": [id_lo, id_hi],
                        "metrics": {
                            "center_distance_mm": round(L, 6),
                            "module_a": round(m1, 6),
                            "module_b": round(m2, 6),
                            "meshing": True,
                        },
                    }
                )
                continue

            if meshing and abs(m1 - m2) <= 1e-5:
                ratio = _gear_ratio_phrase(z_lo, z_hi)
                out.append(
                    {
                        "type": "gear_mesh",
                        "severity": "info",
                        "message": (
                            f"Обнаружена корректная зубчатая пара (z={z_lo} и z={z_hi}). "
                            f"Передаточное число: {ratio}."
                        ),
                        "part_ids": [id_lo, id_hi],
                        "metrics": {
                            "center_distance_mm": round(L, 6),
                            "ideal_center_distance_mm": round(a_nom, 6),
                            "module_mm": round(m1, 6),
                            "teeth_a": z_lo,
                            "teeth_b": z_hi,
                            "gear_ratio": ratio,
                            "gear_ratio_value": round(z_hi / z_lo, 6)
                            if z_lo > 0
                            else None,
                        },
                    }
                )
                continue

            if abs(m1 - m2) <= 1e-5:
                if L < a_nom - 2.0 * tol:
                    out.append(
                        {
                            "type": "gear_mesh",
                            "severity": "warning",
                            "message": (
                                f"Пара «{id_lo}» / «{id_hi}»: оси параллельны, но межосевое "
                                f"L≈{L:.3f} мм меньше ожидаемого для зацепления "
                                f"(m={m1:g}). Риск пересечения венцов."
                            ),
                            "part_ids": [id_lo, id_hi],
                            "metrics": {
                                "center_distance_mm": round(L, 6),
                                "recommended_center_distance_mm": round(a_nom, 6),
                            },
                        }
                    )
                elif L > a_nom + 2.0 * tol:
                    out.append(
                        {
                            "type": "gear_mesh",
                            "severity": "warning",
                            "message": (
                                f"Пара «{id_lo}» / «{id_hi}»: оси параллельны, но межосевое "
                                f"L≈{L:.3f} мм слишком велико для зацепления (m={m1:g}). "
                                f"Оптимальное межосевое расстояние: {a_nom:.3f} мм."
                            ),
                            "part_ids": [id_lo, id_hi],
                            "metrics": {
                                "center_distance_mm": round(L, 6),
                                "recommended_center_distance_mm": round(a_nom, 6),
                            },
                        }
                    )
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


def _gearbox_meta_checks(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    """INFO-статусы после expand generators.gearbox (передаточное число, кинематика)."""
    meta = (blueprint.get("metadata") or {}).get("gearbox_expansion")
    if not isinstance(meta, dict):
        return []
    req = meta.get("requested_ratio")
    act = meta.get("actual_ratio")
    z1 = meta.get("z1")
    z2 = meta.get("z2")
    try:
        req_f = float(req) if req is not None else 0.0
        act_f = float(act) if act is not None else 0.0
    except (TypeError, ValueError):
        return []
    msg = (
        f"Requested ratio: {req_f:g}, actual: {act_f:.4g} "
        f"(z1={z1!s}, z2={z2!s})"
    )
    checks: list[dict[str, Any]] = [
        {
            "type": "gearbox_info",
            "severity": "info",
            "message": msg,
            "part_ids": [],
            "metrics": None,
        },
        {
            "type": "kinematics",
            "severity": "info",
            "message": (
                "Gears rotate in opposite directions (correct for external spur mesh)."
            ),
            "part_ids": [],
            "metrics": None,
        },
    ]
    return checks


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

    # 1b) Зубчатые пары (модуль / межосевое / передаточное число)
    checks.extend(check_gear_meshes(blueprint, warnings))

    checks.extend(_gearbox_meta_checks(blueprint))

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
