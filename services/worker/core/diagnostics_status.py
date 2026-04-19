"""
Чистая логика агрегирования статуса DFM (без CadQuery).

Используется в ``diagnostics.py`` и покрывается быстрыми юнит-тестами.
"""

from __future__ import annotations

from typing import Any, Literal


def aggregate_diagnostics_status(
    checks: list[dict[str, Any]],
) -> Literal["pass", "warning", "fail"]:
    """
    Итоговый статус джоба по списку проверок:

    - Любой ``severity == "fail"`` (в т.ч. interference) → **fail**.
    - Иначе любой ``severity == "warning"`` (тонкие стенки, нависания, …) → **warning**.
    - ``severity == "info"`` (например, корректная зубчатая пара) **не** повышает статус.
    - Иначе → **pass** (в т.ч. только info или пустой список).
    """
    if any(c.get("severity") == "fail" for c in checks):
        return "fail"
    if any(c.get("severity") == "warning" for c in checks):
        return "warning"
    return "pass"
