# SPEC 027 C1 — CloudBinding, WebPilotAuthRealm e autoridade administrativa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans to execute this plan task-by-task. Use superpowers:test-driven-development for every production change and stop at every checkpoint for independent review.

**Goal:** implementar a fundação administrativa de C1 para vincular um Desktop lógico existente a um CloudBinding e a um WebPilotAuthRealm autorizado, com credencial própria revogável/rotacionável e fail-closed, sem ativar WebPilot real, SessionLease, publicação Cloud ou failover.

**Architecture:** a API permanece a autoridade persistente de identidade e autorização. O Desktop autentica os endpoints administrativos com seu `Device <device_secret>` já existente. O vínculo Cloud usa uma credencial de alta entropia própria; o plaintext trafega apenas no request HTTPS de criação/rotação, é imediatamente reduzido a hash e nunca é persistido, retornado ou logado. Realm e autorização device↔realm são administrados fora do PWA. C1 cria contratos e autoridade; o shell Northflank continua somente health/readiness. C2 cuidará de SessionLease/Auth Broker e C3 de source/failover.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, psycopg/PostgreSQL, Supabase REST/RPC, pytest, Docker local.

**Spec:** `specs/027-alertam-cloud-continuity.md`, `specs/025-webpilot-http-observed-weather-shadow-migration.md`, `/home/ciro/dev/prog/alertamaritimo/specs/030-device-admin-operational-gate.md`.

## Global Constraints

- A execução começa somente após **R0 independente aprovado** e reconciliação Git autorizada.
- A branch API/PWA/Cloud será uma única `feat/spec027-cloud`, criada da `feat/api-bootstrap` reconciliada com o spike `dc23003`.
- Não criar branches C1-A/B/C/D, C2, C3 ou C4.
- No Desktop, só criar `feat/spec027-cloud` se surgir alteração Desktop realmente necessária; a base deve ser `develop` já contendo Plan 5.
- Shadow real em execução fica intocado; Selenium segue fonte oficial.
- Nenhum WebPilot real no Cloud, cookie, SessionLease, usuário/senha WebPilot ou HTML autenticado em C1.
- Nenhuma publicação `source=cloud`, snapshot Cloud, failover/failback, lease/fencing, evento/push Cloud ou cutover.
- Nenhuma migration de produção. Migration C1 pode ser criada e testada somente em banco local/efêmero.
- Nenhum push, merge em branch compartilhada, deploy Vercel/Northflank ou operação Supabase de produção sem autorização humana posterior.
- Nenhum segredo em logs, exceptions, fixtures, URLs, responses ou handoffs.
- Cada checkpoint termina com commit local, testes, `git diff --check`, atualização do controle central e **STOP** para Rn independente.

## Base reconciliada exigida antes de criar a feature branch

R0 deve revisar e autorizar esta sequência; P0 não a executa:

1. **Desktop:** integrar `feat/spec025-plan5-shadow-evidence-gate@9e5b5e1` em `develop@abe386f` por fast-forward, usando checkout/worktree separado para não trocar nem interromper o processo Shadow em execução.
2. **API/PWA:** integrar `feat/pre-spec027-cloud-infra-spike@dc23003` em `feat/api-bootstrap@8177332`. `git merge-tree --write-tree` foi limpo; será merge real porque as branches divergiram em `af5e81f`.
3. **Documentação antiga:** não mergear `docs/pre-plan4-gate-alignment@ecb7b37`; seu conteúdo útil já está incorporado e superseded na base atual. Remover branch/worktree somente após R0 e nova verificação de conteúdo.
4. Rodar regressões da base reconciliada e registrar o novo SHA.
5. Só então criar `feat/spec027-cloud` a partir do novo SHA de `feat/api-bootstrap`.

## C1 — contratos aprovados por este plano

### Identidades persistentes

`WebPilotAuthRealmRecord`: `realm_id`, `active`, timestamps administrativos.

`RealmDeviceAuthorizationRecord`: `realm_id`, `device_id`, `authorized_at`, `revoked_at | None`. Autorização ativa exige realm ativo e `revoked_at is None`.

`CloudBindingRecord`: `cloud_binding_id: UUID`, `device_id`, `realm_id`, `credential_hash` com `repr=False`, `credential_version >= 1`, `status: active|revoked`, `created_at`, `updated_at`, `revoked_at`.

Invariantes:
- no máximo um CloudBinding ativo por `device_id`;
- binding pertence a device e realm existentes;
- criar/rotacionar exige device `enabled=true`, realm ativo e autorização device↔realm ativa;
- `enabled=false` não apaga binding, mas o torna não utilizável;
- revogar autorização de realm preserva histórico do binding, mas o torna não utilizável;
- revogação explícita do binding é permanente; rebind posterior recebe novo `cloud_binding_id`;
- credencial Cloud é distinta de `DEVICE_SECRET` e de qualquer credencial/sessão WebPilot.

### Contrato HTTP administrativo Desktop-only

Todos sob `/api/v1/devices/{device_id}`:

- `GET /cloud-binding`: usa autenticação de status, portanto metadata pode ser lida por credencial válida mesmo com `enabled=false`; nunca retorna credential/hash; retorna metadata + `device_enabled`, `realm_authorized`, `usable`.
- `PUT /cloud-binding`: body `realm_id` + `credential: SecretStr`; device precisa estar enabled; mesmo realm + mesma credencial ativa é idempotente; binding ativo diferente retorna 409 sem troca silenciosa.
- `POST /cloud-binding/rotate`: body com nova `credential: SecretStr`; mesma credencial atual é idempotente sem bump; credencial diferente troca hash atomicamente e incrementa `credential_version` uma vez.
- `DELETE /cloud-binding`: revoga binding ativo; retry é idempotente; não revoga celulares, view secret ou device.

Não criar endpoint PWA/Bearer nem endpoint de SessionLease em C1.

### Credencial

- Cliente gera segredo com CSPRNG; referência futura: `secrets.token_urlsafe(32)`.
- API recebe plaintext apenas sobre HTTPS, modelado como Pydantic `SecretStr`.
- Persistência usa somente `hash_secret()`; token é de alta entropia, não senha humana.
- Response nunca devolve plaintext nem hash.
- Middleware HTTP atual não loga body/headers.
- Verificação usa `verify_secret()`/`hmac.compare_digest`.

### Persistência proposta — migration 019

Criar somente em C1-B: `api/supabase/migrations/019_cloud_binding_realm.sql`.

Tabelas:
- `public.webpilot_auth_realms`;
- `public.webpilot_auth_realm_devices`;
- `public.cloud_bindings`.

Proteções:
- FKs para devices/realms;
- partial unique index garantindo um binding ativo por device;
- checks para status e versão positiva;
- RLS habilitado; revoke de anon/authenticated; nenhuma policy pública;
- funções/RPCs mutantes usadas somente pelo backend/server role; revogar `EXECUTE` também de `PUBLIC`, além de `anon`/`authenticated`, e conceder somente ao papel backend apropriado;
- nenhuma seed de produção embutida.

As mutações ensure/create, rotate e revoke devem ser atômicas e idempotentes no banco e espelhadas pelo MemoryRepository. A mesma operação transacional/RPC deve revalidar `devices.enabled`, realm ativo e membership ativa imediatamente antes da mutação; o check do endpoint é defesa inicial, não autoridade suficiente contra corrida administrativa.

## Review Focus

- cross-device: device B jamais lê/muta A;
- cross-realm: Desktop não escolhe realm não autorizado;
- `enabled=false`/persistence unavailable nunca viram permissão;
- nenhum plaintext/hash da Cloud credential em response/log/repr/fixture;
- nunca reutilizar `DEVICE_SECRET` como Cloud credential;
- nenhuma condição de corrida permite dois bindings ativos ou double-rotate em retry;
- PWA/Bearer não alcança administração Cloud;
- migration sem policy/grant público;
- `cloud/` continua sem WebPilot/SessionLease/source/failover.

---

## C1-A — Domínio, interfaces e invariantes

**Checkpoint:** C1-A → parar para R1.

**Files:**
- Create: `api/app/repositories/cloud_bindings.py`
- Modify: `api/app/repositories/events.py` somente para compor o protocolo agregado quando o contrato estiver estável
- Modify: `api/app/repositories/memory.py`
- Create: `api/tests/unit/test_cloud_binding_contract.py`
- Create: `api/tests/unit/test_cloud_binding_memory_repository.py`

### Step A1 — RED: contrato não existe

Escrever testes primeiro para records/enums/protocol, `credential_hash` fora de `repr()`, autorização ativa/revogada e ausência de SessionLease/source no contrato C1.

Run:
`cd api && uv run pytest tests/unit/test_cloud_binding_contract.py -q -W error`

Expected RED: módulo/interface ausente.

### Step A2 — GREEN: modelos e protocol mínimos

Implementar os records/enums/protocol em `cloud_bindings.py`, sem API, SQL ou runtime Cloud.

Run novamente; expected GREEN.

### Step A3 — RED: invariantes do MemoryRepository

Testes primeiro:
- autorizar device em realm;
- um único active binding por device;
- mesmo ensure realm+hash idempotente;
- ensure diferente conflita;
- rotate mesma hash não incrementa versão;
- rotate nova hash incrementa uma vez;
- revoke repetido idempotente;
- histórico preservado após revoke;
- operações scoped não cruzam device.

### Step A4 — GREEN/refactor

Implementar MemoryRepository usando seu lock. Não adicionar endpoints.

### Step A5 — Gate C1-A

Run:
- testes C1-A;
- `cd api && uv run pytest tests/unit/test_memory_repository.py tests/unit/test_devices_repository_contract.py -q -W error`;
- `git diff --check`.

Commit local sugerido: `feat(cloud): define binding and realm domain contracts`.

Atualizar controle central e **STOP R1**.

---

## C1-B — Persistência, credencial e endpoints administrativos

**Checkpoint:** somente após R1 aprovado; parar para R2.

**Files:**
- Create: `api/supabase/migrations/019_cloud_binding_realm.sql`
- Modify: `api/app/repositories/cloud_bindings.py`
- Modify: `api/app/repositories/postgres.py`
- Modify: `api/app/repositories/supabase.py`
- Modify: `api/app/repositories/events.py`
- Create: `api/app/models/cloud_binding.py`
- Create: `api/app/services/cloud_binding_service.py`
- Create: `api/app/api/v1/cloud_bindings.py`
- Modify: `api/app/api/v1/router.py`
- Modify: `api/app/core/errors.py`
- Create: `api/scripts/admin_cloud_realm.py`
- Modify: `api/scripts/admin_device.py` para incluir referências Cloud no guard de compensação
- Create/Modify: testes abaixo.

### Step B1 — RED: migration/DDL

Create `api/tests/unit/test_cloud_binding_sql.py` e testar:
- três tabelas e FKs;
- partial unique active per device;
- status/version checks;
- RLS/revokes;
- nenhuma public policy;
- RPC/SQL para ensure/rotate/revoke atômicos;
- funções não concedidas a anon/authenticated.

Run expected RED porque migration 019 não existe.

### Step B2 — GREEN: migration 019 somente local

Implementar SQL. **Não executar `make prod-migrate` nem conectar ao Supabase produção.**

### Step B3 — RED: Postgres/Supabase repositories

Create:
- `api/tests/integration/test_cloud_binding_postgres.py`
- `api/tests/unit/test_supabase_cloud_binding_repository.py`

Cobrir mapping seguro, RPC names/payloads, idempotência, conflitos tipados, persistence error sanitizado, autorização de realm e projection de autorização do binding.

Postgres pode skip sem `TEST_POSTGRES_DSN`; Supabase MockTransport precisa RED/GREEN sempre.

### Step B4 — GREEN: repositories

Postgres usa as funções transacionais da migration; Supabase usa RPC com server key. Repository recebe/persiste apenas hash, nunca plaintext.

### Step B5 — RED: service/model credential lifecycle

Create `api/tests/unit/test_cloud_binding_service.py` e cobrir:
- `SecretStr` redaction;
- create faz hash antes do repository;
- same secret/realm idempotente;
- conflito não altera binding;
- rotate same secret sem bump;
- rotate new secret com um bump;
- revoke idempotente;
- response sem `credential`/`credential_hash`.

### Step B6 — GREEN: service/models/errors

Implementar mínimo. Erros Desktop-facing podem distinguir realm não autorizado (403), binding conflict (409) e binding not found (404), sem expor existência/segredo de outro device.

### Step B7 — RED: endpoints Desktop-only

Create `api/tests/integration/test_cloud_binding_api.py` e cobrir:
- PUT/GET/rotate/delete;
- Device auth obrigatória;
- Bearer/view token rejeitado;
- disabled: GET metadata permitido com secret válido; mutações rejeitadas;
- wrong secret 401;
- responses sem secret/hash;
- persistence failure 503 sem mutação.

### Step B8 — GREEN: router

Criar router e incluir no v1 router. Não adicionar rota/front-end PWA.

### Step B9 — RED/GREEN: autoridade administrativa de realm

Create `api/tests/unit/test_admin_cloud_realm.py`.

`api/scripts/admin_cloud_realm.py` terá somente operações administrativas:
- ensure/create realm;
- authorize device;
- revoke device authorization;
- usa credencial administrativa já existente do backend;
- imprime somente IDs/status não secretos;
- nunca cria CloudBinding/Cloud credential.

Modificar `_DEPENDENCY_PROBES` em `admin_device.py` para impedir compensação/deleção de device com realm authorization ou binding existente.

Nenhum comando administrativo é executado contra produção neste checkpoint.

### Step B10 — Gate C1-B

Run:
- testes C1-B;
- `cd api && uv run pytest tests/unit tests/integration/test_cloud_binding_api.py -q -W error`;
- se Docker local disponível, `make test-all` para migration em Postgres efêmero;
- `git diff --check`.

**Nunca** `prod-migrate`, deploy ou push.

Commit local sugerido: `feat(cloud): add binding persistence and desktop admin API`.

Atualizar controle central e **STOP R2**.

---

## C1-C — Fail-closed, isolamento cross-device/cross-realm e autenticação do binding

**Checkpoint:** somente após R2; parar para R3.

**Files:**
- Modify: `api/app/services/cloud_binding_service.py`
- Modify: `api/app/repositories/cloud_bindings.py` somente se o projection de autorização precisar de ajuste
- Modify repositories somente quando um RED comprovar necessidade de atomicidade/correção
- Create: `api/tests/unit/test_cloud_binding_authorization.py`
- Create: `api/tests/integration/test_cloud_binding_adversarial.py`
- Modify: `api/tests/integration/test_cloud_binding_api.py`

### Step C1 — RED: autoridade da credencial Cloud

Adicionar teste para serviço interno:
`authenticate_cloud_binding(cloud_binding_id, credential) -> AuthorizedCloudBinding`.

Casos RED:
- binding active + hash correto + device enabled + realm active + membership ativa => autorizado;
- hash errado => negar;
- binding revoked => negar;
- device disabled => negar;
- realm inactive => negar;
- membership revoked => negar;
- persistence unavailable => fail-closed/503-equivalente;
- retorno autorizado contém somente IDs/realm, nunca hash.

### Step C2 — GREEN: verificador central

Implementar usando projection coerente do repository. C1 não cria grace próprio: sem autorização confirmada, bloqueia. Qualquer grace do runtime Cloud exige plano posterior.

Nenhuma rota usa isso para WebPilot ou snapshot em C1.

### Step C3 — RED: cross-device

Testes adversariais:
- secret A contra path B não lê nem altera B;
- A não usa binding_id de B;
- delete/rotate são scoped ao device;
- conflito não revela existência de binding de outro device.

### Step C4 — RED: cross-realm e revogações

- device só binda realm com membership ativa;
- revogar membership invalida credential auth imediatamente;
- reautorizar membership pode tornar binding ativo utilizável se o binding não foi revogado;
- `enabled=false` torna binding não utilizável imediatamente;
- re-enable restaura apenas se realm authorization e binding continuam ativos;
- binding explicitamente revogado continua revogado após re-enable.

### Step C5 — RED: logs/serialization

Capturar logs/reprs/exceptions e provar ausência de plaintext credential, credential_hash, DEVICE_SECRET e Supabase server key.

### Step C6 — GREEN/refactor

Implementar apenas o necessário. Não tocar `cloud/`, WebPilot, SessionLease, snapshot ou source.

### Step C7 — Gate C1-C

Run:
- autorização/adversarial;
- regressões de disabled device existentes;
- repository tests;
- full API suite;
- `git diff --check`.

Commit local sugerido: `test(cloud): enforce binding authority and isolation`.

Atualizar controle central e **STOP R3**.

---

## C1-D — Integração local, contratos Desktop e encerramento C1

**Checkpoint:** somente após R3; parar para R4.

**Default:** não alterar o Desktop runtime. O contrato HTTP é validado pela API/TestClient e contract tests. Só criar branch Desktop `feat/spec027-cloud` se R3/R4 exigir cliente concreto; nunca alterar o checkout onde Shadow está rodando.

**Files:**
- Create: `api/tests/contract/test_cloud_binding_desktop_contract.py`
- Modify: `cloud/tests/test_service.py` somente para reforçar isolamento, se necessário
- Modify: documento central de checkpoints
- Opcional apenas por decisão de revisão: Desktop `src/alertam/infrastructure/cloud_binding_http.py` + testes, em worktree separado e sem bootstrap/UI wiring.

### Step D1 — Contract RED/GREEN

Provar:
- request/response estável para Desktop;
- credential write-only;
- metadata inclui device/realm/binding/version/status/usable sem secrets;
- HTTP error codes previsíveis;
- nenhum contrato Mobile/PWA alterado.

### Step D2 — Cloud shell isolation

Run `make cloud-test` e, se Docker disponível, `make cloud-smoke`.

Confirmar que shell continua apenas health/readiness e 404 para rotas operacionais; nenhuma importação da API C1 dispara WebPilot.

### Step D3 — Regressões

API/PWA:
- `make test`;
- `cd frontend && npm test -- --run`;
- `git diff --check <C1_BASE>..HEAD`.

Banco local:
- `make test-all` em Postgres efêmero, se disponível;
- `make migrate-list` mostra 019;
- registrar explicitamente que migration de produção **NÃO foi aplicada**.

Desktop:
- nenhuma mudança por default;
- Shadow permanece rodando/intocado;
- Selenium permanece oficial.

### Step D4 — Security audit

Revisar ocorrências no diff de `cookie|sessionlease|source=cloud|device_secret|credential_hash|authorization`.

Confirmar:
- nenhuma fixture/handoff contém valor real;
- nenhuma rota PWA;
- nenhuma policy pública;
- nenhum secret em log/response;
- nenhum WebPilot real;
- nenhum source/failover.

### Step D5 — Encerramento C1

Atualizar controle central com base reconciliada, commits C1-A..D, RED/GREEN, migration 019 criada mas não aplicada, skips, segurança e pendências para C2-P.

Commit documental sugerido: `docs: close spec027 c1 for independent review`.

**STOP obrigatório para R4.**

R4 não autoriza automaticamente merge da feature, push, migration produção, deploy, C2 ou WebPilot/SessionLease real.

---

## Rollback / recuperação

Enquanto C1 não tiver migration em produção:
- rollback é revert dos commits locais da feature;
- Postgres efêmero pode ser destruído/recriado;
- nenhum dado de produção precisa ser revertido.

Não criar down-migration destrutiva neste plano. Se migration 019 for autorizada futuramente para produção, deployment/rollback terá gate e plano operacional próprios.

## Saída esperada após R4

C1 entrega somente:
- identidade persistente de realm;
- autorização administrativa device↔realm;
- CloudBinding persistente;
- credencial própria hash-only, rotacionável/revogável;
- endpoints Desktop-only;
- verificador central fail-closed;
- testes de isolamento e segurança.

C1 **não entrega** SessionLease, cookies WebPilot, Auth Broker, collector Cloud, snapshot Cloud, source arbitration, failover/failback, eventos/push ou cutover.

O próximo passo após C1 aprovado é **C2-P — plano do Auth Broker/SessionLease**, nunca C2 automático.
