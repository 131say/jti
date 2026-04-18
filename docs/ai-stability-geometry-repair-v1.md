# Core Feature: AI Stability & Geometry Repair Layer

## 1. Задача

Снизить число отказов при генерации через LLM и защитить воркер от заведомо некорректной геометрии: **Validate & Repair** на API и **clamp / skip** на воркере.

## 2. Self-Correction (API)

В `services/api/services/ai_service.py`: если `BlueprintPayload.model_validate` не проходит, выполняется до **2** повторных запросов к Gemini с текстом ошибок Pydantic и копией невалидного JSON (`_repair_prompt`). Константа `MAX_REPAIR_ATTEMPTS = 2`.

## 3. Геометрия (Worker)

- **`clamp_hole_diameter_to_solid`** в `core/geometry.py`: диаметр отверстия не больше **0.95 × min** габарита bbox тела (до выреза).
- **`generator._apply_operation_dict`**: операции `hole`, `fillet`, `chamfer` обёрнуты в `try/except`; при любой ошибке (OCP, топология, пересечение) соответствующая операция **пропускается**, предыдущее тело сохраняется; в лог пишется предупреждение.

## 4. UX

- **`ParametricPanel`** под вьювером: числовые поля по `geometry.parts` для `cylinder` / `box`; кнопка «Обновить модель» отправляет JSON в `POST /jobs` без LLM.
- Переключатель **AI / Код**: в режиме «Код» промпт отключён, запуск только из JSON.

## 5. Реализация

1. ✅ `ai_service.py` — цикл repair.
2. ✅ `geometry.py` + `generator.py` — clamp и пропуск отверстия.
3. ✅ `ParametricPanel.tsx` + `page.tsx`.
