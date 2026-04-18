"""Построение базовых тел без операций (примитивы v1)."""

from __future__ import annotations

from typing import Any, Sequence

import cadquery as cq

from worker.core.exceptions import BlueprintGenerationError
from worker.core.profile_preflight import (
    validate_extruded_profile_points,
    validate_revolved_profile_points,
)


def make_cylinder(radius: float, height: float) -> cq.Workplane:
    """Цилиндр вдоль +Z, основание в Z=0 (как ``circle().extrude``)."""
    return cq.Workplane("XY").circle(radius).extrude(height)


def make_box(length: float, width: float, height: float) -> cq.Workplane:
    """Параллелепипед, центрированный по умолчанию (как ``Workplane.box``)."""
    return cq.Workplane("XY").box(length, width, height)


def make_extruded_profile(points: Sequence[Any], height: float) -> cq.Workplane:
    """
    Замкнутый 2D-полигон в плоскости XY, экструзия вдоль +Z на ``height``.

    ``points`` проходят предпроверку (см. ``validate_extruded_profile_points``).
    """
    cleaned = validate_extruded_profile_points(points)
    h = float(height)
    if h <= 0:
        raise BlueprintGenerationError("extruded_profile: height должен быть > 0")
    return cq.Workplane("XY").polyline(cleaned).close().extrude(h)


def make_revolved_profile(points: Sequence[Any], angle_deg: float) -> cq.Workplane:
    """
    Замкнутый контур в плоскости XZ (x — от оси Y, z — вдоль Z), вращение вокруг Y.

    См. ``validate_revolved_profile_points`` (x >= 0, угол (0,360], политика оси).
    """
    cleaned, ang = validate_revolved_profile_points(points, angle_deg)
    return cq.Workplane("XZ").polyline(cleaned).close().revolve(
        float(ang),
        (0, 0, 0),
        (0, 1, 0),
    )
