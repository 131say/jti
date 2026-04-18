"""MJCF: строка XML из Blueprint (поршень)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from worker.core.mjcf_gen import build_mjcf_xml  # noqa: E402


class TestMjcfGen(unittest.TestCase):
    def test_piston_xml_contains_mesh_and_joint(self) -> None:
        path = _ROOT / "examples" / "piston-assembly.blueprint.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        xml = build_mjcf_xml(payload)
        self.assertIn('model="AI_Forge_Sim"', xml)
        self.assertIn("piston_head_mesh", xml)
        self.assertIn("con_rod_mesh", xml)
        self.assertIn('name="piston_pin"', xml)
        self.assertIn('type="hinge"', xml)
        self.assertIn("friction=", xml)

    def test_demo_fillets_materials_presets_friction(self) -> None:
        """Пресеты material на деталях → friction на geom (MuJoCo)."""
        path = _ROOT / "examples" / "demo-fillets-materials.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        xml = build_mjcf_xml(payload)
        self.assertIn("piston_head_mesh", xml)
        self.assertIn("con_rod_mesh", xml)
        self.assertIn('friction="0.38', xml)
        self.assertIn('friction="0.42', xml)


if __name__ == "__main__":
    unittest.main()
