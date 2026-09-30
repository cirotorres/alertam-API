# SPEC 026 — Plano 1: API e ciclo de vida de instalações mobile

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar a API/Supabase a autoridade do ciclo de vida das instalações mobile, com código curto, plataforma, revogação completa, listagem administrativa, heartbeat e troca idempotente entre Desktops.

**Architecture:** `mobile_installations` continua sendo a identidade canônica por aparelho. A API acrescenta metadados de apresentação e operações atômicas no repositório; sessão mobile, administração Desktop e switch reutilizam essas operações sem duplicar regras. A PWA antiga permanece compatível porque `platform` é opcional e os campos atuais da resposta de sessão são preservados.

**Tech Stack:** FastAPI, Pydantic, Python 3.12, Supabase/PostgreSQL, psycopg, httpx, pytest.

**Spec:** `specs/026-mobile-installation-management-safe-pairing-switch.md`

## Global Constraints

- `installation_id` UUID continua sendo a identidade técnica canônica.
- `platform` aceita somente `ios`, `android` ou `other`; ausência em cliente antigo significa `other`.
- `display_code` possui 6 caracteres do alfabeto `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, é gerado no servidor e nunca autentica.
- Uma instalação revogada nunca volta a `active=true`.
- Um `installation_id` nunca muda de `device_id`.
- Revogação individual encerra tracking e desativa Push da instalação.
- Revogados são retornados ao Desktop somente por 30 dias; inatividade nunca revoga.
- Validação de QR é side-effect free.
- Switch A→B é atômico e reconciliável pelo mesmo `switch_id`.
- `VIEW_SECRET` nunca aparece em logs.
- Clientes antigos de sessão continuam aceitos.

## Review Focus

- Colisão de `display_code`: retry deve criar outro código sem deixar instalação parcial.
- Retry de switch após resposta de rede ambígua: mesmo `switch_id` + mesmo payload deve retornar B sem exigir A ainda ativa.
- Reuso malicioso de `switch_id` com payload diferente: rejeitar sem mutação.
- Revogação repetida/concorrente: deve ser idempotente e não reativar nada.
- Datas-limite de 30 dias e timestamps timezone-aware: item exatamente dentro da janela aparece; fora dela não.

---

### Task 1: Expandir o contrato de domínio das instalações

**Files:**
- Modify: `api/app/repositories/devices.py`
- Modify: `api/app/repositories/memory.py`
- Create: `api/app/services/mobile_installation_service.py`
- Test: `api/tests/unit/test_mobile_installation_service.py`
- Modify: `api/tests/unit/test_mobile_installation_repository.py`

**Interfaces:**
- Consumes: `DevicesRepository`, relógio injetável e gerador seguro de código.
- Produces: `MobileInstallationRecord.platform`, `display_code`; `MobileInstallationService.ensure(...)`, `list_for_device(...)`, `touch(...)`, `revoke(...)`.

- [ ] **Step 1: escrever testes RED para normalização e código curto**

Criar testes que provem `normalize_mobile_platform("ios") == "ios"`, valores desconhecidos viram `other`, e `generate_display_code()` produz exatamente 6 caracteres apenas do alfabeto aprovado.

- [ ] **Step 2: executar os testes focados e observar falha**

Run: `cd api && uv run pytest tests/unit/test_mobile_installation_service.py -q`  
Expected: FAIL por módulo/funções ainda inexistentes.

- [ ] **Step 3: definir tipos e serviço**

Em `repositories/devices.py`, estender `MobileInstallationRecord` com `platform: str` e `display_code: str`.

Em `mobile_installation_service.py`, produzir:
`normalize_mobile_platform(value: str | None) -> str`  
`generate_display_code() -> str`  
`MobileInstallationService(repository, clock=None, code_factory=generate_display_code)`.

- [ ] **Step 4: testar a regra “revogado não ressuscita”**

Alterar o teste existente que hoje permite reativação para provar o novo comportamento: após revogar, `ensure` retorna `None` e o registro continua inativo.

- [ ] **Step 5: implementar a semântica mínima no Memory repository**

Modificar `ensure_mobile_installation(device_id, installation_id, *, platform="other", display_code=None)` para criar somente quando inexistente; reutilizar somente ativo do mesmo Desktop; rejeitar revogado/outro Desktop.

Adicionar:
`list_mobile_installations(device_id, *, revoked_since: datetime) -> tuple[MobileInstallationRecord, ...]`  
`touch_mobile_installation(device_id, installation_id, *, platform: str) -> MobileInstallationRecord | None`.

- [ ] **Step 6: provar janela de 30 dias e heartbeat**

Adicionar testes com relógio fixo para ativos sempre listados, revogado exatamente em 30d listado, revogado >30d omitido, touch atualizando `last_seen_at` sem reativar item revogado. `platform` só pode substituir o valor persistido quando o atual for `other`; heartbeat não fica alternando uma plataforma já conhecida.

- [ ] **Step 7: executar suite unitária focada**

Run: `cd api && uv run pytest tests/unit/test_mobile_installation_service.py tests/unit/test_mobile_installation_repository.py -q`  
Expected: PASS.

- [ ] **Step 8: commit do contrato de domínio**

```bash
git add api/app/repositories/devices.py api/app/repositories/memory.py api/app/services/mobile_installation_service.py api/tests/unit/test_mobile_installation_service.py api/tests/unit/test_mobile_installation_repository.py
git commit -m "feat: define ciclo de vida de instalações mobile"
```

### Task 2: Persistência SQL/Supabase e revogação completa

**Files:**
- Create: `api/supabase/migrations/013_mobile_installation_management.sql`
- Modify: `api/app/repositories/postgres.py`
- Modify: `api/app/repositories/supabase.py`
- Modify: `api/tests/unit/test_mobile_installations_sql.py`
- Modify: `api/tests/unit/test_postgres_mobile_installation_repository.py`
- Modify: `api/tests/unit/test_supabase_mobile_installation_repository.py`
- Modify: `api/tests/integration/test_mobile_installation_postgres.py`

**Interfaces:**
- Consumes: interfaces de Task 1.
- Produces: persistência equivalente em Memory/Postgres/Supabase; RPCs atualizados para ensure/touch/revoke/list.

- [ ] **Step 1: escrever testes RED para a migration 013**

Provar que existem colunas `platform` e `display_code`, unicidade de `display_code`, backfill, ensure sem reativação, RPC de touch e revogação que também encerra `tracked_vessels` e desativa `push_installations`. Regressão obrigatória: `rotate_device_view_secret` continua revogando instalações mobile, trackings e Push de todo o `device_id`.

- [ ] **Step 2: rodar testes SQL focados**

Run: `cd api && uv run pytest tests/unit/test_mobile_installations_sql.py -q`  
Expected: FAIL por migration 013 inexistente.

- [ ] **Step 3: criar migration 013**

Adicionar/backfillar `platform NOT NULL DEFAULT 'other'` e `display_code`; validar alfabeto/tamanho; criar unicidade; redefinir `ensure_mobile_installation`; criar `touch_mobile_installation`; redefinir `revoke_mobile_installation` com tracking + push.

O backfill gera códigos somente para dados legados; novas instalações recebem código gerado pela API.

- [ ] **Step 4: adaptar PostgresRepository**

Atualizar selects/mapeamento de `MobileInstallationRecord` e implementar list/touch.

- [ ] **Step 5: adaptar SupabaseRepository**

Atualizar `select`, mapeamento, payloads RPC e os novos métodos com o mesmo contrato.

- [ ] **Step 6: testar colisão de código sem estado parcial**

Introduzir erro tipado `MobileInstallationDisplayCodeConflictError`. O serviço tenta novamente com novo código; o teste força `AAAAAA` em colisão e depois `BBBBBB`.

- [ ] **Step 7: rodar testes unitários + integração**

Run: `cd api && uv run pytest tests/unit/test_mobile_installation_service.py tests/unit/test_mobile_installations_sql.py tests/unit/test_postgres_mobile_installation_repository.py tests/unit/test_supabase_mobile_installation_repository.py tests/integration/test_mobile_installation_postgres.py -q`  
Expected: PASS.

- [ ] **Step 8: commit de persistência**

```bash
git add api/supabase/migrations/013_mobile_installation_management.sql api/app/repositories api/tests
git commit -m "feat: persiste metadados e revogação mobile"
```

### Task 3: Sessão mobile com metadados, validação de QR e heartbeat

**Files:**
- Modify: `api/app/models/mobile_session.py`
- Create: `api/app/models/mobile_installation.py`
- Modify: `api/app/services/mobile_session_service.py`
- Modify: `api/app/api/v1/mobile_session.py`
- Create: `api/app/api/v1/mobile_pairing.py`
- Modify: `api/app/api/v1/router.py`
- Test: `api/tests/integration/test_mobile_session.py`

**Interfaces:**
- Consumes: `MobileInstallationService` da Task 1.
- Produces: sessão retorna `device_id`, `installation_id`, `display_code`, `platform`; `POST /mobile/pairing/validate`; `POST /mobile/session/heartbeat`.

- [ ] **Step 1: escrever RED para compatibilidade**

Body antigo sem `platform` continua 200 e retorna `platform="other"` + código de 6 caracteres, preservando `device_id` e `installation_id`.

- [ ] **Step 2: escrever RED para cliente novo**

Body com `platform="ios"` retorna `platform="ios"`; recovery GET devolve os mesmos metadados.

- [ ] **Step 3: escrever RED para instalação revogada**

Após DELETE/revogação, POST com o mesmo UUID e QR ainda válido retorna 401 e não reativa a linha.

- [ ] **Step 4: implementar request/response compatíveis**

`MobileSessionRequest.platform: str | None = None`.  
`MobileSessionResponse` mantém campos atuais e adiciona `display_code: str`, `platform: str`.

`MobileSessionService.create_session(..., platform=None)` usa `MobileInstallationService.ensure`.

- [ ] **Step 5: adicionar validação de pareamento side-effect free**

Criar `PairingValidationRequest(device_id: str)` e um router dedicado `mobile_pairing.py` para `POST /api/v1/mobile/pairing/validate` com Bearer VIEW_SECRET; registrá-lo em `api/v1/router.py`.

Teste compara repositório/cookies antes e depois e prova que nenhuma instalação foi criada. Não encaixar essa rota sob o prefixo `/mobile/session`.

- [ ] **Step 6: adicionar heartbeat**

Criar `MobileHeartbeatRequest(platform: str | None)` e `POST /api/v1/mobile/session/heartbeat` autenticado pelo cookie.

Testar atualização de `last_seen_at`, normalização de plataforma e 401 para revogado.

- [ ] **Step 7: rodar integração de sessão**

Run: `cd api && uv run pytest tests/integration/test_mobile_session.py -q`  
Expected: PASS.

- [ ] **Step 8: commit da sessão/validação**

```bash
git add api/app/models api/app/services/mobile_session_service.py api/app/api/v1/mobile_session.py api/tests/integration/test_mobile_session.py
git commit -m "feat: estende sessão e validação mobile"
```

### Task 4: API administrativa autenticada pelo Desktop

**Files:**
- Create: `api/app/api/v1/mobile_installations.py`
- Create: `api/app/services/mobile_installation_admin_service.py`
- Modify: `api/app/api/v1/router.py`
- Test: `api/tests/integration/test_mobile_installation_admin.py`

**Interfaces:**
- Consumes: `DeviceAuthService`, list/revoke da instalação.
- Produces: `GET /devices/{device_id}/mobile-installations`; `DELETE /devices/{device_id}/mobile-installations/{installation_id}`.

- [ ] **Step 1: escrever RED de autenticação e isolamento**

Cobrir sem Device auth, segredo errado e tentativa do Desktop A de listar/revogar instalação de B.

- [ ] **Step 2: escrever RED da resposta**

GET retorna `active_count`, `active` e `recently_revoked`, somente com os campos aprovados e filtro de 30 dias.

- [ ] **Step 3: implementar router e modelos**

Seguir o padrão de `access.py`: parsear `Device`, autenticar o `device_id` do path e só então chamar o serviço.

- [ ] **Step 4: escrever RED da revogação individual**

DELETE da própria instalação é idempotente, encerra tracking, desativa Push e faz sessão subsequente retornar 401.

- [ ] **Step 5: implementar revogação administrativa**

Não revelar existência de instalação de outro Desktop. Retry da própria instalação já revogada permanece seguro.

- [ ] **Step 6: rodar testes administrativos**

Run: `cd api && uv run pytest tests/integration/test_mobile_installation_admin.py -q`  
Expected: PASS.

- [ ] **Step 7: commit da administração**

```bash
git add api/app/api/v1/mobile_installations.py api/app/services/mobile_installation_admin_service.py api/app/api/v1/router.py api/tests/integration/test_mobile_installation_admin.py
git commit -m "feat: adiciona gestão administrativa de aparelhos"
```

### Task 5: Switch atômico e idempotente A→B

**Files:**
- Create: `api/supabase/migrations/014_mobile_session_switch.sql`
- Modify: `api/app/repositories/devices.py`
- Modify: `api/app/repositories/memory.py`
- Modify: `api/app/repositories/postgres.py`
- Modify: `api/app/repositories/supabase.py`
- Modify: `api/app/models/mobile_session.py`
- Modify: `api/app/services/mobile_session_service.py`
- Modify: `api/app/api/v1/mobile_session.py`
- Test: `api/tests/unit/test_mobile_installation_repository.py`
- Create: `api/tests/integration/test_mobile_session_switch.py`

**Interfaces:**
- Produces: `POST /api/v1/mobile/session/switch` e `DevicesRepository.switch_mobile_installation(...)`.
- Request: `device_id`, `installation_id`, `platform`, `switch_id`; Bearer autentica B; cookie representa A no primeiro attempt.
- Response: mesmo shape de `MobileSessionResponse` para B.

- [ ] **Step 1: RED de sucesso A→B**

Sessão A existente + Bearer válido de B cria B, revoga A, encerra tracking/push A e emite cookie resolvendo B.

- [ ] **Step 2: RED de falha antes do commit**

Forçar erro transacional e provar que A permanece ativa e B não existe.

- [ ] **Step 3: RED de retry idempotente**

Repetir mesmo `switch_id`/payload após sucesso retorna a mesma B sem exigir A ativa e sem segunda instalação. Forçar também colisão do primeiro `display_code` de B: o retry interno deve escolher outro código sem revogar A até a criação de B poder ser confirmada.

- [ ] **Step 4: RED de payload divergente**

Mesmo `switch_id` com outro payload falha sem mutação.

- [ ] **Step 5: persistir idempotência**

Na migration 014, criar armazenamento mínimo de switch com `switch_id` único, identidade A/B, payload necessário e `completed_at`. A RPC verifica replay antes de exigir A ativa. Não reabrir/regravar a migration 013 depois que ela já tiver sido aplicada em algum ambiente.

- [ ] **Step 6: implementar repositories**

Memory imita a RPC; Postgres chama RPC SQL; Supabase chama a mesma RPC REST.

- [ ] **Step 7: implementar endpoint**

`MobileSessionService.switch_session(...)` valida VIEW_SECRET de B; repository executa transação; sucesso assina cookie com hash atual de B.

- [ ] **Step 8: rodar testes de switch**

Run: `cd api && uv run pytest tests/integration/test_mobile_session_switch.py tests/unit/test_mobile_installation_repository.py -q`  
Expected: PASS.

- [ ] **Step 9: commit do switch**

```bash
git add api/supabase/migrations/014_mobile_session_switch.sql api/app/repositories api/app/models/mobile_session.py api/app/services/mobile_session_service.py api/app/api/v1/mobile_session.py api/tests
git commit -m "feat: adiciona troca segura de sessão mobile"
```

### Task 6: Gate completo da API e handoff

**Files:**
- Modify: `api/DEPLOY_VERCEL.md`
- Create: `docs/superpowers/handoffs/2026-09-30-spec026-plan1-api-complete-handoff.md`

**Interfaces:**
- Produces: API pronta para o Plano 2.

- [ ] **Step 1: rodar testes SQL/integração aplicáveis**

Executar migration/testes Postgres conforme o fluxo atual do projeto.

- [ ] **Step 2: rodar gate completo da API**

Run: `make test`  
Expected: todos os testes API verdes.

- [ ] **Step 3: rodar `git diff --check` e revisar segredos**

Confirmar que nenhum log/fixture expõe VIEW_SECRET.

- [ ] **Step 4: atualizar deploy docs**

Adicionar migrations 013 e 014 à ordem de migrations e registrar que a API nova deve ser publicada antes de PWA/Desktop da SPEC 026.

- [ ] **Step 5: criar handoff**

Registrar interfaces finais, endpoints, migration, commits, testes e eventuais divergências aprovadas.

- [ ] **Step 6: commit final do Plano 1**

```bash
git add api/DEPLOY_VERCEL.md docs/superpowers/handoffs/2026-09-30-spec026-plan1-api-complete-handoff.md
git commit -m "docs: consolida api da gestão mobile"
```
