"""Расчёт BOM (масса, объём, оценка стоимости сырья по пресетам материалов)."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from worker.core.bearings import bearing_catalog_label, purchased_bearing_price_usd
from worker.core.fasteners import (
    fastener_catalog_label,
    purchased_fastener_price_usd,
)
from worker.core.gears import gear_catalog_label
from worker.core.materials import MATERIAL_PRESETS
from worker.core.mjcf_gen import _part_mass_kg, _prepare_parts
from worker.generator import build_part_solid


def _density_by_mat_id(blueprint: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for m in (blueprint.get("simulation") or {}).get("materials") or []:
        mid = m.get("mat_id")
        if mid is not None:
            out[str(mid)] = float(m["density"])
    return out


def build_bom_from_blueprint(
    blueprint: dict[str, Any],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """
    Возвращает словарь для API/Redis: parts, total_mass_g, total_cost_usd.
    cost_usd — только при известном пресете material на детали (cost_per_kg_usd).
    Ошибка по одной детали не прерывает остальные (warnings дополняются).
    """
    w = warnings if warnings is not None else []
    density_by_mat = _density_by_mat_id(blueprint)
    parts_rows: list[dict[str, Any]] = []
    total_mass_g = 0.0
    total_cost_usd = 0.0

    for part in _prepare_parts(blueprint):
        pid = str(part["part_id"])
        try:
            solid = build_part_solid(part)
        except Exception as e:
            w.append(f"BOM {pid}: построение тела: {e!s}")
            continue
        try:
            vol_mm3 = float(solid.Volume())
        except Exception as e:
            w.append(f"BOM {pid}: объём: {e!s}")
            continue
        vol_cm3 = vol_mm3 / 1000.0
        try:
            mass_kg = _part_mass_kg(part, density_by_mat)
        except Exception as e:
            w.append(f"BOM {pid}: масса: {e!s}")
            continue
        mass_g = mass_kg * 1000.0

        mat_key = part.get("material")
        mat_str: str | None
        if isinstance(mat_key, str) and mat_key.strip():
            mat_str = mat_key.strip()
        else:
            sim = part.get("_sim_node")
            mat_str = str(sim["mat_id"]) if sim and sim.get("mat_id") else None

        cost_usd = 0.0
        item_type = "manufactured"
        catalog_label: str | None = None
        if part.get("base_shape") == "fastener":
            item_type = "purchased"
            fp = part.get("parameters") or {}
            catalog_label = fastener_catalog_label(fp)
            cost_usd = purchased_fastener_price_usd(fp)
        elif part.get("base_shape") == "bearing":
            item_type = "purchased"
            fp = part.get("parameters") or {}
            catalog_label = bearing_catalog_label(fp)
            cost_usd = purchased_bearing_price_usd(fp)
        elif part.get("base_shape") == "gear":
            item_type = "manufactured"
            fp = part.get("parameters") or {}
            catalog_label = gear_catalog_label(fp, part_id=pid)
            if isinstance(mat_key, str) and mat_key.strip():
                preset = MATERIAL_PRESETS.get(mat_key.strip())
                if preset is not None:
                    cost_usd = mass_kg * float(preset.cost_per_kg_usd)
        elif isinstance(mat_key, str) and mat_key.strip():
            preset = MATERIAL_PRESETS.get(mat_key.strip())
            if preset is not None:
                cost_usd = mass_kg * float(preset.cost_per_kg_usd)

        row: dict[str, Any] = {
            "part_id": pid,
            "material": mat_str,
            "mass_g": round(mass_g, 4),
            "volume_cm3": round(vol_cm3, 4),
            "cost_usd": round(cost_usd, 4),
            "item_type": item_type,
        }
        if catalog_label is not None:
            row["catalog_label"] = catalog_label
        parts_rows.append(row)
        total_mass_g += mass_g
        total_cost_usd += cost_usd

    return {
        "parts": parts_rows,
        "total_mass_g": round(total_mass_g, 4),
        "total_cost_usd": round(total_cost_usd, 4),
    }


def write_bom_csv(path: Path, bom: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = bom.get("parts") or []
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "part_id",
                "material",
                "mass_g",
                "volume_cm3",
                "cost_usd",
                "item_type",
                "catalog_label",
            ]
        )
        for row in parts:
            w.writerow(
                [
                    row.get("part_id", ""),
                    row.get("material") or "",
                    row.get("mass_g", ""),
                    row.get("volume_cm3", ""),
                    row.get("cost_usd", ""),
                    row.get("item_type", ""),
                    row.get("catalog_label", "") or "",
                ]
            )
        w.writerow([])
        w.writerow(
            [
                "TOTAL",
                "",
                bom.get("total_mass_g", ""),
                "",
                bom.get("total_cost_usd", ""),
                "",
                "",
            ]
        )


def bom_csv_string(bom: dict[str, Any]) -> str:
    buf = io.StringIO()
    parts = bom.get("parts") or []
    w = csv.writer(buf)
    w.writerow(
        [
            "part_id",
            "material",
            "mass_g",
            "volume_cm3",
            "cost_usd",
            "item_type",
            "catalog_label",
        ]
    )
    for row in parts:
        w.writerow(
            [
                row.get("part_id", ""),
                row.get("material") or "",
                row.get("mass_g", ""),
                row.get("volume_cm3", ""),
                row.get("cost_usd", ""),
                row.get("item_type", ""),
                row.get("catalog_label", "") or "",
            ]
        )
    return buf.getvalue()
