"""Массивы отверстий linear_pattern / circular_pattern (Blueprint v1.2)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from worker.core.geometry import (  # noqa: E402
    expand_circular_pattern_to_hole_dicts,
    expand_linear_pattern_to_hole_dicts,
)
from api.core.resolver import resolve_blueprint_variables  # noqa: E402
from api.models import BlueprintPayload  # noqa: E402
from api.models_raw import RawBlueprintPayload  # noqa: E402
from worker.generator import build_part_solid  # noqa: E402


class TestHolePatterns(unittest.TestCase):
    def test_linear_expand_grid(self) -> None:
        op = {
            "type": "linear_pattern",
            "count_x": 2,
            "count_y": 2,
            "spacing_x": 20.0,
            "spacing_y": 30.0,
            "operation": {
                "type": "hole",
                "diameter": 5.0,
                "position": [10.0, 10.0, 5.0],
                "direction": [0, 0, -1],
                "depth": "through_all",
            },
        }
        holes = expand_linear_pattern_to_hole_dicts(op)
        self.assertEqual(len(holes), 4)
        self.assertEqual(holes[0]["position"], [10.0, 10.0, 5.0])
        self.assertEqual(holes[1]["position"], [30.0, 10.0, 5.0])
        self.assertEqual(holes[2]["position"], [10.0, 40.0, 5.0])
        self.assertEqual(holes[3]["position"], [30.0, 40.0, 5.0])

    def test_circular_expand_six(self) -> None:
        op = {
            "type": "circular_pattern",
            "center": [0, 0, 0],
            "radius": 15.0,
            "count": 6,
            "angle": 360.0,
            "operation": {
                "type": "hole",
                "diameter": 5.0,
                "position": [999, 999, 999],
                "direction": [0, 0, -1],
                "depth": "through_all",
            },
        }
        holes = expand_circular_pattern_to_hole_dicts(op)
        self.assertEqual(len(holes), 6)
        self.assertAlmostEqual(holes[0]["position"][0], 15.0, places=5)
        self.assertAlmostEqual(holes[0]["position"][1], 0.0, places=5)
        self.assertNotEqual(holes[0]["position"], [999, 999, 999])

    def test_demo_flange_validates_and_builds(self) -> None:
        path = _ROOT / "examples" / "demo-flange-pattern.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw_bp = RawBlueprintPayload.model_validate(raw)
        resolved = resolve_blueprint_variables(raw_bp.model_dump(mode="json"))
        BlueprintPayload.model_validate(resolved)
        solid = build_part_solid(resolved["geometry"]["parts"][0])
        self.assertIsNotNone(solid)


if __name__ == "__main__":
    unittest.main()
