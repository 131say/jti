"""Тесты resolve_assembly_mates (Blueprint v3.0)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from api.core.mate_solver import MateResolutionError, resolve_assembly_mates  # noqa: E402


def _minimal_sim() -> dict:
    return {
        "materials": [{"mat_id": "m", "density": 1000, "friction": 0.5}],
        "nodes": [{"part_id": "plate", "mat_id": "m"}, {"part_id": "bolt", "mat_id": "m"}],
        "joints": [],
    }


class TestMateSolver(unittest.TestCase):
    def test_snap_aligns_bolt_to_hole_world(self) -> None:
        bp = {
            "metadata": {"project_id": "t_mate", "schema_version": "3.0"},
            "global_settings": {"units": "mm", "up_axis": "Z"},
            "geometry": {
                "parts": [
                    {
                        "part_id": "plate",
                        "base_shape": "box",
                        "material": "steel",
                        "parameters": {"length": 50, "width": 40, "height": 8},
                        "position": [0, 0, 4],
                        "rotation": [0, 0, 0],
                        "operations": [
                            {
                                "type": "hole",
                                "diameter": 8.5,
                                "depth": "through_all",
                                "position": [10, 20, 0],
                                "direction": [0, 0, 1],
                            }
                        ],
                    },
                    {
                        "part_id": "bolt",
                        "base_shape": "fastener",
                        "material": "steel",
                        "parameters": {
                            "type": "bolt_hex",
                            "size": "M8",
                            "length": 20,
                            "fit": "clearance",
                        },
                        "operations": [],
                    },
                ]
            },
            "simulation": _minimal_sim(),
            "assembly_mates": [
                {
                    "type": "snap_to_operation",
                    "source_part": "bolt",
                    "target_part": "plate",
                    "target_operation_index": 0,
                    "reverse_direction": False,
                }
            ],
        }
        out, _ = resolve_assembly_mates(bp, warnings=None)
        bolt = out["geometry"]["parts"][1]
        self.assertAlmostEqual(bolt["position"][0], 10.0, places=5)
        self.assertAlmostEqual(bolt["position"][1], 20.0, places=5)
        self.assertAlmostEqual(bolt["position"][2], 4.0, places=5)

    def test_cycle_raises(self) -> None:
        bp = {
            "metadata": {"project_id": "t_cycle", "schema_version": "3.0"},
            "global_settings": {"units": "mm", "up_axis": "Z"},
            "geometry": {
                "parts": [
                    {
                        "part_id": "a",
                        "base_shape": "box",
                        "parameters": {"length": 1, "width": 1, "height": 1},
                        "operations": [
                            {
                                "type": "hole",
                                "diameter": 3,
                                "depth": "through_all",
                                "position": [0, 0, 0],
                                "direction": [0, 0, 1],
                            }
                        ],
                    },
                    {
                        "part_id": "b",
                        "base_shape": "box",
                        "parameters": {"length": 1, "width": 1, "height": 1},
                        "operations": [
                            {
                                "type": "hole",
                                "diameter": 3,
                                "depth": "through_all",
                                "position": [0, 0, 0],
                                "direction": [0, 0, 1],
                            }
                        ],
                    },
                ]
            },
            "simulation": {
                "materials": [{"mat_id": "m", "density": 1000, "friction": 0.5}],
                "nodes": [
                    {"part_id": "a", "mat_id": "m"},
                    {"part_id": "b", "mat_id": "m"},
                ],
                "joints": [],
            },
            "assembly_mates": [
                {
                    "type": "snap_to_operation",
                    "source_part": "a",
                    "target_part": "b",
                    "target_operation_index": 0,
                },
                {
                    "type": "snap_to_operation",
                    "source_part": "b",
                    "target_part": "a",
                    "target_operation_index": 0,
                },
            ],
        }
        with self.assertRaises(MateResolutionError):
            resolve_assembly_mates(bp)

    def test_debug_constraints_returns_transforms(self) -> None:
        bp = {
            "metadata": {"project_id": "t_dbg", "schema_version": "3.5"},
            "global_settings": {"units": "mm", "up_axis": "Z"},
            "geometry": {
                "parts": [
                    {
                        "part_id": "plate",
                        "base_shape": "box",
                        "parameters": {"length": 50, "width": 40, "height": 8},
                        "position": [0, 0, 4],
                        "rotation": [0, 0, 0],
                        "operations": [
                            {
                                "type": "hole",
                                "diameter": 8.5,
                                "depth": "through_all",
                                "position": [10, 20, 0],
                                "direction": [0, 0, 1],
                            }
                        ],
                    },
                    {
                        "part_id": "bolt",
                        "base_shape": "fastener",
                        "parameters": {
                            "type": "bolt_hex",
                            "size": "M8",
                            "length": 20,
                            "fit": "clearance",
                        },
                        "operations": [],
                    },
                ]
            },
            "simulation": _minimal_sim(),
            "assembly_mates": [
                {
                    "type": "concentric",
                    "source_part": "bolt",
                    "target_part": "plate",
                    "target_operation_index": 0,
                },
                {
                    "type": "coincident",
                    "source_part": "bolt",
                    "target_part": "plate",
                    "offset": 0.0,
                    "flip": False,
                },
            ],
        }
        out, dbg = resolve_assembly_mates(bp, warnings=None, debug_constraints=True)
        self.assertIsNotNone(dbg)
        self.assertIn("bolt", dbg or {})
        self.assertIn("position", dbg["bolt"])
        bolt = out["geometry"]["parts"][1]
        self.assertAlmostEqual(bolt["position"][0], 10.0, places=5)
        self.assertAlmostEqual(bolt["position"][1], 20.0, places=5)
        self.assertAlmostEqual(bolt["position"][2], 4.0, places=5)

    def test_fillet_index_rejected(self) -> None:
        bp = {
            "metadata": {"project_id": "t_fillet", "schema_version": "3.0"},
            "global_settings": {"units": "mm", "up_axis": "Z"},
            "geometry": {
                "parts": [
                    {
                        "part_id": "plate",
                        "base_shape": "box",
                        "parameters": {"length": 10, "width": 10, "height": 2},
                        "operations": [
                            {
                                "type": "fillet",
                                "radius": 0.5,
                                "selector": "ALL",
                            }
                        ],
                    },
                    {
                        "part_id": "bolt",
                        "base_shape": "fastener",
                        "parameters": {
                            "type": "bolt_hex",
                            "size": "M8",
                            "length": 10,
                            "fit": "clearance",
                        },
                        "operations": [],
                    },
                ]
            },
            "simulation": _minimal_sim(),
            "assembly_mates": [
                {
                    "type": "snap_to_operation",
                    "source_part": "bolt",
                    "target_part": "plate",
                    "target_operation_index": 0,
                }
            ],
        }
        with self.assertRaises(MateResolutionError):
            resolve_assembly_mates(bp)


if __name__ == "__main__":
    unittest.main()
