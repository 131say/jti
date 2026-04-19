"""
DFM: пара gear↔gear при пересечении тел — severity warning (не fail).

Требует CadQuery (как воркер). Без пакета тесты пропускаются.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

try:
    import cadquery as cq  # noqa: F401
except ImportError:
    cq = None  # type: ignore[assignment]


def _two_overlapping_gears_blueprint() -> dict:
    """Две одинаковые preview-шестерни в начале координат — гарантированное пересечение."""
    gear = {
        "base_shape": "gear",
        "parameters": {
            "module": 2.0,
            "teeth": 16,
            "thickness": 6.0,
            "bore_diameter": 5.0,
            "high_lod": False,
        },
        "operations": [],
    }
    return {
        "geometry": {
            "parts": [
                {**gear, "part_id": "g_a"},
                {**gear, "part_id": "g_b"},
            ]
        }
    }


def _two_overlapping_boxes_blueprint() -> dict:
    """Два одинаковых ящика в начале координат — пересечение должно давать fail."""
    box = {
        "base_shape": "box",
        "parameters": {"length": 20.0, "width": 20.0, "height": 10.0},
        "operations": [],
    }
    return {
        "geometry": {
            "parts": [
                {**box, "part_id": "b_a"},
                {**box, "part_id": "b_b"},
            ]
        }
    }


@unittest.skipIf(cq is None, "cadquery не установлен")
class TestDiagnosticsGearGearInterference(unittest.TestCase):
    def test_gear_gear_intersection_is_warning_not_fail(self) -> None:
        from worker.core.diagnostics import run_engineering_diagnostics

        result = run_engineering_diagnostics(_two_overlapping_gears_blueprint())
        self.assertEqual(result["status"], "warning")
        inter = [
            c
            for c in result["checks"]
            if c.get("type") == "interference"
        ]
        self.assertEqual(len(inter), 1, inter)
        chk = inter[0]
        self.assertEqual(chk["severity"], "warning")
        self.assertEqual(set(chk["part_ids"]), {"g_a", "g_b"})
        vol = chk["metrics"]["interference_volume_mm3"]
        self.assertGreater(vol, 0.0)
        self.assertIn("шестер", chk["message"].lower())

    def test_box_box_intersection_remains_fail(self) -> None:
        from worker.core.diagnostics import run_engineering_diagnostics

        result = run_engineering_diagnostics(_two_overlapping_boxes_blueprint())
        self.assertEqual(result["status"], "fail")
        inter = [c for c in result["checks"] if c.get("type") == "interference"]
        self.assertEqual(len(inter), 1)
        self.assertEqual(inter[0]["severity"], "fail")
        self.assertGreater(inter[0]["metrics"]["interference_volume_mm3"], 0.0)


if __name__ == "__main__":
    unittest.main()
