"""
Стандартные метизы (M6–M12): без физической резьбы, упрощённая брутформа для MVP.
Шестигранник: второй аргумент cq.polygon — радиус описанной окружности (центр → вершина).
"""

from __future__ import annotations

import math
from typing import Any, Literal

import cadquery as cq
from cadquery import Vector

from worker.core.exceptions import BlueprintGenerationError

SizeM = Literal["M6", "M8", "M10", "M12"]


def _hex_vertex_radius(across_flats: float) -> float:
    """Расстояние центр→вершина по известному размеру под ключ (между гранями)."""
    return float(across_flats) / math.sqrt(3.0)


class _Spec:
    __slots__ = (
        "shaft_d",
        "head_af",
        "head_h",
        "nut_af",
        "nut_h",
        "hole_clr",
        "washer_od",
        "washer_t",
    )

    def __init__(
        self,
        *,
        shaft_d: float,
        head_af: float,
        head_h: float,
        nut_af: float,
        nut_h: float,
        hole_clr: float,
        washer_od: float,
        washer_t: float,
    ) -> None:
        self.shaft_d = shaft_d
        self.head_af = head_af
        self.head_h = head_h
        self.nut_af = nut_af
        self.nut_h = nut_h
        self.hole_clr = hole_clr
        self.washer_od = washer_od
        self.washer_t = washer_t


FASTENER_TABLE: dict[SizeM, _Spec] = {
    "M6": _Spec(
        shaft_d=6.0,
        head_af=10.0,
        head_h=4.0,
        nut_af=10.0,
        nut_h=5.0,
        hole_clr=6.4,
        washer_od=12.5,
        washer_t=1.6,
    ),
    "M8": _Spec(
        shaft_d=8.0,
        head_af=13.0,
        head_h=5.3,
        nut_af=13.0,
        nut_h=6.5,
        hole_clr=8.5,
        washer_od=17.0,
        washer_t=1.6,
    ),
    "M10": _Spec(
        shaft_d=10.0,
        head_af=16.0,
        head_h=6.4,
        nut_af=16.0,
        nut_h=8.0,
        hole_clr=10.5,
        washer_od=21.0,
        washer_t=2.0,
    ),
    "M12": _Spec(
        shaft_d=12.0,
        head_af=18.0,
        head_h=7.5,
        nut_af=18.0,
        nut_h=10.0,
        hole_clr=12.5,
        washer_od=24.0,
        washer_t=2.5,
    ),
}


def _get_spec(size: str) -> _Spec:
    try:
        return FASTENER_TABLE[size]  # type: ignore[index]
    except KeyError as e:
        raise BlueprintGenerationError(
            f"Неизвестный размер метиза {size!r} (допустимо M6, M8, M10, M12)"
        ) from e


def make_bolt_hex(*, size: str, length: float) -> cq.Shape:
    if length <= 0:
        raise BlueprintGenerationError("bolt_hex: length должен быть > 0")
    sp = _get_spec(size)
    rv = _hex_vertex_radius(sp.head_af)
    head = cq.Workplane("XY").polygon(6, rv).extrude(sp.head_h)
    bolt = head.faces(">Z").workplane().circle(sp.shaft_d / 2.0).extrude(length)
    return bolt.val()


def make_nut_hex(*, size: str) -> cq.Shape:
    sp = _get_spec(size)
    rv = _hex_vertex_radius(sp.nut_af)
    body = cq.Workplane("XY").polygon(6, rv).extrude(sp.nut_h)
    hole_r = sp.hole_clr / 2.0
    nut = body.faces("<Z").workplane().circle(hole_r).cutThruAll()
    return nut.val()


def make_washer(*, size: str) -> cq.Shape:
    sp = _get_spec(size)
    od = sp.washer_od
    rid = sp.hole_clr / 2.0
    ro = od / 2.0
    w = (
        cq.Workplane("XY")
        .circle(ro)
        .extrude(sp.washer_t)
        .faces("<Z")
        .workplane()
        .circle(rid)
        .cutThruAll()
    )
    return w.val()


def build_fastener_solid(parameters: dict[str, Any]) -> cq.Shape:
    ft = parameters.get("type")
    size = str(parameters.get("size") or "")
    if ft == "bolt_hex":
        length = float(parameters.get("length") or 0.0)
        return make_bolt_hex(size=size, length=length)
    if ft == "nut_hex":
        return make_nut_hex(size=size)
    if ft == "washer":
        return make_washer(size=size)
    raise BlueprintGenerationError(f"fastener: неизвестный type {ft!r}")


def fastener_catalog_label(parameters: dict[str, Any]) -> str:
    ft = parameters.get("type")
    size = str(parameters.get("size") or "?")
    if ft == "bolt_hex":
        L = float(parameters.get("length") or 0.0)
        return f"Стандартное изделие: Болт {size}×{L:.0f}"
    if ft == "nut_hex":
        return f"Стандартное изделие: Гайка {size}"
    if ft == "washer":
        return f"Стандартное изделие: Шайба {size}"
    return "Стандартное изделие"


def purchased_fastener_price_usd(parameters: dict[str, Any]) -> float:
    """Фиксированные ориентиры для BOM (USD)."""
    ft = parameters.get("type")
    size = str(parameters.get("size") or "M8")
    key = (str(ft), size)
    table: dict[tuple[str, str], float] = {
        ("bolt_hex", "M6"): 0.08,
        ("bolt_hex", "M8"): 0.10,
        ("bolt_hex", "M10"): 0.14,
        ("bolt_hex", "M12"): 0.18,
        ("nut_hex", "M6"): 0.04,
        ("nut_hex", "M8"): 0.05,
        ("nut_hex", "M10"): 0.07,
        ("nut_hex", "M12"): 0.09,
        ("washer", "M6"): 0.015,
        ("washer", "M8"): 0.02,
        ("washer", "M10"): 0.025,
        ("washer", "M12"): 0.03,
    }
    return table.get(key, 0.10)


def assembly_pose(part: dict[str, Any]) -> "cq.Location":
    """Положение детали в сборке: translation × Euler (градусы), как cq.Rot."""
    pos = part.get("position")
    rot = part.get("rotation")
    px, py, pz = 0.0, 0.0, 0.0
    if pos is not None and len(pos) >= 3:
        px, py, pz = float(pos[0]), float(pos[1]), float(pos[2])
    rx, ry, rz = 0.0, 0.0, 0.0
    if rot is not None and len(rot) >= 3:
        rx, ry, rz = float(rot[0]), float(rot[1]), float(rot[2])
    if pos is None and rot is None:
        return cq.Location()
    return cq.Location(Vector(px, py, pz)) * cq.Location(cq.Rot(rx, ry, rz))
