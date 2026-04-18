"""Атомарные булевы операции и вспомогательная геометрия (CadQuery)."""

from __future__ import annotations

import logging
import math
from typing import Any, Union

import cadquery as cq
from cadquery.occ_impl.geom import Plane

from worker.core.exceptions import BlueprintGenerationError

logger = logging.getLogger(__name__)

# Макс. диаметр отверстия относительно минимального ребра bbox (чуть < 1.0 — зазор для ядра).
HOLE_DIAM_MAX_FACTOR = 1.0 - 1e-4


def normalize_edge_selector(selector: str) -> str | None:
    """
    Преобразует значение ``selector`` из Blueprint в аргумент CadQuery ``edges(...)``.

    - ``ALL`` (регистронезависимо) или пустая строка — все рёбра (``None`` → ``edges()`` без фильтра).
    - Одиночные ``X`` / ``Y`` / ``Z`` — рёбра, параллельные оси (``|X``, ``|Y``, ``|Z``).
    - Иначе строка передаётся как есть (например ``>Z``, ``<X``, ``|Z``).
    """
    s = (selector or "").strip()
    if not s or s.upper() == "ALL":
        return None
    if s in ("X", "Y", "Z"):
        return f"|{s}"
    return s


def apply_fillet(
    wp: cq.Workplane,
    radius: float,
    selector: str = "ALL",
) -> cq.Workplane:
    """
    Скругление рёбер тела на стеке ``Workplane``.

    См. ``normalize_edge_selector`` для значений ``selector``.
    """
    if radius <= 0:
        raise BlueprintGenerationError("fillet: radius должен быть > 0")
    try:
        solid = wp.findSolid()
    except ValueError as e:
        raise BlueprintGenerationError("apply_fillet: на стеке нет solid") from e

    sel = normalize_edge_selector(selector)
    cut_wp = cq.Workplane().add(solid)
    if sel is None:
        return cut_wp.edges().fillet(radius)
    return cut_wp.edges(sel).fillet(radius)


def apply_chamfer(
    wp: cq.Workplane,
    length: float,
    selector: str = "ALL",
) -> cq.Workplane:
    """Фаска на рёбрах; параметры аналогичны ``apply_fillet``."""
    if length <= 0:
        raise BlueprintGenerationError("chamfer: length должен быть > 0")
    try:
        solid = wp.findSolid()
    except ValueError as e:
        raise BlueprintGenerationError("apply_chamfer: на стеке нет solid") from e

    sel = normalize_edge_selector(selector)
    cut_wp = cq.Workplane().add(solid)
    if sel is None:
        return cut_wp.edges().chamfer(length)
    return cut_wp.edges(sel).chamfer(length)


def clamp_hole_diameter_to_solid(
    solid: cq.Shape,
    diameter: float,
    *,
    part_id: str | None = None,
    warnings: list[str] | None = None,
) -> float:
    """
    Ограничивает диаметр отверстия долей от минимального габарита тела (по bbox),
    чтобы избежать заведомо некорректных вырезов относительно размеров детали.
    """
    if diameter <= 0:
        return diameter
    try:
        bb = solid.BoundingBox()
    except Exception:
        return diameter
    extent = min(bb.xlen, bb.ylen, bb.zlen)
    if extent <= 0:
        return diameter
    cap = extent * HOLE_DIAM_MAX_FACTOR
    if diameter > cap:
        pid = part_id or "?"
        msg = (
            f"Part '{pid}': hole diameter clamped from {diameter:.6g} mm to {cap:.6g} mm "
            f"(max ≈ min bbox edge × {HOLE_DIAM_MAX_FACTOR:g}, extent={extent:.6g} mm)"
        )
        logger.info("%s", msg)
        if warnings is not None:
            warnings.append(msg)
        return cap
    return diameter


def normalize_direction(
    direction: tuple[float, float, float] | list[float],
) -> tuple[float, float, float]:
    """Нормализует вектор направления; нулевой вектор — ошибка."""
    x, y, z = float(direction[0]), float(direction[1]), float(direction[2])
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-9:
        raise BlueprintGenerationError("Вектор direction не должен быть нулевым")
    return (x / n, y / n, z / n)


def apply_hole(
    wp: cq.Workplane,
    diameter: float,
    position: tuple[float, float, float],
    direction: tuple[float, float, float],
    depth: Union[float, str],
) -> cq.Workplane:
    """
    Сквозное или глухое цилиндрическое отверстие в теле на стеке ``Workplane``.

    :param wp: Рабочая плоскость с ровно одним **solid** на стеке (через ``add(solid)``).
    :param diameter: Диаметр отверстия.
    :param position: Точка на оси отверстия (мировые координаты).
    :param direction: Ось сверла; будет нормализован.
    :param depth: ``\"through_all\"`` или положительная глубина для ``cutBlind``.
    :return: Новый ``Workplane`` с результатом вычитания.
    """
    if diameter <= 0:
        raise BlueprintGenerationError("diameter должен быть > 0")

    try:
        solid = wp.findSolid()
    except ValueError as e:
        raise BlueprintGenerationError("apply_hole: на стеке нет solid") from e

    ndir = normalize_direction(direction)
    radius = diameter / 2.0
    plane = Plane(position, None, ndir)
    cut_wp = cq.Workplane(plane).add(solid).circle(radius)

    if depth == "through_all":
        return cut_wp.cutThruAll()

    if isinstance(depth, (int, float)):
        d = float(depth)
        if d <= 0:
            raise BlueprintGenerationError("Числовой depth должен быть > 0")
        return cut_wp.cutBlind(d)

    raise BlueprintGenerationError(
        "depth должен быть числом или строкой 'through_all'"
    )


def expand_linear_pattern_to_hole_dicts(op: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Разворачивает ``linear_pattern`` в список операций ``hole``.

    Базовая точка первой копии — ``position`` дочернего hole; сетка в плоскости XY:
    x += i * spacing_x, y += j * spacing_y, z без изменений.
    Порядок: j = 0..count_y-1, i = 0..count_x-1.
    """
    inner = op.get("operation")
    if not isinstance(inner, dict) or inner.get("type") != "hole":
        raise BlueprintGenerationError(
            "linear_pattern: вложенная operation должна быть type=hole"
        )
    pos = inner["position"]
    cx, cy, cz = float(pos[0]), float(pos[1]), float(pos[2])
    count_x = int(op["count_x"])
    count_y = int(op["count_y"])
    if count_x < 1 or count_y < 1:
        raise BlueprintGenerationError(
            "linear_pattern: count_x и count_y должны быть >= 1"
        )
    sx = float(op["spacing_x"])
    sy = float(op["spacing_y"])
    out: list[dict[str, Any]] = []
    for j in range(count_y):
        for i in range(count_x):
            px = cx + i * sx
            py = cy + j * sy
            pz = cz
            h = {**inner, "position": [px, py, pz]}
            out.append(h)
    return out


def expand_circular_pattern_to_hole_dicts(op: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Круговой массив: точки на окружности в плоскости XY через ``center``, ``radius``.
    Угол ``angle`` (градусы) делится на ``count`` интервалов; ``position`` дочернего hole не используется.
    """
    inner = op.get("operation")
    if not isinstance(inner, dict) or inner.get("type") != "hole":
        raise BlueprintGenerationError(
            "circular_pattern: вложенная operation должна быть type=hole"
        )
    center = op["center"]
    r = float(op["radius"])
    count = int(op["count"])
    angle_total = float(op["angle"])
    if count < 1:
        raise BlueprintGenerationError("circular_pattern: count должен быть >= 1")
    out: list[dict[str, Any]] = []
    for i in range(count):
        theta_deg = (i / count) * angle_total if count > 0 else 0.0
        theta = math.radians(theta_deg)
        px = float(center[0]) + r * math.cos(theta)
        py = float(center[1]) + r * math.sin(theta)
        pz = float(center[2])
        h = {**inner, "position": [px, py, pz]}
        out.append(h)
    return out
