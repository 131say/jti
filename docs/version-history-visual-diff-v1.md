# Core Feature: Version History & Visual Diff (Anti-Drift)

## 1. Проблема

Итеративный AI мог перезаписать JSON без возможности отката; дрейф параметров оставался неочевидным.

## 2. Решение (клиент)

- Хук **`useBlueprintHistory`**: стек `past` / `present` / `future`, операции **`commit`**, **`undo`**, **`redo`**, **`reset`**.
- После успешной генерации воркер сохраняет в Redis поле **`blueprint`**; API отдаёт его в **`GET /jobs`**, фронт вызывает **`commit`** с новым JSON (старый `present` уходит в `past`).
- Кнопки **Undo / Redo** (иконки Lucide) над редактором; режим **Diff** — два read-only поля «предыдущая» vs «текущая» (если есть история).
- **`ParametricPanel`**: опциональный **`baselineJson`** (`previousCommitted`) — жёлтая рамка у полей, где число отличается от базовой версии.
- При ошибке задачи (в т.ч. после self-correction LLM) показывается **toast**; текст в редакторе не затирается.

## 3. Бэкенд

- Воркер при **`completed`** пишет в состояние задачи **`blueprint`**: тот же словарь, что ушёл в генерацию.

## 4. Backlog

- Структурированные предупреждения и построчный diff библиотекой уровня git (см. [iterative-design-context-aware-v1.md](iterative-design-context-aware-v1.md)).
