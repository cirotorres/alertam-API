# SPEC 027 — C2-P: Auth Broker / SessionLease federada + collector headless em standby

**Status:** R5-F1..F4 CORRIGIDOS DOCUMENTALMENTE — PRONTO PARA R5.1 INDEPENDENTE; C2 não iniciado.
**Data:** 2026-10-08
**Base C1 tecnicamente encerrada:** `feat/spec027-cloud@61342b2ac47ffa48bfe90787b8aa2afb4bb4cda8`
**Repositório coordenador:** `/home/ciro/dev/prog/alertamaritimoAPI`
**Desktop canônico:** `/home/ciro/dev/prog/alertamaritimo`
**Autoridade:** `specs/027-alertam-cloud-continuity.md`, roadmap Cloud e handoff central da SPEC 027.

## 1. Objetivo exato do C2

C2 entrega somente a federação segura da sessão WebPilot por realm e um collector Cloud **headless em standby**, capaz de consumir uma SessionLease aceita e executar o mesmo núcleo HTTP/parser validado pela SPEC 025, sem assumir autoridade operacional.

C2 deve provar:

1. Desktop autorizado publica material de sessão temporário sem enviar usuário/senha WebPilot;
2. o broker identifica inequivocamente o publisher e rejeita replay/regressão;
3. generations locais de publishers diferentes nunca são comparadas entre si;
4. cada sessão nova aceita recebe `realm_epoch` monotônico server-side;
5. expiração, revogação, rotação e invalidação semântica são fail-closed;
6. o Cloud consome somente sessão do realm autorizado pelo CloudBinding;
7. o collector HTTP/parser é reutilizado da implementação Desktop validada, sem fork/copiar fonte;
8. o Cloud executa em standby e produz apenas observabilidade local/sanitizada;
9. nenhuma publicação `source=cloud`, snapshot Cloud, failover/failback, fencing de source ou cutover nasce em C2.

## 2. Fronteira C2 × C3

### C2 pode

- registrar/rotacionar/revogar identidade de publisher;
- receber SessionLease de Desktops autorizados;
- ordenar aceitações por `realm_epoch`;
- cifrar a sessão em repouso;
- selecionar a sessão aceita mais nova ainda utilizável;
- invalidar semanticamente uma lease quando o WebPilot responde como login;
- permitir que um CloudBinding autorizado leia a lease do seu realm;
- executar WebPilot HTTP/parser em **standby**;
- registrar health/estado do broker e resultado de coleta sem payload operacional;
- testar tudo com cookies sintéticos/fake WebPilot e PostgreSQL efêmero.

### C2 não pode

- escrever snapshots em nome do Cloud;
- introduzir `source=cloud`;
- arbitrar Desktop × Cloud;
- detectar Desktop stale para assumir source;
- implementar heartbeat/fencing/hysteresis de source;
- implementar failover ou failback;
- emitir eventos/push do Cloud;
- ativar WebPilot real no Cloud por default;
- migrar 020 em produção;
- substituir Selenium como fonte oficial do Desktop.

Esses itens pertencem a C3/C3-P ou etapas posteriores.

## 3. Decisões arquiteturais obrigatórias

### 3.1 Broker fica na API; Cloud é consumidor

A FastAPI/Postgres continua sendo a autoridade persistente porque já possui:

- `WebPilotAuthRealm`;
- membership realm↔device;
- `CloudBinding`;
- `authenticate_cloud_binding()`;
- persistência PostgreSQL/Supabase e gates fail-closed.

O serviço `cloud/` não mantém a verdade autoritativa de anti-replay/epoch em memória. Ele consulta o broker.

### 3.2 Publisher identity

Um publisher é identificado por:

```
realm_id
device_id          # derivado da autenticação Device; nunca aceito livremente do payload
publisher_id       # UUID persistido pelo Desktop, não secreto
local_generation   # monotônico somente dentro desse publisher_id
```

Regras:

- um `publisher_id` pertence a um único `device_id + realm_id`;
- há no máximo um publisher ativo por `device_id + realm_id`;
- rotacionar publisher cria novo `publisher_id` e revoga o anterior atomicamente;
- `local_generation` só é comparada dentro do mesmo `publisher_id`;
- perda/reinstalação do estado local é recuperada por **rotação explícita de publisher**, nunca por reduzir silenciosamente a generation;
- `publisher_id` não é segredo e pode aparecer em metadata/log sanitizado.

### 3.3 Generation local do Desktop

Não usar diretamente o contador em memória atual de `WebPilotAuthCoordinator` como anti-replay cross-restart.

Criar um pequeno estado persistente do publisher Desktop:

```
publisher_id: UUID
last_assigned_generation: int64
realm_id
device_id
```

Semântica:

- geração atribuída atomicamente antes da primeira tentativa de publicação;
- retry de transporte da mesma SessionLease reutiliza a mesma generation;
- gaps são permitidos;
- regressão nunca é permitida;
- corrupção/indisponibilidade desse estado impede **apenas a publicação federada**; não derruba coleta Selenium/local do Desktop;
- reset só ocorre por rotação explícita de `publisher_id`.

### 3.4 realm_epoch

`realm_epoch`:

- é `bigint` monotônico **por realm**;
- é atribuído exclusivamente pelo broker ao aceitar uma nova generation;
- nunca vem do cliente;
- retry idempotente da mesma generation não incrementa epoch;
- generation de publisher A e B não é comparada; apenas os epochs aceitos ordenam o realm.

Exemplo obrigatório:

```
Desktop A publisher=A gen=37 -> realm_epoch=101
Desktop B publisher=B gen=1  -> realm_epoch=102
Desktop A publisher=A gen=38 -> realm_epoch=103
replay A gen=37              -> rejeitado
```

#### 3.4.1 Idempotência completa de `publisher_id + local_generation`

A chave de idempotência é exatamente `publisher_id + local_generation`.

O broker diferencia retry legítimo de reuse conflitante pelo **payload semanticamente normalizado**, nunca por igualdade de ciphertext, porque AES-GCM usa nonce aleatório.

Normalização canônica server-side antes de encrypt/persistir:

- `realm_id` e `publisher_id` já resolvidos/autorizados pelo servidor;
- `local_generation` inteiro positivo;
- `expires_at` em UTC, na precisão definida pelo contrato, ou `null`;
- cookies limitados à whitelist do wire contract;
- nomes de cookie não vazios;
- nomes duplicados rejeitados para evitar semântica ambígua;
- cookies ordenados por `name`;
- JSON UTF-8 canônico, com chaves ordenadas e separadores estáveis.

A API calcula **server-side** um `payload_fingerprint` usando HMAC-SHA-256 sobre esse payload canônico com uma chave dedicada de idempotência, diferente das chaves de criptografia. O cliente não envia fingerprint confiável e o banco não armazena hash simples não-keyed do material secreto.

Semântica obrigatória:

1. primeira publisher/generation válida:
   - calcula fingerprint;
   - cifra o payload;
   - aceita uma nova lease;
   - incrementa `realm_epoch` uma única vez;
2. mesma publisher/generation + mesmo fingerprint:
   - retorna exatamente a `lease_id + realm_epoch + metadata` já persistida;
   - não sobrescreve ciphertext/metadata;
   - não incrementa epoch;
3. mesma publisher/generation + fingerprint diferente:
   - produz conflito tipado, por exemplo `SessionLeaseGenerationConflict`;
   - não altera a lease existente;
   - não incrementa epoch;
4. generation menor que `last_generation` continua replay/regressão e é rejeitada.

Atomicidade PostgreSQL obrigatória:

- lock da linha do publisher primeiro;
- busca `publisher_id + local_generation` existente sob lock;
- se existir, compara fingerprint e resolve idempotência/conflito **antes** de tocar no contador do realm;
- só se não existir incrementa `realm_epoch` e insere a lease;
- corrida de requests iguais retorna a mesma lease/epoch;
- corrida de requests diferentes para a mesma generation produz um vencedor e um conflito tipado, sem segundo epoch.

A chave HMAC de fingerprint é secret de runtime. Ausente/inválida => publicação fail-closed. Rotação dessa chave não é implícita no C2; se for necessária, exige versão persistida/planejamento próprio para não quebrar retries de generations já aceitas.

### 3.5 SessionLease wire contract

Request Desktop→broker, conceitualmente:

```
realm_id
publisher_id
local_generation
expires_at | null
cookies[]:
  name
  value
  expiry | null
```

Não transportar campos Selenium/browser desnecessários.

Limites obrigatórios:

- quantidade máxima de cookies;
- tamanho máximo por nome/value e payload total;
- nomes vazios rejeitados;
- `expires_at` normalizado UTC;
- cookie values são `SecretStr`/write-only nos modelos;
- nenhum cookie/valor aparece em repr, ValidationError, response ou logs.

Metadata aceita retorna somente:

```
lease_id
realm_id
publisher_id
local_generation
realm_epoch
received_at
expires_at
status
```

### 3.6 Envelope criptográfico fixo — AES-256-GCM

Cookie/session material não fica plaintext no PostgreSQL/Supabase.

C2 fixa explicitamente **AES-256-GCM** como AEAD.

#### Keyring

Configuração de runtime:

- keyring `key_version -> chave AES-256 de 32 bytes`;
- exatamente uma `active_key_version` para novas cifras;
- versões anteriores podem permanecer carregadas **somente para decrypt** durante rotação;
- versão desconhecida, chave ausente, chave com tamanho inválido ou active version ausente => fail-closed;
- remover chave antiga só é permitido quando não existir lease ainda utilizável/retenção necessária naquela versão;
- nenhuma chave real aparece em fixture, log, error, handoff ou arquivo versionado.

Cada lease persiste seu `key_version`. Nova escrita sempre usa a active version; leitura usa a versão persistida.

#### Plaintext canônico

O plaintext cifrado é o payload normalizado definido em 3.4.1, contendo apenas o material de sessão necessário.

#### AAD canônica

A AAD é UTF-8 canônica e **não secreta**, vinculando o ciphertext à identidade e metadata imutável da linha:

```
schema_version = 1
lease_id
realm_id
publisher_id
local_generation
expires_at_normalized | null
key_version
```

- `lease_id` é gerado server-side antes da cifra;
- `realm_epoch` e `received_at` não entram na AAD porque são atribuídos atomicamente na aceitação persistente depois da cifra;
- alterar qualquer campo da AAD deve fazer decrypt falhar.

#### Persistência

DB armazena somente:

- ciphertext;
- nonce aleatório de 96 bits;
- `key_version`;
- metadata/AAD em colunas tipadas;
- `payload_fingerprint` HMAC separado para idempotência.

Reuso de nonce com a mesma chave é proibido.

#### Testes obrigatórios

- roundtrip AES-256-GCM com keyring sintético;
- duas cifras do mesmo plaintext produzem nonce/ciphertext distintos;
- ciphertext não contém cookie;
- swap de ciphertext/nonce entre leases falha;
- swap entre realms/publishers/generations falha;
- alteração de `expires_at`, `lease_id` ou `key_version` falha;
- wrong key => fail-closed;
- unknown key_version => fail-closed;
- malformed nonce/ciphertext/tag => fail-closed;
- AAD divergente => fail-closed;
- versão antiga configurada decrypta lease antiga, mas nunca é usada para encrypt novo;
- nenhum material criptográfico/cookie em repr/log/error.

Re-encryption massiva não é requisito do C2; a rotação suportada é leitura por keyring versionado + novas cifras na active version.

### 3.7 Expiração, revogação e invalidação semântica

Uma lease é inutilizável quando qualquer condição for falsa:

- realm ativo;
- publisher ativo;
- publisher device enabled;
- membership publisher↔realm ativa;
- lease não revogada;
- lease não invalidada semanticamente;
- `expires_at` ausente ou no futuro.

`expires_at` é validade nominal; não prova que a sessão ainda funciona.

Se WebPilot HTTP identificar página de login:

1. Cloud invalida explicitamente `lease_id + realm_epoch` no broker;
2. broker marca aquele epoch semanticamente inválido de forma idempotente;
3. Cloud solicita novamente a melhor lease restante/mais nova;
4. no máximo um retry HTTP após mudança efetiva de lease;
5. a lease invalidada nunca é ressuscitada.

### 3.8 Autenticação dos dois lados

**Publisher Desktop**

- usa esquema `Device` já existente;
- `device_id` vem do path/auth;
- exige `enabled=true`;
- exige realm ativo;
- exige membership ativa;
- não usa CloudBinding credential para publicar sessão.

**Cloud consumer**

- usa `cloud_binding_id` + CloudBinding credential;
- credencial somente em header/body seguro, nunca query string;
- reutiliza `authenticate_cloud_binding()` do C1;
- só pode receber/invalidate lease do realm do binding;
- cross-binding/cross-realm deve falhar sem revelar existência.

### 3.8.1 Compatibilidade obrigatória de providers/contas

Federação multi-provider só é permitida após um gate explícito de compatibilidade do realm.

Modelo mínimo:

```
ProviderScopeProfile:
  scope_id
  schema_version
  capabilities[]
```

O profile WebPilot v1 deve representar as capacidades realmente necessárias ao collector C2, como leitura da grid de manobras e meteorologia quando esse consumidor estiver habilitado.

Regras:

- o realm possui um `required_provider_scope` administrativamente configurado/versionado;
- cada publisher registra uma proposta de `provider_scope`/capability profile sem username, senha ou cookie;
- publisher **não pode autoaprovar** o próprio scope: nasce `scope_unverified`;
- o profile precisa ser um ID/version conhecido pelo broker e compatível com o `required_provider_scope` do realm;
- somente operação backend/admin autenticada pode marcar o publisher `verified`, após evidência de que aquele Desktop/conta exerce localmente as capacidades exigidas; o registro retém apenas profile/status/timestamp, nunca credencial WebPilot;
- se a comprovação necessária não existir, o publisher permanece `scope_unverified`;
- publisher `scope_unverified` ou incompatível pode existir para diagnóstico/admin, mas **nenhuma lease dele é selecionável/consumível**;
- mudança do profile requerido pelo realm torna publishers divergentes inelegíveis imediatamente, fail-closed;
- profile não contém identidade da conta WebPilot nem credenciais.

Persistência mínima:

- `required_provider_scope`/versão no realm ou tabela de profile associada;
- `provider_scope`, `scope_status = unverified|verified|incompatible` e `scope_verified_at` no publisher;
- RPC de aceitação revalida compatibilidade sob lock antes de aceitar/selecionar uma lease.

Testes C2-A:

- publisher compatível pode publicar lease;
- incompatível/unverified não torna lease selecionável;
- alteração do required scope bloqueia novas aceitações incompatíveis;
- erro/indisponibilidade da validação => fail-closed.

Testes C2-C, antes da matriz multi-provider:

- A compatível + B compatível => federação permitida;
- A compatível + B incompatível => B nunca vira provider selecionável e não recebe epoch utilizável;
- nenhum teste pode depender apenas da premissa verbal de permissões equivalentes.

### 3.9 Persistência proposta — migration 020

Criar apenas em C2-A, inicialmente local/efêmera:

`020_webpilot_session_broker.sql`.

Tabelas propostas:

#### `webpilot_session_publishers`

- `publisher_id uuid PK`;
- `realm_id FK`;
- `device_id FK`;
- `last_generation bigint >= 0`;
- `provider_scope` / profile version;
- `scope_verified_at` ou estado equivalente;
- `status active|revoked`;
- `created_at/updated_at/revoked_at`;
- índice único parcial: um publisher ativo por `realm_id, device_id`.

#### `webpilot_session_leases`

- `lease_id uuid PK`;
- `realm_id FK`;
- `publisher_id FK`;
- `local_generation bigint > 0`;
- `realm_epoch bigint > 0`;
- `received_at`;
- `expires_at nullable`;
- `status accepted|revoked|invalidated`;
- `ciphertext`;
- `nonce`;
- `key_version > 0`;
- `payload_schema_version`;
- `payload_fingerprint` HMAC-SHA-256 calculado server-side;
- timestamps de revoke/invalidation;
- unique `publisher_id, local_generation`;
- unique `realm_id, realm_epoch`.

#### `webpilot_realm_epoch_counters`

- `realm_id PK/FK`;
- `last_epoch bigint >= 0`.

RPCs atômicas devem:

- bloquear/revalidar device, realm, membership, publisher e `provider_scope`;
- rejeitar regression;
- comparar `payload_fingerprint` server-side para a mesma generation;
- tornar retry de mesmo payload idempotente;
- produzir conflito tipado para mesma publisher/generation com payload diferente;
- incrementar epoch somente em nova lease aceita e nunca antes de resolver idempotência;
- rotacionar publisher e revogar anterior numa única transação;
- invalidar/revogar com escopo estrito;
- usar `SECURITY DEFINER`, `search_path` fixo, objetos `public.*`;
- revogar EXECUTE de PUBLIC/anon/authenticated e conceder apenas backend necessário;
- RLS ligado, sem policy pública.

### 3.10 Reuso do collector validado — wheel canônico sem stack Desktop

**Decisão C2-P:** não copiar `webpilot_auth.py`, `webpilot_http.py`, `webpilot_grid_html.py`, parser ou modelos para `cloud/`.

Fonte canônica permanece no repositório Desktop `cirotorres/alertam`.

O `pyproject.toml` Desktop atual declara Selenium, webdriver-manager, Pillow e pyttsx3 como dependências gerais. Portanto, **é proibido instalar o wheel normalmente no Cloud e deixar o instalador puxar esse stack por transitividade**.

Durante C2-B:

1. construir um wheel do Desktop a partir do **SHA Desktop revisado** do checkpoint;
2. injetar esse wheel no build/test local do Cloud como artefato, sem versionar wheel no Git;
3. instalar explicitamente com `python -m pip install --no-deps <alertam-wheel>`, ou comando `uv` com semântica comprovadamente equivalente;
4. declarar em `cloud/pyproject.toml` somente dependências realmente necessárias ao import closure headless;
5. Cloud importa diretamente apenas os módulos headless validados;
6. não importar `alertam.bootstrap`, UI, browser, Selenium worker, áudio ou módulos de packaging Desktop no runtime Cloud.

#### Gate de import closure headless

O container/venv do Cloud deve ser construído **sem** instalar `selenium`, `webdriver-manager`, `Pillow` ou `pyttsx3`, salvo dependência tecnicamente comprovada do closure headless.

Os testes devem provar:

- wheel instalado com `--no-deps`/equivalente;
- imports headless funcionam em processo limpo;
- inventário com `importlib.util.find_spec()` ou equivalente confirma ausência do stack Selenium/browser quando não necessário;
- `sys.modules` após os imports não contém Selenium/Tk/browser/UI;
- nenhum driver/browser é inicializado;
- fixture histórica de grid produz resultado equivalente ao Desktop;
- `WebPilotHttpClient` mantém same-origin, login detection e one-retry;
- nenhum arquivo do parser/HTTP/auth foi copiado para `cloud/`.

O wheel pode conter outros módulos do pacote Desktop; o que não pode ocorrer é instalar dependências operacionais desnecessárias ou importar esses módulos no processo Cloud.

Se o closure headless exigir dependência não prevista ou o wheel com `--no-deps` não for executável, **STOP arquitetura** e pedir decisão antes de extrair subpacote ou mudar packaging. Não criar fork silencioso e não instalar o stack Desktop completo como atalho.

Para sandbox local, o wheel pode ser construído da worktree Desktop revisada e fornecido como build artifact/context. Deploy remoto continua bloqueado sem autorização própria.

### 3.11 Standby headless

C2-B adiciona ao `cloud/` somente:

- broker client;
- session source/provider;
- auth coordinator local;
- WebPilotHttpClient + parsers vindos do wheel Desktop;
- loop de coleta standby;
- observabilidade sanitizada.

O standby:

- não publica snapshot;
- não chama endpoint de snapshot;
- não define `source`;
- não emite eventos/push;
- não altera Mobile/PWA;
- mantém apenas resultado local efêmero/metadata, por exemplo:
  - realm_id;
  - realm_epoch;
  - lease age;
  - auth state;
  - last_collection_at;
  - last_collection_result;
  - contagem de navios/parse success, sem linhas/cookies.

Por default, testes/sandbox usam **fake WebPilot**/transport sintético. WebPilot real no Cloud continua proibido.

## 4. Endpoints/contratos previstos

Nomes finais podem ser refinados na implementação, mas o escopo deve permanecer:

### Desktop-only

```
PUT    /api/v1/devices/{device_id}/webpilot-session-publisher
DELETE /api/v1/devices/{device_id}/webpilot-session-publisher
POST   /api/v1/devices/{device_id}/webpilot-session-leases
POST   /api/v1/devices/{device_id}/webpilot-session-leases/revoke
```

Todos exigem `Device` auth + autoridade realm.

### Cloud internal/backend-only

```
GET  /api/v1/cloud-bindings/{cloud_binding_id}/webpilot-session-lease
POST /api/v1/cloud-bindings/{cloud_binding_id}/webpilot-session-lease/invalidate
```

- CloudBinding credential nunca em query string;
- responses com `Cache-Control: no-store`;
- nenhuma rota Mobile/PWA;
- nenhum endpoint entrega histórico completo de cookies.

## 5. Estratégia de Git/worktrees para C2

### API/PWA/Cloud

Continuar na mesma:

```
feat/spec027-cloud
```

Base de planejamento: `61342b2ac47ffa48bfe90787b8aa2afb4bb4cda8`.

Após R5, C2-A começa nessa branch somente quando C2-P for aprovado.

### Desktop

Somente quando C2-B realmente exigir publisher Desktop:

- criar worktree separada;
- branch Desktop `feat/spec027-cloud`;
- base = `develop` corrente no momento da criação, contendo fechamento SPEC 025;
- nunca fazer checkout/reset/stash no checkout onde o Shadow está rodando;
- registrar SHA real antes da primeira mudança.

## 6. Checkpoints de execução — 3 blocos maiores

A política continua: cada checkpoint é entregue **sem commit/stage**, recebe revisão independente e só depois da aprovação é feito um commit exato.

---

# C2-A — Broker, persistência, anti-replay e contratos

**Gate:** R6 independente.

**Escopo principal:** API/Postgres; sem Desktop runtime e sem collector Cloud.

### A1 — RED de domínio

Criar testes para:

- publisher identity;
- publisher rotation;
- generation monotônica por publisher;
- generations de publishers diferentes não comparáveis;
- realm_epoch monotônico;
- duplicate same generation + mesmo payload normalizado idempotente;
- same publisher/generation + payload diferente => conflito tipado, sem overwrite/epoch;
- regression/stale generation rejeitada;
- mesma generation com publisher revogado rejeitada;
- realm/device/membership inválidos fail-closed;
- provider_scope compatível/incompatível/unverified;
- expires_at no passado não selecionável;
- explicit revoke e semantic invalidation;
- persistence unavailable fail-closed.

### A2 — Modelos e services

Criar modelos separados:

- `SessionPublisherRecord`;
- `SessionLeasePublishRequest`;
- `AcceptedSessionLeaseMetadata`;
- `EncryptedSessionLeaseRecord`;
- `DecryptedSessionLease`.

Secret fields sempre `repr=False` / `SecretStr`.

### A3 — RED/GREEN migration 020

Testes estruturais primeiro; depois migration.

Obrigatório PostgreSQL real:

- FKs;
- constraints;
- partial unique;
- unique publisher/generation;
- unique realm/epoch;
- RLS;
- privileges;
- atomic publisher rotation;
- atomic accept lease;
- concurrency de dois publishers;
- concurrency same publisher same generation + payload igual;
- concurrency same publisher same generation + payload diferente;
- comparação server-side do fingerprint sob lock;
- provider_scope revalidado sob lock;
- no epoch increment em retry idempotente nem em conflito de payload.

Nenhum skip SQL permitido no gate R6.

### A4 — crypto envelope

RED/GREEN:

- AES-256-GCM roundtrip com keyring sintético;
- nonce distinto;
- ciphertext não contém cookie;
- AAD canônica vinculada a lease/realm/publisher/generation/expires/key_version;
- ciphertext/nonce swap entre leases/realms falha;
- wrong key/version/AAD => fail-closed;
- malformed ciphertext/tag/nonce => fail-closed;
- versão anterior decrypt-only; active version para encrypt;
- nenhum secret em exception/repr/log.

### A5 — repositories + Supabase MockTransport

Implementar Memory/Postgres/Supabase conforme contrato.

MockTransport cobre:

- payload válido;
- malformed HTTP 200 sanitizado;
- backend failure sanitizada;
- replay conflict tipado;
- ausência de cookie/server key em erro.

### A6 — endpoints

Desktop publisher endpoints:

- somente `Device`;
- enabled=false => 403/fail-closed;
- membership/realm inactive => 403;
- publisher rotate idempotente;
- publish metadata sem cookies;
- 401/403/409/422/503 previsíveis.

Cloud internal endpoints:

- autenticação via CloudBinding;
- cross-binding/cross-realm bloqueados;
- no-store;
- lease secret só no caminho autenticado;
- semantic invalidation idempotente e epoch-scoped.

### A7 — gate R6

Rodar:

- testes C2-A direcionados;
- Supabase MockTransport;
- PostgreSQL real sem skip;
- `make test-all`;
- `make migrate-list` com 020;
- `git diff --check`;
- security grep/redaction.

**Proibições:** nenhuma migration produção, nenhum Cloud collector, nenhum Desktop publisher runtime, nenhum WebPilot real.

**STOP R6.**

---

# C2-B — Publisher Desktop + collector Cloud headless em standby

**Gate:** R7 independente.

**Escopo:** integração cross-repo controlada; sem source/failover.

### B1 — preparar Desktop worktree isolada

Após R6 aprovado/commitado:

- criar Desktop `feat/spec027-cloud` em worktree nova;
- basear no `develop` corrente;
- registrar SHA;
- verificar Shadow original ativo/intocado.

### B2 — publisher state RED→GREEN

Criar no Desktop estado persistente dedicado, por exemplo:

```
SessionPublisherStateStore
publisher_id
last_assigned_generation
```

Testar:

- criação inicial;
- persistência/restart;
- incremento atômico;
- retry reaproveita generation;
- corrupção => publisher remoto indisponível sem afetar Selenium/local;
- rotação gera novo publisher_id;
- nenhum cookie salvo nesse arquivo.

### B3 — HTTP publisher Desktop

Adaptador fino acionado por `_on_webpilot_session` **depois** da publicação local bem-sucedida.

Regras:

- nunca bloqueia a UI/Tk;
- nunca impede `webpilot_auth.publish()` local;
- falha de broker é log sanitizado/estado remoto indisponível;
- usa Device auth existente;
- não envia usuário/senha;
- envia apenas cookie wire whitelist;
- publisher/local_generation corretos;
- timeout/retry limitado e idempotente.

Nenhuma mudança na autoridade Selenium/Shadow.

### B4 — wheel canônico do collector

Buildar wheel do Desktop SHA revisado e instalá-lo no ambiente Cloud com `--no-deps` (ou equivalente comprovado), mantendo o stack Desktop fora do runtime.

Contract tests devem provar:

- Cloud importa o wheel em ambiente onde Selenium/webdriver-manager/Pillow/pyttsx3 não foram instalados;
- nenhum arquivo do parser/HTTP foi copiado para `cloud/`;
- fixture histórica de grid produz resultado equivalente;
- WebPilotHttpClient mantém same-origin/login detection/one-retry;
- import closure não importa/inicializa Selenium/Tk/browser/UI;
- se qualquer dependência Desktop geral for necessária, o checkpoint para para decisão arquitetural.

Se isso falhar por dependência estrutural, **STOP arquitetura**; não duplicar módulos.

### B5 — BrokerSessionProvider no Cloud

Implementar adapter Cloud:

- autentica pelo CloudBinding;
- obtém lease atual do broker;
- publica cookies somente no auth coordinator local;
- associa local lease ao `realm_epoch`;
- ao login semântico, invalida exatamente o lease/epoch consumido;
- busca nova lease;
- no máximo um retry se o epoch mudou;
- nenhuma lease válida => `AUTH_UNAVAILABLE`, sem loop.

### B6 — Standby collector

Executar maneuvers/weather com transport fake/fixture:

- fetch;
- parse;
- resultado somente in-memory/status;
- zero POST de snapshot;
- zero event/push;
- zero `source=cloud`.

### B7 — gate R7

API:

- regressões completas;
- broker contracts.

Desktop:

- testes publisher/state;
- testes existentes auth/http/shadow;
- `make check`;
- `git diff --check`.

Cloud:

- `make cloud-test`;
- build/smoke com wheel;
- testes de import closure;
- fake WebPilot only.

**STOP R7.**

---

# C2-C — Integração multi-provider, sandbox sintético e encerramento C2

**Gate:** R8 independente.

### C1 — gate de compatibilidade + matriz multi-provider

Antes da ordenação multi-provider, provar com PostgreSQL real:

1. A profile compatível + B profile compatível => ambos elegíveis;
2. B profile incompatível/unverified => nenhuma lease B torna-se selecionável e nenhum epoch utilizável é atribuído a ela;
3. mudança do required scope torna publishers incompatíveis fail-closed.

Somente depois executar dois publishers compatíveis:

1. A gen 37 aceita epoch 101;
2. B gen 1 aceita epoch 102;
3. replay A 37 rejeitado;
4. A gen 38 aceita epoch 103;
5. revoke B não afeta A;
6. rotate publisher A revoga identidade antiga;
7. old publisher A não publica mais;
8. device/realm/membership disable bloqueiam imediatamente.

### C2 — expiry/invalidation/recovery

Testar:

- expires_at passado => não selecionado;
- expires_at futuro não impede invalidação semântica;
- login response invalida epoch usado;
- fallback para próxima lease válida do realm;
- sem lease válida => auth unavailable;
- nova publicação restaura standby;
- broker restart preserva epoch/anti-replay;
- Cloud restart recupera current lease sem resetar realm_epoch.

### C3 — sandbox Docker totalmente sintético

Adicionar ambiente local efêmero com:

- PostgreSQL;
- API;
- Cloud;
- fake WebPilot fixture server;
- cookies sintéticos;
- dois Desktop publishers simulados.

Cenário:

- publish A;
- Cloud coleta/parsa;
- publish B mais novo;
- Cloud troca lease;
- replay rejeitado;
- fake WebPilot retorna login;
- lease invalidada;
- Cloud passa para outra lease válida ou AUTH_UNAVAILABLE;
- nenhuma escrita snapshot/source.

Por default **não usar WebPilot real nem Northflank remoto**. Deploy remoto exige autorização separada.

### C4 — observabilidade

Expor somente metadata sanitizada:

- broker realm_id;
- current realm_epoch;
- publisher_id;
- lease age/expiry state;
- auth state;
- last standby cycle;
- reason codes enumerados.

Nunca:

- cookies;
- ciphertext;
- Device secret;
- CloudBinding credential;
- Authorization header;
- raw HTML;
- session payload.

### C5 — fechamento C2

Gates:

- C2 unit/integration;
- PostgreSQL real sem skip;
- Supabase MockTransport;
- Desktop `make check`;
- API `make test-all`;
- frontend regressão se contratos compartilhados forem tocados;
- `make cloud-test`;
- `make cloud-smoke`/sandbox synthetic;
- restart test;
- security audit;
- `git diff --check` nos dois repos.

Registrar explicitamente:

- 020 não aplicada em produção;
- WebPilot real não usado pelo Cloud;
- Cloud não publicou snapshot/source;
- Shadow/Selenium intactos;
- C3 não iniciado.

**STOP R8.** Após aprovação/commit de C2, o próximo passo é **C3-P**, nunca C3 automático.

## 7. Testes obrigatórios por risco

### Anti-replay

- same publisher, generation menor;
- same publisher, same generation + mesmo payload normalizado => mesma lease/epoch;
- same publisher, same generation + payload diferente => conflito tipado;
- concorrência de payloads iguais => mesma lease/epoch;
- concorrência de payloads diferentes => um vencedor + conflito, sem segundo epoch;
- same publisher, same generation após revoke;
- new publisher generation 1;
- old publisher após rotation;
- persistence retry.

### Isolamento

- device A não registra publisher para B;
- publisher A não publica realm B sem membership;
- binding realm A não lê lease realm B;
- invalidate cross-realm bloqueado;
- realm disabled bloqueia publish e consume;
- device disabled bloqueia publish e binding consume.

### Secrets

- cookie write-only;
- no cookie em OpenAPI response;
- no cookie em repr/log/error;
- ciphertext no DB;
- fingerprint HMAC keyed, nunca hash simples do cookie;
- ciphertext/nonce/AAD swap fail-closed;
- key/version/AAD invalid fail-closed;
- headers nunca logados;
- `Cache-Control: no-store` no lease interno.

### Restart

- API restart preserva realm_epoch;
- Cloud restart não causa nova epoch;
- Desktop restart preserva publisher state;
- publisher state perdido exige rotation, não generation rollback.

## 8. Observabilidade mínima C2

Eventos estruturados permitidos:

- `session_publisher_rotated`;
- `session_lease_accepted`;
- `session_lease_replay_rejected`;
- `session_lease_revoked`;
- `session_lease_invalidated`;
- `standby_auth_unavailable`;
- `standby_collection_ok`;
- `standby_collection_failed`.

Campos permitidos:

- realm_id;
- publisher_id;
- realm_epoch;
- local_generation;
- reason code;
- duration/age.

Não logar:

- cookie name/value se desnecessário;
- cookie value sempre proibido;
- ciphertext/nonce;
- secrets;
- headers;
- raw body/HTML.

## 9. Rollback

Enquanto migration 020 não estiver em produção:

- rollback API/Cloud = revert dos commits locais aprovados;
- DB efêmero pode ser destruído/recriado;
- nenhum down-migration destrutivo;
- publisher state sintético/local pode ser removido nos testes.

Desktop:

- publisher federado é adicional e fail-open para a operação local: remover/reverter publisher não altera Selenium, Shadow ou WebPilot local;
- qualquer falha no publisher remoto deve ser isolada do pipeline oficial.

Se algum passo exigir mudança de autoridade operacional, source, snapshot ou Selenium oficial: **STOP** e devolver ao planejamento; isso não pertence ao C2.

## 10. Security review obrigatório antes de R8

Auditar diff por:

```
cookie
credential
authorization
device_secret
cloud_binding
session
cipher
nonce
realm_epoch
source
snapshot
failover
failback
```

Confirmar:

- somente valores sintéticos em fixtures;
- nenhuma URL com segredo;
- nenhum log de header/body secreto;
- nenhuma rota Mobile/PWA de sessão;
- nenhum endpoint público SQL;
- nenhuma policy aberta;
- wheel instalado com `--no-deps`/equivalente e sem stack Selenium/browser instalado sem necessidade comprovada;
- nenhuma dependency importando Selenium/Tk no processo Cloud;
- nenhum `source=cloud` funcional.

## 11. Base/gates humanos

- C1 final: `61342b2ac47ffa48bfe90787b8aa2afb4bb4cda8`.
- C2-P: este documento, sem commit antes de R5.1.
- R5 aprovou a macro e solicitou F1..F4; R5.1 aprova/rejeita o plano corrigido.
- C2-A → R6 → commit após aprovação.
- C2-B → R7 → commit após aprovação.
- C2-C → R8 → commit após aprovação.
- R8 não autoriza merge/push/deploy/migration produção/C3.
- C3 começa somente por **C3-P** próprio.

## 12. Saída esperada do C2

Ao terminar C2, ainda sem continuidade operacional ativa:

```
Desktop autorizado
   └─ publica SessionLease temporária
        └─ Auth Broker
             ├─ anti-replay por publisher/local_generation
             ├─ realm_epoch server-side
             ├─ encrypted-at-rest
             └─ seleção/revogação/invalidação
                    └─ CloudBinding autorizado
                         └─ collector HTTP/parser headless
                              └─ STANDBY ONLY
```

Nenhum Mobile percebe mudança; nenhum source é trocado.

**STOP atual:** este é somente C2-P corrigido após R5. Não implementar nenhum item C2 antes de R5.1 independente.
