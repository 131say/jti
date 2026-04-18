"""Сборка Blueprint → cq.Assembly (без fuse), экспорт STEP/STL."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from worker.generator import (  # noqa: E402
    build_assembly_from_blueprint,
    export_artifacts,
)


class TestAssemblyBlueprint(unittest.TestCase):
    def test_piston_two_named_parts(self) -> None:
        path = _ROOT / "examples" / "piston-assembly.blueprint.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assy = build_assembly_from_blueprint(payload)
        self.assertEqual(len(assy.children), 2)
        names = {c.name for c in assy.children}
        self.assertEqual(names, {"piston_head", "con_rod"})

    def test_export_artifacts_creates_files(self) -> None:
        payload = {
            "geometry": {
                "parts": [
                    {
                        "part_id": "a",
                        "base_shape": "box",
                        "parameters": {"length": 10, "width": 10, "height": 10},
                        "operations": [],
                    },
                    {
                        "part_id": "b",
                        "base_shape": "cylinder",
                        "parameters": {"radius": 5, "height": 20},
                        "operations": [],
                    },
                ]
            }
        }
        assy = build_assembly_from_blueprint(payload)
        with tempfile.TemporaryDirectory() as tmp:
            step_path, glb_path = export_artifacts(assy, Path(tmp))
            self.assertTrue(step_path.is_file() and step_path.stat().st_size > 0)
            self.assertTrue(glb_path.is_file() and glb_path.stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
