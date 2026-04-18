"""Геометрическое ядро воркера (примитивы + булевы операции).

Тяжёлые подмодули (CadQuery) не импортируются на уровне пакета — только явные
``from worker.core.geometry import ...`` и т.д.
"""

from worker.core.exceptions import BlueprintGenerationError

__all__ = [
    "BlueprintGenerationError",
]
