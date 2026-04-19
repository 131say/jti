"""Тесты expand_blueprint_generators + finalize."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from api.core.gearbox_expand import (  # noqa: E402
    GearboxExpansionError,
    expand_blueprint_generators,
)
from api.core.resolver import BlueprintResolutionError, finalize_resolved_blueprint  # noqa: E402
from api.models import ResolvedBlueprintPayload  # noqa: E402


def _minimal_sim() -> dict:
    return {
        "materials": [{"mat_id": "steel", "density": 7850, "friction": 0.42}],
        "nodes": [],
        "joints": [],
    }


class TestGearboxExpand(unittest.TestCase):
    def test_ratio_out_of_range(self) -> None:
        bp = {
            "metadata": {"project_id": "t", "schema_version": "4.3"},
            "global_settings": {"units": "mm", "up_axis": "Z"},
            "geometry": {"parts": []},
            "simulation": _minimal_sim(),
            "generators": [
                {
                    "type": "gearbox",
                    "ratio": 1.2,
                    "module": 2,
                    "thickness": 10,
                    "bore_diameter": 8,
                }
            ],
        }
        with self.assertRaises(GearboxExpansionError):
            expand_blueprint_generators(bp)

    def test_expand_and_finalize(self) -> None:
        bp = {
            "metadata": {"project_id": "t_gb", "schema_version": "4.3"},
            "global_variables": {
                "gearbox_ratio": 3.0,
                "gearbox_module": 2.0,
                "gear_thickness": 10.0,
                "gear_bore": 8.0,
            },
            "global_settings": {"units": "mm", "up_axis": "Z"},
            "geometry": {"parts": []},
            "simulation": _minimal_sim(),
            "generators": [
                {
                    "type": "gearbox",
                    "ratio": "$gearbox_ratio",
                    "module": "$gearbox_module",
                    "thickness": "$gear_thickness",
                    "bore_diameter": "$gear_bore",
                    "center_distance": "auto",
                    "high_lod": False,
                }
            ],
        }
        fin, _ = finalize_resolved_blueprint(bp, mate_warnings=None)
        ResolvedBlueprintPayload.model_validate(fin)
        self.assertNotIn("generators", fin)
        parts = fin["geometry"]["parts"]
        ids = {p["part_id"] for p in parts}
        self.assertEqual(ids, {"shaft_1", "shaft_2", "gear_input", "gear_output"})
        meta = fin["metadata"].get("gearbox_expansion")
        self.assertIsInstance(meta, dict)
        self.assertEqual(meta.get("z1"), 10)
        self.assertIn("assembly_mates", fin)
        self.assertGreater(len(fin["assembly_mates"]), 0)

    def test_finalize_bad_ratio_message(self) -> None:
        bp = {
            "metadata": {"project_id": "t", "schema_version": "4.3"},
            "global_settings": {"units": "mm", "up_axis": "Z"},
            "geometry": {"parts": []},
            "simulation": _minimal_sim(),
            "generators": [
                {
                    "type": "gearbox",
                    "ratio": 12.0,
                    "module": 2,
                    "thickness": 10,
                    "bore_diameter": 8,
                }
            ],
        }
        with self.assertRaises(BlueprintResolutionError) as ctx:
            finalize_resolved_blueprint(bp)
        self.assertIn("1.5", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
