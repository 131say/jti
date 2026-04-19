"""
DFM check_gear_meshes: INFO (идеальное зацепление), FAIL (разные модули), WARNING (слишком далеко).

Требует CadQuery (воркер). Без пакета тесты пропускаются.
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


def _gear(
    part_id: str,
    module: float,
    teeth: int,
    *,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> dict:
    return {
        "part_id": part_id,
        "base_shape": "gear",
        "parameters": {
            "module": float(module),
            "teeth": int(teeth),
            "thickness": 8.0,
            "bore_diameter": 5.0,
            "high_lod": False,
        },
        "operations": [],
        "position": [position[0], position[1], position[2]],
        "rotation": [0.0, 0.0, 0.0],
    }


def _bp(*parts: dict) -> dict:
    return {"geometry": {"parts": list(parts)}}


def _ideal_center_mm(m1: float, m2: float, z1: int, z2: int) -> float:
    """Синхронно с diagnostics._ideal_center_distance(m_mid, z1, z2)."""
    m_mid = 0.5 * (m1 + m2)
    return m_mid * (z1 + z2) * 0.5 + 0.05 * m_mid


@unittest.skipIf(cq is None, "cadquery не установлен")
class TestCheckGearMeshes(unittest.TestCase):
    def test_ideal_meshing_emits_info(self) -> None:
        from worker.core.diagnostics import check_gear_meshes

        m = 2.0
        z1, z2 = 20, 30
        a = _ideal_center_mm(m, m, z1, z2)
        w: list[str] = []
        checks = check_gear_meshes(
            _bp(
                _gear("g_pinion", m, z1, position=(0.0, 0.0, 0.0)),
                _gear("g_wheel", m, z2, position=(a, 0.0, 0.0)),
            ),
            w,
        )
        infos = [c for c in checks if c.get("type") == "gear_mesh" and c.get("severity") == "info"]
        self.assertEqual(len(infos), 1, checks)
        self.assertIn("Передаточное число", infos[0]["message"])
        met = infos[0].get("metrics") or {}
        self.assertEqual(met.get("gear_ratio"), "2:3")
        self.assertAlmostEqual(met.get("gear_ratio_value"), 1.5, places=4)

    def test_module_mismatch_when_meshing_emits_fail(self) -> None:
        from worker.core.diagnostics import check_gear_meshes

        m1, m2 = 2.0, 3.0
        z1 = z2 = 20
        a = _ideal_center_mm(m1, m2, z1, z2)
        w: list[str] = []
        checks = check_gear_meshes(
            _bp(
                _gear("g_a", m1, z1, position=(0.0, 0.0, 0.0)),
                _gear("g_b", m2, z2, position=(a, 0.0, 0.0)),
            ),
            w,
        )
        fails = [c for c in checks if c.get("type") == "gear_mesh" and c.get("severity") == "fail"]
        self.assertEqual(len(fails), 1, checks)
        self.assertIn("Несовпадение модулей", fails[0]["message"])

    def test_center_distance_too_large_emits_warning(self) -> None:
        from worker.core.diagnostics import check_gear_meshes

        m = 2.0
        z1 = z2 = 20
        a = _ideal_center_mm(m, m, z1, z2)
        tol = 0.1 * m
        # L > a_nom + 2*tol → ветка «слишком далеко»
        x_far = a + 2.0 * tol + 15.0
        w: list[str] = []
        checks = check_gear_meshes(
            _bp(
                _gear("g_left", m, z1, position=(0.0, 0.0, 0.0)),
                _gear("g_right", m, z2, position=(x_far, 0.0, 0.0)),
            ),
            w,
        )
        warns = [
            c for c in checks if c.get("type") == "gear_mesh" and c.get("severity") == "warning"
        ]
        self.assertEqual(len(warns), 1, checks)
        self.assertIn("слишком велико", warns[0]["message"])
        met = warns[0].get("metrics") or {}
        self.assertAlmostEqual(met.get("recommended_center_distance_mm"), a, places=3)


if __name__ == "__main__":
    unittest.main()
