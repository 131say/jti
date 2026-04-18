# Developer Experience (DX) & Environment Setup

## 1. Концепция

Монорепозиторий объединяет Node.js (фронтенд), Python (API + Worker) и Docker-инфраструктуру (Redis + MinIO). Переменные окружения стандартизированы; для запуска используется корневой **Makefile**.

## 2. Управление переменными окружения (.env)

Секреты и URL не коммитятся. Для старта используются шаблоны:

| Файл | Назначение |
|------|------------|
| `apps/web/.env.local.example` | Копировать в `apps/web/.env.local` |
| `services/.env.example` | Копировать в `services/.env` (общий для API и воркера) |

### `apps/web/.env.local.example`

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8899
```

### `services/.env.example`

```env
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT=http://localhost:9000
S3_EXTERNAL_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=aiforge
S3_SECRET_KEY=aiforge_secret
S3_BUCKET=artifacts

# Опционально: генерация Blueprint из текста (Gemini), см. docs/llm-integration-natural-language-v1.md
# GEMINI_API_KEY=
# GEMINI_MODEL=gemini-2.0-flash
```

Приложения подгружают `services/.env` через `python-dotenv` при старте API и воркера.

## 3. Оркестрация локального запуска (Makefile)

Корневой `Makefile` (из корня репозитория):

| Target | Действие |
|--------|----------|
| `make infra-up` | `docker compose up -d redis minio` |
| `make infra-down` | Остановка контейнеров MinIO и Redis |
| `make install` | `python3 -m venv .venv`, pip (api + worker), `npm install` в `apps/web` |
| `make dev-api` | Uvicorn с hot-reload, порт **8899** |
| `make dev-worker` | Arq с `PYTHONPATH=services` |
| `make dev-web` | Next.js dev server, порт **3000** |

## 4. Быстрый старт (кратко)

1. `cp services/.env.example services/.env` и `cp apps/web/.env.local.example apps/web/.env.local`
2. `make infra-up`
3. `make install` (один раз)
4. В трёх терминалах: `make dev-api`, `make dev-worker`, `make dev-web`

Полная версия: корневой [README.md](../README.md).

## 5. REPL: `apply_hole` (CadQuery)

После `make install` и активации venv:

```bash
cd /path/to/jti
source .venv/bin/activate
export PYTHONPATH=services
python
```

```python
import cadquery as cq
from worker.core.geometry import apply_hole
from worker.core.primitives import make_cylinder

wp = make_cylinder(20, 50)  # R=20, H=50
wp = apply_hole(
    wp,
    diameter=10,
    position=(0, 0, 25),
    direction=(0, 0, 1),
    depth="through_all",
)
solid = wp.val()
print("Volume:", solid.Volume())
```

## 6. CORS и фронт

API разрешает origin из `CORS_ORIGINS` (по умолчанию `localhost:3000` и `127.0.0.1:3000`). Для загрузки GLTF с MinIO может понадобиться CORS на стороне бакета — см. [frontend-integration-polling-threejs.md](frontend-integration-polling-threejs.md).
