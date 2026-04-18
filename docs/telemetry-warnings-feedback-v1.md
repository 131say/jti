# Core Feature: Telemetry & Warnings Feedback Loop

## 1. Проблема

Кламп диаметра отверстий и пропуск «битых» операций спасали генерацию, но не были видны пользователю.

## 2. Решение

- Воркер накапливает строки в списке `warnings` при клампе (`geometry.clamp_hole_diameter_to_solid`) и при пропуске операций (`generator._apply_operation_dict`: отверстие, fillet или chamfer при ошибке OCP/топологии).
- Список сохраняется в Redis вместе с `status: completed` под ключом `warnings`.
- API: `GET /api/v1/jobs/{id}` возвращает `warnings: string[] | null`.
- Фронт: жёлтая плашка над панелью параметров.

## 3. Кламп

Коэффициент: `HOLE_DIAM_MAX_FACTOR = 1.0 - 1e-4` (макс. диаметр ≈ минимальное ребро bbox × этот множитель).

## 4. Реализация

1. `geometry.py` — константа и параметры `part_id`, `warnings` у `clamp_hole_diameter_to_solid`.
2. `generator.py` — прокидка `warnings` в `build_part_solid` / `build_assembly_from_blueprint`.
3. `worker/main.py` — запись `warnings` в состояние задачи.
4. `models.py` + `routes/jobs.py` + `api.ts` + `useJobPolling` + `page.tsx`.
