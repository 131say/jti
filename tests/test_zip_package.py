"""Упаковка project.zip (assembly/, parts/, scripts/, simulation/, bom.csv)."""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from worker.zip_packaging import create_project_zip  # noqa: E402


class TestZipPackage(unittest.TestCase):
    def test_create_project_zip_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "assembly").mkdir(parents=True)
            (base / "parts").mkdir()
            (base / "scripts").mkdir()
            (base / "simulation").mkdir()
            (base / "assembly" / "model.glb").write_bytes(b"GLB")
            (base / "assembly" / "assembly.step").write_bytes(b"STEP")
            (base / "simulation" / "simulation.xml").write_text("<mujoco/>", encoding="utf-8")
            (base / "bom.csv").write_text("part_id,material\n", encoding="utf-8")
            (base / "parts" / "a.stl").write_bytes(b"stlA")
            (base / "parts" / "a.step").write_bytes(b"stpA")
            (base / "parts" / "b.stl").write_bytes(b"stlB")
            (base / "scripts" / "build_model.py").write_text("# eject\n", encoding="utf-8")
            (base / "simulation" / "physics_preview.mp4").write_bytes(b"mp4")
            zpath = base / "project.zip"
            create_project_zip(base, zpath)
            self.assertTrue(zpath.is_file())
            with zipfile.ZipFile(zpath, "r") as zf:
                names = set(zf.namelist())
            self.assertEqual(
                names,
                {
                    "assembly/model.glb",
                    "assembly/assembly.step",
                    "simulation/simulation.xml",
                    "simulation/physics_preview.mp4",
                    "bom.csv",
                    "scripts/build_model.py",
                    "parts/a.stl",
                    "parts/a.step",
                    "parts/b.stl",
                },
            )


if __name__ == "__main__":
    unittest.main()
