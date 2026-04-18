# Implementation Plan: Hole Operation (v1.0)

## 1. Задача

Добавить в `generator.py` поддержку операции `hole` для примитивов `box` и `cylinder`. Реализация должна поддерживать позиционирование, направление вектора и сквозное сверление.

## 2. Алгоритм в CadQuery

Для гибкого сверления (не только по осям X, Y, Z) используется временная рабочая плоскость, ориентированная по вектору направления.

**Шаги генерации:**

1. Выбрать базовое тело (`Solid`).
2. Создать `Plane(origin=position, normal=direction)` (xDir может быть вычислен автоматически).
3. `cq.Workplane(plane).add(solid).circle(radius).cutThruAll()` или `cutBlind(depth)`.
4. Для `depth === "through_all"` — `cutThruAll()`; для числа — `cutBlind(float(depth))`.

## 3. Обновление `generator.py`

Функция `_apply_single_hole(solid, op)`:

- **Валидация:** `diameter > 0`, нормализованный ненулевой `direction`.
- **Трансформация:** `cadquery.occ_impl.geom.Plane(position, None, direction)`.
- **depth:** строка `"through_all"` → `cutThruAll()`; иначе положительное число → `cutBlind(depth)`.

## 4. Юнит-тест

Файл `tests/test_generator_holes.py`:

- **Тест 1 (осевой):** цилиндр R=20, H=50 + отверстие D=10, `through_all`, ось Z.
- **Тест 2 (смещение):** куб 50×50×50 + отверстие со смещением `[10, 10, 0]`.
- **Тест 3 (угол):** направление `[1, 1, 0]` (нормализовано).

## 5. Ожидаемый результат

Воркер обрабатывает пример поршня с отверстиями и выдаёт корректный STL для вьювера.
