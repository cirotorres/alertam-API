SHELL := /bin/bash
.DEFAULT_GOAL := help

DEV_COMPOSE := docker compose -f docker-compose.dev.yml
PROD_COMPOSE := docker compose -f docker-compose.prod.yml
PROD_ENV := api/.env.prod

.PHONY: help run dev dev-up dev-down dev-reset dev-logs dev-ps dev-config dev-info \
        dev-db-shell dev-api-shell api-run sync test test-unit test-contract \
        test-integration test-all docker-build prod-env prod-check prod prod-up \
        prod-down prod-logs prod-ps prod-config prod-rebuild

help:
	@printf '%s\n' \
	  'AlertaM monorepo — comandos principais' \
	  '' \
	  'DEV' \
	  '  make run            Sobe API + Postgres local + frontend em foreground' \
	  '  make dev-up         Sobe o stack dev em background' \
	  '  make dev-down       Para o stack dev' \
	  '  make dev-reset      Para o stack e APAGA o volume do banco dev' \
	  '  make dev-logs       Acompanha logs do stack dev' \
	  '  make dev-ps         Mostra os serviços dev' \
	  '  make dev-info       Mostra URLs e credenciais locais de teste' \
	  '  make dev-db-shell   Abre psql no banco dev' \
	  '  make dev-api-shell  Abre shell no container da API' \
	  '' \
	  'API LOCAL (sem Docker)' \
	  '  make sync           Sincroniza dependências com uv' \
	  '  make api-run        Executa somente a FastAPI local com reload' \
	  '' \
	  'TESTES' \
	  '  make test           Executa a suíte local (integrações DB sem DSN são skip)' \
	  '  make test-unit      Executa testes unitários' \
	  '  make test-contract  Executa testes de contrato' \
	  '  make test-integration Executa integrações disponíveis localmente' \
	  '  make test-all       Executa TODA a suíte em Docker com Postgres efêmero' \
	  '' \
	  'PROD / SUPABASE' \
	  '  make prod-env       Cria api/.env.prod a partir do exemplo (uma única vez)' \
	  '  make prod-config    Valida o compose prod' \
	  '  make prod           Sobe API + frontend em background usando Supabase' \
	  '  make prod-down      Para o stack prod' \
	  '  make prod-logs      Acompanha logs do stack prod' \
	  '  make prod-ps        Mostra os serviços prod' \
	  '  make prod-rebuild   Rebuilda e sobe o stack prod' \
	  '' \
	  'IMAGENS' \
	  '  make docker-build   Builda a imagem production da API'

run: dev

dev:
	$(DEV_COMPOSE) up --build

dev-up:
	$(DEV_COMPOSE) up -d --build

dev-down:
	$(DEV_COMPOSE) down --remove-orphans

dev-reset:
	@echo 'ATENÇÃO: removendo containers E volume persistente do banco dev.'
	$(DEV_COMPOSE) down -v --remove-orphans

dev-logs:
	$(DEV_COMPOSE) logs -f --tail=200

dev-ps:
	$(DEV_COMPOSE) ps

dev-config:
	$(DEV_COMPOSE) config

dev-info:
	@printf '%s\n' \
	  'Frontend:      http://localhost:5173' \
	  'API direta:    http://localhost:8000' \
	  'Health proxy:  http://localhost:5173/api/v1/health' \
	  'Postgres host: localhost:55431 (default)' \
	  '' \
	  'Seed DEV local:' \
	  '  DEVICE_ID=pecem-01' \
	  '  DEVICE_SECRET=dev-device-secret-change-me' \
	  '  VIEW_SECRET=VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV'

dev-db-shell:
	$(DEV_COMPOSE) exec db psql -U alertam -d alertam_dev

dev-api-shell:
	$(DEV_COMPOSE) exec api /bin/sh

sync:
	cd api && uv sync --extra dev

api-run:
	cd api && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

test:
	cd api && uv run pytest -q -W error

test-unit:
	cd api && uv run pytest tests/unit -q -W error

test-contract:
	cd api && uv run pytest tests/contract -q -W error

test-integration:
	cd api && uv run pytest tests/integration -q -W error

test-all:
	@set -e; \
	trap '$(DEV_COMPOSE) --profile test rm -sf db-test >/dev/null 2>&1 || true' EXIT; \
	$(DEV_COMPOSE) --profile test run --rm --build tests

docker-build:
	docker build --target prod -t alertam-api:local ./api

prod-env:
	@if [ -e "$(PROD_ENV)" ]; then \
		echo "$(PROD_ENV) já existe; nenhuma alteração foi feita."; \
	else \
		cp api/.env.prod.example "$(PROD_ENV)"; \
		echo "$(PROD_ENV) criado. Preencha SUPABASE_URL e SUPABASE_SECRET_KEY."; \
	fi

prod-check:
	@test -f "$(PROD_ENV)" || { \
		echo "Erro: $(PROD_ENV) não existe."; \
		echo "Execute 'make prod-env' e preencha as credenciais Supabase."; \
		exit 1; \
	}
	@grep -q '^SUPABASE_URL=https://' "$(PROD_ENV)" || { \
		echo 'Erro: SUPABASE_URL precisa ser preenchida em api/.env.prod.'; \
		exit 1; \
	}
	@grep -Eq '^SUPABASE_SECRET_KEY=sb_secret_.+' "$(PROD_ENV)" || { \
		echo 'Erro: SUPABASE_SECRET_KEY precisa ser preenchida em api/.env.prod.'; \
		exit 1; \
	}

prod: prod-check
	$(PROD_COMPOSE) up -d --build

prod-up: prod

prod-down:
	$(PROD_COMPOSE) down --remove-orphans

prod-logs:
	$(PROD_COMPOSE) logs -f --tail=200

prod-ps:
	$(PROD_COMPOSE) ps

prod-config: prod-check
	$(PROD_COMPOSE) config

prod-rebuild: prod-check
	$(PROD_COMPOSE) build --no-cache
	$(PROD_COMPOSE) up -d
