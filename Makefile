# AI-Forge — локальная разработка (запускайте из корня репозитория).
# Требования: Docker, Python 3.12+, Node.js 20+.

.DEFAULT_GOAL := help

.PHONY: help infra-up infra-down install dev-api dev-worker dev-web test

VENV := .venv
UVICORN := $(VENV)/bin/uvicorn
ARQ := $(VENV)/bin/arq
PIP := $(VENV)/bin/pip
COMPOSE := docker compose -f docker-compose.yml

help:
	@echo "AI-Forge Makefile"
	@echo "  make infra-up     — Redis + MinIO (docker compose)"
	@echo "  make infra-down   — остановить Redis и MinIO"
	@echo "  make install      — venv + pip (api, worker) + npm (web)"
	@echo "  make dev-api      — FastAPI / uvicorn :8899"
	@echo "  make dev-worker   — Arq worker"
	@echo "  make dev-web      — Next.js :3000"
	@echo "  make test         — unittest (PYTHONPATH=services:services/api)"

infra-up:
	$(COMPOSE) up -d redis minio

infra-down:
	$(COMPOSE) stop minio redis

install:
	python3 -m venv $(VENV)
	$(PIP) install -U pip
	$(PIP) install -r services/api/requirements.txt
	$(PIP) install -r services/worker/requirements.txt
	cd apps/web && npm install

dev-api:
	cd services/api && ../../$(UVICORN) main:app --host 127.0.0.1 --port 8899 --reload

dev-worker:
	cd services && PYTHONPATH=. ../$(ARQ) worker.main.WorkerSettings -v

dev-web:
	cd apps/web && npm run dev

test:
	PYTHONPATH=services:services/api $(VENV)/bin/python -m unittest discover -s tests -p 'test_*.py' -v
