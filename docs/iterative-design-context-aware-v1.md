# Core Feature: Iterative Design & Context-Aware AI

## 1. Проблема

Ранее каждый текстовый промпт вызывал zero-shot генерацию Blueprint без опоры на уже открытую в редакторе модель.

## 2. Решение

Источник истины — клиент. При `POST /api/v1/jobs` с телом:

```json
{
  "prompt": "Увеличь радиус поршня на 2 мм",
  "current_blueprint": { ... }
}
```

поле **`current_blueprint`** опционально. Если оно есть и проходит Pydantic-валидацию `BlueprintPayload`, в `ai_service` используется **`EDIT_SYSTEM_PROMPT`**: модель получает текущий JSON и запрос пользователя и должна вернуть **полный** обновлённый Blueprint.

Если `current_blueprint` нет — прежний zero-shot режим (`SYSTEM_PROMPT`).

## 3. API

- Модель **`JobCreateWithPrompt`** в `services/api/models.py` описывает контракт (документация / OpenAPI).
- В `routes/jobs.py` при пути `prompt` читается **`current_blueprint`**, при необходимости валидируется.

## 4. Frontend

- При отправке промпта, если в textarea JSON распознан как Blueprint (есть `metadata`, `geometry`, `simulation`, `global_settings`), в тело запроса добавляется **`current_blueprint`**.
- Под полем промпта: подсказка «Редактирование текущей модели» / «Создание новой модели».

## 5. Backlog (техдолг)

- **Структурированные предупреждения** вместо `string[]`: поля вроде `code`, `message`, `severity`, `part_id` для привязки к деталям и подсветке во вьювере (enterprise-уровень).
