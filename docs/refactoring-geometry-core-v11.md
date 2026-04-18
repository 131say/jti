# Refactoring: Geometry Utilities & Modular Testing

## 1. Цель

Повысить надёжность геометрического ядра за счёт выноса операций в изолированные функции и расширения покрытия юнит-тестами.

## 2. Структура Worker

- `services/worker/core/geometry.py` — атомарные операции (`apply_hole`, `normalize_direction`).
- `services/worker/core/primitives.py` — базовые тела (`make_box`, `make_cylinder`).
- `services/worker/core/exceptions.py` — `BlueprintGenerationError`.
- `services/worker/generator.py` — оркестрация: разбор JSON, вызов `core`, экспорт.

## 3. Сигнатура `apply_hole`

```python
def apply_hole(
    wp: cq.Workplane,
    diameter: float,
    position: tuple[float, float, float],
    direction: tuple[float, float, float],
    depth: float | str,
) -> cq.Workplane
```

Вход: `Workplane` с одним solid на стеке (`add(solid)`). Выход — новый `Workplane` после вычитания.

## 4. Тесты

- `tests/test_unit_geometry.py` — граничные случаи (нулевой direction, «далёкая» плоскость, касание грани, угол).
- `tests/test_generator_holes.py` — интеграция по полному blueprint.

`make test` запускает `unittest discover` по каталогу `tests/`.

## 5. CI

Корневой `Makefile`, цель `make test`, без отдельного пайплайна в этом репозитории — при подключении CI достаточно вызвать `make test` в окружении с установленными зависимостями воркера (включая `cadquery`).
