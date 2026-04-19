# AI-Forge

Монорепозиторий: Next.js (веб), FastAPI (API), Arq + Python (воркер), Docker (Redis, MinIO).

## Текущая версия

Актуальный production-milestone по контракту Blueprint (генератор редуктора **v4.3**, constraints **v3.5** и др.):

- **Git-тег:** [`v4.3-auto-gearbox`](https://github.com/131say/jti/releases/tag/v4.3-auto-gearbox)

## Контракты данных (JSON Schemas)

Машиночитаемые схемы лежат в каталоге [`schemas/`](schemas/). Для онбординга и проверки JSON в CI/редакторах ориентируйтесь на последний контракт редуктора и генераторов:

| Версия | Файл | Описание |
|--------|------|----------|
| **4.3** | [`schemas/blueprint-v4.3.schema.json`](https://github.com/131say/jti/blob/main/schemas/blueprint-v4.3.schema.json) | `generators.gearbox`, `schema_version` **4.3**, пустой `geometry.parts` при генераторе |
| 3.5 | [`schemas/blueprint-v3.5.schema.json`](https://github.com/131say/jti/blob/main/schemas/blueprint-v3.5.schema.json) | Constraint mates: `concentric`, `coincident`, `distance` |

Полный список схем — в [`schemas/`](schemas/). Валидация в рантайме дублируется моделями Pydantic в `services/api/models*.py`.

## Быстрый старт

### 1. Переменные окружения

- Скопируйте шаблоны и переименуйте:

  ```bash
  cp services/.env.example services/.env
  cp apps/web/.env.local.example apps/web/.env.local
  ```

- При необходимости отредактируйте `services/.env` и `apps/web/.env.local` (базовые значения совпадают с локальным MinIO из `docker-compose.yml`).

### 2. Инфраструктура

```bash
make infra-up
```

Поднимаются **Redis** и **MinIO** (порты **6379** и **9000**).

Остановка только этих сервисов:

```bash
make infra-down
```

### 3. Зависимости

```bash
make install
```

Создаётся корневой виртуальный env `.venv`, ставятся зависимости API и воркера, затем `npm install` в `apps/web`.

Если установка воркера падает на тяжёлых пакетах (например CadQuery/MuJoCo), временно установите только API: ` .venv/bin/pip install -r services/api/requirements.txt`.

### 4. Три терминала

После `make infra-up` и `make install`:

| Терминал | Команда |
|----------|---------|
| 1 | `make dev-api` — API на [http://127.0.0.1:8899](http://127.0.0.1:8899), Swagger `/docs` |
| 2 | `make dev-worker` — очередь Arq |
| 3 | `make dev-web` — фронт на [http://localhost:3000](http://localhost:3000) |

API и воркер автоматически подхватывают `services/.env` (см. `python-dotenv` в `main.py`). Next.js читает `apps/web/.env.local`.

### 5. Проверка

- Откройте веб-интерфейс и нажмите **Run Forge** (пример Blueprint подгружается из `public/`).
- Либо `curl http://127.0.0.1:8899/ping`.

### Тесты (геометрия)

```bash
make test
```

Подробнее: [docs/developer-experience.md](docs/developer-experience.md), [docs/ai-stability-geometry-repair-v1.md](docs/ai-stability-geometry-repair-v1.md) (repair loop, геометрия), [docs/telemetry-warnings-feedback-v1.md](docs/telemetry-warnings-feedback-v1.md) (warnings в UI), [docs/version-history-visual-diff-v1.md](docs/version-history-visual-diff-v1.md) (история JSON, diff), [docs/llm-integration-natural-language-v1.md](docs/llm-integration-natural-language-v1.md) (промпт → Blueprint / Gemini), [docs/iterative-design-context-aware-v1.md](docs/iterative-design-context-aware-v1.md) (итеративное редактирование), [docs/assemblies-step-export-hierarchy-v1.md](docs/assemblies-step-export-hierarchy-v1.md) (сборки CadQuery и STEP), [docs/mjcf-generator-v1.md](docs/mjcf-generator-v1.md) (MJCF / MuJoCo), [docs/zip-archiving-download-ui-v1.md](docs/zip-archiving-download-ui-v1.md) (ZIP и UI), [docs/implementation-plan-hole-operation-v1.md](docs/implementation-plan-hole-operation-v1.md), [docs/refactoring-geometry-core-v11.md](docs/refactoring-geometry-core-v11.md).
