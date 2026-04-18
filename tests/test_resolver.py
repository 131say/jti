"""Резолвер global_variables и $-выражений (Blueprint v2.0, до Pydantic)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from api.core.resolver import (  # noqa: E402
    BlueprintResolutionError,
    resolve_blueprint_variables,
)
from api.models import BlueprintPayload  # noqa: E402
from api.models_raw import RawBlueprintPayload  # noqa: E402
from worker.generator import build_part_solid  # noqa: E402


class TestMathResolver(unittest.TestCase):
    def test_demo_parametric_resolves_and_validates(self) -> None:
        path = _ROOT / "examples" / "demo-parametric-box.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        RawBlueprintPayload.model_validate(raw)
        resolved = resolve_blueprint_variables(raw)
        self.assertEqual(resolved["geometry"]["parts"][0]["parameters"]["length"], 100.0)
        self.assertEqual(resolved["geometry"]["parts"][0]["parameters"]["width"], 60.0)
        self.assertEqual(resolved["geometry"]["parts"][0]["parameters"]["height"], 20)
        bp = BlueprintPayload.model_validate(resolved)
        self.assertEqual(bp.metadata.schema_version, "2.0")
        self.assertEqual(bp.global_variables, {"base_width": 100.0, "hole_margin": 15.0})

    def test_demo_parametric_builds_solid(self) -> None:
        path = _ROOT / "examples" / "demo-parametric-box.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        resolved = resolve_blueprint_variables(raw)
        BlueprintPayload.model_validate(resolved)
        solid = build_part_solid(resolved["geometry"]["parts"][0])
        self.assertGreater(float(solid.Volume()), 0.0)

    def test_unknown_variable(self) -> None:
        raw = {
            "metadata": {"project_id": "t", "schema_version": "2.0"},
            "global_variables": {"a": 1.0},
            "global_settings": {"units": "mm", "up_axis": "Z"},
            "geometry": {
                "parts": [
                    {
                        "part_id": "p",
                        "base_shape": "cylinder",
                        "parameters": {"radius": "$missing", "height": 10},
                        "operations": [],
                    }
                ]
            },
            "simulation": {
                "materials": [{"mat_id": "m", "density": 1000, "friction": 0.1}],
                "nodes": [{"part_id": "p", "mat_id": "m"}],
                "joints": [],
            },
        }
        with self.assertRaises(BlueprintResolutionError) as ctx:
            resolve_blueprint_variables(raw)
        self.assertIn("Unknown variable", str(ctx.exception))

    def test_division_by_zero(self) -> None:
        raw = {
            "metadata": {"project_id": "t", "schema_version": "2.0"},
            "global_variables": {"a": 1.0},
            "global_settings": {"units": "mm", "up_axis": "Z"},
            "geometry": {
                "parts": [
                    {
                        "part_id": "p",
                        "base_shape": "cylinder",
                        "parameters": {"radius": "$a / 0", "height": 10},
                        "operations": [],
                    }
                ]
            },
            "simulation": {
                "materials": [{"mat_id": "m", "density": 1000, "friction": 0.1}],
                "nodes": [{"part_id": "p", "mat_id": "m"}],
                "joints": [],
            },
        }
        with self.assertRaises(BlueprintResolutionError) as ctx:
            resolve_blueprint_variables(raw)
        self.assertIn("Division by zero", str(ctx.exception))

    def test_global_variable_expression_rejected(self) -> None:
        raw = {
            "metadata": {"project_id": "t", "schema_version": "2.0"},
            "global_variables": {"a": "$b", "b": 1.0},
            "global_settings": {"units": "mm", "up_axis": "Z"},
            "geometry": {"parts": []},
            "simulation": {
                "materials": [],
                "nodes": [],
                "joints": [],
            },
        }
        with self.assertRaises(BlueprintResolutionError):
            resolve_blueprint_variables(raw)


if __name__ == "__main__":
    unittest.main()
