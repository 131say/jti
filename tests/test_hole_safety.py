"""Ограничение диаметра отверстия по bbox тела."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from worker.core.geometry import (  # noqa: E402
    HOLE_DIAM_MAX_FACTOR,
    clamp_hole_diameter_to_solid,
)
from worker.core.primitives import make_box  # noqa: E402


class TestHoleClamp(unittest.TestCase):
    def test_clamps_to_bbox(self) -> None:
        solid = make_box(10, 10, 10).val()
        d = clamp_hole_diameter_to_solid(solid, 100.0)
        cap = 10.0 * HOLE_DIAM_MAX_FACTOR
        self.assertAlmostEqual(d, cap, places=6)
        self.assertGreater(d, 0)

    def test_telemetry_append(self) -> None:
        solid = make_box(10, 10, 10).val()
        w: list[str] = []
        clamp_hole_diameter_to_solid(solid, 100.0, part_id="p1", warnings=w)
        self.assertEqual(len(w), 1)
        self.assertIn("p1", w[0])


if __name__ == "__main__":
    unittest.main()
