# Core Feature: MJCF (MuJoCo XML) Generator

## 1. Задача

Создать модуль `services/worker/core/mjcf_gen.py`, который преобразует `BlueprintPayload` в валидный XML-файл формата MJCF (`.xml`). Это позволяет запускать физическую симуляцию сгенерированных сборок.

## 2. Логика маппинга (CAD → Physics)

MuJoCo требует разделения визуальных/коллизионных объектов (`geom`) и кинематических связей (`joint`).

**Алгоритм генерации:**

1. **Корень:** тег `<mujoco model="AI_Forge_Sim">`.
2. **Активы:** для каждой детали — `<mesh>` в `<asset>` с файлом `mesh/<part_id>.stl` и масштабом из `global_settings.units` (например mm → m).
3. **Мир (`worldbody`):** дерево тел по `simulation.joints` (родитель → ребёнок); корни — детали, не являющиеся `child_part` ни в одном joint.
4. **Масса:** `simulation.nodes` (`mass_override` или плотность × объём CAD).
5. **Шарниры:** для `hinge` / `slider` / `ball` — атрибуты `axis`, `pos` (из `anchor_point`), при необходимости `range` из `limits`. Тип `fixed` пока не поддержан.

## 3. Воркер

`generate_blueprint_task` загружает `model.step`, `model.stl` и **`project.zip`**, внутри которого лежат `simulation.xml` и `mesh/<part_id>.stl` (структура для `<compiler meshdir="mesh">`). См. [zip-archiving-download-ui-v1.md](zip-archiving-download-ui-v1.md).

## 4. API

В ответе `GET /api/v1/jobs/{id}` при `status=completed` поле `artifacts.zip_url` — presigned GET на `project.zip`. Устаревшие задачи могут иметь `artifacts.mjcf_url`, если в Redis сохранён `mjcf_key`.

## 5. Задачи реализации

1. ✅ `services/worker/core/mjcf_gen.py` (`xml.etree`).
2. ✅ Интеграция в воркер и загрузка в MinIO.
3. ✅ `JobArtifacts.mjcf_url` в API.
