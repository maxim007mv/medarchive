.PHONY: setup secrets up down lint typecheck test e2e ci images gen-api fixtures

API := uv run --directory apps/api
export NEXT_TELEMETRY_DISABLED := 1

setup:
	corepack enable pnpm
	pnpm install --frozen-lockfile
	uv sync --directory apps/api --frozen
	pnpm --filter e2e exec playwright install chromium

secrets:
	$(API) python ../../infra/secrets/generate.py

up: secrets
	docker compose up -d --build --wait

down:
	docker compose down

lint:
	$(API) ruff check --config pyproject.toml . ../../infra
	$(API) ruff format --check --config pyproject.toml . ../../infra
	pnpm --filter web lint

typecheck:
	$(API) mypy app tests ../../infra/secrets
	pnpm --filter web typecheck
	pnpm --filter e2e typecheck

test:
	$(API) pytest
	pnpm --filter web test

# Needs the stack from `make up`.
e2e:
	pnpm --filter e2e test

ci: lint typecheck test

images:
	docker build -t medarchive/api:local apps/api
	docker build -t medarchive/web:local -f apps/web/Dockerfile .

gen-api:
	pnpm --filter web gen:api

fixtures:
	uv run qa/fixtures/generate.py
