"""Разбор JSON из ответа LLM (без вызова API)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent / "services" / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from services.ai_service import extract_json_from_text  # noqa: E402


class TestExtractJson(unittest.TestCase):
    def test_plain_object(self) -> None:
        self.assertEqual(
            extract_json_from_text('{"a": 1, "b": "x"}'),
            {"a": 1, "b": "x"},
        )

    def test_fenced_json(self) -> None:
        self.assertEqual(
            extract_json_from_text('```json\n{"k": 2}\n```'),
            {"k": 2},
        )


if __name__ == "__main__":
    unittest.main()
