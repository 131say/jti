"""Граф сборки и PDF-инструкция (MVP)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from worker.core.pdf_generator import (  # noqa: E402
    build_assembly_steps,
    build_mate_edges,
    topological_sort_parts,
)


class TestPdfGeneratorGraph(unittest.TestCase):
    def test_topo_bracket_before_bolt(self) -> None:
        bp = {
            "geometry": {
                "parts": [
                    {"part_id": "bracket"},
                    {"part_id": "bolt"},
                ]
            },
            "assembly_mates": [
                {
                    "type": "snap_to_operation",
                    "source_part": "bolt",
                    "target_part": "bracket",
                    "target_operation_index": 0,
                }
            ],
        }
        edges, _ = build_mate_edges(bp)
        self.assertEqual(edges, [("bracket", "bolt")])
        ordered, cyc = topological_sort_parts(
            ["bracket", "bolt"],
            edges,
        )
        self.assertFalse(cyc)
        self.assertEqual(ordered, ["bracket", "bolt"])

    def test_assembly_steps_one_mate(self) -> None:
        bp = {
            "geometry": {
                "parts": [
                    {"part_id": "bracket"},
                    {"part_id": "bolt"},
                ]
            },
            "assembly_mates": [
                {
                    "type": "snap_to_operation",
                    "source_part": "bolt",
                    "target_part": "bracket",
                    "target_operation_index": 0,
                }
            ],
        }
        steps, w = build_assembly_steps(bp, warnings=[])
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].source_part, "bolt")
        self.assertEqual(steps[0].target_part, "bracket")
        self.assertFalse(w)

    def test_generate_pdf_smoke(self) -> None:
        try:
            from worker.core.pdf_generator import generate_assembly_instructions_pdf
        except ImportError:
            self.skipTest("reportlab/Pillow not installed")
        bp = {
            "metadata": {"project_id": "t"},
            "geometry": {
                "parts": [
                    {"part_id": "a"},
                    {"part_id": "b"},
                ]
            },
            "assembly_mates": [],
        }
        bom = {
            "parts": [
                {
                    "part_id": "a",
                    "material": "steel",
                    "mass_g": 1.0,
                    "cost_usd": 0.0,
                    "item_type": "manufactured",
                }
            ],
            "total_mass_g": 1.0,
            "total_cost_usd": 0.0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "out.pdf"
            generate_assembly_instructions_pdf(p, bp, bom, step_warnings=[])
            self.assertTrue(p.is_file())
            self.assertGreater(p.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main()
