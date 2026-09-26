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
- Nunca enviar `SUPABASE_SECRET_KEY` nem a chave legada `SUPABASE_SERVICE_ROLE_KEY` ao Desktop ou frontend.
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

- [x] RED/GREEN: fixture válida do `MobileSnapshotBuilder` é aceita.
- [x] RED/GREEN: `schema_version != 1` é rejeitado e fica classificável como `unsupported_snapshot_schema`.
- [x] RED/GREEN: campos extras são rejeitados.
- [x] RED/GREEN: navio sem qualquer chave da whitelist é rejeitado.
- [x] RED/GREEN: `weather` e `marine` aceitam somente `{}` ou bloco completo.
- [x] RED/GREEN: timestamps obrigatórios sem timezone são rejeitados.
- [x] RED/GREEN: item active exige `ACTIVE + completed_at=null`.
- [x] RED/GREEN: item completed exige `COMPLETED + completed_at`.
- [x] RED/GREEN: medidas presentes precisam ser numéricas e não aceitam strings numéricas.
- [x] GREEN: modelos mínimos implementados.
- [x] GREEN: unit + contract da Task 2 executados.
- [x] REFACTOR: modelos permanecem puros, sem persistência.
- [x] REVIEW: contrato comparado campo a campo com o DTO real do Desktop e a SPEC 018.

### Registro da Task 2 — 2026-09-25

- Fixture `mobile_snapshot_v1.json` gerada diretamente pelo `MobileSnapshotBuilder` real do Desktop.
- `MobileSnapshotV1` e DTOs internos criados com `extra="forbid"`.
- `boot_id` validado como UUID e `sequence` como inteiro estritamente positivo.
- Timestamps contratuais validados como timezone-aware.
- Navios exigem todas as chaves da whitelist v1, inclusive campos nullable presentes com `null`.
- `weather` e `marine` aceitam somente bloco vazio ou bloco v1 completo.
- Medições numéricas usam tipos estritos para impedir coerção silenciosa de strings.
- Manobras recentes validam tipo, status e coerência entre grupo active/completed e `completed_at`.
- Testes de contrato garantem que a fixture do Desktop não contém `linhas_brutas` nem campos fora do contrato.
- Revisão da etapa: nenhum acesso ao banco, nenhuma regra náutica recriada e nenhuma dependência da aplicação Desktop introduzida.
- Verificação final da etapa: suíte completa da API com 24 testes verdes antes do commit.

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

- [x] RED/GREEN: header Device válido extrai somente o token.
- [x] RED/GREEN: Bearer válido extrai somente o token.
- [x] RED/GREEN: esquema ausente/incorreto/token vazio gera 401 genérico.
- [x] RED/GREEN: hashing usa SHA-256 e verificação usa `hmac.compare_digest`.
- [x] RED/GREEN: erros públicos não contêm o segredo recebido.
- [x] GREEN: utilitários mínimos implementados.
- [x] GREEN: testes da Task 3 executados.
- [x] REFACTOR: security permanece sem dependência de router ou Supabase.
- [x] REVIEW: os erros públicos não distinguem causa interna de falha de credencial.

### Registro da Task 3 — 2026-09-25

- `hash_secret()` implementado com SHA-256 hexadecimal.
- `verify_secret()` compara hashes com `hmac.compare_digest`.
- Headers `Authorization: Device <token>` e `Authorization: Bearer <token>` possuem parsers independentes.
- Headers ausentes, com esquema incorreto, token vazio ou token contendo espaços extras são rejeitados com 401 genérico.
- `InvalidDeviceCredentialsError` expõe somente `invalid_device_credentials` e mensagem pública curta.
- `InvalidViewCredentialsError` expõe somente `invalid_view_credentials` e mensagem pública curta.
- Nenhum token, header bruto ou hash é incluído nas mensagens de erro.
- Revisão da etapa: a camada security não acessa repository, FastAPI, Supabase ou logging.
- Verificação final da etapa: suíte completa da API com 43 testes verdes antes do commit.

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

- [x] RED/GREEN: repository em memória representa dispositivo inexistente, vazio e com snapshot.
- [x] RED/GREEN: DTOs de autenticação persistem somente hashes, nunca segredo em texto puro.
- [x] GREEN: DTOs e Protocol de persistência definidos.
- [x] RED/GREEN: provisionamento gera `DEVICE_SECRET` com 32 bytes de entropia e persiste somente seu SHA-256.
- [x] RED/GREEN: provisionamento não sobrescreve silenciosamente um `device_id` já existente.
- [x] RED/GREEN: CLI administrativo mostra o segredo uma única vez e gera SQL contendo apenas o hash.
- [x] GREEN: migration habilita RLS e não cria policy pública.
- [x] GREEN: script administrativo local criado, sem endpoint público de cadastro.
- [x] GREEN: testes da Task 4 executados.
- [x] REVIEW: routers futuros não conhecem SQL e nenhum fluxo público cria dispositivos.

### Registro da Task 4 — 2026-09-25

- Criado `DeviceAuthRecord` com somente `device_secret_hash` e `view_secret_hash`.
- Criado `StoredSnapshot`, `SnapshotCandidate`, `AcceptSnapshotResult` e enum de resultados para preparar a fronteira da Task 5.
- Criado `DevicesRepository` como Protocol para autenticação, leitura, rotação e aceitação atômica futura.
- **Ruling:** o contrato ganhou `create_device()`, necessário para o provisionamento administrativo. Custo se essa decisão mudar: adaptação pequena do provisionador e dos repositories.
- `MemoryDeviceRepository` passou a suportar criação sem overwrite, leitura de snapshot e rotação de hash, preservando compatibilidade com os testes anteriores.
- Migration `001_devices.sql` cria uma única linha por dispositivo, habilita RLS e não cria policy pública.
- Migration revoga acesso direto de `anon` e `authenticated`; a futura API usará apenas credencial privada de servidor.
- `provision_device()` gera segredo de 32 bytes, entrega o plaintext apenas ao chamador e persiste somente SHA-256.
- CLI administrativo permite gerar o segredo hoje e emitir o `INSERT` seguro para execução manual futura no SQL Editor do Supabase.
- A saída SQL nunca contém o segredo em texto puro.
- Revisão da etapa: nenhuma rota pública de cadastro foi criada e o mock local não substitui a atomicidade PostgreSQL da Task 5.
- Verificação final da etapa: suíte completa da API com 52 testes verdes antes do commit.

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

- [x] RED/GREEN: todos os resultados de ordenação cobertos no mock e no PostgreSQL.
- [x] RED/GREEN: repetição idempotente mantém o `received_at` original.
- [x] RED/GREEN: concorrência não deixa snapshot antigo vencer.
- [x] GREEN: função SQL/RPC transacional implementada.
- [x] GREEN: adapter RPC do repository implementado.
- [x] REFACTOR: validação de ordem e UPDATE acontecem sob o mesmo lock/transaction no banco.
- [x] REVIEW: concorrência serverless revisada em PostgreSQL real.

### Registro da Task 5 — 2026-09-25

- `MemoryDeviceRepository.accept_snapshot_atomic()` implementa os cinco resultados do contrato sob lock local e relógio injetável.
- Migration `002_accept_snapshot_rpc.sql` usa `SELECT ... FOR UPDATE` para serializar decisões por dispositivo.
- Comparação idempotente usa igualdade estrutural de `jsonb`, portanto não depende de ordem de chaves ou whitespace.
- Mesmo `boot_id + sequence + payload` retorna `idempotent` sem atualizar `received_at`.
- Reutilização da mesma sequence com conteúdo diferente retorna `sequence_reuse_mismatch`.
- Sequence menor no mesmo boot retorna `out_of_order`; boot diferente pode reiniciar em 1.
- Duas requisições concorrentes foram exercitadas contra PostgreSQL 16 real; o estado final permaneceu na maior sequence.
- `SupabaseDeviceRepository` chama `/rest/v1/rpc/accept_device_snapshot` e converte a resposta em `AcceptSnapshotResult`.
- Falha HTTP/RPC é convertida para `PersistenceUnavailableError` sem vazar chave de servidor.
- **Ruling:** para novos projetos Supabase, a API usa `SUPABASE_SECRET_KEY` como credencial principal; `SUPABASE_SERVICE_ROLE_KEY` fica apenas como fallback legado. Custo se a estratégia mudar: ajuste restrito à configuração e aos headers do repository.
- Secret Key atual é enviada no header `apikey`; chave legada mantém `Authorization: Bearer` para compatibilidade.
- `httpx` passou a dependência de produção; `psycopg` permanece somente em dependências de desenvolvimento/teste.
- `.env.example` documenta Secret Key atual e fallback legado.
- Verificação final da etapa: suíte completa com 69 testes verdes, incluindo 6 integrações PostgreSQL.

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

- [x] RED/GREEN: credencial inválida retorna 401 genérico.
- [x] RED/GREEN: payload válido chega a `accept_snapshot_atomic`.
- [x] RED/GREEN: resposta não devolve snapshot completo.
- [x] RED/GREEN: repetição idempotente retorna 200 preservando `received_at`.
- [x] RED/GREEN: conflitos retornam 409 com código correto.
- [x] RED/GREEN: erro de repository nunca vira sucesso e retorna 503.
- [x] RED/GREEN: versão desconhecida retorna 422 / `unsupported_snapshot_schema`.
- [x] RED/GREEN: schema ausente não é confundido com versão não suportada.
- [x] RED/GREEN: autenticação inválida é resolvida antes da validação do body.
- [x] GREEN: service e router mínimos implementados.
- [x] GREEN: testes do POST executados.
- [x] REFACTOR: regra de negócio permanece no service; parsing HTTP permanece no router/dependency.
- [x] REVIEW: endpoint comparado com o `SnapshotHttpClient` da 017.

### Registro da Task 6 — 2026-09-25

- Criado `SnapshotService` para autenticação do dispositivo e mapeamento dos resultados de persistência.
- Criado `AuthenticatedDevice` como contexto explícito entre a dependency autenticada e a gravação do snapshot.
- Criado `POST /api/v1/devices/{device_id}/snapshot` com `Authorization: Device <secret>`.
- O router interpreta o header; o service valida o segredo contra o hash persistido.
- **Ruling:** autenticação passou a ser dependency da rota para ocorrer antes da validação Pydantic do body, conforme a ordem definida na SPEC 018. Custo se essa ordem mudar: simplificação pequena do router.
- Payload inválido com credencial inválida retorna 401, evitando revelar detalhes do contrato antes da autenticação.
- Sucesso e retry idempotente retornam somente `ok + received_at`; o snapshot completo nunca volta no POST.
- `out_of_order_snapshot` e `sequence_reuse_mismatch` retornam 409.
- Falha de persistência é convertida para 503 / `persistence_unavailable`.
- Versão desconhecida recebe 422 / `unsupported_snapshot_schema`; campo `schema_version` ausente continua sendo erro de validação genérico até a padronização completa da Task 9.
- **Ruling:** o handler mínimo de `RequestValidationError` foi iniciado nesta etapa somente para distinguir versão desconhecida; a normalização geral de 422 continua pertencendo à Task 9.
- `httpx2` foi adicionado apenas às dependências de desenvolvimento para manter o `TestClient` atual do Starlette sem warning; `httpx` continua sendo o cliente de produção do Supabase.
- Revisão da etapa: router não acessa repository diretamente e service não conhece FastAPI.
- Verificação final da etapa: suíte completa com 85 testes verdes, incluindo integrações PostgreSQL e warnings tratados como erro.

## Task 7 — VIEW_SECRET e rotação

**Entrega:** dispositivo autenticado registra/rotaciona o segredo de leitura.

**Rota:** `PUT /api/v1/devices/{device_id}/view-access`

**Arquivos previstos:**
- `app/services/access_service.py`
- `app/api/v1/access.py`
- `tests/unit/test_access_service.py`
- `tests/integration/test_put_view_access.py`

- [x] RED/GREEN: exige Authorization Device válido.
- [x] RED/GREEN: token curto ou fora de base64url é rejeitado.
- [x] RED/GREEN: repository recebe somente SHA-256, nunca plaintext.
- [x] RED/GREEN: resposta é 204 e não contém segredo.
- [x] RED/GREEN: rotação invalida imediatamente o token anterior.
- [x] RED/GREEN: erros 422 não ecoam o VIEW_SECRET recebido.
- [x] GREEN: service + endpoint implementados.
- [x] GREEN: testes da Task 7 executados.
- [x] REFACTOR: autenticação de dispositivo extraída para serviço compartilhado.
- [x] REVIEW: geração de QR/token permanece fora da API e erros não expõem segredos.

### Registro da Task 7 — 2026-09-25

- Criado `DeviceAuthService` compartilhado pelos fluxos de snapshot e rotação, evitando duplicação da verificação de `DEVICE_SECRET`.
- Criado `AccessService` com validação de `VIEW_SECRET` em formato base64url e mínimo de 43 caracteres.
- Criado `PUT /api/v1/devices/{device_id}/view-access` com autenticação Device resolvida antes da validação do body.
- O endpoint retorna `204 No Content` e nunca devolve o `VIEW_SECRET`.
- O service calcula SHA-256 e entrega somente o hash ao repository.
- Segunda rotação substitui o hash anterior imediatamente; o token antigo deixa de validar.
- **Ruling:** validação de comprimento/formato do `VIEW_SECRET` fica no service, não no Pydantic, para impedir que erros de validação reflitam o segredo em detalhes internos.
- O fallback global de `RequestValidationError` foi sanitizado para `invalid_request_payload` sem incluir valores de entrada; a Task 9 continuará responsável por consolidar esse handler.
- `SupabaseDeviceRepository.get_device_auth()` lê apenas identificador e hashes necessários para autenticação.
- `SupabaseDeviceRepository.rotate_view_secret_hash()` chama RPC recebendo somente hash.
- Migration `003_rotate_view_secret_rpc.sql` atualiza `view_secret_hash`, `view_secret_updated_at` e `updated_at` usando relógio do PostgreSQL.
- A RPC retorna `false` quando o dispositivo não existe e não cria registro automaticamente.
- Revisão da etapa: nenhuma geração de QR, nenhum plaintext persistido e nenhuma resposta/error payload contém segredo.
- Verificação final da etapa: suíte completa com 106 testes verdes, incluindo integrações PostgreSQL e warnings tratados como erro.

## Task 8 — GET read-only para o mobile

**Entrega:** frontend futuro lê o último snapshot somente pela API.

**Rota:** `GET /api/v1/devices/{device_id}/snapshot`

**Meta de saída:**
- `received_at`
- `age_seconds`
- `collector_online`
- `stale_after_seconds`
- [x] RED/GREEN: Bearer inválido, ausente ou VIEW_SECRET não provisionado retorna 401 genérico.
- [x] RED/GREEN: dispositivo autenticado sem snapshot retorna 404 / `snapshot_not_available`.
- [x] RED/GREEN: GET válido devolve snapshot completo + meta.
- [x] RED/GREEN: 119 s → online.
- [x] RED/GREEN: 120 s → offline.
- [x] RED/GREEN: snapshot offline continua sendo devolvido.
- [x] RED/GREEN: cálculo usa apenas `received_at`.
- [x] RED/GREEN: falha de persistência na leitura retorna 503 sem inventar dados.
- [x] GREEN: leitura e cálculo implementados.
- [x] GREEN: testes da Task 8 executados.
- [x] REFACTOR: relógio e stale threshold são injetáveis/testáveis.
- [x] REVIEW: `generated_at` não influencia online/offline.

### Registro da Task 8 — 2026-09-25

- Criado `SnapshotReadService` para autenticação por `VIEW_SECRET`, leitura e cálculo de disponibilidade.
- Criado GET `/api/v1/devices/{device_id}/snapshot` com `Authorization: Bearer <VIEW_SECRET>`.
- Dispositivo inexistente, VIEW_SECRET ausente no banco e token incorreto são indistinguíveis externamente: todos retornam 401 genérico.
- Dispositivo autenticado sem snapshot retorna 404 / `snapshot_not_available`.
- Resposta de sucesso contém `snapshot` validado como `MobileSnapshotV1` e envelope `meta`.
- `age_seconds` é calculado exclusivamente por `now_utc - received_at`.
- Limite validado: 119 segundos permanece online; 120 segundos já é offline.
- Snapshot offline continua sendo devolvido integralmente.
- Alterar `generated_at` para valor histórico não altera o estado online/offline.
- Relógio e `stale_after_seconds` são injetáveis no service/router/app para testes determinísticos.
- `SupabaseDeviceRepository.get_snapshot()` lê snapshot + metadados úteis da linha única do dispositivo.
- Linha sem snapshot e dispositivo inexistente retornam `None` no repository; a autenticação prévia do service define a semântica pública.
- Falha de leitura no repository é convertida para 503 / `persistence_unavailable`.
- Nenhum cache de snapshot em memória foi introduzido para o caminho Supabase/serverless.
- Verificação final da etapa: suíte completa com 123 testes verdes, incluindo integrações PostgreSQL e warnings tratados como erro.

## Task 9 — Router v1, health, CORS e observabilidade

**Entrega:** shell HTTP consistente.

**Arquivos previstos:**
- `app/api/v1/router.py`
- `app/api/v1/health.py`
- `app/core/logging.py`
- ajustes em `app/main.py`
- testes de shell/logging

- [x] RED/GREEN: `/api/v1/health` responde sem consultar repository/snapshot.
- [x] RED/GREEN: rotas v1 são expostas uma única vez no contrato OpenAPI.
- [x] RED/GREEN: CORS fica fechado por padrão e não usa wildcard.
- [x] RED/GREEN: `ALLOWED_ORIGINS` explícito é respeitado.
- [x] RED/GREEN: logs contêm método, rota, status e duração.
- [x] RED/GREEN: logs nunca contêm Authorization ou request body.
- [x] RED/GREEN: erros de validação Pydantic usam envelope sanitizado `detail.code + detail.message`.
- [x] RED/GREEN: `schema_version` desconhecido mantém 422 / `unsupported_snapshot_schema`.
- [x] GREEN: router v1, health, CORS, middleware, logging e handler central implementados.
- [x] REVIEW: estrutura permanece compatível com same-origin do frontend.

### Registro da Task 9 — 2026-09-25

- Criado `create_v1_router()` como agregador único com prefixo `/api/v1`.
- Routers de snapshot e acesso passaram a usar prefixos relativos `/devices`, preservando as URLs públicas existentes.
- Criado `GET /api/v1/health` independente de repository, Supabase e snapshot.
- **Ruling:** a verificação de rotas únicas usa o contrato OpenAPI, não a lista interna `app.routes`, pois a versão atual do FastAPI representa routers incluídos por `_IncludedRouter`. Custo se o framework mudar: apenas teste de shell.
- `create_app()` aceita `Settings` injetável e usa `STALE_AFTER_SECONDS` da configuração quando não há override de teste.
- `ALLOWED_ORIGINS` é normalizado como lista; CORS middleware só é instalado quando a lista é não vazia.
- CORS permite apenas origens explícitas, métodos do MVP e headers `Authorization`/`Content-Type`; wildcard não é usado.
- Criado middleware ASGI de logging que mede duração e registra somente método, path, status e `duration_ms`.
- Middleware não lê nem registra headers, query payload, body ou resposta.
- Handler central de `RequestValidationError` devolve `invalid_request_payload` sem `input` e preserva o caso específico `unsupported_snapshot_schema`.
- `LOG_LEVEL` passa a configurar o logger HTTP da aplicação.
- Revisão da etapa: health isolado, CORS fechado por padrão, logs sanitizados e URLs públicas inalteradas.
- Verificação final da etapa: suíte completa com 131 testes verdes, incluindo integrações PostgreSQL e warnings tratados como erro.

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
