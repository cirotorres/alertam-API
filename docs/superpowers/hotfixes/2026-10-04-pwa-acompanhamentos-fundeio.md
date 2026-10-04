# Hotfix — PWA Acompanhamentos + notificações de fundeio

**Data:** 2026-10-04  
**Status:** implementação local concluída; aguardando revisão independente.  
**Branch:** `hotfix/pwa-acompanhamentos-fundeio`  
**Base:** `origin/feat/api-bootstrap` em `c000307 fix: oculta footer em gavetas`  
**Worktree:** `/home/ciro/dev/prog/alertamaritimoAPI-hotfix-pwa-acompanhamentos-fundeio`  
**Commit/push/deploy:** NÃO realizados.  
**Migration 017 em produção:** NÃO aplicada.

## 1. Escopo aprovado

Esta hotfix foi solicitada antes da retomada do Plano 3 e permanece isolada da árvore A3/SPEC 025.

### 1.1 Acompanhamentos não visualizados

- Linha da página `Acompanhados` deve ficar destacada quando houver alteração nova daquele navio ainda não visualizada.
- O estado deve sobreviver a fechar/reabrir o PWA.
- Abrir aquele acompanhamento específico marca somente aquele navio como lido.
- A primeira ativação não deve transformar histórico antigo em não lido.

### 1.2 Conclusões — comportamento preservado

O usuário determinou explicitamente que a hotfix **não altere** a regra atual:

- `Conclusões = ON`: conclusão de qualquer navio pode notificar.
- `Conclusões = OFF`: conclusão de navio não acompanhado não notifica.
- Navio em `Acompanhando` continua podendo notificar conclusão mesmo com a opção geral desligada.

A hotfix apenas adiciona testes de regressão para congelar essa semântica.

### 1.3 Entradas no fundeio

Nova preferência independente, **ON por padrão**.

Notificar quando o navio passa a integrar a seção `FUNDEADO`:
- `PREVISTO -> FUNDEADO`;
- `ATRACADO/DESATRACANDO -> FUNDEADO`;
- qualquer outra seção -> `FUNDEADO`;
- navio ausente no snapshot anterior que aparece agora em `FUNDEADO`.

Não repetir em `FUNDEADO -> FUNDEADO`. Se sair e depois voltar, a nova entrada volta a ser elegível.

O primeiro snapshot sem predecessor é baseline silenciosa.

O critério usa **`section == "FUNDEADO"`**, coerente com a lista/aba Fundeados do PWA.

## 2. Isolamento

A árvore principal estava em `feat/spec025-a3-mobile-snapshot-v2` com A3 não commitada.

Foi criado worktree separado:

```text
/home/ciro/dev/prog/alertamaritimoAPI-hotfix-pwa-acompanhamentos-fundeio
```

Branch:

```text
hotfix/pwa-acompanhamentos-fundeio
```

Base:

```text
origin/feat/api-bootstrap
c000307 fix: oculta footer em gavetas
```

Nenhum commit ou push foi realizado.

## 3. Acompanhamentos não lidos

### Estratégia

O feed de tracking existente foi mantido. O PWA persiste localmente, por **device + installation**:

- último cursor processado;
- conjunto de `tracked_vessel_id` ainda não visualizados.

Chave:

```text
alertam.mobile.tracking.unread.v1:<deviceId>:<installationId>
```

Quando não existe cursor salvo, o primeiro poll continua sendo baseline e apenas registra o cursor atual.

Quando existe cursor salvo, o primeiro poll usa `after=<cursor>`, inclusive após o PWA ter ficado fechado, e acumula os IDs dos navios alterados.

Na lista:
- linha não lida recebe `.is-unread`;
- há fundo/borda/stripe de destaque;
- abrir a linha remove somente aquele ID;
- deep-link direto daquele acompanhamento também marca como lido.

### TDD

RED observado:
- cursor salvo era ignorado;
- linha não recebia `.is-unread`;
- Provider permanecia `read` após receber evento posterior ao cursor.

GREEN focado:
- `useTrackingPolling.test.tsx`: 5 passed;
- `TrackingProvider.test.tsx`: 6 passed;
- `TrackedVesselsPage.test.tsx`: 4 passed.

Gate frontend focado posterior: **51 passed**.

## 4. Conclusões preservadas

Nenhuma lógica de produção do `PushDispatchService` foi alterada para este item.

Foram adicionados testes para:

1. `completed=true` + navio não acompanhado -> envia;
2. `completed=false` + navio não acompanhado -> não envia;
3. `completed=false` + acompanhamento ativo -> envia via deep-link do acompanhamento.

Uma primeira versão do teste reutilizava o mesmo `event_id` de um `CONFIRMED`, produzindo falso negativo. O helper foi corrigido para criar o tipo correto desde o início; não houve correção de produção.

Com os testes de fundeio no mesmo arquivo:

```text
tests/unit/test_push_dispatch_service.py
21 passed
```

## 5. Detecção de entrada no fundeio

Novo módulo:

```text
api/app/services/anchorage_entry.py
```

`detect_anchorage_entries(...)` compara o snapshot aceito com o último snapshot persistido.

Regras:
- sem predecessor -> zero eventos;
- current fora de `FUNDEADO` -> ignora;
- previous já `FUNDEADO` -> ignora;
- previous em outra seção -> gera entrada;
- vessel ausente no previous -> gera entrada;
- identidade prioriza IMO, com fallback controlado por nome normalizado.

O `event_id` é UUID5 determinístico com device, boot, sequence e identidade do navio.

## 6. Integração com POST de snapshot

`SnapshotService` lê o snapshot anterior antes do aceite atômico.

Somente `AcceptSnapshotStatus.ACCEPTED` executa a detecção.

`IDEMPOTENT` não redispara, portanto retry do mesmo snapshot não duplica notificação.

Falha no dispatch pós-persistência é isolada/logada e não transforma snapshot já aceito em erro HTTP.

Integração validada:
- baseline PREVISTO: 0 eventos;
- snapshot seguinte FUNDEADO: 1 evento;
- retry idempotente: continua 1 evento.

```text
tests/integration/test_post_snapshot.py
10 passed
```

## 7. Web Push de fundeio

Foi adicionado `AnchoragePushDispatchService`.

Elegibilidade:
- instalação ativa;
- evento posterior ao opt-in;
- `preferences.anchored == true`;
- respeita a supressão de foreground existente (75 s por padrão).

Payload:

```text
title = "Entrada no fundeio"
body  = "<NAVIO> · Fundeado"
url   = "/"
```

Falha permanente desativa somente a instalação afetada.

### Limitação conhecida

Esta hotfix **não cria uma tabela nova de delivery/retry persistente para fundeio**. Uma falha transitória do provedor Web Push nessa categoria é best-effort.

Isso foi mantido assim para não transformar a hotfix em um novo subsistema persistido de eventos. O Revisor deve decidir explicitamente se essa limitação é aceitável.

## 8. Preferência `anchored`

Nova flag:

```text
anchored: boolean
```

Rótulo:

```text
Entradas no fundeio
```

Default: `true`.

Propagada por:
- Pydantic;
- `PushPreferences`;
- service de instalação/preferências;
- endpoint;
- Memory/Postgres/Supabase;
- cliente TypeScript;
- `PushProvider`;
- ConfigPage.

## 9. Compatibilidade com instalações existentes

### localStorage

Estados antigos possuem somente quatro flags.

Na leitura:

```text
anchored ausente -> anchored=true
```

sem apagar o opt-in salvo.

Teste: `legacy_four_flag_snapshot_defaults_anchorage_on`.

### Supabase

Migration nova:

```text
api/supabase/migrations/017_anchorage_notifications.sql
```

Adiciona:

```sql
pref_anchored boolean not null default true
```

e uma **sobrecarga nova** de `update_push_preferences` com `p_anchored`.

A assinatura antiga de quatro flags **não é removida**. Isso permite aplicar a migration antes do deploy:
- API antiga continua chamando o RPC antigo;
- API nova usa a assinatura nova.

A nova assinatura é revogada de `public/anon/authenticated` e concedida somente a `service_role`.

### Postgres

A coluna adicionada por `ALTER TABLE` fica fisicamente no fim da tabela. Para a implementação nova não depender dessa ordem, `upsert/update/touch/get/list` usam seleção explícita na ordem do mapper, incluindo `pref_anchored`.

## 10. RED -> GREEN principal

### Não lidos
- esperado `after=5`; código antigo fazia baseline;
- esperado `.is-unread`; classe ausente;
- esperado `unread`; Provider retornava `read`.

### Detecção/preferência
Antes da implementação:
- 5 testes falharam porque `SnapshotService` não aceitava callback de fundeio;
- preferência falhou porque `PushPreferences` não tinha `anchored`;
- frontend falhou porque parser/config não conheciam a quinta opção.

### Dispatcher
- 4 testes falharam exclusivamente pela ausência de `AnchoragePushDispatchService`.

### Compatibilidade local
- estado legado de quatro flags retornava `null`; após a correção retorna flags antigas + `anchored=true`.

## 11. Evidências

### Baseline antes da hotfix

Frontend focado:

```text
17 passed
```

API focada:

```text
25 passed
```

### Focados finais

Frontend tracking/push/config:

```text
6 test files passed
51 tests passed
```

Push dispatcher:

```text
21 passed
```

Persistência/preferências:

```text
22 passed
```

POST snapshot:

```text
10 passed
```

Migration/Supabase pós-ajuste de retrocompatibilidade:

```text
12 passed
```

### Gates completos

API:

```text
441 passed, 34 skipped
```

Frontend:

```text
48 test files passed
269 tests passed
```

Build:

```text
npm run build
PASS
PWA service worker gerado
```

Diff:

```text
git diff --check
PASS
```

`npm ci` reportou 2 vulnerabilidades moderadas já presentes nas dependências travadas. Não foi executado `npm audit fix`; nenhuma atualização de dependência faz parte desta hotfix.

## 12. Arquivos principais

### Backend
- `api/app/services/anchorage_entry.py` — novo;
- `api/app/services/snapshot_service.py`;
- `api/app/services/push_dispatch_service.py`;
- `api/app/services/push_installation_service.py`;
- `api/app/models/push.py`;
- `api/app/repositories/events.py`;
- `api/app/repositories/postgres.py`;
- `api/app/repositories/supabase.py`;
- `api/app/api/v1/push.py`;
- `api/app/api/v1/snapshots.py`;
- `api/app/api/v1/router.py`;
- `api/app/main.py`;
- `api/supabase/migrations/017_anchorage_notifications.sql`.

### Frontend
- `frontend/src/features/tracking/trackingUnreadStorage.ts` — novo;
- `frontend/src/features/tracking/useTrackingPolling.ts`;
- `frontend/src/features/tracking/TrackingProvider.tsx`;
- `frontend/src/pages/TrackedVesselsPage.tsx`;
- `frontend/src/styles/app.css`;
- `frontend/src/api/pushClient.ts`;
- `frontend/src/features/push/PushProvider.tsx`;
- `frontend/src/features/push/pushPreferenceStorage.ts`;
- `frontend/src/pages/ConfigPage.tsx`;
- `frontend/src/app/App.tsx`.

Testes correspondentes foram atualizados/adicionados.

## 13. Estado de rollout

- hotfix branch local: SIM;
- implementação: SIM;
- migration criada: SIM;
- migration aplicada em produção: **NÃO**;
- commit: **NÃO**;
- push: **NÃO**;
- merge em `feat/api-bootstrap`: **NÃO**;
- deploy: **NÃO**.

## 14. Ordem após aprovação

**Não executar antes do parecer do Revisor.**

1. Revisor aprova a hotfix.
2. Aplicar `017_anchorage_notifications.sql` em produção.
3. Confirmar schema/RPC read-only.
4. Commit da hotfix.
5. Push de `hotfix/pwa-acompanhamentos-fundeio`.
6. Merge em `feat/api-bootstrap`.
7. Push de `feat/api-bootstrap` para deploy automático.
8. Smoke pós-deploy:
   - quinta opção aparece ON;
   - evento novo de acompanhamento destaca a linha e abrir limpa;
   - Conclusões mantém os três cenários;
   - entrada controlada em FUNDEADO gera push com opção ON;
   - opção OFF silencia a categoria.

## 15. Pedido ao Revisor

Revisar somente esta hotfix, com atenção a:

1. cursor/persistência dos não lidos e ausência de replay histórico;
2. marcação de lido somente no acompanhamento aberto;
3. preservação da semântica de `Conclusões`;
4. `qualquer seção -> FUNDEADO` e vessel novo/retornado;
5. idempotência do POST snapshot;
6. default/migração de `anchored=true`;
7. retrocompatibilidade do RPC durante rollout;
8. adapters Postgres/Supabase;
9. aceitabilidade da limitação best-effort em falha Web Push transitória;
10. gates completos e escopo.

**Nenhuma etapa de migration/commit/push/merge/deploy deve ocorrer antes do parecer do Revisor.**


## 16. Revisão independente R1 — Revisor — 2026-10-04

**Tipo:** revisão independente de código, testes, migration e plano de rollout.  
**Resultado:** implementação funcional da hotfix está consistente, porém **NÃO liberada para merge/deploy** por blocker de integração com A3/MobileSnapshot v2.  
**Alterações feitas pelo Revisor:** nenhuma alteração de código; somente testes/read-only e este registro documental.

### 16.1 Finding R1-F1 — Critical — pipeline proposto rebaixa consumidores A3 para v1-only

A hotfix está baseada em:

    c000307 fix: oculta footer em gavetas
    branch hotfix/pwa-acompanhamentos-fundeio

Essa base contém somente o contrato legado:

    API:      MobileSnapshotV1 / schema_version Literal[1]
    frontend: schema_version z.literal(1)

Reprodução independente usando o fixture v2 aprovado da A3:

    hotfix_accepts_v2=False
    first_error_type=literal_error
    first_error_loc=('schema_version',)

Portanto a branch hotfix, como está hoje, **não aceita nem renderiza MobileSnapshot v2**.

O passo 6/7 do plano atual propõe:

    merge -> feat/api-bootstrap
    push -> deploy automático

Esse fluxo não é seguro após a evolução já aprovada da A3/Task 6. Um deploy dessa árvore manteria/reintroduziria consumidores v1-only e, quando o Desktop produtor v2 for publicado, o POST de snapshots v2 será rejeitado.

#### Evidência externa read-only

O deployment atualmente servido em Production foi inspecionado:

    id=dpl_GPF8qGcBw2kPCGZ3b96LhGzePynW
    target=production
    readyState=READY
    aliases incluem alertam-api-git-feat-api-bootstrap-...

O bundle atualmente servido contém a cópia legada:

    "Condições meteorológicas e marítimas recebidas do AlertaM Desktop via API Open-Meteo."

e não contém os marcadores A3:

    "Estação Pecém · observação"
    "Open-Meteo · fallback/modelo"

Isso indica que o deployment Git atual já está novamente na linha v1-only de `feat/api-bootstrap`.
Esse estado operacional não foi causado por esta hotfix, mas torna obrigatório reconciliar a linha A3 antes de qualquer rollout posterior do Desktop v2.

#### Critério de correção

Antes de merge/push/deploy desta hotfix:

1. materializar/reconciliar a base aprovada A3 v1+v2 com a linha de produção Git;
2. portar/rebasear esta hotfix sobre uma base que preserve:
   - API `MobileSnapshot = v1 | v2`;
   - GET/POST v1+v2;
   - tratamento de schema desconhecido da A3;
   - contrato Zod v1+v2;
   - `WeatherPage` v1+v2;
3. adaptar a detecção de fundeio para trabalhar com o contrato compartilhado de vessels sem reduzir o endpoint novamente a `MobileSnapshotV1`;
4. rerodar gates da hotfix + gates A3 de regressão;
5. somente depois definir a branch que disparará o deploy automático.

**R1-F1: BLOCKER.**

### 16.2 Áreas funcionais aprovadas nesta R1

#### Acompanhamentos não visualizados

A estratégia foi considerada coerente:
- cursor persistido por `deviceId:installationId`;
- primeiro poll sem cursor é baseline e não cria replay histórico;
- cursor salvo retoma com `after=<cursor>`;
- páginas cheias são drenadas em sequência;
- IDs alterados são acumulados em `unreadTrackedVesselIds`;
- abrir uma linha remove somente aquele `tracked_vessel_id`;
- deep-link aberto também marca aquele acompanhamento como lido;
- persistência é best-effort local sem quebrar a UI.

Não foi identificado finding funcional nesse bloco.

#### Conclusões

A produção de `PushDispatchService` não foi alterada para mudar a regra.
Os testes congelam corretamente:
- geral ON + não acompanhado => envia;
- geral OFF + não acompanhado => não envia;
- geral OFF + acompanhado ativo => envia via deep-link do acompanhamento.

Sem finding.

#### Entrada no fundeio

A detecção atende o escopo sequencial normal:
- primeiro snapshot sem predecessor é silencioso;
- qualquer seção diferente de FUNDEADO -> FUNDEADO gera entrada;
- vessel novo que aparece FUNDEADO gera entrada;
- FUNDEADO -> FUNDEADO não repete;
- saída e retorno voltam a ser elegíveis;
- retry idempotente do mesmo snapshot não redispara;
- identidade prioriza IMO com fallback de nome.

O produtor Desktop oficial publica snapshots em uma única thread latest-only, portanto a leitura do predecessor antes do aceite atômico não foi classificada como blocker para o fluxo oficial.

#### Preferência anchored e migration 017

A implementação foi considerada coerente:
- default `anchored=true`;
- localStorage legado de quatro flags migra para `anchored=true`;
- Pydantic/API/frontend propagam a quinta opção;
- migration adiciona `pref_anchored boolean not null default true`;
- nova sobrecarga de `update_push_preferences` não remove a assinatura antiga;
- privilégios da nova assinatura ficam restritos a `service_role`;
- Postgres usa seleção explícita compatível com a coluna adicionada no fim;
- Supabase mapeia por nome.

### 16.3 Decisão sobre best-effort de fundeio

A ausência de tabela própria de delivery/retry para a categoria de fundeio é **aceitável nesta hotfix**, com dívida explicitamente documentada.

Consequência aceita:
- falha transitória do provedor, interrupção entre persistência do snapshot e envio ou outro erro não permanente pode perder aquela notificação;
- o próximo snapshot FUNDEADO -> FUNDEADO não recria o evento.

Isso significa **at-most-once / best-effort**, não entrega garantida.
Não deve ser descrito futuramente como push durável/exatamente uma vez.

A decisão é aceitável para manter a hotfix pequena; se confiabilidade de entrega dessa categoria se tornar requisito operacional, deverá migrar para um evento/delivery persistente.

### 16.4 Comportamento de push para navio acompanhado

Um navio acompanhado que entra em FUNDEADO pode ser elegível para:
- push de acompanhamento (mudança do tracking);
- push geral de entrada no fundeio, se `anchored=true`.

Não há deduplicação entre as duas categorias.
Isso foi considerado consequência compatível com o escopo atual, pois são preferências/categorias independentes e o usuário pediu que entradas em fundeio também notifiquem.

### 16.5 Gates independentes

Executados pelo Revisor:

- API completa `make test` com `-W error`: **PASS**;
- frontend completo: **48 arquivos / 269 testes passed**;
- PWA/TypeScript build: **PASS**;
- migration/adapters focados: **9 passed**;
- snapshot/push hotfix focado: **56 passed**;
- `git diff --check`: **PASS**.

Warning React `act(...)` em `AppShell.test.tsx` permanece warning preexistente e não foi classificado como finding desta hotfix.

### 16.6 Parecer R1

- **Código funcional da hotfix:** APROVADO nos três objetivos solicitados.
- **Migration 017 isoladamente:** tecnicamente coerente.
- **Plano de merge/deploy descrito na seção 14:** NÃO APROVADO.
- **Hotfix como pacote para produção:** BLOQUEADA por R1-F1.

Nenhuma migration, commit, push, merge ou deploy deve ser executado com a sequência atual.

Próxima ação do Executor:
- reconciliar/forward-portar a hotfix sobre a linha A3 v1+v2 aprovada;
- atualizar este documento com a nova base e estratégia de rollout;
- submeter a árvore integrada a uma R2 focada em R1-F1 + regressão A3/hotfix.

