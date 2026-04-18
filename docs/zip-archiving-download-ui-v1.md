# Core Feature: ZIP Archiving & Download UI

## 1. Задача

Автоматическая упаковка сгенерированных файлов (XML, STEP, STL по деталям) в единый ZIP на стороне воркера и возможность скачать архив из веб-интерфейса.

## 2. Логика упаковки (Worker)

Используется стандартная библиотека Python `zipfile` (`create_project_zip` в `generator.py`).

**Структура архива `project.zip`:**

```text
project.zip
├── simulation.xml
├── model.step
└── mesh/
    ├── piston_head.stl
    └── con_rod.stl
```

**Алгоритм:** после генерации файлов во временной папке создаётся `project.zip`, загрузка в MinIO: `{job_id}/project.zip`. Отдельная загрузка `mesh/*.stl` и `simulation.xml` не выполняется — MuJoCo-сцена поставляется целиком в архиве (меньше presigned-ссылок).

## 3. API

В `JobArtifacts` поле `zip_url` — presigned GET на `project.zip` (если в Redis есть `zip_key`).

Поле `mjcf_url` сохраняется для старых задач, у которых в Redis остался `mjcf_key`.

## 4. Frontend

Панель «Артефакты»: кнопка «Скачать всё (ZIP)» и ссылка «Открыть в MuJoCo Play» ([mujoco.org/play](https://mujoco.org/play)).

## 5. Реализация

- `create_project_zip` в `services/worker/generator.py`
- `generate_blueprint_task` загружает `project.zip`
- `page.tsx` — кнопка и ссылка
