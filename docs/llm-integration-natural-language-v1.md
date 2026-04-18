# Core Feature: LLM Integration (Natural Language to Blueprint)

## 1. Задача

Интеграция Gemini API в `services/api`, чтобы пользователь мог отправлять текстовый запрос вместо ручного редактирования JSON. Генерация валидного Blueprint v1.0 (zero-shot по системному промпту).

## 2. Архитектура

Модуль `services/api/services/ai_service.py`:

- **System prompt** — правила схемы v1.0, допустимые примитивы для воркера (`box`, `cylinder`), поля `simulation`, векторы для `hole` и `joint`.
- **JSON** — ответ модели в режиме `response_mime_type="application/json"`; при сбое — разбор текста и `extract_json_from_text` (в т.ч. блок `` ```json ``).
- **Валидация** — `BlueprintPayload.model_validate`. При ошибке пользователь получает HTTP 422 с текстом.

Переменные окружения: `GEMINI_API_KEY` или `GOOGLE_API_KEY`, опционально `GEMINI_MODEL` (по умолчанию `gemini-2.0-flash`).

## 3. API

`POST /api/v1/jobs`:

- Тело **полного Blueprint** (как раньше) — без поля `prompt`.
- Или **`{ "prompt": "..." }`** — zero-shot.
- Или **`{ "prompt": "...", "current_blueprint": { ... } }`** — итеративное редактирование (см. [iterative-design-context-aware-v1.md](iterative-design-context-aware-v1.md)).

Коды ошибок: **503** — нет ключа API; **502** — сбой Gemini; **422** — невалидный JSON или Blueprint.

## 4. Frontend

Поле «Промпт (Gemini)» над JSON-редактором. Если строка промпта непустая, **Run Forge** отправляет `{ "prompt": "..." }`; иначе — разобранный JSON из текстового поля.

## 5. Задачи (статус)

1. Зависимость `google-generativeai` в `services/api/requirements.txt`.
2. Системный промпт и `generate_blueprint_from_prompt` в `ai_service.py`.
3. Обновление `routes/jobs.py`.
4. UI: поле промпта в `apps/web/src/app/page.tsx`.
