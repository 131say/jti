"""
Генератор редуктора (Blueprint v4.3): expand ``generators[].type == \"gearbox\"``.

Порядок пайплайна (критичен): expand → resolve_blueprint_variables → resolve_assembly_mates.

Прямозубая пара: оси валов параллельны +Z, межосевое задаётся mate ``distance`` вдоль мировой X
(после совмещения центров в нуле fallback-ось X). Смещение валов **только по Z** для spur
не применяется — иначе нарушается плоскость зацепления; см. ``metadata.gearbox_expansion``.
"""

from __future__ import annotations

import re
from typing import Any

_DOLLAR = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)$")


class GearboxExpansionError(ValueError):
    """Некорректные параметры генератора редуктора."""


def _as_float(x: Any, *, ctx: str) -> float:
    if isinstance(x, bool):
        raise GearboxExpansionError(f"{ctx}: ожидалось число")
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        t = x.strip()
        if _DOLLAR.match(t):
            raise GearboxExpansionError(
                f"{ctx}: ссылка {t!r} должна разрешаться через global_variables до expansion"
            )
        try:
            return float(t)
        except ValueError as e:
            raise GearboxExpansionError(f"{ctx}: не число: {x!r}") from e
    raise GearboxExpansionError(f"{ctx}: неподдерживаемый тип {type(x).__name__}")


def _resolve_gen_scalar(
    value: Any,
    gv: dict[str, Any],
    *,
    ctx: str,
) -> float:
    if isinstance(value, bool):
        raise GearboxExpansionError(f"{ctx}: ожидалось число")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        m = _DOLLAR.match(s)
        if m:
            key = m.group(1)
            if key not in gv:
                raise GearboxExpansionError(
                    f"{ctx}: неизвестная переменная global_variables.{key}"
                )
            raw = gv[key]
            if isinstance(raw, str) and "$" in raw:
                raise GearboxExpansionError(
                    f"{ctx}: global_variables.{key} не должен содержать $ (MVP)"
                )
            return _as_float(raw, ctx=f"{ctx} (${key})")
        return float(s)
    raise GearboxExpansionError(f"{ctx}: неподдерживаемый тип")


def _pick_gearbox(gens: list[Any]) -> tuple[dict[str, Any] | None, list[str]]:
    w: list[str] = []
    first: dict[str, Any] | None = None
    for i, g in enumerate(gens):
        if not isinstance(g, dict):
            raise GearboxExpansionError(f"generators[{i}]: ожидался объект")
        t = g.get("type")
        if t != "gearbox":
            raise GearboxExpansionError(
                f"generators[{i}]: неизвестный type {t!r} (MVP: только gearbox)"
            )
        if first is None:
            first = g
        else:
            w.append(
                "generators: в MVP обрабатывается только первый gearbox; остальные проигнорированы"
            )
    return first, w


def expand_blueprint_generators(
    blueprint: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """
    Если есть ``generators`` с gearbox — подменяет geometry.parts, assembly_mates,
    дополняет global_variables и simulation.nodes; удаляет ключ ``generators``.

    В ``metadata.gearbox_expansion`` записывается сводка (для диагностик / UI).
    """
    out = blueprint
    gens_raw = out.get("generators")
    if gens_raw is None:
        return out, []
    if not isinstance(gens_raw, list):
        raise GearboxExpansionError("generators должен быть массивом")
    if len(gens_raw) == 0:
        out.pop("generators", None)
        return out, []

    gen, gen_warnings = _pick_gearbox(list(gens_raw))
    if gen is None:
        out.pop("generators", None)
        return out, gen_warnings

    gv: dict[str, Any] = dict(out.get("global_variables") or {})

    ratio = _resolve_gen_scalar(gen.get("ratio"), gv, ctx="gearbox.ratio")
    module = _resolve_gen_scalar(gen.get("module"), gv, ctx="gearbox.module")
    thickness = _resolve_gen_scalar(gen.get("thickness"), gv, ctx="gearbox.thickness")
    bore = _resolve_gen_scalar(gen.get("bore_diameter"), gv, ctx="gearbox.bore_diameter")
    high_lod = bool(gen.get("high_lod", False))
    cd_raw = gen.get("center_distance", "auto")

    if ratio < 1.5 or ratio > 10.0:
        raise GearboxExpansionError(
            "Gearbox ratio out of supported range (1.5–10)"
        )
    if module <= 0 or thickness <= 0 or bore <= 0:
        raise GearboxExpansionError(
            "gearbox: module, thickness, bore_diameter должны быть > 0"
        )

    z1 = max(10, int(round(20.0 / ratio)))
    z2 = int(round(z1 * ratio))
    if z2 < 4:
        z2 = 4
    actual_ratio = z2 / z1

    backlash = 0.05 * module
    center_distance = module * (z1 + z2) / 2.0 + backlash
    if cd_raw != "auto":
        center_distance = _resolve_gen_scalar(
            cd_raw, gv, ctx="gearbox.center_distance"
        )

    if z2 > 60 and high_lod:
        gen_warnings.append(
            "High LOD gear with >60 teeth may take significant time to process."
        )

    gv["bore_diameter"] = float(bore)
    gv["thickness"] = float(thickness)
    gv["module"] = float(module)
    gv["z1"] = float(z1)
    gv["z2"] = float(z2)
    gv["gear_center_distance"] = float(center_distance)
    gv["gear_ratio_actual"] = float(actual_ratio)
    gv["gear_ratio_requested"] = float(ratio)

    axis_hole_d = min(max(1.0, bore * 0.15), bore * 0.45)

    parts: list[dict[str, Any]] = [
        {
            "part_id": "shaft_1",
            "base_shape": "cylinder",
            "material": "steel",
            "parameters": {
                "radius": "$bore_diameter / 2",
                "height": "$thickness * 2",
            },
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "operations": [
                {
                    "type": "hole",
                    "diameter": axis_hole_d,
                    "depth": "through_all",
                    "position": [0.0, 0.0, 0.0],
                    "direction": [0.0, 0.0, 1.0],
                }
            ],
        },
        {
            "part_id": "shaft_2",
            "base_shape": "cylinder",
            "material": "steel",
            "parameters": {
                "radius": "$bore_diameter / 2",
                "height": "$thickness * 2",
            },
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "operations": [
                {
                    "type": "hole",
                    "diameter": axis_hole_d,
                    "depth": "through_all",
                    "position": [0.0, 0.0, 0.0],
                    "direction": [0.0, 0.0, 1.0],
                }
            ],
        },
        {
            "part_id": "gear_input",
            "base_shape": "gear",
            "material": "steel",
            "parameters": {
                "module": "$module",
                "teeth": "$z1",
                "thickness": "$thickness",
                "bore_diameter": "$bore_diameter",
                "high_lod": high_lod,
            },
            "operations": [],
        },
        {
            "part_id": "gear_output",
            "base_shape": "gear",
            "material": "steel",
            "parameters": {
                "module": "$module",
                "teeth": "$z2",
                "thickness": "$thickness",
                "bore_diameter": "$bore_diameter",
                "high_lod": high_lod,
            },
            "operations": [],
        },
    ]

    mates: list[dict[str, Any]] = [
        {
            "type": "concentric",
            "source_part": "gear_input",
            "target_part": "shaft_1",
            "target_operation_index": 0,
            "reverse_direction": False,
        },
        {
            "type": "coincident",
            "source_part": "gear_input",
            "target_part": "shaft_1",
            "offset": 0.0,
            "flip": False,
        },
        {
            "type": "concentric",
            "source_part": "gear_output",
            "target_part": "shaft_2",
            "target_operation_index": 0,
            "reverse_direction": False,
        },
        {
            "type": "coincident",
            "source_part": "gear_output",
            "target_part": "shaft_2",
            "offset": 0.0,
            "flip": False,
        },
        {
            "type": "distance",
            "source_part": "shaft_2",
            "target_part": "shaft_1",
            "value": "$gear_center_distance",
        },
    ]

    sim = out.setdefault("simulation", {})
    mats = sim.setdefault("materials", [])
    if not any(isinstance(m, dict) and m.get("mat_id") == "steel" for m in mats):
        mats.append({"mat_id": "steel", "density": 7850, "friction": 0.42})

    nodes = sim.setdefault("nodes", [])
    have = {str(n.get("part_id")) for n in nodes if isinstance(n, dict)}
    for pid in ("shaft_1", "shaft_2", "gear_input", "gear_output"):
        if pid not in have:
            nodes.append({"part_id": pid, "mat_id": "steel"})
            have.add(pid)

    geo = out.setdefault("geometry", {})
    geo["parts"] = parts
    out["assembly_mates"] = mates
    out["global_variables"] = gv
    out.pop("generators", None)

    meta = out.setdefault("metadata", {})
    if not isinstance(meta, dict):
        meta = {}
        out["metadata"] = meta
    meta["gearbox_expansion"] = {
        "requested_ratio": float(ratio),
        "actual_ratio": float(actual_ratio),
        "z1": z1,
        "z2": z2,
        "module": float(module),
        "center_distance": float(center_distance),
        "shaft_z_stagger_applied": False,
        "shaft_layout_note": (
            "Spur MVP: parallel Z axes, coplanar mesh; XY separation via distance mate "
            "(no Z stagger — preserves gear_mesh plane)."
        ),
    }

    return out, gen_warnings
