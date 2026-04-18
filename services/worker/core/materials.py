"""Пресеты инженерных материалов: физика (плотность, трение) и визуал (RGB, шероховатость)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MaterialPreset:
    """Стандартный материал AI-Forge (ключ — snake_case в Blueprint)."""

    key: str
    label: str
    density_kg_m3: float
    friction: float
    color_r: float
    color_g: float
    color_b: float
    roughness: float
    #: Ориентировочная цена сырья, USD / кг (оценка BOM, не финальная себестоимость).
    cost_per_kg_usd: float


def _rgb(r: float, g: float, b: float) -> tuple[float, float, float]:
    return (r, g, b)


# Плотность кг/м³; трение — скользящее (как первый коэффициент MuJoCo geom); RGB 0..1.
MATERIAL_PRESETS: dict[str, MaterialPreset] = {
    "steel": MaterialPreset(
        key="steel",
        label="Steel (Сталь)",
        density_kg_m3=7850.0,
        friction=0.42,
        color_r=0.42,
        color_g=0.44,
        color_b=0.47,
        roughness=0.28,
        cost_per_kg_usd=2.0,
    ),
    "aluminum_6061": MaterialPreset(
        key="aluminum_6061",
        label="Aluminum 6061 (Алюминий)",
        density_kg_m3=2700.0,
        friction=0.38,
        color_r=0.65,
        color_g=0.66,
        color_b=0.70,
        roughness=0.48,
        cost_per_kg_usd=5.0,
    ),
    "abs_plastic": MaterialPreset(
        key="abs_plastic",
        label="Plastic ABS",
        density_kg_m3=1050.0,
        friction=0.45,
        color_r=0.18,
        color_g=0.35,
        color_b=0.65,
        roughness=0.82,
        cost_per_kg_usd=20.0,
    ),
    "rubber": MaterialPreset(
        key="rubber",
        label="Rubber (Резина)",
        density_kg_m3=1100.0,
        friction=0.92,
        color_r=0.12,
        color_g=0.12,
        color_b=0.12,
        roughness=0.94,
        cost_per_kg_usd=15.0,
    ),
}


def hex_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    """#RRGGBB или RRGGBB → (r,g,b) в диапазоне 0..1."""
    s = hex_color.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) != 6:
        raise ValueError(f"Ожидался hex #RRGGBB, получено: {hex_color!r}")
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return (r, g, b)


@dataclass(frozen=True)
class ResolvedPartAppearance:
    """Плотность/трение и цвет после учёта пресета и поля visual."""

    density_kg_m3: float
    friction: float
    color_r: float
    color_g: float
    color_b: float
    roughness: float


def resolve_part_material(part: dict[str, Any]) -> ResolvedPartAppearance | None:
    """
    Если у детали задано ``material`` (ключ пресета), возвращает физику и цвет.
    Поле ``visual`` может переопределить цвет (#hex) и roughness.
    Неизвестный ключ пресета — ``None`` (воркер использует только simulation.materials).
    """
    raw = part.get("material")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    key = str(raw).strip()
    preset = MATERIAL_PRESETS.get(key)
    if preset is None:
        return None

    vis = part.get("visual") if isinstance(part.get("visual"), dict) else {}
    cr, cg, cb = preset.color_r, preset.color_g, preset.color_b
    if vis.get("color") is not None:
        try:
            cr, cg, cb = hex_to_rgb01(str(vis["color"]))
        except ValueError:
            cr, cg, cb = preset.color_r, preset.color_g, preset.color_b

    rough = preset.roughness
    if vis.get("roughness") is not None:
        try:
            rough = float(vis["roughness"])
            rough = max(0.0, min(1.0, rough))
        except (TypeError, ValueError):
            rough = preset.roughness

    return ResolvedPartAppearance(
        density_kg_m3=preset.density_kg_m3,
        friction=preset.friction,
        color_r=cr,
        color_g=cg,
        color_b=cb,
        roughness=rough,
    )


def list_preset_keys() -> tuple[str, ...]:
    """Ключи пресетов в стабильном порядке (для UI / API)."""
    return tuple(sorted(MATERIAL_PRESETS.keys()))
