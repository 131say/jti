"""Тесты геометрии: операции hole в generator.py."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

# Корень репозитория / services в PYTHONPATH
_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from worker.generator import build_shape_from_blueprint  # noqa: E402


def _vol(payload: dict) -> float:
    return build_shape_from_blueprint(payload).Volume()


class TestGeneratorHoles(unittest.TestCase):
    def test_axial_through_hole_cylinder(self) -> None:
        """Цилиндр R=20, H=50; осевое отверстие D=10 через всё по Z."""
        solid_no = build_shape_from_blueprint(
            {
                "geometry": {
                    "parts": [
                        {
                            "part_id": "c1",
                            "base_shape": "cylinder",
                            "parameters": {"radius": 20, "height": 50},
                            "operations": [],
                        }
                    ]
                }
            }
        )
        solid_yes = build_shape_from_blueprint(
            {
                "geometry": {
                    "parts": [
                        {
                            "part_id": "c1",
                            "base_shape": "cylinder",
                            "parameters": {"radius": 20, "height": 50},
                            "operations": [
                                {
                                    "type": "hole",
                                    "diameter": 10,
                                    "depth": "through_all",
                                    "position": [0, 0, 25],
                                    "direction": [0, 0, 1],
                                }
                            ],
                        }
                    ]
                }
            }
        )
        v0 = solid_no.Volume()
        v1 = solid_yes.Volume()
        self.assertGreater(v0, 0)
        self.assertGreater(v1, 0)
        self.assertLess(v1, v0)

    def test_offset_hole_box(self) -> None:
        """Куб 50×50×50; отверстие со смещением [10, 10, 0]."""
        payload = {
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
                                "type": "hole",
                                "diameter": 8,
                                "depth": "through_all",
                                "position": [10, 10, 0],
                                "direction": [0, 0, 1],
                            }
                        ],
                    }
                ]
            }
        }
        v = _vol(payload)
        self.assertGreater(v, 0)

    def test_angled_hole_direction(self) -> None:
        """Отверстие под углом: направление [1, 1, 0] (нормализуется)."""
        n = math.sqrt(2)
        dx, dy = 1 / n, 1 / n
        payload = {
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
                                "diameter": 6,
                                "depth": "through_all",
                                "position": [0, 0, 0],
                                "direction": [dx, dy, 0],
                            }
                        ],
                    }
                ]
            }
        }
        v = _vol(payload)
        self.assertGreater(v, 0)


if __name__ == "__main__":
    unittest.main()
