.PHONY: install dev api web migrate test test-api test-web test-e2e test-e2e-full lint format build sample reset-data provider-check compose eval eval-gate

# A macOS user on Homebrew Python 3.13 has no `python3.12` binary, and the very first
# documented command would fail. Fall back to `python3` and let the venv install surface
# a clear version error instead of "command not found".
PYTHON ?= $(shell command -v python3.12 2>/dev/null || command -v python3)

install:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -c apps/api/constraints.lock -e 'apps/api[dev]'
	cd apps/web && npm ci

dev:
	@echo "Run 'make api' and 'make web' in separate terminals."

api:
	.venv/bin/uvicorn app.main:app --reload --app-dir apps/api

web:
	cd apps/web && npm run dev

migrate:
	.venv/bin/alembic -c apps/api/alembic.ini upgrade head

test: test-api test-web

test-api:
	cd apps/api && ../../.venv/bin/python -m pytest tests

test-web:
	cd apps/web && npm test -- --run

test-e2e:
	cd apps/web && npm run test:e2e

test-e2e-full:
	cd apps/web && npm run test:e2e:full-stack

eval:
	.venv/bin/python eval/run.py

eval-gate:
	.venv/bin/python eval/run.py --gate

lint:
	cd apps/api && ../../.venv/bin/ruff check . ../../scripts ../../eval
	cd apps/api && ../../.venv/bin/ruff format --check . ../../scripts ../../eval
	cd apps/api && ../../.venv/bin/mypy app
	cd apps/web && npm run lint

format:
	cd apps/api && ../../.venv/bin/ruff format . ../../scripts ../../eval
	cd apps/api && ../../.venv/bin/ruff check --fix . ../../scripts ../../eval
	cd apps/web && npm run format

build:
	cd apps/web && npm run build

sample:
	.venv/bin/python scripts/load_sample_data.py

reset-data:
	.venv/bin/python scripts/reset_local_data.py

provider-check:
	.venv/bin/python scripts/check_provider.py

compose:
	docker compose up --build
