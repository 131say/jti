# Frontend Integration: Polling Logic & Three.js Viewer

## 1. Концепция страницы «Workspace»

Страница разделена на два блока: редактор Blueprint JSON (слева) и 3D-вьювер (справа). Основная задача фронтенда — управлять состоянием асинхронной задачи.

## 2. Стейт-машина клиента (React State)

Для управления процессом введён тип `JobPhase`:

- `idle` — начальное состояние.
- `submitting` — отправка Blueprint на API.
- `polling` — ожидание завершения (циклические вызовы `GET /api/v1/jobs/{id}`).
- `loading_asset` — получена ссылка, Three.js загружает бинарные данные.
- `success` — модель отображена.
- `error` — ошибка на любом из этапов.

Реализация: `apps/web/src/hooks/useJobPolling.ts`.

## 3. Логика поллинга (Polling Strategy)

Используется цикл `sleep` + `GET` (без `react-query` в MVP).

- **Интервал:** 2 секунды (`pollMs`).
- **Условие выхода:** статус в ответе API равен `completed` или `failed`.
- **Безопасность:** если поллинг длится более 60 секунд — таймаут (`timeoutMs`).

## 4. Компонент 3D-просмотра (React-Three-Fiber)

Используется `@react-three/drei` для камеры, сцены и загрузчиков.

**Стек вьювера:**

- `Canvas` — корневая сцена.
- `Stage` — освещение и подгонка камеры.
- `OrbitControls` — вращение и зум.
- `useGLTF` / `STLLoader` — загрузка по presigned URL; для CAD-меша с бэка сейчас приходит **`.stl`** (см. ADR CadQuery), для glTF — прежняя ветка.
- `Suspense` + `useProgress` + `Html` — индикатор загрузки.

Файл: `apps/web/src/components/viewer/ModelViewer.tsx`.

## 5. API-клиент и переменные

- `apps/web/src/lib/api.ts` — `POST /api/v1/jobs`, `GET /api/v1/jobs/{id}`.
- Базовый URL API: `NEXT_PUBLIC_API_BASE_URL` (по умолчанию `http://127.0.0.1:8899`).

Пример Blueprint для кнопки «Run Forge»: `public/piston-assembly.blueprint.json`.

## 6. CORS (FastAPI)

Браузер обращается к API с другого origin (`localhost:3000` → `127.0.0.1:8899`). В `services/api/main.py` включён `CORSMiddleware`; список origin задаётся переменной `CORS_ORIGINS` (по умолчанию `http://localhost:3000` и `http://127.0.0.1:3000`).

## 7. Важный нюанс: CORS MinIO и GLTF

Загрузка GLTF по presigned URL идёт с origin страницы (например `http://localhost:3000`) на хост MinIO (`http://localhost:9000`). Если браузер блокирует ответ, на бакете MinIO нужно настроить CORS (или проксирование через тот же origin). Для локальной разработки при необходимости используйте `mc cors set` или политику CORS в MinIO Console.

## 8. Воркер и валидный GLTF

Воркер загружает в бакет минимальный валидный glTF (треугольник Khronos, embedded buffer): `services/worker/assets/minimal_triangle.gltf`, чтобы `useGLTF` в браузере успешно парсил файл.
