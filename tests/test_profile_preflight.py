"""Предпроверки 2D-профиля, extruded_profile и revolved_profile в воркере."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from api.core.resolver import resolve_blueprint_variables  # noqa: E402
from api.models import BlueprintPayload  # noqa: E402
from api.models_raw import RawBlueprintPayload  # noqa: E402
from worker.core.exceptions import BlueprintGenerationError  # noqa: E402
from worker.core.profile_preflight import (  # noqa: E402
    validate_extruded_profile_points,
    validate_revolved_profile_points,
)
from worker.generator import build_part_solid  # noqa: E402


class TestProfilePreflight(unittest.TestCase):
    def test_remove_closing_duplicate(self) -> None:
        pts = [
            [0, 0],
            [10, 0],
            [10, 10],
            [0, 10],
            [0, 0],
        ]
        c = validate_extruded_profile_points(pts)
        self.assertEqual(len(c), 4)

    def test_degenerate_edge_raises(self) -> None:
        pts = [[0, 0], [0.001, 0], [0, 10]]
        with self.assertRaises(BlueprintGenerationError) as ctx:
            validate_extruded_profile_points(pts)
        self.assertIn("вырожденное", str(ctx.exception).lower())

    def test_self_intersect_raises(self) -> None:
        pts = [[0, 0], [1, 1], [0, 1], [1, 0]]
        with self.assertRaises(BlueprintGenerationError) as ctx:
            validate_extruded_profile_points(pts)
        self.assertIn("самопересека", str(ctx.exception).lower())

    def test_demo_bracket_builds(self) -> None:
        path = _ROOT / "examples" / "demo-custom-bracket.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw_bp = RawBlueprintPayload.model_validate(raw)
        resolved = resolve_blueprint_variables(raw_bp.model_dump(mode="json"))
        BlueprintPayload.model_validate(resolved)
        solid = build_part_solid(resolved["geometry"]["parts"][0])
        self.assertGreater(float(solid.Volume()), 0.0)

    def test_revolve_negative_x_raises(self) -> None:
        pts = [[10, 0], [10, 10], [-1, 5]]
        with self.assertRaises(BlueprintGenerationError) as ctx:
            validate_revolved_profile_points(pts, 360.0)
        self.assertIn("X < 0", str(ctx.exception))

    def test_revolve_angle_invalid_raises(self) -> None:
        pts = [[0, 0], [10, 0], [10, 10], [0, 10]]
        with self.assertRaises(BlueprintGenerationError) as ctx:
            validate_revolved_profile_points(pts, 0.0)
        self.assertIn("angle", str(ctx.exception).lower())

    def test_revolve_two_axis_runs_raises(self) -> None:
        pts = [
            [0, 0],
            [0, 2],
            [2, 2],
            [2, 4],
            [0, 4],
            [0, 6],
            [3, 6],
            [3, 0],
        ]
        with self.assertRaises(BlueprintGenerationError) as ctx:
            validate_revolved_profile_points(pts, 360.0)
        self.assertIn("оси", str(ctx.exception).lower())

    def test_demo_revolve_pulley_builds(self) -> None:
        path = _ROOT / "examples" / "demo-revolve-pulley.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw_bp = RawBlueprintPayload.model_validate(raw)
        resolved = resolve_blueprint_variables(raw_bp.model_dump(mode="json"))
        BlueprintPayload.model_validate(resolved)
        solid = build_part_solid(resolved["geometry"]["parts"][0])
        self.assertGreater(float(solid.Volume()), 0.0)


if __name__ == "__main__":
    unittest.main()
