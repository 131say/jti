"""Тесты fillet/chamfer в geometry.py и generator."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

import cadquery as cq  # noqa: E402

from worker.core.geometry import (  # noqa: E402
    apply_chamfer,
    apply_fillet,
    normalize_edge_selector,
)
from worker.generator import build_shape_from_blueprint  # noqa: E402


class TestNormalizeEdgeSelector(unittest.TestCase):
    def test_all_variants(self) -> None:
        self.assertIsNone(normalize_edge_selector("ALL"))
        self.assertIsNone(normalize_edge_selector("all"))
        self.assertEqual(normalize_edge_selector("Z"), "|Z")
        self.assertEqual(normalize_edge_selector(">Z"), ">Z")


class TestApplyFilletChamferGeometry(unittest.TestCase):
    def test_fillet_reduces_volume_vs_box(self) -> None:
        base = cq.Workplane().box(50, 50, 50).val()
        v0 = base.Volume()
        wp = apply_fillet(cq.Workplane().add(base), 2.0, "ALL")
        v1 = wp.val().Volume()
        self.assertLess(v1, v0)

    def test_chamfer_reduces_volume(self) -> None:
        base = cq.Workplane().box(40, 40, 40).val()
        v0 = base.Volume()
        wp = apply_chamfer(cq.Workplane().add(base), 1.5, "|Z")
        v1 = wp.val().Volume()
        self.assertLess(v1, v0)


class TestGeneratorFilletChamfer(unittest.TestCase):
    def test_fillet_on_box_ok(self) -> None:
        solid = build_shape_from_blueprint(
            {
                "geometry": {
                    "parts": [
                        {
                            "part_id": "b1",
                            "base_shape": "box",
                            "parameters": {
                                "length": 50,
                                "width": 50,
                                "height": 50,
                            },
                            "operations": [
                                {
                                    "type": "fillet",
                                    "radius": 3,
                                    "selector": "|Z",
                                }
                            ],
                        }
                    ]
                }
            }
        )
        self.assertGreater(solid.Volume(), 0)

    def test_impossible_fillet_skipped_with_warning(self) -> None:
        warnings: list[str] = []
        solid = build_shape_from_blueprint(
            {
                "geometry": {
                    "parts": [
                        {
                            "part_id": "b1",
                            "base_shape": "box",
                            "parameters": {
                                "length": 10,
                                "width": 10,
                                "height": 10,
                            },
                            "operations": [
                                {
                                    "type": "fillet",
                                    "radius": 50,
                                    "selector": "ALL",
                                }
                            ],
                        }
                    ]
                }
            },
            warnings=warnings,
        )
        self.assertGreater(solid.Volume(), 0)
        self.assertTrue(any("fillet skipped" in w.lower() for w in warnings))

    def test_chamfer_after_hole(self) -> None:
        solid = build_shape_from_blueprint(
            {
                "geometry": {
                    "parts": [
                        {
                            "part_id": "b1",
                            "base_shape": "box",
                            "parameters": {
                                "length": 40,
                                "width": 40,
                                "height": 40,
                            },
                            "operations": [
                                {
                                    "type": "hole",
                                    "diameter": 8,
                                    "depth": "through_all",
                                    "position": [0, 0, 0],
                                    "direction": [0, 0, 1],
                                },
                                {
                                    "type": "chamfer",
                                    "length": 1.0,
                                    "selector": ">Z",
                                },
                            ],
                        }
                    ]
                }
            }
        )
        self.assertGreater(solid.Volume(), 0)


if __name__ == "__main__":
    unittest.main()
