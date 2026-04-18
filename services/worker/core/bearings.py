"""
Стандартные подшипники (каталог): упрощённое кольцо OD/ID/ширина без шариков (MVP).
"""

from __future__ import annotations

import re
from typing import Any

import cadquery as cq

from worker.core.exceptions import BlueprintGenerationError


class _BearingSpec:
    __slots__ = ("bore_d", "outer_d", "width")

    def __init__(self, *, bore_d: float, outer_d: float, width: float) -> None:
        self.bore_d = float(bore_d)
        self.outer_d = float(outer_d)
        self.width = float(width)


# Ключи — нормализованные строки (нижний регистр, без пробелов)
BEARING_TABLE: dict[str, _BearingSpec] = {
    "608": _BearingSpec(bore_d=8.0, outer_d=22.0, width=7.0),
    "608zz": _BearingSpec(bore_d=8.0, outer_d=22.0, width=7.0),
    "6000": _BearingSpec(bore_d=10.0, outer_d=26.0, width=8.0),
    "6000zz": _BearingSpec(bore_d=10.0, outer_d=26.0, width=8.0),
    "6001": _BearingSpec(bore_d=12.0, outer_d=28.0, width=8.0),
    "6001zz": _BearingSpec(bore_d=12.0, outer_d=28.0, width=8.0),
    "6200": _BearingSpec(bore_d=10.0, outer_d=30.0, width=9.0),
    "6200zz": _BearingSpec(bore_d=10.0, outer_d=30.0, width=9.0),
    "6201": _BearingSpec(bore_d=12.0, outer_d=32.0, width=10.0),
    "6201zz": _BearingSpec(bore_d=12.0, outer_d=32.0, width=10.0),
    "6202": _BearingSpec(bore_d=15.0, outer_d=35.0, width=11.0),
    "6202zz": _BearingSpec(bore_d=15.0, outer_d=35.0, width=11.0),
}


def _normalize_series(series: str) -> str:
    s = str(series).strip().lower()
    s = re.sub(r"\s+", "", s)
    return s


def get_bearing_spec(series: str) -> _BearingSpec:
    key = _normalize_series(series)
    if key not in BEARING_TABLE:
        known = ", ".join(sorted(set(BEARING_TABLE.keys()))[:12])
        raise BlueprintGenerationError(
            f"bearing: неизвестная серия {series!r}. Примеры: {known}, …"
        )
    return BEARING_TABLE[key]


def make_bearing_solid(parameters: dict[str, Any]) -> cq.Shape:
    series = str(parameters.get("series") or "")
    sp = get_bearing_spec(series)
    r_out = sp.outer_d / 2.0
    r_in = sp.bore_d / 2.0
    h = sp.width
    if r_in >= r_out:
        raise BlueprintGenerationError("bearing: некорректные размеры кольца")
    outer = cq.Workplane("XY").circle(r_out).extrude(h)
    return outer.faces(">Z").workplane().circle(r_in).cutThruAll().val()


def bearing_catalog_label(parameters: dict[str, Any]) -> str:
    series = str(parameters.get("series") or "?")
    return f"Стандартное изделие: Подшипник {series.strip()}"


def purchased_bearing_price_usd(parameters: dict[str, Any]) -> float:
    """Ориентиры BOM (USD)."""
    key = _normalize_series(str(parameters.get("series") or ""))
    table: dict[str, float] = {
        "608": 0.35,
        "608zz": 0.35,
        "6000": 0.45,
        "6000zz": 0.45,
        "6001": 0.50,
        "6001zz": 0.50,
        "6200": 0.55,
        "6200zz": 0.55,
        "6201": 0.65,
        "6201zz": 0.65,
        "6202": 0.75,
        "6202zz": 0.75,
    }
    return table.get(key, 0.50)
