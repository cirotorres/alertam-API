# AlertaM Mobile API — Plano de Implementação TDD

> Para agentes de implementação: executar este plano tarefa por tarefa, sempre em RED → GREEN → REFACTOR. Não iniciar o frontend neste plano.

**Objetivo:** construir a API FastAPI que recebe o MobileSnapshot v1 do AlertaM Desktop, mantém somente o último snapshot válido no Supabase e o expõe em modo somente leitura para o futuro cliente mobile.

**Arquitetura:** o projeto maior será um monorepo em `/home/ciro/dev/prog/alertamaritimoAPI`, com `api/` e `frontend/` separados por responsabilidade. A API será stateless e será a única camada com acesso ao Supabase. O frontend Vite mobile-only dependerá apenas da API.

**Stack prevista da API:** Python 3.12, FastAPI, Pydantic v2, pytest, TestClient/httpx e PostgreSQL/Supabase.

**Fontes de verdade do contrato:**
- Desktop: `/home/ciro/dev/prog/alertamaritimo/specs/017-snapshot-mobile-sync-desktop.md`
- API: `/home/ciro/dev/prog/alertamaritimo/specs/018-api-fastapi-supabase.md`
- DTO real: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/mobile_snapshot.py`
- Testes reais: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_snapshot.py`

## Estado atual do monorepo

O monorepo local já possui Git inicializado e `origin` apontando para `https://github.com/cirotorres/alertam-API.git`. O trabalho inicial da API está isolado na branch local `feat/api-bootstrap`; nenhum push foi realizado por este plano.

A API está fixada em Python 3.12 e possui `.env.example`. Enquanto o Supabase real não existir, `PERSISTENCE_BACKEND=memory` usa um repository efêmero local, sem rede. O backend `supabase` será introduzido atrás da mesma fronteira de repository.
## Decisões arquiteturais já fechadas

- Um único monorepo conterá `api/` e `frontend/`.
- A API e o frontend continuam projetos independentes internamente.
- O AlertaM Desktop continua sendo a fonte autoritativa dos dados operacionais.
- O Desktop publica snapshots; a API não coleta WebPilot.
- O Supabase é persistência privada da API.
- O frontend nunca acessa Supabase diretamente.
- A API mantém somente o snapshot atual no MVP.
- O frontend será read-only.
- O plano do frontend será escrito somente depois de o contrato GET da API estar estável.
- Preferência futura: API e frontend sob a mesma origem quando a infraestrutura permitir, reduzindo CORS.

## Restrições globais

- A API não depende de Tkinter, Selenium, WebPilot ou módulos internos do Desktop.
- Nunca enviar `SUPABASE_SERVICE_ROLE_KEY` ao Desktop ou frontend.
- Não persistir `DEVICE_SECRET` ou `VIEW_SECRET` em texto puro.
- Novos segredos devem ser gerados com no mínimo 32 bytes aleatórios; não aceitar segredo operacional escolhido manualmente pelo usuário.
- Não logar Authorization, snapshots completos, segredos ou hashes completos.
- Aceitar inicialmente apenas `schema_version = 1`.
- Rejeitar campos extras no contrato.
- Todo timestamp contratual deve possuir timezone.
- POST mantém somente o último snapshot; não criar histórico cloud involuntário.
- `received_at` é sempre produzido pelo servidor em UTC.
- `collector_online` usa somente `received_at`.
- `STALE_AFTER_SECONDS = 120`; exatamente 120 s já significa offline.
- Ordem, idempotência e persistência devem ser atômicas no banco.
- Testes unitários não dependem de Internet nem Supabase real.
- Desenvolvimento local pode usar `PERSISTENCE_BACKEND=memory`; esse modo nunca substitui os testes posteriores da operação atômica PostgreSQL/Supabase.
- `.env.example` documenta todas as variáveis da API e `.env` real permanece ignorado pelo Git.
- Implementação segue TDD estrito: RED → GREEN → REFACTOR.
- Após cada bloco relevante, revisar a implementação contra a SPEC 018.
- Não começar o frontend neste plano.

## Fronteira já implementada pelo Desktop

O Desktop já entrega:

- `POST /api/v1/devices/{device_id}/snapshot`
- `Authorization: Device <DEVICE_SECRET>`
- `Content-Type: application/json`
- timeout HTTP máximo de 10 s
- no máximo um request em voo
- um único slot pending latest-only
- retry assíncrono
- `boot_id` novo por execução
- `sequence` crescente dentro do mesmo boot

O payload contém:
- `schema_version`
- `boot_id`
- `sequence`
- `generated_at`
- `collector`
- `port`
- `vessels`
- `weather`
- `marine`
- `recent_maneuvers`

A API não interpreta regra náutica. Ela autentica, valida, ordena, persiste e disponibiliza leitura.
## Estrutura alvo da API

```text
alertamaritimoAPI/
├── api/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   ├── models/
│   │   ├── security/
│   │   ├── repositories/
│   │   ├── services/
│   │   └── api/v1/
│   ├── supabase/migrations/
│   └── tests/
└── frontend/
    └── futuro projeto Vite mobile-only
```

Dentro da API:
- router = HTTP, parsing, DI e status codes;
- models = contrato Pydantic;
- security = parsing/hash/comparação de credenciais;
- services = regras de negócio da API;
- repositories = persistência;
- migrations = schema e operação atômica PostgreSQL.

Routers não acessam Supabase diretamente.
## Review Focus

Durante a implementação, revisar especialmente:

1. **Concorrência:** duas instâncias serverless recebem snapshots quase simultaneamente; o antigo não pode sobrescrever o novo.
2. **Idempotência:** retransmitir o mesmo `boot_id + sequence + payload` não pode alterar `received_at`.
3. **Reutilização conflitante:** mesmo `boot_id + sequence` com payload diferente deve gerar 409.
4. **Timestamps:** nenhum datetime sem timezone pode atravessar o contrato.
5. **Segredos:** respostas, logs, exceptions e fixtures nunca podem vazar credenciais reais.

---

## Task 1 — Bootstrap mínimo e configuração

**Entrega:** aplicação FastAPI inicializável e configurável sem acessar rede.

**Arquivos previstos:**
- `pyproject.toml`
- `app/main.py`
- `app/core/config.py`
- `tests/unit/test_config.py`
- `tests/unit/test_app.py`

**Interfaces:**
- `create_app() -> FastAPI`
- `Settings` com Supabase, stale threshold, environment, origins e log level.

- [x] RED/GREEN: `create_app()` retorna FastAPI sem conexão externa.
- [x] RED/GREEN: modo `memory` funciona sem credenciais Supabase e `STALE_AFTER_SECONDS` possui default 120.
- [x] RED/GREEN: backend `supabase` sem credenciais é rejeitado cedo.
- [x] RED/GREEN: import de `app.main` não abre conexão, arquivo ou thread.
- [x] GREEN: bootstrap mínimo criado sem acesso externo.
- [x] GREEN: suíte da Task 1 executada.
- [x] REFACTOR: configuração permanece sem efeitos colaterais.
- [x] REVIEW: implementação comparada com as restrições da SPEC 018.

### Registro da Task 1 — 2026-09-25

- Bootstrap FastAPI criado com factory `create_app()`.
- Python fixado em 3.12 para desenvolvimento e deploy.
- `.env.example` criado e `.env` mantido fora do Git.
- `PERSISTENCE_BACKEND=memory` permite desenvolvimento local sem Supabase.
- `PERSISTENCE_BACKEND=supabase` falha cedo se as credenciais obrigatórias estiverem ausentes.
- `MemoryDeviceRepository` adicionado apenas como apoio local provisório; atomicidade/idempotência continuam reservadas às Tasks 4–5.
- Estrutura `frontend/` preservada no monorepo sem iniciar o frontend.
- Revisão da etapa: nenhum acesso de rede no bootstrap, nenhum segredo administrativo exposto e nenhuma dependência do Desktop introduzida.
- Verificação final da etapa: `uv run pytest -q` deve permanecer verde antes do commit.

## Task 2 — Contrato Pydantic MobileSnapshot v1

**Entrega:** validação estrita do JSON realmente produzido pela SPEC 017.

**Arquivos previstos:**
- `app/models/mobile_snapshot.py`
- `tests/fixtures/mobile_snapshot_v1.json`
- `tests/unit/test_mobile_snapshot_model.py`
- `tests/contract/test_desktop_snapshot_contract.py`

**Modelos previstos:**
- `MobileSnapshotV1`
- `VesselV1`
- `CollectorV1`
- `WeatherV1`
- `MarineV1`
- `RecentManeuversV1`
- `ManeuverV1`

- [ ] RED: fixture válida do `MobileSnapshotBuilder` é aceita.
- [ ] RED: `schema_version != 1` é rejeitado e fica classificável como `unsupported_snapshot_schema`.
- [ ] RED: campos extras são rejeitados.
- [ ] RED: navio sem qualquer chave da whitelist é rejeitado.
- [ ] RED: `weather` e `marine` aceitam somente `{}` ou bloco completo.
- [ ] RED: timestamps obrigatórios sem timezone são rejeitados.
- [ ] RED: item active exige `ACTIVE + completed_at=null`.
- [ ] RED: item completed exige `COMPLETED + completed_at`.
- [ ] GREEN: implementar os modelos mínimos.
- [ ] GREEN: rodar unit + contract da Task 2.
- [ ] REFACTOR: nenhuma persistência dentro dos modelos.
- [ ] REVIEW: comparar campo a campo com o DTO real do Desktop.
## Task 3 — Credenciais e erros sanitizados

**Entrega:** parsing e hash de credenciais sem vazar segredos.

**Arquivos previstos:**
- `app/security/credentials.py`
- `app/core/errors.py`
- `tests/unit/test_credentials.py`
- `tests/unit/test_errors.py`

**Interfaces:**
- `hash_secret(secret: str) -> str`
- `verify_secret(secret: str, expected_hash: str) -> bool`
- `parse_device_authorization(header: str | None) -> str`
- `parse_bearer_authorization(header: str | None) -> str`

- [ ] RED: header Device válido extrai somente o token.
- [ ] RED: Bearer válido extrai somente o token.
- [ ] RED: esquema ausente/incorreto/token vazio gera 401 genérico.
- [ ] RED: comparação usa SHA-256 + `hmac.compare_digest`.
- [ ] RED: erros/logs não contêm o segredo.
- [ ] GREEN: implementar utilitários mínimos.
- [ ] GREEN: rodar testes da Task 3.
- [ ] REFACTOR: security não conhece router nem Supabase.
- [ ] REVIEW: dispositivo inexistente e segredo incorreto não podem ser distinguíveis externamente.
## Task 4 — Schema Supabase e contrato do repository

**Entrega:** persistência representável sem banco real e schema SQL mínimo.

**Estado provisório:** já existe `MemoryDeviceRepository` testado para desenvolvimento local sem Supabase. Ele não implementa ainda ordenação/idempotência atômica; essas regras continuam pertencendo às Tasks 4–5 e ao PostgreSQL real.

**Arquivos previstos:**
- `app/repositories/devices.py`
- `supabase/migrations/001_devices.sql`
- `scripts/provision_device.py`
- `tests/unit/test_devices_repository_contract.py`
- `tests/unit/test_provision_device.py`

**Interface do repository:**
- `get_device_auth(device_id: str) -> DeviceAuthRecord | None`
- `get_snapshot(device_id: str) -> StoredSnapshot | None`
- `rotate_view_secret_hash(...)`
- `accept_snapshot_atomic(...) -> AcceptSnapshotResult`

Tabela `devices`:
- `device_id` primary key
- `device_secret_hash`
- `view_secret_hash`
- `snapshot jsonb`
- `snapshot_schema_version`
- `boot_id`
- `sequence`
- `generated_at`
- `received_at`
- timestamps de criação/atualização e rotação

- [ ] RED: fake repository representa dispositivo inexistente, vazio e com snapshot.
- [ ] RED: interface não aceita segredo em texto puro.
- [ ] GREEN: definir DTOs/Protocol de persistência.
- [ ] RED: provisionamento gera `DEVICE_SECRET` com `secrets.token_urlsafe(32)` ou entropia equivalente, mostra o segredo uma única vez e persiste somente seu SHA-256.
- [ ] RED: provisionamento não sobrescreve silenciosamente um `device_id` já existente.
- [ ] GREEN: migration habilita RLS e não cria policy pública.
- [ ] GREEN: criar script administrativo local de provisionamento, sem endpoint público de cadastro.
- [ ] GREEN: rodar testes da Task 4.
- [ ] REVIEW: routers futuros não conhecem SQL e nenhum fluxo público cria dispositivos.
## Task 5 — Operação atômica de ordenação e idempotência

**Entrega:** uma única operação PostgreSQL decide se o snapshot é aceito, repetido ou conflitante.

**Arquivos previstos:**
- `supabase/migrations/002_accept_snapshot_rpc.sql`
- `tests/unit/test_snapshot_ordering.py`
- `tests/integration/test_accept_snapshot_repository.py`

**Resultados:**
- `accepted`
- `idempotent`
- `out_of_order`
- `sequence_reuse_mismatch`
- `device_not_found`

Regras:
- mesmo boot + sequence maior → accepted;
- mesmo boot + mesma sequence + payload igual → idempotent;
- mesmo boot + mesma sequence + payload diferente → mismatch;
- mesmo boot + sequence menor → out_of_order;
- boot diferente → sequence pode reiniciar.

- [ ] RED: cobrir todas as regras acima.
- [ ] RED: idempotência mantém `received_at` original.
- [ ] RED: concorrência não deixa snapshot antigo vencer.
- [ ] GREEN: implementar função SQL/RPC transacional.
- [ ] GREEN: implementar adaptador do repository.
- [ ] REFACTOR: nunca fazer SELECT de validação + UPDATE independente.
- [ ] REVIEW: revisar concorrência serverless.
## Task 6 — POST do snapshot

**Entrega:** endpoint de escrita completo para o Desktop.

**Rota:** `POST /api/v1/devices/{device_id}/snapshot`

**Arquivos previstos:**
- `app/services/snapshot_service.py`
- `app/api/v1/snapshots.py`
- `app/models/responses.py`
- `tests/unit/test_snapshot_service.py`
- `tests/integration/test_post_snapshot.py`

**Mapeamento mínimo:**
- sucesso → 200;
- credencial inválida → 401 / `invalid_device_credentials`;
- out of order → 409 / `out_of_order_snapshot`;
- sequence reutilizada com payload diferente → 409 / `sequence_reuse_mismatch`;
- schema não suportado → 422 / `unsupported_snapshot_schema`;
- persistência temporariamente indisponível → 503.

- [ ] RED: credencial inválida retorna 401 genérico.
- [ ] RED: payload válido chega a `accept_snapshot_atomic`.
- [ ] RED: resposta não devolve snapshot completo.
- [ ] RED: repetição idempotente retorna 200.
- [ ] RED: conflitos retornam 409 correto.
- [ ] RED: erro de repository nunca vira sucesso.
- [ ] GREEN: implementar service e router mínimos.
- [ ] GREEN: rodar testes do POST.
- [ ] REFACTOR: regra no service; HTTP no router.
- [ ] REVIEW: comparar com `SnapshotHttpClient` da 017.
## Task 7 — VIEW_SECRET e rotação

**Entrega:** dispositivo autenticado registra/rotaciona o segredo de leitura.

**Rota:** `PUT /api/v1/devices/{device_id}/view-access`

**Arquivos previstos:**
- `app/services/access_service.py`
- `app/api/v1/access.py`
- `tests/unit/test_access_service.py`
- `tests/integration/test_put_view_access.py`

- [ ] RED: exige Authorization Device válido.
- [ ] RED: token curto/formato inválido é rejeitado.
- [ ] RED: repository recebe apenas hash.
- [ ] RED: resposta é 204 e não contém segredo.
- [ ] RED: rotação invalida imediatamente o token anterior.
- [ ] GREEN: implementar service + endpoint.
- [ ] GREEN: rodar testes da Task 7.
- [ ] REFACTOR: geração de QR/token continua fora deste endpoint.
- [ ] REVIEW: verificar logs/exceptions.

## Task 8 — GET read-only para o mobile

**Entrega:** frontend futuro lê o último snapshot somente pela API.

**Rota:** `GET /api/v1/devices/{device_id}/snapshot`

**Meta de saída:**
- `received_at`
- `age_seconds`
- `collector_online`
- `stale_after_seconds`
- [ ] RED: Bearer inválido ou VIEW_SECRET ausente retorna 401 genérico.
- [ ] RED: dispositivo sem snapshot retorna 404 / `snapshot_not_available`.
- [ ] RED: GET válido devolve snapshot completo + meta.
- [ ] RED: 119 s → online.
- [ ] RED: 120 s → offline.
- [ ] RED: snapshot offline continua sendo devolvido.
- [ ] RED: cálculo usa apenas `received_at`.
- [ ] GREEN: implementar leitura e cálculo.
- [ ] GREEN: rodar testes da Task 8.
- [ ] REFACTOR: relógio injetável/testável.
- [ ] REVIEW: `generated_at` não influencia online/offline.

## Task 9 — Router v1, health, CORS e observabilidade

**Entrega:** shell HTTP consistente.

**Arquivos previstos:**
- `app/api/v1/router.py`
- `app/api/v1/health.py`
- `app/core/logging.py`
- ajustes em `app/main.py`
- testes de shell/logging

- [ ] RED: `/api/v1/health` responde sem consultar snapshot.
- [ ] RED: rotas v1 são montadas uma única vez.
- [ ] RED: CORS não usa wildcard por padrão.
- [ ] RED: `ALLOWED_ORIGINS` explícito é respeitado.
- [ ] RED: logs contêm método, rota, status e duração.
- [ ] RED: logs nunca contêm Authorization ou snapshot completo.
- [ ] RED: erros de validação Pydantic são convertidos para o envelope `detail.code + detail.message`, sem expor detalhes internos.
- [ ] RED: `schema_version` desconhecido retorna especificamente 422 / `unsupported_snapshot_schema`.
- [ ] GREEN: implementar router, middleware, logging e handler central de `RequestValidationError`.
- [ ] REVIEW: manter caminho preparado para same-origin com o frontend.
## Task 10 — Contrato ponta a ponta Desktop → API → Mobile

**Entrega:** prova automatizada de compatibilidade da 017 com a API.

**Arquivos previstos:**
- `tests/fixtures/mobile_snapshot_v1.json`
- `tests/contract/test_desktop_to_mobile_roundtrip.py`

- [ ] RED: fixture é gerada/capturada a partir do `MobileSnapshotBuilder`, sem Selenium.
- [ ] RED: POST aceita exatamente a fixture real.
- [ ] RED: GET devolve o mesmo snapshot sem perda ou reformatação.
- [ ] RED: `linhas_brutas`, cookies, logs e sessão não aparecem.
- [ ] GREEN: corrigir somente incompatibilidades reais.
- [ ] GREEN: executar toda suíte aplicável.
- [ ] REVIEW: quebra incompatível exige futura nova `schema_version`.

## Task 11 — Preparação de deploy na Vercel

**Entrega:** API FastAPI deployável na Vercel sem alterar as regras testadas.

- [ ] RED: smoke test prova que o entrypoint de deploy expõe a mesma app FastAPI.
- [ ] GREEN: adicionar somente configuração necessária de deploy.
- [ ] GREEN: variáveis sensíveis ficam exclusivamente no ambiente.
- [ ] REVIEW: nenhuma credencial administrativa versionada.
- [ ] REVIEW: deploy não usa memória local como fonte de verdade.

## Ordem obrigatória

1. Bootstrap/config.
2. Contrato Pydantic.
3. Segurança/erros.
4. Repository/schema.
5. Atomicidade/idempotência.
6. POST Desktop.
7. VIEW_SECRET.
8. GET mobile.
9. CORS/logging/health.
10. Round-trip de contrato.
11. Deploy.
## Ciclo TDD obrigatório

Para cada comportamento:

1. escrever um teste mínimo;
2. executar e confirmar RED pelo motivo esperado;
3. implementar somente o mínimo necessário;
4. executar o teste alvo e confirmar GREEN;
5. executar a suíte da área;
6. refatorar mantendo tudo verde;
7. revisar contra a SPEC 018 antes de avançar.

Mocks/fakes entram nas fronteiras externas. Teste unitário não toca Internet.

## Comandos previstos após o scaffold

```bash
uv sync --extra dev
uv run pytest tests/unit -q
uv run pytest tests/contract -q
uv run pytest tests/integration -q
uv run pytest -q
```

Integrações que exigirem Supabase real devem ser isoladas e puladas quando o ambiente de teste não estiver configurado.

## Critérios para liberar o planejamento do frontend

A API só libera o plano do Vite mobile-only quando:
- unitários estiverem verdes;
- contrato real MobileSnapshot v1 estiver verde;
- POST → persistência → GET fizer round-trip sem perda de campos;
- autenticação Device e Bearer estiver coberta;
- somente hashes forem persistidos;
- ordenação/idempotência forem atômicas;
- regra 119/120 s estiver coberta;
- falha de persistência não retornar sucesso;
- snapshot offline continuar disponível;
- logs estiverem sanitizados;
- Supabase continuar privado atrás da API;
- revisão final da SPEC 018 não encontrar problema crítico/importante.
## Fora deste plano

Não implementar ainda:
- React/Vite mobile-only;
- mapa mobile;
- tabs/footer/drawer;
- ficha visual do navio;
- polling do navegador;
- cache offline/service worker/PWA;
- QR Code e UX de pareamento;
- push notification;
- WebSocket/SSE;
- histórico cloud.

Esses itens terão plano próprio dentro do mesmo monorepo após estabilização da API.

## Handoff futuro para o frontend

O frontend deverá depender somente do contrato HTTP público:
- `device_id`;
- `VIEW_SECRET`;
- `GET /api/v1/devices/{device_id}/snapshot`;
- envelope `snapshot + meta`.

O frontend não conhecerá schema SQL, service role, RPC, repository nem detalhes internos do Desktop.

## Observação de workflow

O Git do monorepo já está inicializado e aponta para o repositório remoto `cirotorres/alertam-API`.

Fluxo obrigatório por etapa:
1. executar a etapa em TDD, preservando RED → GREEN → REFACTOR;
2. executar a suíte relevante e a suíte completa disponível;
3. revisar código, segurança, contrato e aderência à SPEC 018;
4. registrar no plano o que foi implementado e o resultado da revisão;
5. criar somente então um commit exclusivo daquela etapa, com mensagem descritiva em português;
6. iniciar a etapa seguinte apenas após esse commit;
7. não fazer push automaticamente;
8. se uma etapa exigir credencial, serviço externo ou ação manual do Ciro, interromper naquele ponto e informar exatamente o que é necessário.
