"""Агрегирование статуса DFM без CadQuery (моки списка checks)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICES = _ROOT / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from worker.core.diagnostics_status import aggregate_diagnostics_status  # noqa: E402


class TestAggregateDiagnosticsStatus(unittest.TestCase):
    def test_empty_checks_is_pass(self) -> None:
        self.assertEqual(aggregate_diagnostics_status([]), "pass")

    def test_single_warning_is_warning(self) -> None:
        checks = [
            {
                "type": "overhang",
                "severity": "warning",
                "message": "m",
                "part_ids": ["a"],
            },
        ]
        self.assertEqual(aggregate_diagnostics_status(checks), "warning")

    def test_single_fail_is_fail(self) -> None:
        checks = [
            {
                "type": "interference",
                "severity": "fail",
                "message": "collision",
                "part_ids": ["a", "b"],
                "metrics": {"interference_volume_mm3": 1.0},
            },
        ]
        self.assertEqual(aggregate_diagnostics_status(checks), "fail")

    def test_interference_fail_overrides_warnings(self) -> None:
        """Коллизия (fail) доминирует над любыми warning."""
        checks = [
            {
                "type": "thin_feature",
                "severity": "warning",
                "message": "thin",
                "part_ids": ["x"],
            },
            {
                "type": "interference",
                "severity": "fail",
                "message": "hit",
                "part_ids": ["a", "b"],
            },
            {
                "type": "overhang",
                "severity": "warning",
                "message": "oh",
                "part_ids": ["y"],
            },
        ]
        self.assertEqual(aggregate_diagnostics_status(checks), "fail")

    def test_multiple_warnings_only_warning(self) -> None:
        checks = [
            {"severity": "warning", "type": "t1", "message": "", "part_ids": []},
            {"severity": "warning", "type": "t2", "message": "", "part_ids": []},
        ]
        self.assertEqual(aggregate_diagnostics_status(checks), "warning")

    def test_explicit_pass_severity_does_not_trigger_warning(self) -> None:
        """Записи с severity pass не повышают до warning."""
        checks = [
            {
                "type": "custom",
                "severity": "pass",
                "message": "ok",
                "part_ids": [],
            },
        ]
        self.assertEqual(aggregate_diagnostics_status(checks), "pass")

    def test_missing_severity_treated_as_pass(self) -> None:
        checks = [{"type": "x", "message": "m"}]
        self.assertEqual(aggregate_diagnostics_status(checks), "pass")

    def test_fail_first_in_list_still_fail(self) -> None:
        checks = [
            {"severity": "fail", "type": "interference"},
            {"severity": "warning", "type": "thin"},
        ]
        self.assertEqual(aggregate_diagnostics_status(checks), "fail")

    def test_info_only_still_pass(self) -> None:
        """severity info (например, корректная зубчатая пара) не повышает статус."""
        checks = [
            {
                "type": "gear_mesh",
                "severity": "info",
                "message": "ok pair",
                "part_ids": ["g1", "g2"],
            },
        ]
        self.assertEqual(aggregate_diagnostics_status(checks), "pass")


if __name__ == "__main__":
    unittest.main()
