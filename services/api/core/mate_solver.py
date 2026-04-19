"""
Разрешение assembly_mates: v3.0 snap_to_operation + v3.5 constraints
(concentric, coincident, distance). Детерминированный топосорт и порядок
concentric → coincident → distance на каждую source-деталь.

Внутри: scipy.spatial.transform.Rotation (кватернионы); в Blueprint — Эйлер xyz (градусы).
"""

from __future__ import annotations

import copy
import logging
from collections import defaultdict, deque
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


def _rotation_align_local_z_to_world(dir_world: np.ndarray) -> Rotation:
    """Локальная +Z → dir_world (единичный)."""
    d = _normalize(dir_world.reshape(3))
    ez = np.array([0.0, 0.0, 1.0], dtype=float)
    rot, _ = Rotation.align_vectors(d.reshape(1, 3), ez.reshape(1, 3))
    return rot


def _euler_xyz_deg(R: Rotation) -> tuple[float, float, float]:
    e = R.as_euler("xyz", degrees=True)
    return float(e[0]), float(e[1]), float(e[2])


def _perpendicular_unit(u: np.ndarray) -> np.ndarray:
    u = _normalize(u)
    for cand in (
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
    ):
        w = np.cross(u, cand)
        nw = float(np.linalg.norm(w))
        if nw > 1e-9:
            return w / nw
    return np.array([1.0, 0.0, 0.0])


def _hole_from_operation(
    op: dict[str, Any],
    *,
    part_id: str,
    idx: int,
) -> tuple[np.ndarray, np.ndarray]:
    ot = op.get("type")
    if ot != "hole":
        raise MateResolutionError(
            f"mate hole ref: part {part_id!r}, operation[{idx}] имеет type={ot!r}; "
            "для concentric/snap допускается только hole (MVP)."
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
    mate_ctx: dict[str, dict[str, Any]],
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

    R_align = _rotation_align_local_z_to_world(d_world)
    rx, ry, rz = _euler_xyz_deg(R_align)
    src_part["position"] = (float(p_world[0]), float(p_world[1]), float(p_world[2]))
    src_part["rotation"] = (rx, ry, rz)
    ctx = mate_ctx.setdefault(part_id, {})
    ctx["axis_u"] = _normalize(d_world)
    ctx["anchor_world"] = p_world.copy()


def _apply_concentric(
    src_part: dict[str, Any],
    mate: dict[str, Any],
    tgt_part: dict[str, Any],
    *,
    part_id: str,
    tgt_id: str,
    warnings: list[str],
    mate_ctx: dict[str, dict[str, Any]],
) -> None:
    idx = mate.get("target_operation_index")
    if not isinstance(idx, int) or idx < 0:
        raise MateResolutionError(
            f"concentric {part_id!r}: target_operation_index должен быть int >= 0"
        )
    rev = bool(mate.get("reverse_direction", False))
    ops = tgt_part.get("operations")
    if not isinstance(ops, list) or idx >= len(ops):
        raise MateResolutionError(f"concentric: у детали {tgt_id!r} нет operations[{idx}]")
    op = ops[idx]
    if not isinstance(op, dict):
        raise MateResolutionError(f"operations[{idx}] у {tgt_id!r} должен быть объектом")
    p_loc, d_loc = _hole_from_operation(op, part_id=tgt_id, idx=idx)
    R_t, T_t = _pose_to_RT(tgt_part)
    d_world = _RT_apply_dir(R_t, d_loc)
    if rev:
        d_world = -d_world
    d_world = _normalize(d_world)

    if src_part.get("rotation") is not None:
        warnings.append(
            f"assembly_mates: concentric перезаписывает rotation у {part_id!r} (ось → hole)"
        )
    R_align = _rotation_align_local_z_to_world(d_world)
    rx, ry, rz = _euler_xyz_deg(R_align)
    src_part["rotation"] = (rx, ry, rz)
    p_world = _RT_apply_point(R_t, T_t, p_loc)
    ctx = mate_ctx.setdefault(part_id, {})
    ctx["axis_u"] = d_world.copy()
    ctx["anchor_world"] = p_world.copy()


def _apply_coincident(
    src_part: dict[str, Any],
    mate: dict[str, Any],
    tgt_part: dict[str, Any],
    *,
    part_id: str,
    tgt_id: str,
    warnings: list[str],
    mate_ctx: dict[str, dict[str, Any]],
) -> None:
    ctx = mate_ctx.setdefault(part_id, {})
    u = ctx.get("axis_u")
    if u is None:
        _, t_s = _pose_to_RT(src_part)
        _, t_t = _pose_to_RT(tgt_part)
        delta = t_s - t_t
        nu = float(np.linalg.norm(delta))
        if nu < 1e-9:
            u = np.array([1.0, 0.0, 0.0], dtype=float)
        else:
            u = delta / nu
    else:
        u = _normalize(np.asarray(u, dtype=float))

    off = float(mate.get("offset", 0) or 0)
    flip = bool(mate.get("flip", False))
    if flip:
        u = -u
        ctx["axis_u"] = u.copy()
    else:
        ctx["axis_u"] = u.copy()

    anchor = ctx.get("anchor_world")
    if anchor is not None:
        target_center = np.asarray(anchor, dtype=float).reshape(3)
    else:
        _, t_t = _pose_to_RT(tgt_part)
        target_center = t_t
    pos = target_center + off * u

    if src_part.get("position") is not None:
        warnings.append(
            f"assembly_mates: coincident перезаписывает position у {part_id!r}"
        )

    R_mat, _ = _pose_to_RT(src_part)
    r_s = Rotation.from_matrix(R_mat)
    if flip:
        r_s = r_s * Rotation.from_rotvec(np.pi * _perpendicular_unit(u))
    euler = r_s.as_euler("xyz", degrees=True)
    src_part["position"] = (float(pos[0]), float(pos[1]), float(pos[2]))
    src_part["rotation"] = (float(euler[0]), float(euler[1]), float(euler[2]))


def _apply_distance(
    src_part: dict[str, Any],
    mate: dict[str, Any],
    tgt_part: dict[str, Any],
    *,
    part_id: str,
    tgt_id: str,
    warnings: list[str],
    mate_ctx: dict[str, dict[str, Any]],
) -> None:
    val = mate.get("value")
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise MateResolutionError(
            f"distance {part_id!r}: value должен быть числом (после resolve $-выражений)"
        )
    dist = float(val)

    ctx = mate_ctx.setdefault(part_id, {})
    u = ctx.get("axis_u")
    if u is None:
        _, t_s = _pose_to_RT(src_part)
        _, t_t = _pose_to_RT(tgt_part)
        delta = t_s - t_t
        nu = float(np.linalg.norm(delta))
        if nu < 1e-9:
            u = np.array([1.0, 0.0, 0.0], dtype=float)
        else:
            u = delta / nu
    else:
        u = _normalize(np.asarray(u, dtype=float))

    _, t_t = _pose_to_RT(tgt_part)
    pos = t_t + dist * u

    if src_part.get("position") is not None:
        warnings.append(
            f"assembly_mates: distance перезаписывает position у {part_id!r}"
        )

    R_mat, _ = _pose_to_RT(src_part)
    euler = Rotation.from_matrix(R_mat).as_euler("xyz", degrees=True)
    src_part["position"] = (float(pos[0]), float(pos[1]), float(pos[2]))
    src_part["rotation"] = (float(euler[0]), float(euler[1]), float(euler[2]))


_MATE_TYPE_ORDER = {
    "concentric": 0,
    "snap_to_operation": 0,
    "coincident": 1,
    "distance": 2,
}


def _mate_sort_key(m: dict[str, Any], idx: int) -> tuple[int, int]:
    t = str(m.get("type") or "")
    return (_MATE_TYPE_ORDER.get(t, 99), idx)


def _build_edges(mates_raw: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Рёбра (target, source): target должен быть резолвен раньше source."""
    edges: list[tuple[str, str]] = []
    for m in mates_raw:
        if not isinstance(m, dict):
            continue
        t = m.get("type")
        if t not in (
            "snap_to_operation",
            "concentric",
            "coincident",
            "distance",
        ):
            raise MateResolutionError(f"assembly_mates: неизвестный type {t!r}")
        s = m.get("source_part")
        tgt = m.get("target_part")
        if not isinstance(s, str) or not s:
            raise MateResolutionError(f"{t}: source_part должен быть непустой строкой")
        if not isinstance(tgt, str) or not tgt:
            raise MateResolutionError(f"{t}: target_part должен быть непустой строкой")
        edges.append((tgt, s))
    return edges


def _toposort_sources(
    mates_raw: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> list[str]:
    """Порядок применения mate к source-деталям (Kahn по рёбрам target→source)."""
    nodes: set[str] = set(by_id.keys())
    edges = _build_edges(mates_raw)
    adj: dict[str, list[str]] = defaultdict(list)
    indeg: dict[str, int] = {n: 0 for n in nodes}
    for tgt, src in edges:
        if tgt not in nodes or src not in nodes:
            raise MateResolutionError(
                f"assembly_mates: неизвестный part_id в связке {tgt!r} → {src!r}"
            )
        adj[tgt].append(src)
        indeg[src] += 1

    q = deque(sorted(n for n in nodes if indeg[n] == 0))
    order: list[str] = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in sorted(adj[u]):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)

    sources = {str(m.get("source_part")) for m in mates_raw if isinstance(m, dict)}
    if any(indeg.get(s, 0) > 0 for s in sources):
        unresolved = [s for s in sorted(sources) if indeg.get(s, 0) > 0]
        a = unresolved[0]
        b = unresolved[1] if len(unresolved) > 1 else a
        raise MateResolutionError(
            f"Обнаружена циклическая привязка между {a!r} и {b!r} (assembly_mates)."
        )

    rank = {p: i for i, p in enumerate(order)}
    return sorted(sources, key=lambda s: rank.get(s, len(order)))


def _mates_for_source_ordered(
    mates_raw: list[dict[str, Any]], source_id: str
) -> list[dict[str, Any]]:
    indexed = [
        (i, m)
        for i, m in enumerate(mates_raw)
        if isinstance(m, dict) and str(m.get("source_part") or "") == source_id
    ]
    indexed.sort(key=lambda im: _mate_sort_key(im[1], im[0]))
    return [m for _, m in indexed]


def _extract_transforms(
    blueprint: dict[str, Any],
) -> dict[str, dict[str, list[float]]]:
    out: dict[str, dict[str, list[float]]] = {}
    for p in (blueprint.get("geometry") or {}).get("parts") or []:
        if not isinstance(p, dict):
            continue
        pid = p.get("part_id")
        if not pid:
            continue
        pos = p.get("position")
        rot = p.get("rotation")
        if pos is None and rot is None:
            continue
        entry: dict[str, list[float]] = {}
        if pos is not None and len(pos) == 3:
            entry["position"] = [float(pos[0]), float(pos[1]), float(pos[2])]
        if rot is not None and len(rot) == 3:
            entry["rotation"] = [float(rot[0]), float(rot[1]), float(rot[2])]
        if entry:
            out[str(pid)] = entry
    return out


def resolve_assembly_mates(
    blueprint: dict[str, Any],
    *,
    warnings: list[str] | None = None,
    debug_constraints: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """
    Копирует blueprint, применяет assembly_mates.
    Возвращает (blueprint, resolved_transforms | None).
    """
    out = copy.deepcopy(blueprint)
    w = warnings if warnings is not None else []
    mates_raw = out.get("assembly_mates")
    if not mates_raw:
        return out, (_extract_transforms(out) if debug_constraints else None)
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

    mate_ctx: dict[str, dict[str, Any]] = {}

    src_order = _toposort_sources(mates_raw, by_id)

    for src_id in src_order:
        for mate in _mates_for_source_ordered(mates_raw, src_id):
            mt = mate.get("type")
            tgt_id = str(mate["target_part"])
            if tgt_id not in by_id:
                raise MateResolutionError(f"assembly_mates: неизвестный target_part {tgt_id!r}")
            src_part = by_id[src_id]
            tgt_part = by_id[tgt_id]
            if mt == "snap_to_operation":
                _apply_snap_mate(
                    src_part, mate, tgt_part, part_id=src_id, tgt_id=tgt_id, warnings=w, mate_ctx=mate_ctx
                )
            elif mt == "concentric":
                _apply_concentric(
                    src_part, mate, tgt_part, part_id=src_id, tgt_id=tgt_id, warnings=w, mate_ctx=mate_ctx
                )
            elif mt == "coincident":
                _apply_coincident(
                    src_part, mate, tgt_part, part_id=src_id, tgt_id=tgt_id, warnings=w, mate_ctx=mate_ctx
                )
            elif mt == "distance":
                _apply_distance(
                    src_part, mate, tgt_part, part_id=src_id, tgt_id=tgt_id, warnings=w, mate_ctx=mate_ctx
                )
            else:
                raise MateResolutionError(f"assembly_mates: неизвестный type {mt!r}")

    dbg = _extract_transforms(out) if debug_constraints else None
    return out, dbg
