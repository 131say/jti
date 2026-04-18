"""Юнит-тесты атомарной геометрии (без полного Blueprint JSON)."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

import cadquery as cq  # noqa: E402

from worker.core.exceptions import BlueprintGenerationError  # noqa: E402
from worker.core.geometry import apply_hole, normalize_direction  # noqa: E402
from worker.core.primitives import make_box  # noqa: E402


class TestNormalizeDirection(unittest.TestCase):
    def test_zero_raises(self) -> None:
        with self.assertRaises(BlueprintGenerationError):
            normalize_direction((0.0, 0.0, 0.0))

    def test_tiny_nonzero_ok(self) -> None:
        v = normalize_direction((1e-4, 1.0, 0.0))
        self.assertAlmostEqual(v[0] ** 2 + v[1] ** 2 + v[2] ** 2, 1.0, places=5)


class TestApplyHoleUnit(unittest.TestCase):
    def _cube_wp(self) -> cq.Workplane:
        return make_box(20, 20, 20)

    def test_through_all_reduces_volume(self) -> None:
        wp0 = self._cube_wp()
        v0 = wp0.val().Volume()
        wp1 = apply_hole(
            cq.Workplane().add(wp0.val()),
            6.0,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            "through_all",
        )
        v1 = wp1.val().Volume()
        self.assertLess(v1, v0)

    def test_out_of_bounds_still_runs(self) -> None:
        """Отверстие со смещённой плоскостью: ядро не падает (поведение OCP)."""
        solid = make_box(10, 10, 10).val()
        wp = cq.Workplane().add(solid)
        wp2 = apply_hole(
            wp,
            4.0,
            (50.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            "through_all",
        )
        self.assertGreater(wp2.val().Volume(), 0)

    def test_coincident_surface_hole(self) -> None:
        """Отверстие с осевой точкой на верхней грани (z = половина высоты для centered box)."""
        solid = make_box(10, 10, 10).val()
        wp = cq.Workplane().add(solid)
        wp2 = apply_hole(
            wp,
            3.0,
            (0.0, 0.0, 5.0),
            (0.0, 0.0, 1.0),
            "through_all",
        )
        self.assertGreater(wp2.val().Volume(), 0)

    def test_angled_hole_vector(self) -> None:
        n = math.sqrt(2)
        solid = make_box(30, 30, 30).val()
        wp = cq.Workplane().add(solid)
        wp2 = apply_hole(
            wp,
            5.0,
            (0.0, 0.0, 0.0),
            (1.0 / n, 1.0 / n, 0.0),
            "through_all",
        )
        self.assertGreater(wp2.val().Volume(), 0)


if __name__ == "__main__":
    unittest.main()
