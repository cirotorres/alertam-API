# SPEC 025 — Etapa A3 — MobileSnapshot v2 — Execução

**Data:** 2026-10-03  
**Repositório principal desta rodada:** `/home/ciro/dev/prog/alertamaritimoAPI`  
**Branch:** `feat/spec025-a3-mobile-snapshot-v2`  
**Base/HEAD de início:** `755eaa2 fix: ajusta interface mobile`  
**Plano normativo:** `docs/superpowers/plans/2026-09-29-spec025-plan3-mobile-snapshot-v2.md`  
**SPEC:** `specs/025-webpilot-http-observed-weather-shadow-migration.md`  
**Dependência:** A2 integralmente liberada pelo Revisor.  
**Commit/push:** não realizados pelo Executor.  
**STOP vigente:** Task 5 do Plan 3 exige deploy/smoke + confirmação humana antes de Task 6.

## 1. Escopo executado nesta rodada

Foram executadas somente as Tasks 1–4 e a Step 1 da Task 5 do Plan 3:

1. API aceita MobileSnapshot v1 + v2;
2. serviços/endpoints API propagam e persistem a mesma versão recebida;
3. PWA/TypeScript/Zod aceita v1 + v2;
4. WeatherPage renderiza v1 e v2 sem recalcular freshness;
5. suítes locais completas e build PWA executados.

**Não executado:**
- deploy da API/PWA;
- smoke externo/produção;
- Desktop produtor de snapshot v2;
- Task 6;
- Task 7;
- Plan 4 / Shadow.

## 2. Regra de rollout preservada

Ordem obrigatória da SPEC:

    API v1+v2
        ↓
    PWA v1+v2
        ↓
    deploy + smoke
        ↓
    confirmação humana
        ↓
    Desktop começa a publicar v2

O Desktop atual permanece publicando **schema_version 1**.  
Nenhum código Desktop foi alterado pelo Executor nesta A3 até este checkpoint.

## 3. Task 1 — contrato Pydantic MobileSnapshot v2

### RED

Foram adicionados fixtures sanitizados:
- `api/tests/fixtures/mobile_snapshot_v2_webpilot.json`;
- `api/tests/fixtures/mobile_snapshot_v2_fallback.json`.

Os testes v2 foram escritos antes da implementação.

RED observado:
- **10 testes v2 falharam** porque `MobileSnapshotV2` e `MobileSnapshot` ainda não existiam;
- testes v1 existentes continuaram passando.

### Implementação

`api/app/models/mobile_snapshot.py` passou a preservar `MobileSnapshotV1` e acrescentar:

- `UnavailableV2`;
- `WebPilotAtmospherePrimaryV2`;
- `OpenMeteoAtmospherePrimaryV2`;
- `OpenMeteoComplementaryV2`;
- `AtmosphereV2`;
- `OpenMeteoMarineV2`;
- `MobileSnapshotV2`;
- `MobileSnapshot = Annotated[MobileSnapshotV1 | MobileSnapshotV2, Field(discriminator="schema_version")]`.

Invariantes:
- WebPilot somente `source=webpilot + mode=observed`;
- Open-Meteo primary somente `source=open_meteo + mode=fallback`;
- primary Open-Meteo exige complementary unavailable;
- primary unavailable exige complementary unavailable;
- unavailable é bloco estrito somente com `status`;
- timestamps WebPilot obrigatórios e aware;
- medições usam tipos numéricos estritos;
- `extra="forbid"` preservado.

`SnapshotReadResponse.snapshot` passou a aceitar a união v1|v2.

### Segurança

Os fixtures/contratos v2 possuem teste negativo para material proibido:
- cookie;
- Authorization;
- session_generation;
- HTML;
- token WebPilot.

### GREEN

Foco Task 1:
- **30 testes passed**.

## 4. Task 2 — propagação v1|v2 pela API

### RED

Antes da propagação:
- POST v2 retornava 422;
- roundtrip v2 retornava 422;
- GET de v2 já era aceito pelo modelo de leitura da Task 1.

### Implementação

Alterados:
- `api/app/api/v1/snapshots.py`;
- `api/app/services/snapshot_service.py`;
- `api/app/main.py`.

O serviço:
- recebe a união;
- persiste o JSON recebido sem conversão;
- persiste `snapshot_schema_version` correspondente;
- mantém ordenação/idempotência por `boot_id/sequence`, não por versão.

O GET retorna a mesma versão persistida.

### Ruling do Executor

O Plan 3 não listava `api/app/main.py` na Task 2, porém a troca de literal simples por união
Pydantic discriminada mudou o erro de schema desconhecido para:

    union_tag_invalid

Sem adaptar o handler, o contrato público mudaria de:

    unsupported_snapshot_schema

para:

    invalid_request_payload

Foi feita a menor alteração possível no handler para reconhecer:
- a forma legada `literal_error`;
- a nova forma `union_tag_invalid` cujo discriminador é `schema_version`.

**Custo se a decisão estiver errada:** somente a classificação pública do 422 de schema não
suportado precisaria ser revista; persistência e modelos não dependem desse ruling.

### GREEN

Foco Task 2:
- **59 testes passed**.

Suíte API:
- `make test`: **PASS**, exit 0.

## 5. Task 3 — contrato TypeScript/Zod v1|v2

Fixtures Pydantic foram copiados para:
- `frontend/src/test/fixtures/mobile_snapshot_v2_webpilot.json`;
- `frontend/src/test/fixtures/mobile_snapshot_v2_fallback.json`.

### RED

Antes da implementação:
- os dois fixtures v2 eram rejeitados como “Versão de snapshot não suportada”;
- v1 e testes negativos existentes continuavam verdes.

### Implementação

`frontend/src/api/contract.ts` passou a produzir:
- `MobileSnapshotV1`;
- `MobileSnapshotV2`;
- `MobileSnapshot = MobileSnapshotV1 | MobileSnapshotV2`.

Zod mantém contratos estritos e rejeita:
- schema 3;
- unavailable com campos extras;
- WebPilot/fallback;
- Open-Meteo/observed;
- Open-Meteo primary com complementary preenchido;
- bloco fresh/stale sem campos estruturais exigidos.

Consumidores operacionais que só acessam campos compartilhados passaram de
`MobileSnapshotV1` para `MobileSnapshot`:
- `MapPage.tsx`;
- `projections.ts`;
- `berthMap.ts`;
- `PortMap.tsx`.

Nenhum cast inseguro foi adicionado.

### GREEN

Foco Task 3:
- **23 testes passed**.

## 6. Task 4 — WeatherPage v1 + v2

### RED

Três testes v2 falharam inicialmente porque `WeatherPage` ainda acessava
`snapshot.weather`, ausente no schema v2.

### Implementação

O cabeçalho comum permanece estável:
- `Tempo e mar`;
- `Pecém - CE`.

O branch v1 mantém a apresentação legada.

O branch v2 lê diretamente o estado calculado pelo Desktop:
- **não calcula freshness por timestamps**;
- não transforma stale/fresh;
- não preenche zeros.

#### WebPilot primary

Exibe:
- Estação Pecém · observação;
- WebPilot;
- atualizado/desatualizado conforme payload;
- vento atual;
- vento médio;
- vento máximo;
- direção;
- temperatura;
- sensação térmica;
- umidade;
- pressão;
- pressão 6h;
- precipitação.

#### Open-Meteo fallback

Exibe:
- `Open-Meteo · fallback/modelo`;
- status recebido;
- vento;
- **rajada**.

Não apresenta rajada como “vento máximo da estação”.

#### Complementary

Se disponível:
- `Complementar / previsão`;
- Open-Meteo;
- status recebido;
- condição/visibilidade.

Se unavailable:
- `Dados indisponíveis`.

#### Marine

Exibe:
- `Condições marítimas`;
- `Open-Meteo Marine`;
- status recebido;
- métricas marítimas.

### Compatibilidade v1

Durante GREEN foi detectada uma corrida de teste: o primeiro desenho da implementação criava um
`h1` para “aguardando” e depois substituía o nó quando o snapshot chegava. O cabeçalho foi tornado
comum/estável entre waiting, v1 e v2, preservando a experiência anterior.

### GREEN

WeatherPage + contrato:
- **46 testes passed**.

Frontend completo:
- **48 arquivos passed**;
- **273 testes passed**.

Build:
- `npm run build`: **PASS**;
- Vite/PWA e service worker gerados.

Observação preexistente:
- a suíte imprime warning React `act(...)` em `AppShell.test.tsx`;
- não é falha e não pertence ao escopo A3.

## 7. Task 5 — hard rollout gate

### Step 1 — consumidores locais

Executado de forma agregada:

    cd /home/ciro/dev/prog/alertamaritimoAPI
    make test
    cd frontend
    npm test -- --run
    npm run build
    cd ..
    git diff --check

Resultado:
- API: **PASS**, exit 0;
- frontend: **273 passed / 48 test files**;
- PWA build: **PASS**;
- `git diff --check`: **exit 0**.

### Step 2 — deploy/smoke

**NÃO EXECUTADA.**

O usuário autorizou continuidade da sequência da SPEC, mas manteve as regras anteriores:
ações externas/deploy e commit/push continuam exigindo autorização explícita.

O Plan 3 também define explicitamente:

> Do not begin Task 6 until user confirms API/PWA consumers are ready.

Portanto o Executor parou no ponto correto.

## 8. Working tree / proteção

Antes da A3 já existiam alterações documentais locais no repositório API/PWA, incluindo:
- planos SPEC 025;
- handoff de provisioning;
- SPEC 025;
- `specs/README.md`;
- `docs/superpowers/strategy/`;
- `specs/027-alertam-cloud-continuity.md`.

Esses itens **não pertencem automaticamente à implementação A3** e não devem ser limpos,
resetados ou incluídos em commit por padrão.

Nenhum commit/push foi realizado pelo Executor.

## 9. Controle de checkpoints

Entradas abaixo são sequenciais e devem ser preservadas.  
Executor e Revisor devem acrescentar novas rodadas sem apagar histórico.

### A3 — execução de consumidores E1 — Executor — 2026-10-03

**Resultado:**
- Tasks 1–4 concluídas localmente;
- Task 5 Step 1 concluída;
- API v1+v2 localmente pronta;
- PWA v1+v2 localmente pronta;
- Desktop permanece produtor v1;
- deploy/smoke ainda não autorizado;
- Task 6 não iniciada.

**Gates:**
- API full: PASS;
- frontend: 273 passed;
- PWA build: PASS;
- `git diff --check`: exit 0.

**STOP obrigatório:**
A3 aguarda:
1. revisão independente desta entrega de consumidores;
2. autorização explícita para deploy/smoke da Task 5;
3. confirmação humana de que API/PWA consumidores estão prontos.

Somente depois desses gates o Desktop poderá iniciar Task 6 e publicar `schema_version=2`.

**Commit/push:** não realizados.  
**Plan 4/Shadow:** não iniciado.

### A3 — rodada de revisão R1 — Revisor — 2026-10-03

**Tipo:** revisão independente, inicialmente somente leitura, dos consumidores MobileSnapshot v2.
**Escopo:** Tasks 1–4 + Task 5 Step 1; sem deploy, sem Desktop produtor v2.
**Resultado:** correções requeridas antes de liberar tecnicamente os consumidores A3.
**Alterações feitas pelo Revisor:** nenhuma alteração de código; somente este registro documental.

#### Findings R1

**Critical:** nenhum finding identificado.

#### R1-F1 — Important — `SnapshotService` não expõe a união v1|v2 no próprio contrato de tipo

**Local:** `api/app/services/snapshot_service.py:29-45`.

**Cenário:** o arquivo passou a importar `MobileSnapshot`, mas as assinaturas de
`accept_snapshot()` e `accept_authenticated_snapshot()` continuam anotadas como
`MobileSnapshotV1`. Esse nome deixou de ser importado no módulo.

Com `from __future__ import annotations`, o fluxo HTTP não quebra imediatamente, porque FastAPI
valida a união no endpoint e as anotações do serviço ficam adiadas. Porém a anotação do serviço
fica inválida e não representa o contrato A3.
Reprodução independente:

    accept_snapshot NameError name 'MobileSnapshotV1' is not defined
    accept_authenticated_snapshot NameError name 'MobileSnapshotV1' is not defined

A reprodução foi feita com `typing.get_type_hints()` sobre os dois métodos.

**Impacto:**
- viola a interface definida na Task 2: `SnapshotService accepts MobileSnapshot union`;
- introspecção de tipos quebra em runtime;
- type-checking/documentação/refactors futuros podem assumir incorretamente que o serviço é v1-only;
- o comportamento HTTP v2 atual continua funcional, portanto não foi classificado como Critical.

**Critério de correção:**
- anotar ambos os métodos com `MobileSnapshot`;
- eliminar referência não resolvível a `MobileSnapshotV1` no serviço;
- adicionar prova simples de que as type hints do serviço resolvem e apontam para a união v1|v2,
  ou cobertura equivalente que impeça regressão do contrato.

**Resposta do Executor:** _pendente na R1_.

#### R1-F2 — Important — PWA descarta o cardinal WebPilot e exibe direção diferente da fonte

**Local:** `frontend/src/pages/WeatherPage.tsx:44-50,192-216`.

**Cenário:** o snapshot v2 WebPilot carrega simultaneamente:

    wind_direction_deg: 65
    wind_direction_cardinal: "ENE"

mas a `WeatherPage` chama apenas `direction(primary.wind_direction_deg)`. O helper converte graus
para uma rosa de apenas 8 pontos e não usa `wind_direction_cardinal`.

Reprodução independente do algoritmo atual:

    source_cardinal=ENE
    rendered_by_current_helper=65° NE

Busca no frontend confirmou que `wind_direction_cardinal` só aparece no schema/fixture e não é
consumido pela UI.

**Impacto:**
- a PWA altera a informação cardinal observada da estação (`ENE` -> `NE`);
- o contrato v2 transporta explicitamente o cardinal para preservar a semântica WebPilot;
- direção do vento é dado operacional exibido ao usuário e a PWA deveria apresentar a fonte de
  forma mais completa, não reduzir silenciosamente sua precisão.
**Critério normativo:**
- contrato v2 fixado no Plan 3 inclui `wind_direction_cardinal` para o primary WebPilot;
- SPEC 025 §9.4 exige preservar graus e cardinal quando fornecidos;
- SPEC 025 §18 exige representação mais completa das fontes na PWA.

**Critério de correção:**
- no branch WebPilot, usar o cardinal recebido quando não nulo, preservando também os graus;
- manter derivação por graus para Open-Meteo/Marine, que não possuem cardinal textual no contrato;
- adicionar teste da fixture realista `65° / ENE` garantindo que a PWA não renderize `NE`.

**Resposta do Executor:** _pendente na R1_.

#### Pontos aprovados na R1

- `MobileSnapshotV1` permanece aceito, inclusive blocos v1 vazios conforme testes existentes;
- contrato Pydantic v2 rejeita combinações source/mode inválidas;
- `unavailable` com campos extras é rejeitado;
- timestamp WebPilot naïve é rejeitado;
- string numérica em medição v2 é rejeitada;
- roundtrip POST/GET v2 preserva estrutura e versão sem conversão;
- schema 3 continua retornando `unsupported_snapshot_schema`;
- ruling em `api/app/main.py` é considerado correção mínima e coerente com a mudança para união
  discriminada;
- consumidores compartilhados de mapa/projeções usam somente campos comuns de `MobileSnapshot`;
- não foram encontrados casts inseguros para fingir v1;
- WeatherPage não recalcula fresh/stale por relógio/timestamp;
- WebPilot, fallback Open-Meteo, complementary e Marine permanecem blocos separados;
- fallback usa `Rajada`, não `Vento máximo`;
- payload/fixtures v2 não expõem material de sessão listado pela SPEC.

#### Gates conferidos na R1

- branch: `feat/spec025-a3-mobile-snapshot-v2`;
- HEAD/base: `755eaa2 fix: ajusta interface mobile`;
- API focada consumidor/roundtrip: **59 passed**, exit code 0;
- API completa `make test`: exit code 0 com `-W error`;
- frontend focado contrato/pages/mapa: **52 passed**, exit code 0;
- frontend completo: **48 test files / 273 tests passed**, exit code 0;
- `npm run build`: PASS, incluindo `tsc -b`, Vite e service worker PWA;
- `git diff --check`: exit 0;
- warning React `act(...)` permanece preexistente e não é failure A3;
- nenhum commit/push/deploy foi realizado pelo Revisor.

#### Hard rollout gate / limites

- deploy API/PWA e smoke externo continuam **NÃO executados**;
- Desktop produtor v2 continua **NÃO iniciado**;
- Task 6 permanece bloqueada independentemente desta revisão;
- Plan 4/Shadow não foi iniciado.

#### Situação atual após R1

- **Consumidores A3: NÃO liberados tecnicamente pelo Revisor.**
- Executor deve corrigir somente **R1-F1 e R1-F2** e registrar resposta em nova entrada sequencial;
- depois das correções, realizar **R2 — re-review independente** focada nesses dois findings e gates;
- mesmo após eventual R2 verde, Task 6 continua proibida até deploy/smoke da Task 5 + confirmação
  humana explícita de que API/PWA consumidores estão prontos;
- commit/push/deploy continuam dependentes de autorização explícita do usuário.

### A3 — rodada de correção R1 — Executor — 2026-10-03

**Escopo desta rodada:** exclusivamente **R1-F1** e **R1-F2**.  
**Critical novo:** nenhum identificado pelo Executor.  
**Deploy:** não realizado.  
**Desktop produtor v2 / Task 6:** não iniciado.  
**Commit/push:** não realizados.  
**Plan 4/Shadow:** não iniciado.

#### R1-F1 — SnapshotService deve expor MobileSnapshot v1|v2 nas type hints

Finding confirmado no código antes da correção.

Estado anterior:

    from app.models.mobile_snapshot import MobileSnapshot

mas:

    SnapshotService.accept_snapshot(..., snapshot: MobileSnapshotV1)
    SnapshotService.accept_authenticated_snapshot(..., snapshot: MobileSnapshotV1)

Como `from __future__ import annotations` adia a resolução, o fluxo HTTP podia funcionar, porém:

    typing.get_type_hints(SnapshotService.accept_snapshot)

falhava com:

    NameError: name 'MobileSnapshotV1' is not defined

##### RED

Foi criado o teste:

    test_snapshot_service_type_hints_expose_mobile_snapshot_union

Primeira execução RED:

    NameError: name 'MobileSnapshotV1' is not defined

Isso reproduziu diretamente o finding do Revisor.

##### Correção

As duas assinaturas agora usam exatamente:

    snapshot: MobileSnapshot

Não existe mais referência `MobileSnapshotV1` no contrato de entrada do `SnapshotService`.

O teste usa:

    get_type_hints(..., include_extras=True)

porque `MobileSnapshot` é um `Annotated[..., Field(discriminator="schema_version")]` e
`get_type_hints()` sem `include_extras=True` remove o metadata `Annotated` por definição.
Assim a prova verifica o alias discriminado completo, e não apenas a união interna.

##### GREEN

Execução focada final:

    uv run pytest tests/unit/test_snapshot_service.py -q       -k 'type_hints_expose_mobile_snapshot_union'

Resultado:

    1 passed

**R1-F1: corrigido pelo Executor e pronto para R2.**

#### R1-F2 — preservar cardinal textual WebPilot na WeatherPage

Finding confirmado com a fixture A3 realista:

    wind_direction_deg: 65
    wind_direction_cardinal: "ENE"

Estado anterior da UI WebPilot:

    direction(primary.wind_direction_deg)

O helper de 8 pontos derivava:

    65° NE

e descartava o cardinal explícito `ENE` recebido da estação.

##### RED

O teste existente do cenário WebPilot foi reforçado para exigir, dentro da métrica
`Direção do vento`:

    65° ENE

e garantir ausência de:

    65° NE

Execução RED observada:

    Unable to find an element with the text: 65° ENE

DOM real no failure:

    <dd>65° NE</dd>

##### Correção

Foi adicionado helper restrito ao observado WebPilot:

    observedDirection(degrees, cardinal)

Semântica:
- graus + cardinal fornecido => preserva ambos, por exemplo `65° ENE`;
- graus presentes + cardinal ausente => mantém derivação existente por graus;
- graus ausentes + cardinal presente => apresenta o cardinal;
- ambos ausentes => `—`.

Somente o branch:

    primary.source === "webpilot"

usa `observedDirection(...)`.

Open-Meteo fallback, Marine e v1 continuam usando a derivação anterior por graus e **não**
receberam cardinal inventado.

##### GREEN

Execução focada final:

    npm test -- --run src/pages/pages.test.tsx       -t 'weather_page_v2_webpilot_separates_observation_complementary_and_marine'

Resultado:

    1 passed | 28 skipped

A fixture `65° / ENE` agora é exibida como:

    65° ENE

e `65° NE` não aparece nesse cenário.

**R1-F2: corrigido pelo Executor e pronto para R2.**

#### Gates após R1-F1/R1-F2

Executado novamente, depois das duas correções:

    cd /home/ciro/dev/prog/alertamaritimoAPI
    make test
    cd frontend
    npm test -- --run
    npm run build
    cd ..
    git diff --check

Resultados:

- API `make test`: **PASS**, exit code 0, com `-W error`;
- frontend completo: **48 test files / 273 tests passed**;
- PWA/TypeScript build: **PASS**;
- Vite build: **PASS**;
- service worker PWA: **PASS**;
- `git diff --check`: **exit 0**.

Warning React `act(...)` preexistente em `AppShell.test.tsx` continua aparecendo como warning,
não failure, e não foi alterado nesta rodada.

#### Arquivos tocados especificamente pela correção R1

- `api/app/services/snapshot_service.py`;
- `api/tests/unit/test_snapshot_service.py`;
- `frontend/src/pages/WeatherPage.tsx`;
- `frontend/src/pages/pages.test.tsx`.

Observação: esses arquivos já continham mudanças A3 anteriores não commitadas; portanto o
`git diff --stat` contra HEAD representa **A3 acumulada**, não apenas esta rodada R1. O escopo
específico desta correção é o descrito acima.

#### Situação após correção R1

- **R1-F1:** corrigido, aguardando R2;
- **R1-F2:** corrigido, aguardando R2;
- demais pontos aprovados na R1 não foram reabertos;
- API/PWA consumidores continuam localmente prontos;
- **Consumidores A3 ainda não são declarados liberados pelo Executor**: aguardam R2 independente;
- deploy/smoke Task 5 continua não executado;
- Task 6 Desktop continua bloqueada mesmo que R2 seja verde, até deploy/smoke + confirmação humana;
- commit/push/deploy continuam dependentes de autorização explícita do usuário.

#### Instrução para R2

O Revisor deve fazer uma nova passagem independente focada em:

1. confirmar que `SnapshotService.accept_snapshot` e
   `accept_authenticated_snapshot` resolvem type hints para `MobileSnapshot` v1|v2;
2. confirmar que o cenário WebPilot `65° / ENE` é exibido como `65° ENE`, sem regressão para
   Open-Meteo/Marine;
3. repetir os gates relevantes;
4. registrar o parecer R2 abaixo desta entrada, preservando todo o histórico.

R2 não deve autorizar automaticamente deploy nem Task 6.

### A3 — rodada de re-review R2 — Revisor — 2026-10-03

**Tipo:** re-revisão independente focada em R1-F1, R1-F2 e gates dos consumidores.
**Resultado:** **APROVADA TECNICAMENTE**. R1-F1 e R1-F2 resolvidos; nenhum novo finding identificado.
**Alterações feitas pelo Revisor:** nenhuma alteração de código; somente este registro documental.

#### Verificação independente de R1-F1

As duas APIs do `SnapshotService` agora recebem explicitamente:

    snapshot: MobileSnapshot

Reprodução com `typing.get_type_hints(..., include_extras=True)`:

    accept_snapshot True typing.Annotated[MobileSnapshotV1 | MobileSnapshotV2, ... discriminator='schema_version']
    accept_authenticated_snapshot True typing.Annotated[MobileSnapshotV1 | MobileSnapshotV2, ... discriminator='schema_version']

Também foi confirmado que não resta referência `MobileSnapshotV1` em
`api/app/services/snapshot_service.py`.

**R1-F1 — Important — ENCERRADO.**
#### Verificação independente de R1-F2

O branch WebPilot passou a usar `observedDirection(degrees, cardinal)` e preserva o cardinal
recebido da estação.

Caso realista da fixture:

    wind_direction_deg = 65
    wind_direction_cardinal = "ENE"

Resultado esperado e coberto:

    65° ENE

O teste também garante ausência de `65° NE` nesse cenário.

Open-Meteo fallback e Marine continuam usando a derivação por graus, sem cardinal textual
inventado. Os dois testes focados WebPilot + fallback passaram juntos.

**R1-F2 — Important — ENCERRADO.**
#### Gates conferidos na R2

- branch: `feat/spec025-a3-mobile-snapshot-v2`;
- HEAD/base permanece `755eaa2 fix: ajusta interface mobile`;
- teste focado de type hints: PASS;
- testes focados WeatherPage WebPilot + fallback: **2 passed**, exit code 0;
- API focada consumidores/roundtrip: **60 passed**, exit code 0;
- API completa `make test`: PASS, exit code 0, com `-W error`;
- frontend completo: **48 test files / 273 tests passed**, exit code 0;
- `npm run build`: PASS (`tsc -b`, Vite, PWA/service worker);
- `git diff --check`: exit 0;
- warning React `act(...)` permanece preexistente e não é failure A3;
- nenhum commit/push/deploy foi realizado pelo Revisor.

#### Rollout / escopo negativo

- busca no Desktop confirmou que produtor Mobile atual ainda não contém `schema_version=2`;
- deploy API/PWA continua não executado;
- smoke externo v1 + v2 sintético continua não executado;
- Task 6 Desktop continua não iniciada;
- Plan 4/Shadow continua não iniciado.
#### Fechamento da revisão de consumidores

- **R1-F1: ENCERRADO.**
- **R1-F2: ENCERRADO.**
- não há finding Critical, Important ou Minor pendente nesta revisão.
- **Consumidores A3 (Tasks 1–4 + Task 5 Step 1): LIBERADOS TECNICAMENTE pelo Revisor.**

Esta liberação encerra somente a revisão local de código/contrato dos consumidores.

#### Hard rollout gate permanece obrigatório

Antes de iniciar Task 6 / Desktop produtor v2, ainda são obrigatórios, nesta ordem:

1. autorização explícita do usuário para deploy/smoke;
2. deploy da API/PWA com suporte v1+v2;
3. smoke provando leitura do v1 atual e aceitação/renderização de v2 sintético seguro;
4. confirmação humana explícita de que os consumidores estão prontos.

**R2 não autoriza automaticamente deploy, commit/push ou Task 6.**

**Gate técnico dos consumidores A3:** SATISFEITO.
**Gate de rollout Task 5 Step 2/3:** PENDENTE.

### A3 — rollout Task 5 Step 2 — Executor — 2026-10-03

**Autorização:** o usuário autorizou explicitamente resolver as pendências do gate de rollout
Task 5 Step 2/3 nesta rodada.

**Objetivo normativo do Step 2:**
- publicar API/PWA consumidores v1+v2;
- provar que o v1 atual continua legível;
- provar aceitação de v2 sintético seguro;
- provar renderização PWA v2;
- somente depois solicitar confirmação humana do Step 3.

#### Pre-flight de deploy

Foi relido o runbook oficial:

    api/DEPLOY_VERCEL.md

A arquitetura atual usa o `vercel.json` raiz com Services:
- `api`;
- `frontend`;
- roteamento same-origin `/api/v1/* -> api`;
- demais rotas -> frontend.

O domínio de produção documentado para a API é:

    https://alertam-api.vercel.app

#### Estado de autenticação Vercel nesta máquina

Foram verificadas as fontes locais de autenticação:

- `.vercel/project.json`: ausente;
- `api/.vercel/project.json`: ausente;
- `frontend/.vercel/project.json`: ausente;
- `VERCEL_TOKEN`: unset;
- `VERCEL_ORG_ID`: unset;
- `VERCEL_PROJECT_ID`: unset;
- arquivos locais de auth do Vercel CLI: ausentes.

Verificação direta:

    npx vercel@62.2.0 whoami

Resultado:

    Vercel CLI 62.2.0
    > Logged out.
    > Run `vercel login` to log in.

O conector Vercel disponível ao Executor também não retornou nenhum team/workspace conectado.

#### Histórico operacional conferido

O handoff:

    docs/superpowers/handoffs/2026-09-30-windows-provisioning-mobile-management-cloud-handoff.md

já registra que, no primeiro uso de outra máquina:
- `vercel link` falha quando não há login;
- o fluxo documentado é `npx --yes vercel@latest login` e depois `link`.

Portanto não existe, no checkout atual, deploy hook/token alternativo documentado que permita
publicar o working tree aprovado sem autenticação.

#### Decisão de segurança/rollout

O Executor **não** usou:

    vercel deploy --temporary

porque um deployment temporário sem o Project/Environment real não prova o hard gate definido no
Plan 3:
- não garante as variáveis de produção;
- não garante o mesmo routing/project;
- não prova que os consumidores reais estão prontos antes do Desktop começar a publicar v2.

Também não foi usado `git commit`/`git push` como atalho para acionar Git Integration, porque
commit/push continuam sem autorização explícita nesta sequência.

#### Situação do Step 2

**Step 2: BLOQUEADO EXCLUSIVAMENTE POR AUTENTICAÇÃO VERCEL.**

Nenhum deploy foi executado.
Nenhum dado de produção foi modificado.
Nenhum v2 sintético foi enviado à produção.
Desktop continua publicando v1.
Task 6 continua bloqueada.

#### Ação externa mínima necessária

Para o Executor poder concluir o Step 2 sem commit/push, é necessário que o usuário faça uma das
ações explícitas de autenticação:

1. conectar/autorizar o Vercel connector da conta que possui o projeto; ou
2. autenticar o Vercel CLI nesta máquina com:

       npx --yes vercel@62.2.0 login

   e, se necessário, vincular o checkout ao projeto com:

       npx --yes vercel@62.2.0 link

Após a autenticação, o Executor pode retomar do mesmo checkpoint, publicar o working tree aprovado,
executar os smokes v1/v2 e registrar o resultado.

#### Step 3

**PENDENTE e não executado.**

A confirmação humana de Step 3 só pode ocorrer depois de um Step 2 real e verde.

#### Limites mantidos

- consumidores A3 continuam tecnicamente aprovados pela R2;
- nenhum commit/push;
- nenhum deploy parcial/temporário foi aceito como substituto;
- nenhum Desktop v2;
- nenhuma Task 6;
- nenhum Plan 4/Shadow.


#### Baseline externo antes do deploy

Embora o novo working tree ainda não possa ser publicado sem autenticação Vercel, o domínio atual de
produção foi consultado sem credenciais para registrar o baseline:

    GET https://alertam-api.vercel.app/api/v1/health
    HTTP 200
    {"ok":true}

    GET https://alertam-api.vercel.app/
    HTTP 200
    frontend HTML servido

Isso comprova que o serviço atual está acessível antes do rollout, mas **não** substitui o smoke
v1/v2 pós-deploy exigido pelo Step 2.

O conector Vercel tentou acessar o deployment e retornou 403 informando que a conexão atual não
está autorizada para o projeto/team, reforçando o mesmo bloqueio observado no CLI local.


### A3 — rollout Task 5 Step 2 — preview e smoke automático — Executor — 2026-10-03

**Projeto Vercel confirmado:** `cirotorres-projects/alertam-api`  
**Projeto ID:** `prj_Z5quPlGf9TiZG1npDvV1vqA2HhM1`  
**Produção atual:** `https://alertam-api.vercel.app`  
**Deployment de preview A3:** `dpl_2Wnu6wxyZYhdZGvpUqWv3y9MxyQm`  
**Preview URL:** `https://alertam-myrex42ib-cirotorres-projects.vercel.app`  
**Estado:** `READY`  
**Target:** Preview, sem promoção para produção.

#### Conferência da topologia de deploy

Foi inspecionado o deployment de produção atual antes do preview.

Confirmado que a Vercel já utiliza o mesmo `vercel.json` do working tree com:
- service `api`: FastAPI, Python 3.12;
- service `frontend`: Vite/PWA;
- rewrite `/api/v1/* -> api`;
- demais rotas -> frontend.

Assim, o preview foi criado contra a mesma topologia usada hoje em produção.

#### Isolamento do preview

As variáveis Vercel existentes estão configuradas somente em Production.
O preview foi deliberadamente mantido sem as credenciais Supabase de produção.

Consequência esperada pelo contrato atual:
- `ENVIRONMENT=development`;
- `PERSISTENCE_BACKEND=memory`;
- mock device isolado;
- Web Push desabilitado.

Nenhum snapshot sintético foi escrito no Supabase.
Nenhum dos dois devices reais encontrados em produção foi usado para o v2 sintético.

#### Smoke 1 — health do preview

Executado no deployment protegido via `vercel curl`:

    GET /api/v1/health

Resultado:

    HTTP 200
    {"ok":true}

#### Smoke 2 — API publicada aceita v2 sintético seguro

Foi usado o fixture A3:

    api/tests/fixtures/mobile_snapshot_v2_webpilot.json

POST no mock device do backend memory do preview.

Resultado:

    {"ok":true,"received_at":"2026-10-03T05:40:35.953121Z"}

Leitura subsequente do mesmo snapshot no preview confirmou:

    schema_version=2
    primary_status=fresh
    primary_source=webpilot
    primary_mode=observed
    wind_direction_deg=65
    wind_direction_cardinal=ENE
    marine_status=fresh
    meta_online=True

Portanto o contrato v2 atravessou a API efetivamente publicada no preview.

#### Smoke 3 — payload v1 real atual continua legível pela nova API publicada

Sem escrever em produção, foi lido do Supabase o snapshot atual de `pecem-01` e copiado para um
arquivo temporário local.

Baseline observado:

    schema_version=1
    sequence=521
    vessels=30
    generated_at=2026-10-03T02:08:02-03:00

Esse payload real foi POSTado apenas no backend memory do preview e depois lido pela nova API.

Resultado:

    {"ok":true,...}
    read_schema_version=1
    read_sequence=521
    read_vessels=30
    meta_online=True

Isso prova que o payload v1 real produzido atualmente pelo Desktop continua aceito e legível pela
nova API publicada, sem alterar o snapshot operacional de produção.

#### Smoke 4 — bundle PWA publicado contém a UI v2 aprovada

O HTML e o bundle JavaScript foram obtidos diretamente do preview protegido.

O asset publicado:

    /assets/index-D4gOY5Rr.js

contém os branches/textos A3 esperados:

- `Estação Pecém · observação`;
- `Vento máximo`;
- `Open-Meteo · fallback/modelo`;
- `Open-Meteo Marine`;
- `Dados indisponíveis`.

Isso comprova que o bundle v2 aprovado foi efetivamente publicado no preview.

#### Smoke visual manual — PENDENTE

O navegador automatizado disponível ao Executor não possui acesso ao preview protegido por
Vercel Authentication. Portanto a última prova do Step 2 é visual/humana:

1. abrir o Preview URL;
2. autenticar na Vercel se solicitado;
3. escolher conexão por código;
4. usar o código temporário emitido pelo Executor nesta rodada;
5. abrir `Tempo`;
6. confirmar que a tela mostra WebPilot observado, `65° ENE`, complementary Open-Meteo e
   Open-Meteo Marine sem erro/zeros artificiais.

O código de pareamento não foi persistido neste documento por ser credencial temporária de 5 min.

#### Estado do rollout após smoke automático

- consumidores A3 continuam tecnicamente aprovados;
- preview A3: READY;
- health preview: PASS;
- v2 sintético na API publicada: PASS;
- payload v1 real atual na nova API publicada: PASS;
- bundle PWA v2 publicado: PASS;
- smoke visual PWA: **PENDENTE de confirmação humana**;
- produção `alertam-api.vercel.app`: **não alterada**;
- promoção para produção: **não executada**;
- Task 5 Step 2: ainda não fechado até smoke visual + promoção/smoke de produção conforme decisão humana;
- Task 5 Step 3: PENDENTE;
- Task 6 Desktop v2: BLOQUEADA;
- commit/push: não realizados.


### A3 — rollout Task 5 Step 2 — produção publicada — Executor — 2026-10-03

**Autorização:** usuário autorizou explicitamente publicar API/PWA A3 em produção e executar o
smoke pós-deploy.

**Desktop:** não alterado; continua produtor `schema_version=1`.  
**Commit/push:** não realizados.  
**Supabase schema/migrations:** não alterados.  
**Task 6:** não iniciada.

#### Deployment de produção

Foi criado deployment novo com ambiente `Production`:

    npx --yes vercel@62.2.0 deploy --prod --yes --force --json

Motivo para novo build em Production, em vez de promover o preview:
- as variáveis reais Supabase/Web Push existem somente no target Production;
- promover o preview isolado poderia preservar ambiente de preview/memory e não representar o
  runtime real.

Resultado:

    deployment id: dpl_6yuQz2Lo8g5hp8afDHZtMuwQFeWZ
    target: production
    readyState: READY
    productionUrl: https://alertam-api.vercel.app
    deploymentUrl: https://alertam-44jl59yff-cirotorres-projects.vercel.app

Alias de produção atualizado:

    https://alertam-api.vercel.app

#### Smoke pós-deploy — health e frontend

Executado após o alias apontar para o novo deployment:

    GET https://alertam-api.vercel.app/api/v1/health
    HTTP 200
    {"ok":true}

    GET https://alertam-api.vercel.app/
    HTTP 200

Asset JavaScript servido em produção:

    /assets/index-D4gOY5Rr.js

O bundle publicado contém os marcadores A3:

- `Estação Pecém · observação`;
- `Open-Meteo · fallback/modelo`;
- `Open-Meteo Marine`;
- `Vento máximo`.

#### Inspeção do deployment ativo

`vercel inspect https://alertam-api.vercel.app --json` confirmou:

    id=dpl_6yuQz2Lo8g5hp8afDHZtMuwQFeWZ
    target=production
    readyState=READY
    alias=alertam-api.vercel.app

#### Error scan

Executado:

    vercel logs dpl_6yuQz2Lo8g5hp8afDHZtMuwQFeWZ       --level error --since 30m --limit 50 --json

Resultado:

    0 error log lines

Nenhum erro runtime foi encontrado no deployment novo durante o smoke.

#### Baseline Supabase após deploy

Consulta somente leitura após o rollout confirmou que os devices reais continuam em v1:

    pecem-01       schema=1 sequence=521
    pecem-55ee08ee schema=1 sequence=805

Portanto:
- o deploy dos consumidores não converteu nem escreveu snapshots automaticamente;
- nenhum v2 sintético foi inserido nos devices reais;
- o Desktop continua sendo a única fonte do snapshot operacional atual.

#### Compatibilidade v1

Antes da promoção para Production, o snapshot v1 real atual de `pecem-01` já havia sido testado
contra o mesmo código A3 publicado em preview isolado:

    schema_version=1
    sequence=521
    vessels=30

POST + GET no backend memory do preview passaram preservando o payload.

A prova final de integração com o runtime real Production será feita pelo usuário agora:
1. executar `make run` no Desktop atual;
2. verificar coleta/Tempo normalmente;
3. conectar o celular pelo fluxo real do próprio Desktop;
4. confirmar que mapa/listas/PWA continuam funcionando;
5. abrir `Tempo` no celular e confirmar que a página renderiza sem erro.

#### Efeito operacional local do Vercel CLI

`vercel link` criou localmente:
- `.vercel/project.json`;
- `.env.local`;
- alteração automática em `.gitignore`.

A alteração em `.gitignore` foi revertida por pertencer apenas ao tooling local.
Para manter os arquivos locais ignorados sem modificar o repositório, foram adicionados somente em:

    .git/info/exclude

os padrões:

    .vercel/
    .env.local

Assim o working tree rastreado não ganhou ruído de deploy.

#### Estado atual do Task 5

Automático:
- consumidores A3 técnicos: SATISFEITOS;
- deploy Production: PASS;
- health Production: PASS;
- frontend/PWA Production servido: PASS;
- bundle A3 ativo: PASS;
- error scan: CLEAN;
- devices reais permanecem v1: confirmado;
- commit/push: não realizados.

Manual:
- Desktop atual `make run` + celular conectado ao Production novo: **PENDENTE de confirmação do usuário**.

**Task 5 Step 2** fica pendente somente dessa confirmação manual de integração real.
**Task 5 Step 3** permanece pendente até o usuário confirmar o smoke.
**Task 6 Desktop v2** continua bloqueada até Step 3.


### A3 — observação do smoke manual: PWA em v1 ainda mostra Open-Meteo — 2026-10-03

O usuário observou corretamente que, após o deployment A3 em produção:
- o Desktop exibe atmosfera observada explicitamente via WebPilot;
- o PWA continua identificando a meteorologia como Open-Meteo;
- os valores do PWA diferem dos valores atmosféricos observados no Desktop.

#### Diagnóstico confirmado pelo Executor

O deployment A3 está ativo em Production:

    deployment=dpl_6yuQz2Lo8g5hp8afDHZtMuwQFeWZ
    readyState=READY
    target=production

O snapshot operacional real recebido em Production de `pecem-01` continua:

    schema_version=1
    has_atmosphere=False

e contém apenas os blocos legados:

    weather={... Open-Meteo ...}
    marine={... Open-Meteo Marine ...}

O código Desktop A2 confirma deliberadamente esse adapter de compatibilidade em:

    src/alertam/application/mobile_sync.py

Ao publicar v1, o `MobileSyncCoordinator` passa ao builder somente:

    weather_state.forecast
    weather_state.marine

O estado observado WebPilot de:

    weather_state.primary / ObservedWeather

não entra no MobileSnapshot v1.

#### Consequência esperada

Mesmo com o **bundle PWA A3 novo** carregado, enquanto o snapshot recebido for
`schema_version=1`, `WeatherPage` entra explicitamente no branch:

    LegacyWeather

Esse branch mantém a semântica antiga:

    Condições meteorológicas e marítimas recebidas ... via API Open-Meteo.

Portanto, neste estágio:
- é esperado o PWA mostrar Open-Meteo;
- é esperado o PWA poder apresentar valores diferentes do Desktop, porque Desktop usa WebPilot
  observado como primário enquanto v1 móvel ainda carrega Forecast/Open-Meteo;
- isso não indica falha de deployment nem falha de WebPilot no Desktop.

#### Relação com Task 6

A convergência visual/dados ocorre somente quando o Desktop iniciar a **Task 6** e passar a publicar
`schema_version=2`, contendo:

    atmosphere.primary = WebPilot observed (quando disponível)
    atmosphere.complementary = Open-Meteo
    marine = Open-Meteo Marine

Nesse momento o PWA A3 já publicado trocará automaticamente para o branch `V2Weather` e exibirá:
- Estação Pecém / WebPilot;
- vento atual/médio/máximo;
- cardinal observado, por exemplo `65° ENE`;
- Open-Meteo separado como complementar/fallback;
- Marine separado.

#### Interpretação correta do smoke atual

O smoke atual com Desktop v1 deve validar apenas:
- pareamento continua funcionando;
- mapa/listas continuam funcionando;
- página Tempo v1 continua renderizando sem erro;
- não houve regressão de compatibilidade com o produtor v1.

**Não é critério deste smoke que os valores do PWA coincidam com o WebPilot do Desktop**, pois isso
só será verdadeiro após Task 6 / snapshot v2.

#### Deploy via Git vs CLI

O deployment A3 não dependeu de push na branch `feat/api-bootstrap`.

Nesta rodada foi feito deployment manual e explícito do working tree aprovado com:

    vercel deploy --prod

Logo, Production recebeu o bundle A3 mesmo sem commit/push/Git Integration.

Git Integration continua podendo publicar automaticamente a partir da branch configurada, mas ela
não é a única forma de atualizar a produção Vercel.


### A3 — revisão independente do rollout pré-Task 6 — Revisor — 2026-10-03

**Tipo:** revisão documental + validação externa somente leitura do hard rollout gate após publicação dos consumidores.
**Resultado:** deployment e compatibilidade v1 confirmados; **Task 6 ainda não liberada** porque falta a prova PWA end-to-end com v2 sintético.

#### Evidências independentes confirmadas pelo Revisor

Produção ativa:

    id=dpl_6yuQz2Lo8g5hp8afDHZtMuwQFeWZ
    target=production
    readyState=READY
    aliases=['alertam-api.vercel.app', 'alertam-api-cirotorres-projects.vercel.app']

Health de produção:

    GET https://alertam-api.vercel.app/api/v1/health
    HTTP 200
    {"ok":true}

Frontend de produção:
- asset ativo: `/assets/index-D4gOY5Rr.js`;
- bundle contém:
  - `Estação Pecém · observação`;
  - `Open-Meteo · fallback/modelo`;
  - `Open-Meteo Marine`;
  - `Vento máximo`.

Desktop:
- continua com `schema_version=1`;
- nenhuma implementação de produtor v2 foi iniciada;
- a ordem consumer-first do rollout permanece preservada.

#### Evidências do Executor consideradas válidas

- preview A3 publicado com backend memory isolado;
- v2 sintético seguro foi POSTado e lido com sucesso no preview:
  - `schema_version=2`;
  - `primary_source=webpilot`;
  - `primary_mode=observed`;
  - `wind_direction_cardinal=ENE`;
- snapshot v1 real atual foi copiado para o preview e fez POST/GET sem perda;
- produção foi publicada posteriormente com o mesmo bundle A3 aprovado;
- devices reais de produção permaneceram em schema v1;
- smoke manual do usuário em produção comprovou que o fluxo v1/PWA continua operacional.

#### Ponto ainda não satisfeito do hard gate

O Plan 3 Task 5 Step 2 exige provar simultaneamente:

1. v1 atual continua legível;
2. API aceita v2 sintético seguro;
3. **PWA renderiza esse v2 corretamente**.

Os itens 1 e 2 possuem evidência suficiente.
O deployment/bundle do item 3 está presente, mas ainda falta a prova operacional de renderização do v2 sintético por uma PWA publicada.

Verificar apenas que o bundle contém os textos A3 não substitui essa prova, porque não demonstra:
- parsing real do response v2 no cliente publicado;
- seleção do branch `V2Weather`;
- renderização de WebPilot + complementary + Marine com o payload sintético;
- ausência de erro runtime nesse fluxo publicado.

A observação manual do usuário em produção com snapshot v1 é uma prova válida de compatibilidade v1, mas não fecha o caso v2 por definição.

#### Parecer

- **Findings de código/deploy novos:** nenhum.
- **Gate técnico consumidores A3:** SATISFEITO.
- **Deploy Production consumidores A3:** SATISFEITO.
- **Compatibilidade operacional v1:** SATISFEITA.
- **Aceitação API de v2 sintético publicado:** SATISFEITA no preview isolado.
- **Renderização PWA publicada de v2 sintético:** PENDENTE.
- **Task 5 Step 2:** PARCIALMENTE SATISFEITA; falta somente a prova acima.
- **Task 5 Step 3 / confirmação humana final:** PENDENTE até o Step 2 ficar integralmente verde.
- **Task 6 Desktop v2:** BLOQUEADA.

#### Prova mínima restante

Executar uma única validação visual/end-to-end contra consumidor publicado usando snapshot v2 sintético seguro, preferencialmente no preview isolado já usado pelo Executor:

- abrir a PWA publicada do preview;
- conectar ao mock device que recebeu o fixture v2;
- abrir `Tempo`;
- confirmar:
  - `Estação Pecém · observação`;
  - `WebPilot`;
  - `65° ENE`;
  - `Complementar / previsão` com Open-Meteo;
  - `Open-Meteo Marine`;
  - ausência de erro/zeros artificiais.

Após essa evidência e confirmação explícita do usuário, o Revisor pode fechar Task 5 Step 2/3 e liberar a entrada na Task 6.

**Não iniciar Task 6 antes desse fechamento.**


### A3 — prova mínima E2E v2 publicada — preparação do smoke persistente — Executor — 2026-10-03

Em resposta direta à exigência do Revisor, o Executor substituiu a estratégia de preview `memory`
por um smoke persistente e isolado contra a PWA publicada em Production.

#### Motivo

O pairing-code do preview `memory` não é uma prova confiável em Vercel serverless:
o código pode ser criado numa invocação e resgatado em outra instância sem o mesmo estado.

Portanto não serão gerados novos códigos nesse preview.

#### Device temporário de smoke

Foi criado no Supabase um device temporário claramente isolado:

    smoke-a3-44d6b926

Esse device:
- não substitui nem altera `pecem-01`;
- não substitui nem altera `pecem-55ee08ee`;
- possui credenciais próprias temporárias;
- será removido após a confirmação visual;
- relações de mobile installation/tracking associadas usam `ON DELETE CASCADE` no schema.

O segredo temporário não é persistido neste documento.

#### Snapshot v2 publicado no device de smoke

Foi publicado pela API Production o fixture A3 aprovado.

Leitura imediata pela própria API Production confirmou:

    post_ok=True
    schema_version=2
    source=webpilot
    mode=observed
    wind_direction_deg=65
    wind_direction_cardinal=ENE
    marine_status=fresh

Assim, o consumidor publicado em Production agora possui um device persistente seguro que serve
um payload v2 real pelo mesmo endpoint usado pela PWA.

#### Próxima e única prova restante

O usuário deve abrir o link direto de pairing temporário fornecido pelo Executor na conversa,
entrar na página `Tempo` e confirmar visualmente:

- `Estação Pecém · observação`;
- `WebPilot`;
- `65° ENE`;
- vento atual/médio/máximo;
- `Complementar / previsão` com Open-Meteo;
- `Open-Meteo Marine`;
- ausência de erro/zeros artificiais.

O link contém um `viewSecret` temporário e por isso não foi copiado para este documento.

Após confirmação:
1. remover o device temporário `smoke-a3-44d6b926`;
2. registrar a prova visual;
3. submeter o fechamento Task 5 Step 2/3 ao Revisor;
4. somente então liberar Task 6 se o Revisor registrar a liberação.

**Task 6 continua bloqueada até essa confirmação e fechamento documental.**


### A3 — E2E visual v2 confirmado pelo usuário — 2026-10-03

O usuário confirmou que a PWA publicada renderizou corretamente o cenário v2 preparado para o gate.

Evidência técnica do mesmo cenário: schema_version=2; source=webpilot; mode=observed; direção 65° ENE; marine_status=fresh.

Resultado segundo o Executor: Task 5 Step 2 SATISFEITA; Task 5 Step 3 confirmação humana SATISFEITA; Task 6 ainda não iniciada.

A Task 6 permanece bloqueada até o Revisor registrar formalmente a liberação.


### A3 — revisão final do hard rollout gate — Revisor — 2026-10-03

**Tipo:** revisão independente da evidência E2E v2 publicada após confirmação visual do usuário.
**Resultado:** hard gate funcional **SATISFEITO**; resta uma pendência operacional de limpeza antes da liberação formal da Task 6.
**Alterações feitas pelo Revisor:** nenhuma alteração de código ou produção; somente consultas read-only e este registro documental.

#### Evidência E2E aceita

A confirmação humana do usuário fecha a prova que permanecia pendente:
- PWA publicada abriu o snapshot `schema_version=2`;
- branch `V2Weather` foi exercitado de ponta a ponta;
- cenário WebPilot observado foi renderizado corretamente;
- direção `65° ENE` foi preservada;
- complementary Open-Meteo foi exibido separadamente;
- Open-Meteo Marine foi exibido separadamente;
- não houve erro/zeros artificiais relatados.

Com isso, os requisitos funcionais do Task 5 Step 2 estão atendidos:
1. v1 atual continua legível;
2. API publicada aceita v2 sintético seguro;
3. PWA publicada renderiza v2 corretamente.

A confirmação explícita do usuário também satisfaz o requisito humano do Task 5 Step 3.

#### Verificação independente de limpeza do smoke

O procedimento do Executor registrou que, após a confirmação visual, o device temporário:

    smoke-a3-44d6b926

deveria ser removido antes do fechamento.

Consulta read-only do Revisor em Production encontrou:

    devices count=1
    snapshot_schema_version=2
    mobile_installations count=1
    push_installations count=0
    tracked_vessels count=0
    maneuver_events count=0
    vessel_tracking_events count=0
    mobile_session_switches count=0

Portanto o artefato temporário de smoke **ainda existe em produção** e possui uma instalação mobile associada.

#### Classificação

**Finding operacional R3-F1 — Important — device temporário de smoke não foi limpo**

Não é falha do contrato v2 nem do rollout funcional, mas é uma pendência de higiene/segurança operacional:
- o device foi criado exclusivamente para smoke;
- possui credenciais temporárias e snapshot v2;
- não deve permanecer como identidade operacional permanente;
- o próprio procedimento E2 definiu remoção após a validação visual.

#### Critério de fechamento

Antes da Task 6:
- remover `smoke-a3-44d6b926` da produção;
- garantir remoção/cascade da instalação mobile associada;
- verificar read-only que não restou linha do device nem dependência ligada a ele;
- registrar a limpeza neste checkpoint.

#### Parecer atual

- **Gate técnico consumidores A3:** SATISFEITO.
- **Deploy Production A3:** SATISFEITO.
- **Compatibilidade v1:** SATISFEITA.
- **API publicada v2:** SATISFEITA.
- **PWA publicada v2 E2E:** SATISFEITA.
- **Task 5 Step 2 funcional:** SATISFEITA.
- **Task 5 Step 3 confirmação humana:** SATISFEITA.
- **Limpeza operacional do smoke:** PENDENTE.
- **Task 6 Desktop v2:** ainda BLOQUEADA somente por R3-F1.

Após o Executor remover o device temporário e o Revisor confirmar ausência residual, a Task 6 poderá ser formalmente liberada sem nova rodada ampla de revisão.


### A3 — correção operacional R3-F1 — Executor — 2026-10-03

**Escopo:** somente limpeza do artefato temporário de smoke exigida pelo Revisor.  
**Código/deploy:** nenhuma alteração.  
**Task 6:** não iniciada.  
**Commit/push:** não realizados.

#### R3-F1 — device temporário de smoke

Target estritamente limitado:

    smoke-a3-44d6b926

Antes da limpeza, verificação transacional confirmou:

    devices=1
    snapshot_schema_version=2
    mobile_installations=1
    push_installations=0
    tracked_vessels=0
    maneuver_events=0
    vessel_tracking_events=0
    mobile_session_switches(from)=0
    mobile_session_switches(to)=0

O registro temporário foi removido por transação administrativa com guard explícito no ID
`smoke-a3-44d6b926`.

A foreign key de `mobile_installations.device_id` possui `ON DELETE CASCADE`; após a remoção,
a mesma transação confirmou:

    devices=0
    mobile_installations=0
    push_installations=0
    tracked_vessels=0
    maneuver_events=0
    vessel_tracking_events=0
    mobile_session_switches(from)=0
    mobile_session_switches(to)=0

#### Verificação read-only independente pós-limpeza

Nova conexão ao banco, fora da transação anterior, confirmou:

    smoke_device_count=0
    smoke_mobile_installations_count=0

Devices operacionais continuam presentes e em schema v1:

    pecem-01       schema=1
    pecem-55ee08ee schema=1

Nenhum device operacional foi alterado por esta limpeza.

#### Situação após R3-F1

- Gate técnico consumidores A3: SATISFEITO;
- Deploy Production A3: SATISFEITO;
- Compatibilidade v1: SATISFEITA;
- API/PWA v2 E2E: SATISFEITA;
- Task 5 Step 2: SATISFEITA;
- Task 5 Step 3: SATISFEITA;
- R3-F1: CORRIGIDO pelo Executor;
- Task 6: ainda não iniciada.

O Revisor pode agora fazer somente a confirmação read-only de ausência residual e registrar a
liberação formal da Task 6, sem nova rodada ampla.


### A3 — fechamento final R3-F1 e liberação da Task 6 — Revisor — 2026-10-03

**Tipo:** verificação independente final, restrita à limpeza operacional pós-smoke.
**Resultado:** **APROVADA**. R3-F1 encerrado; hard rollout gate integralmente satisfeito.
**Alterações feitas pelo Revisor:** nenhuma alteração de código, banco ou deploy; somente consulta read-only e este registro documental.

#### Verificação independente pós-limpeza

Nova consulta read-only em Production confirmou:

    smoke_devices=[]
    smoke_mobile_installations=[]

Os devices operacionais permanecem presentes e em schema v1:

    pecem-01       snapshot_schema_version=1
    pecem-55ee08ee snapshot_schema_version=1

Portanto:
- o device temporário `smoke-a3-44d6b926` foi removido;
- a instalação mobile associada também foi removida;
- não houve impacto nos devices operacionais;
- a ordem consumer-first continua preservada até este checkpoint.

#### Fechamento do finding

**R3-F1 — Important operacional — ENCERRADO.**

Não há finding Critical, Important ou Minor pendente na revisão A3.

#### Estado final do hard rollout gate A3

- **Gate técnico consumidores A3:** SATISFEITO.
- **Deploy Production A3:** SATISFEITO.
- **Compatibilidade v1 real:** SATISFEITA.
- **API publicada aceitando v2 sintético:** SATISFEITA.
- **PWA publicada renderizando v2 E2E:** SATISFEITA.
- **Task 5 Step 2:** SATISFEITA.
- **Task 5 Step 3 / confirmação humana:** SATISFEITA.
- **Limpeza operacional pós-smoke:** SATISFEITA.
- **Desktop produtor continua v1 neste checkpoint:** confirmado.

### Parecer formal

**A entrada na Task 6 — Desktop produtor MobileSnapshot v2 — está LIBERADA pelo Revisor.**

Esta liberação autoriza apenas o início da Task 6 conforme o Plan 3 já aprovado.
Não autoriza automaticamente:
- commit/push;
- mudanças fora do escopo da Task 6;
- início do Plan 4/Shadow antes dos gates próprios;
- refatoração ampla.

A execução da Task 6 deve preservar o contrato v2 já validado pelos consumidores e os invariantes do Plan 3.


### A3 — Task 6 Desktop produtor MobileSnapshot v2 — Executor — 2026-10-03

**Autorização:** Task 6 formalmente LIBERADA pelo Revisor no checkpoint anterior.  
**Escopo:** somente Desktop produtor MobileSnapshot v2 conforme Plan 3.  
**Commit/push:** não realizados.  
**Task 7 / Plan 4 / Shadow:** não iniciados.

#### Condição de workspace

A árvore Desktop estava na branch:

    feat/spec025-a2-observed-weather

com A2 tecnicamente aprovada, porém ainda não commitada.

A Task 6 foi executada sobre essa mesma árvore porque o produtor v2 depende diretamente de
`WeatherComposite` e `ObservedWeather` introduzidos pela A2. Não foi criada worktree limpa para
não separar a Task 6 da base A2 aprovada ainda não materializada em commit.

#### Step 1 — RED do builder v2

O teste focado pré-alteração estava verde:

    18 passed

Foram migradas/adicionadas expectativas para:
- WebPilot fresh => primary observed + complementary Open-Meteo + Marine;
- primeiro problema WebPilot => primary stale;
- Open-Meteo fallback => primary fallback + complementary unavailable;
- ausência total => blocos unavailable;
- ausência de cookie/session/device/view secrets no payload;
- timestamps aware preservados/normalizados;
- sequence consumida somente após build bem-sucedido;
- vessel/recent_maneuvers preservados.

Primeiro RED:

    TypeError: MobileSnapshotBuilder.build() missing 1 required positional argument: 'recent_maneuvers'

Isso confirmou que o builder ainda possuía a assinatura v1
`build(snapshot, weather, marine, recent)`.

#### Step 2 — serialização MobileSnapshot v2

`src/alertam/application/mobile_snapshot.py` passou a:
- consumir `WeatherComposite`;
- emitir `schema_version=2`;
- remover completamente o campo legado `weather`;
- emitir `atmosphere.primary` WebPilot observed fresh/stale;
- emitir `atmosphere.primary` Open-Meteo fallback fresh/stale;
- emitir `atmosphere.complementary` apenas para WebPilot primary;
- emitir `marine` Open-Meteo fresh/stale ou unavailable;
- não serializar geração de sessão/cookies/segredos;
- manter vessels e recent_maneuvers;
- incrementar sequence somente após a construção integral do payload.

GREEN do builder:

    15 passed

#### Step 3 — MobileSyncCoordinator

RED após a mudança do builder:

    5 failed

As falhas mostraram os dois call sites legados ainda passando:

    weather_state.forecast
    weather_state.marine

O coordinator foi adaptado para passar diretamente:

    weather_state  # WeatherComposite

ao builder, tanto no caminho `recent_provider` quanto no caminho legado de
`RecentManeuversState`.

GREEN builder + coordinator + pipeline:

    21 passed

O teste de `runtime_recent_provider` também passou a verificar explicitamente:
- `schema_version == 2`;
- `atmosphere` unavailable quando não há dados;
- `marine` unavailable;
- ausência do campo `weather`.

#### Bootstrap

Nenhuma alteração nova de produção foi necessária em `bootstrap.py`.

A A2 já havia deixado:

    weather_provider = self.weather_coordinator.snapshot

e `WeatherCoordinator.snapshot()` retorna exatamente `WeatherComposite`.

A suíte completa encontrou um único teste legado de bootstrap ainda codificando o contrato v1:

    test_mobile_sync_schema_v1_uses_open_meteo_blocks_from_composite

Ele falhou porque o fake builder ainda exigia quatro argumentos. O teste foi migrado para provar
o contrato real v2: o coordinator entrega o `WeatherComposite` inteiro ao builder.

GREEN focado após a migração:

    27 passed

#### Step 4 — suíte Desktop

Verificação final fresca:

    uv run pytest

Resultado:

    867 passed, 78 skipped in 8.40s

`git diff --check`:

    PASS

#### Step 5 — fixture cross-repo

Foi criado pelo próprio Desktop:

    tests/fixtures/mobile_snapshot_v2_expected.json

Características observadas:
- `schema_version=2`;
- sequence determinística;
- primary source `webpilot`;
- mode `observed`;
- direção `65° ENE`.

Validação API:

    TypeAdapter(MobileSnapshot).validate_python(...)
    API_DESKTOP_V2_CONTRACT=PASS
    schema_version=2

Validação frontend com o parser real:

    parseSnapshotReadResponse(...)
    FRONTEND_DESKTOP_V2_CONTRACT=PASS

Nenhuma rede foi necessária para esse contract check.

#### Arquivos efetivamente tocados pela Task 6

Desktop:
- `src/alertam/application/mobile_snapshot.py`;
- `src/alertam/application/mobile_sync.py`;
- `tests/unit/test_mobile_snapshot.py`;
- `tests/unit/test_mobile_sync_bootstrap.py`;
- `tests/unit/test_mobile_sync_coordinator.py`;
- `tests/fixtures/mobile_snapshot_v2_expected.json`.

`src/alertam/bootstrap.py` e `tests/unit/test_mobile_sync_pipeline.py` já estavam modificados pela
A2 antes desta Task 6 e não receberam alteração nova nesta rodada.

#### Estado para revisão

- Task 6 implementação: concluída pelo Executor;
- focused: PASS;
- Desktop full: 867 passed / 78 skipped;
- API contract com fixture Desktop: PASS;
- frontend contract com fixture Desktop: PASS;
- diff-check: PASS;
- commit/push: NÃO realizados;
- Task 7: NÃO iniciada;
- Plan 4/Shadow: NÃO iniciado.

Solicita-se revisão independente restrita à Task 6 antes de qualquer avanço.


### A3 — Task 6 Desktop produtor v2 — revisão R1 — Revisor — 2026-10-03

**Tipo:** revisão independente restrita à Task 6.
**Resultado:** correções requeridas antes de liberar a Task 6.
**Alterações feitas pelo Revisor:** nenhuma alteração de código; somente reproduções read-only/testes e este registro documental.

#### Findings

**Critical:** nenhum.

#### R1-F1 — Important — builder aceita WeatherComposite inconsistente e consome sequence

**Local:** `src/alertam/application/mobile_snapshot.py:154-196,250-287`.

O Plan 3 exige explicitamente que o Desktop não publique v2 parcialmente construído nem consuma
`sequence` quando o `WeatherComposite` for inconsistente.

Reprodução independente com composite contraditório:
- `primary.status=UNAVAILABLE`;
- mas `source=WEBPILOT`, `mode=OBSERVED` e `observed` preenchidos;
- `marine_status=FRESH` com `marine=None`.

Resultado atual:

    bad_build=ACCEPTED
    sequence=1
    atmosphere={'primary': {'status': 'unavailable'}, 'complementary': {'status': 'unavailable'}}
    marine={'status': 'unavailable'}
    next_sequence=2

Ou seja, o builder normaliza silenciosamente estados impossíveis para `unavailable` e considera o
build bem-sucedido.

**Impacto:**
- mascara regressões do `WeatherCoordinator`;
- consome sequence apesar de input internamente inválido;
- pode publicar um snapshot semanticamente diferente do estado recebido.

**Critério de correção:**
- validar as invariantes do `WeatherComposite` antes de montar/consumir sequence;
- rejeitar combinações impossíveis de status/source/mode/data;
- validar coerência forecast/status e marine/status;
- provar por teste que composite inconsistente levanta erro e que o próximo build válido mantém
  `sequence=1`.

**Resposta do Executor:** _pendente_.

#### R1-F2 — Important — recent_maneuvers não possui whitelist e pode carregar material proibido

**Local:** `src/alertam/application/mobile_snapshot.py:289-309`.

`_recent_payload()` faz:

    item = dict(raw)

e preserva qualquer chave extra recebida.

Reprodução independente com um maneuver contendo:
- `cookie`;
- `session_generation`;
- `html`.

Resultado:

    contains_cookie=True
    contains_session_generation=True
    contains_html=True

O payload produzido pelo Desktop contém esses campos. A validação Pydantic da API rejeita depois:

    api_contract=REJECTED
    first_error_type=extra_forbidden
    first_error_loc=(2, 'recent_maneuvers', 'active', 0, 'cookie')

**Impacto:**
- viola a regra de segurança da SPEC 025 de que MobileSnapshot v2 nunca contém cookie,
  session_generation, headers/HTML/credenciais;
- a API ser estrita não é proteção suficiente, pois o Desktop já serializou e pode tentar transmitir
  o material antes da rejeição.

**Critério de correção:**
- construir cada maneuver por whitelist explícita dos campos do contrato:
  `id,type,vessel_name,berth,pob,status,detected_at,completed_at`;
- não copiar chaves arbitrárias do mapping de origem;
- adicionar teste negativo com campos proibidos provando que não aparecem no payload final.

**Resposta do Executor:** _pendente_.

#### Pontos aprovados

- `schema_version=2` é emitido;
- campo legado `weather` foi removido do v2;
- WebPilot fresh/stale, fallback Open-Meteo, complementary e Marine estão mapeados corretamente
  nos cenários válidos;
- `MobileSyncCoordinator` passa `WeatherComposite` integral ao builder;
- bootstrap já fornece `weather_coordinator.snapshot`;
- vessels/recent_maneuvers contratuais permanecem preservados;
- timestamps são normalizados para aware ISO;
- fixture Desktop v2 passa no contrato Pydantic da API;
- a mesma fixture passa no parser real do frontend;
- não houve expansão para Task 7/Plan 4/Shadow.

#### Gates independentes

- focused Desktop Task 6: **27 passed**;
- Desktop full: **867 passed, 78 skipped**;
- imports: **imports OK 95**;
- `git diff --check`: PASS;
- fixture cross-repo API: PASS;
- fixture cross-repo frontend: PASS.

#### Parecer

- **Task 6: NÃO liberada tecnicamente nesta R1.**
- Corrigir somente R1-F1 e R1-F2.
- Depois realizar R2 independente focada nesses dois findings e repetir os gates relevantes.
- Task 7 e Plan 4/Shadow permanecem bloqueados.
- Commit/push continuam dependentes de autorização explícita do usuário.


### A3 — Task 6 correção R1 — Executor — 2026-10-03

**Escopo:** somente R1-F1 e R1-F2 registrados pelo Revisor.  
**Task 7 / Plan 4 / Shadow:** não iniciados.  
**Commit/push:** não realizados.

#### R1-F1 — validação fail-closed de WeatherComposite

O finding foi reproduzido antes da correção.

Foram adicionados testes negativos para quatro classes de inconsistência:

1. primary `UNAVAILABLE` carregando `WEBPILOT/OBSERVED` e dados observados;
2. `forecast_status=FRESH` com `forecast=None`;
3. `marine_status=FRESH` com `marine=None`;
4. fallback Open-Meteo com `primary.status` divergente de `forecast_status`.

RED:

    4 casos DID NOT RAISE ValueError

A correção foi restrita a
`src/alertam/application/mobile_snapshot.py`.

O builder agora valida, antes de montar payload e antes de calcular/consumir sequence:

- coerência `forecast <-> forecast_status`;
- coerência `marine <-> marine_status`;
- primary unavailable sem source/mode/observed/forecast e sem forecast composto;
- WebPilot primary somente `source=WEBPILOT + mode=OBSERVED + observed presente + forecast primário ausente`;
- Open-Meteo fallback somente `source=OPEN_METEO + mode=FALLBACK + forecast presente + observed ausente`;
- fallback exige `primary.status == forecast_status`;
- fallback exige que `primary.forecast` corresponda ao forecast do composite;
- qualquer outra combinação source/mode é rejeitada.

O teste também prova que, após cada build inválido, o próximo build válido recebe:

    sequence=1

Portanto composite inconsistente não é normalizado silenciosamente e não consome sequence.

#### R1-F2 — whitelist explícita de recent_maneuvers

O finding também foi reproduzido antes da correção.

Foi injetada uma manobra contendo:

    cookie
    session_generation
    html

RED confirmou que as três chaves apareciam no payload final.

`_recent_payload()` deixou de executar:

    item = dict(raw)

e agora constrói cada item exclusivamente pelas chaves contratuais:

    id
    type
    vessel_name
    berth
    pob
    status
    detected_at
    completed_at

Os timestamps continuam normalizados pelo builder.

GREEN prova:
- conjunto exato de oito chaves;
- ausência de `cookie`;
- ausência de `session_generation`;
- ausência de HTML arbitrário.

#### RED → GREEN focado

Antes da produção:
- R1-F1: 4 falhas esperadas por ausência de `ValueError`;
- R1-F2: 1 falha esperada por extras no payload.

Após as correções:

    tests/unit/test_mobile_snapshot.py
    20 passed

Gate focado Task 6:

    tests/unit/test_mobile_snapshot.py
    tests/unit/test_mobile_sync_coordinator.py
    tests/unit/test_mobile_sync_pipeline.py
    tests/unit/test_mobile_sync_bootstrap.py

Resultado:

    32 passed

#### Gates pós-correção

Executado:

    make check

Resultado:

    872 passed, 78 skipped
    imports OK

Contagem independente de módulos importados:

    imports OK 95

Cross-repo Desktop fixture:

    API_DESKTOP_V2_CONTRACT=PASS
    FRONTEND_DESKTOP_V2_CONTRACT=PASS

`git diff --check`:

    PASS

#### Arquivos alterados nesta rodada R1

Somente:
- `src/alertam/application/mobile_snapshot.py`;
- `tests/unit/test_mobile_snapshot.py`.

Observação: qualquer `git diff --stat` desses arquivos contra HEAD inclui também a implementação
Task 6 anterior, pois A2/Task 6 permanecem intencionalmente sem commit. Não interpretar o stat
acumulado como tamanho exclusivo desta correção R1.

#### Situação

- R1-F1: CORRIGIDO pelo Executor;
- R1-F2: CORRIGIDO pelo Executor;
- Task 6: aguardando R2 independente;
- Task 7: bloqueada;
- Plan 4/Shadow: bloqueado;
- commit/push: não realizados.

Solicita-se R2 independente restrita aos dois findings e repetição dos gates relevantes.


### A3 — Task 6 Desktop produtor v2 — re-review R2 — Revisor — 2026-10-03

**Tipo:** re-revisão independente focada em R1-F1, R1-F2 e gates da Task 6.
**Resultado:** **APROVADA TECNICAMENTE**. R1-F1 e R1-F2 resolvidos; nenhum novo finding identificado.
**Alterações feitas pelo Revisor:** nenhuma alteração de código; somente reproduções/testes e este registro documental.

#### Verificação independente de R1-F1

Reprodução do mesmo cenário contraditório da R1:

- primary `UNAVAILABLE` carregando source/mode WebPilot observed e objeto `ObservedWeather`;
- `marine_status=FRESH` com `marine=None`.

Resultado atual:

    bad_build=REJECTED ValueError
    next_sequence=1

Conclusão:
- o builder agora falha closed para composite inconsistente;
- não normaliza silenciosamente o estado inválido;
- o build inválido não consome sequence;
- o build válido seguinte preserva `sequence=1`.

A validação roda antes da serialização e antes do incremento de sequence.

**R1-F1 — Important — ENCERRADO.**

#### Verificação independente de R1-F2

Foi repetida a injeção de campos extras em um item de `recent_maneuvers`, incluindo:
- `cookie`;
- `session_generation`;
- `html`;
- uma chave extra arbitrária.

Resultado produzido pelo Desktop:

    keys=['berth','completed_at','detected_at','id','pob','status','type','vessel_name']
    cookie=False
    session_generation=False
    html=False
    extra_probe=False

O payload sanitizado foi validado diretamente contra o contrato Pydantic da API:

    api_sanitized_contract=PASS
    schema_version=2

Conclusão:
- `recent_maneuvers` agora é serializado por whitelist explícita;
- chaves arbitrárias/proibidas não entram no MobileSnapshot;
- o resultado permanece contratualmente válido para a API.

**R1-F2 — Important — ENCERRADO.**

#### Gates conferidos na R2

- focused Task 6:
  - `test_mobile_snapshot.py`;
  - `test_mobile_sync_coordinator.py`;
  - `test_mobile_sync_pipeline.py`;
  - `test_mobile_sync_bootstrap.py`;
  - resultado: **32 passed**;
- `make check`: **872 passed, 78 skipped**;
- imports: **imports OK 95**;
- `git diff --check`: PASS;
- fixture Desktop v2 -> API Pydantic: **PASS**;
- fixture Desktop v2 -> frontend `parseSnapshotReadResponse`: **PASS**;
- busca negativa: nenhuma expansão para Task 7/Plan 4/Shadow;
- nenhum commit/push foi realizado pelo Revisor.

#### Parecer

- não há finding Critical, Important ou Minor pendente nesta revisão;
- **Task 6 — Desktop produtor MobileSnapshot v2: LIBERADA TECNICAMENTE pelo Revisor**;
- contrato v2 do Desktop permanece compatível com API/PWA já publicados;
- invariantes de sequence e whitelist de segurança estão satisfeitas.

#### Próximo gate do Plan 3

O próximo passo previsto é a **Task 7 — validação manual PWA/iOS após rollout real**.

Ela deve validar com feedback humano:
- labels das fontes;
- estados stale/unavailable;
- valores observados WebPilot;
- fallback Open-Meteo;
- bloco Marine;
- mapas/manobras existentes continuam funcionando.

A Task 7 não está automaticamente concluída por esta R2.

**Plan 4/Shadow permanece bloqueado até a Task 7 ser executada e registrada.**
**Commit/push continuam dependentes de autorização explícita do usuário.**

### A3 — materialização autorizada em commits — Executor — 2026-10-04

**Autorização:** usuário autorizou finalizar/materializar a A3 aprovada em commits na branch `feat/spec025-a3-mobile-snapshot-v2`, excluindo `docs/superpowers/strategy/` e qualquer alteração preexistente fora do escopo.

#### Commit de implementação

    919dc16 feat: materializa consumidores MobileSnapshot v2 da A3

Conteúdo materializado:
- modelos/serviços/endpoints API v1+v2;
- contrato discriminado v1|v2;
- roundtrip/persistência compatível;
- contrato TypeScript/Zod v1|v2;
- projeções/mapa em campos compartilhados;
- WeatherPage v2;
- fixtures e testes A3 correspondentes.

Exclusões deliberadas do commit:
- `docs/superpowers/strategy/`;
- SPEC/Planos antigos já sujos antes da A3;
- handoff de provisioning preexistente;
- `specs/027-alertam-cloud-continuity.md`;
- demais alterações não pertencentes à A3.

#### Gates frescos imediatamente antes da materialização

- API, executado da raiz com `make test`: PASS, exit 0, `-W error`;
- frontend: **48 arquivos / 273 testes passed**;
- `npm run build`: PASS;
- `git diff --check` no escopo A3: PASS;
- busca negativa no staged set: nenhum arquivo proibido incluído.

#### Próximo passo autorizado

1. materializar este checkpoint documental;
2. mergear A3 em `feat/api-bootstrap`;
3. rodar gates completos pós-merge;
4. push/deploy;
5. validar produção aceitando v1+v2;
6. somente após produção confirmada iniciar forward-port da hotfix sobre a nova base A3.

A hotfix `hotfix/pwa-acompanhamentos-fundeio` permanece intocada até a confirmação de produção A3.
