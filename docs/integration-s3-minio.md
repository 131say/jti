# Integration with S3 (MinIO) & Presigned URLs Lifecycle

## 1. Роль хранилища в MVP

Все артефакты (модели `.gltf`, инженерные файлы `.step`, логи симуляции) являются тяжелыми бинарными данными. Они не должны храниться в базе данных. Мы используем MinIO как локальный S3-совместимый слой.

## 2. Сценарий работы с файлами

1. **Worker Fulfillment:** После завершения генерации (CadQuery) воркер сохраняет файл локально, а затем загружает его в бакет `artifacts` (переменная `S3_BUCKET`, по умолчанию `artifacts`).
2. **Path Convention:** Путь к файлу формируется как `{job_id}/{artifact_name}.{ext}`.
3. **Security (Presigned URLs):** Чтобы клиент мог скачать файл из защищенного бакета, API генерирует временную ссылку (TTL: 1 час).

## 3. Техническая реализация (Boto3)

### Настройка клиента (Shared Utility)

И API, и Worker используют `boto3.client("s3", ...)` с указанием `endpoint_url` нашего MinIO.

### Логика Worker (Загрузка)

См. `services/worker/storage.py`: загрузка через `upload_file` в бакет.

### Логика API (Генерация ссылки)

При запросе `GET /api/v1/jobs/{job_id}`, если статус `completed`, API читает из Redis ключи `glb_key` / `step_key` и вызывает `generate_presigned_url` клиентом с **`S3_EXTERNAL_ENDPOINT`** (см. `services/api/storage.py`).

## 4. Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `S3_ENDPOINT` | Внутренний URL MinIO (например `http://minio:9000` в Docker, `http://localhost:9000` локально) |
| `S3_EXTERNAL_ENDPOINT` | URL для подписи presigned ссылок для браузера (часто `http://localhost:9000`) |
| `S3_ACCESS_KEY` | Ключ доступа (в compose: `MINIO_ROOT_USER`) |
| `S3_SECRET_KEY` | Секрет (в compose: `MINIO_ROOT_PASSWORD`) |
| `S3_BUCKET` | Имя бакета (по умолчанию `artifacts`) |

## 5. Важный нюанс: Public vs Internal URL

В Docker-сети воркер видит MinIO как `http://minio:9000`, но браузер пользователя (фронтенд) должен обращаться к `http://localhost:9000`.

**Решение:** использовать переменную `S3_EXTERNAL_ENDPOINT` для генерации преподписанных ссылок в API; воркер продолжает использовать `S3_ENDPOINT` для загрузки.
