"""
Предпроверки 2D-контура: extruded_profile (XY) и revolved_profile (XZ, вращение вокруг Y).

Без молчаливой «починки» — только явные ``BlueprintGenerationError``.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from worker.core.exceptions import BlueprintGenerationError

# Минимальная длина ребра после нормализации (мм).
EDGE_LENGTH_MIN_MM = 0.01
# Точки считаются совпадающими, если ближе (мм).
_POINT_MERGE_MM = 1e-7
# Ось вращения X=0 в эскизе revolved_profile (мм).
_AXIS_X_EPS_MM = 1e-6


def _dist2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _to_pairs(raw: Sequence[Any], *, label: str) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in raw:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise BlueprintGenerationError(
                f"{label}: каждая точка должна быть парой [x, y]"
            )
        out.append((float(p[0]), float(p[1])))
    return out


def _ccw(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    """Псевдоскалярное произведение (ориентация); ~0 — коллинеарно."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(
    a: tuple[float, float],
    b: tuple[float, float],
    p: tuple[float, float],
    eps: float = 1e-12,
) -> bool:
    if abs(_ccw(a, b, p)) > eps:
        return False
    return (
        min(a[0], b[0]) - 1e-12 <= p[0] <= max(a[0], b[0]) + 1e-12
        and min(a[1], b[1]) - 1e-12 <= p[1] <= max(a[1], b[1]) + 1e-12
    )


def _segments_intersect_proper(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> bool:
    d1 = _ccw(p1, p2, p3)
    d2 = _ccw(p1, p2, p4)
    d3 = _ccw(p3, p4, p1)
    d4 = _ccw(p3, p4, p2)

    if (
        (d1 > 1e-15 and d2 < -1e-15 or d1 < -1e-15 and d2 > 1e-15)
        and (d3 > 1e-15 and d4 < -1e-15 or d3 < -1e-15 and d4 > 1e-15)
    ):
        return True

    if abs(d1) <= 1e-12 and _on_segment(p1, p2, p3):
        return True
    if abs(d1) <= 1e-12 and _on_segment(p1, p2, p4):
        return True
    if abs(d3) <= 1e-12 and _on_segment(p3, p4, p1):
        return True
    if abs(d3) <= 1e-12 and _on_segment(p3, p4, p2):
        return True

    return False


def _polygon_self_intersects(pts: list[tuple[float, float]]) -> bool:
    n = len(pts)
    if n < 4:
        return False
    for i in range(n):
        a1, a2 = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            b1, b2 = pts[j], pts[(j + 1) % n]
            vi = {i, (i + 1) % n}
            vj = {j, (j + 1) % n}
            if vi & vj:
                continue
            if _segments_intersect_proper(a1, a2, b1, b2):
                return True
    return False


def _normalize_closed_polygon_2d(
    raw_points: Sequence[Any],
    *,
    label: str,
) -> list[tuple[float, float]]:
    """Общая нормализация замкнутого 2D-полигона (дубликаты, рёбра, самопересечение)."""
    pts = _to_pairs(raw_points, label=label)
    if len(pts) < 3:
        raise BlueprintGenerationError(
            f"{label}: нужно не менее трёх точек [x, y]"
        )

    if len(pts) >= 4 and _dist2(pts[0], pts[-1]) <= _POINT_MERGE_MM:
        pts = pts[:-1]

    cleaned: list[tuple[float, float]] = [pts[0]]
    for p in pts[1:]:
        if _dist2(p, cleaned[-1]) > _POINT_MERGE_MM:
            cleaned.append(p)

    if (
        len(cleaned) >= 2
        and _dist2(cleaned[0], cleaned[-1]) <= _POINT_MERGE_MM
    ):
        cleaned = cleaned[:-1]

    if len(cleaned) < 3:
        raise BlueprintGenerationError(
            f"{label}: после нормализации осталось менее трёх различимых вершин"
        )

    n = len(cleaned)
    for i in range(n):
        a = cleaned[i]
        b = cleaned[(i + 1) % n]
        if _dist2(a, b) < EDGE_LENGTH_MIN_MM:
            raise BlueprintGenerationError(
                f"{label}: вырожденное ребро (длина < {EDGE_LENGTH_MIN_MM} мм)"
            )

    if _polygon_self_intersects(cleaned):
        raise BlueprintGenerationError(f"{label}: контур самопересекается")

    return cleaned


def _edge_lies_on_revolve_axis(
    a: tuple[float, float],
    b: tuple[float, float],
) -> bool:
    """Ребро целиком на оси вращения X=0 в эскизе (оба конца на оси)."""
    return abs(a[0]) < _AXIS_X_EPS_MM and abs(b[0]) < _AXIS_X_EPS_MM


def _check_revolve_axis_touch_policy(pts: list[tuple[float, float]]) -> None:
    """
    Не более одного непрерывного набора рёбер, лежащих на X=0.
    Несколько разрозненных участков на оси → риск non-manifold / ошибок BRep.
    """
    n = len(pts)
    on_axis_edge = [
        _edge_lies_on_revolve_axis(pts[i], pts[(i + 1) % n]) for i in range(n)
    ]
    runs = 0
    for i in range(n):
        if on_axis_edge[i] and not on_axis_edge[(i - 1) % n]:
            runs += 1
    if runs > 1:
        raise BlueprintGenerationError(
            "revolved_profile: несколько разрозненных участков контура на оси вращения "
            "(X=0) не поддерживаются; допустимы один непрерывный отрезок на оси или "
            "касание только в отдельных вершинах без цепочки рёбер на оси"
        )


def validate_extruded_profile_points(
    raw_points: Sequence[Any],
) -> list[tuple[float, float]]:
    """Контур в XY для экструзии вдоль +Z."""
    return _normalize_closed_polygon_2d(raw_points, label="extruded_profile")


def validate_revolved_profile_points(
    raw_points: Sequence[Any],
    angle_deg: float,
) -> tuple[list[tuple[float, float]], float]:
    """
    Контур в плоскости XZ эскиза: (x, z), x — расстояние от оси вращения Y, x >= 0.
    Угол вращения: (0, 360] градусов.
    """
    cleaned = _normalize_closed_polygon_2d(raw_points, label="revolved_profile")
    ang = float(angle_deg)
    if ang <= 0.0 or ang > 360.0:
        raise BlueprintGenerationError(
            "revolved_profile: angle должен быть в интервале (0, 360] градусов"
        )

    for p in cleaned:
        if p[0] < -_AXIS_X_EPS_MM:
            raise BlueprintGenerationError(
                "Revolve profile crosses the axis of revolution (X < 0)"
            )

    _check_revolve_axis_touch_policy(cleaned)
    return cleaned, ang
