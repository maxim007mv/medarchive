.PHONY: setup secrets up down lint typecheck test test-api test-web e2e ci images gen-api fixtures seed \
	contract a11y visual visual-baseline security audit-python audit-node gitleaks trivy zap load \
	alerts verify-block node-runtime

API := uv run --directory apps/api
export NEXT_TELEMETRY_DISABLED := 1
# Testcontainers' Ryuk fails on Docker Desktop for macOS: it cannot bind-mount ~/.docker/run's
# socket, and with the VM socket its port 8080 is often not published in time under load. The
# fixtures stop their containers; an interrupted run leaves them behind (D-011).
export TESTCONTAINERS_RYUK_DISABLED ?= true

# Stack under test for contract, security and load targets (`make up` publishes these ports).
API_URL ?= http://localhost:$(or $(API_PORT),8000)
COMPOSE_PROJECT ?= $(or $(COMPOSE_PROJECT_NAME),medarchive)
IMAGE_TAG ?= local
REPORT_DIR ?= reports

TRIVY_IMAGE := aquasec/trivy:0.76.2
GITLEAKS_IMAGE := zricethezav/gitleaks:v8.30.1
ZAP_IMAGE := ghcr.io/zaproxy/zaproxy@sha256:9624669db72f54d86c4b46a7064518bd9bf79d8c61a4c31befa9923489f328af
K6_IMAGE := grafana/k6:2.3.0
PROMETHEUS_IMAGE := prom/prometheus:v3.16.0
PIP_AUDIT := pip-audit==2.10.0
# Cleaned Node runtime (npm stripped) is what we ship and what Trivy must pass (D-004 / OPS-05).
NODE_RUNTIME_IMAGE := medarchive/node-runtime:22-alpine
BASE_IMAGES := python:3.12-slim-bookworm $(NODE_RUNTIME_IMAGE)

setup:
	corepack enable pnpm
	pnpm install --frozen-lockfile
	uv sync --directory apps/api --frozen
	pnpm --filter e2e exec playwright install chromium webkit

secrets:
	$(API) python ../../infra/secrets/generate.py

up: secrets
	docker compose up -d --build --wait

down:
	docker compose down

lint:
	$(API) ruff check --config pyproject.toml . ../../infra
	$(API) ruff format --check --config pyproject.toml . ../../infra
	$(API) ruff check ../../tools
	$(API) ruff format --check ../../tools
	pnpm --filter web lint

typecheck:
	$(API) mypy app tests ../../infra/secrets ../../tools
	pnpm --filter web typecheck
	pnpm --filter e2e typecheck

test: test-api test-web

test-api:
	$(API) pytest

# VITEST_ARGS: extra reporters for the gate, e.g. --reporter=junit --outputFile=…
test-web:
	pnpm --filter web test $(VITEST_ARGS)

# Needs the stack from `make up`.
e2e:
	pnpm --filter e2e test

ci: lint typecheck test

images:
	docker build -t medarchive/api:$(IMAGE_TAG) apps/api
	docker build -t medarchive/web:$(IMAGE_TAG) -f apps/web/Dockerfile .

gen-api:
	pnpm --filter web gen:api

fixtures:
	uv run qa/fixtures/generate.py

# BE-17: the six task fixtures into a new archive (prints its access key) or into WORKSPACE=<id>.
# Needs the stack from `make up`.
seed:
	docker compose run --rm --no-deps \
		-v "$(CURDIR)/qa/fixtures/manifest.json:/seed/qa/fixtures/manifest.json:ro" \
		-v "$(CURDIR)/MedArchive/05_qa/fixtures:/seed/MedArchive/05_qa/fixtures:ro" \
		api python -m app.cli seed --root /seed $(if $(WORKSPACE),--workspace $(WORKSPACE),--new)

# QA-02: app.openapi() against openapi.yaml for blocks 1..BLOCK, then Schemathesis against the stack.
contract:
	CONTRACT_BLOCK=$(or $(BLOCK),9) $(API) pytest tests/contract
	cd apps/api && CONTRACT_BASE_URL=$(API_URL) SCHEMATHESIS_HOOKS=tests.contract.hooks \
		uv run schemathesis run ../../openapi.yaml --url $(API_URL) --checks all \
		--max-examples 25 --seed 20261110 --workers 1

# QA-05 and QA-06; need the stack. Baselines change only through visual-baseline and review.
a11y:
	pnpm --filter e2e exec playwright test tests/a11y
visual:
	pnpm --filter e2e exec playwright test tests/visual --update-snapshots=none
visual-baseline:
	pnpm --filter e2e exec playwright test tests/visual --update-snapshots=all

# OPS-04, OPS-05: dependency audits, secrets in git history, image vulnerabilities.
security: audit-python audit-node gitleaks node-runtime
	for image in medarchive/api:$(IMAGE_TAG) medarchive/web:$(IMAGE_TAG) $(BASE_IMAGES); do \
		$(MAKE) --no-print-directory trivy IMAGE=$$image || exit 1; done

# Stripped Node base for Trivy and as the pin reference for apps/web/Dockerfile.
node-runtime:
	docker build -f infra/docker/node-runtime.Dockerfile -t $(NODE_RUNTIME_IMAGE) .

audit-python:
	mkdir -p $(REPORT_DIR)
	uv export --directory apps/api --frozen --no-dev --format requirements-txt -q \
		-o $(abspath $(REPORT_DIR))/requirements.txt
	uvx $(PIP_AUDIT) -r $(REPORT_DIR)/requirements.txt --require-hashes --disable-pip \
		-f json -o $(REPORT_DIR)/pip-audit.json

audit-node:
	mkdir -p $(REPORT_DIR)
	pnpm audit --prod --audit-level high --json > $(REPORT_DIR)/pnpm-audit.json

gitleaks:
	mkdir -p $(REPORT_DIR)
	docker run --rm -v "$(CURDIR):/repo:ro" -v "$(abspath $(REPORT_DIR)):/out" $(GITLEAKS_IMAGE) \
		git /repo --redact --no-banner --report-format json --report-path /out/gitleaks.json

# Fails on HIGH or CRITICAL findings that have a fix (OPS-05: no high in the base image).
trivy:
	mkdir -p $(REPORT_DIR)
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v medarchive_trivy_cache:/root/.cache \
		-v "$(abspath $(REPORT_DIR)):/out" $(TRIVY_IMAGE) image --quiet --scanners vuln \
		--severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 --format json \
		-o /out/trivy-$(subst /,-,$(subst :,-,$(IMAGE))).json $(IMAGE)

# ZAP baseline (passive) on the compose network; ZAP_COOKIE carries a session of a fresh archive.
zap:
	mkdir -p $(REPORT_DIR) && chmod 777 $(REPORT_DIR)
	docker run --rm --network $(COMPOSE_PROJECT)_default -v "$(abspath $(REPORT_DIR)):/zap/wrk:rw" \
		$(ZAP_IMAGE) zap-baseline.py -t http://web:3000/ -J zap.json -r zap.html -I \
		-z "-config replacer.full_list(0).description=session -config replacer.full_list(0).enabled=true \
		-config replacer.full_list(0).matchtype=REQ_HEADER -config replacer.full_list(0).matchstr=Cookie \
		-config replacer.full_list(0).regex=false -config replacer.full_list(0).replacement=$(ZAP_COOKIE)"

# k6 on the compose network: seeds LOAD_DOCUMENTS documents, then 50 VU read the list.
load:
	mkdir -p $(REPORT_DIR)
	docker run --rm --network $(COMPOSE_PROJECT)_default -v "$(CURDIR)/load:/load:ro" \
		-v "$(CURDIR)/MedArchive/05_qa/fixtures:/fixtures:ro" -v "$(abspath $(REPORT_DIR)):/out" \
		-e API_URL=http://api:8000 -e LOAD_DOCUMENTS=$(or $(LOAD_DOCUMENTS),1000) \
		$(K6_IMAGE) run --summary-export /out/k6-summary.json /load/k6/documents-list.js

# OPS-08 locally: rule syntax and the unit tests of every alert.
alerts:
	docker run --rm -v "$(CURDIR)/infra/prometheus:/rules:ro" -w /rules --entrypoint promtool \
		$(PROMETHEUS_IMAGE) check rules alerts.yml
	docker run --rm -v "$(CURDIR)/infra/prometheus:/rules:ro" -w /rules --entrypoint promtool \
		$(PROMETHEUS_IMAGE) test rules alerts.test.yml

# Gate of block N on the committed HEAD: `make verify-block N=3`.
verify-block:
	tools/verify_block.sh $(N)
