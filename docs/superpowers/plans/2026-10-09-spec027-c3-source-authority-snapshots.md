# SPEC 027 — C3-P: Source Authority, Snapshot Fencing e Failover/Failback Controlado

**Status:** PLANEJAMENTO SOMENTE — R9-F1..F4 CORRIGIDOS; PRONTO PARA R9.1 INDEPENDENTE; C3 não iniciado.
**Data:** 2026-10-09
**Base API/PWA/Cloud:** `feat/spec027-cloud@b991ffb16d110c617c7c4bc90a842cc9abc22059` — `test(cloud): close c2 multi-provider standby`
**Base Desktop:** `feat/spec027-cloud@c8191bfea696368a7698a08bea727811412c05fd` — `feat(cloud): publish webpilot session leases`
**Repositório coordenador:** `/home/ciro/dev/prog/alertamaritimoAPI/.worktrees/spec027-cloud`
**Desktop:** `/home/ciro/dev/prog/alertamaritimo/.worktrees/spec027-cloud`
**Autoridade documental:** SPEC 027, roadmap Cloud, handoff central, C2-P e fechamento R8.1.

---

## 1. Objetivo exato do C3

C3 transforma o collector Cloud validado em C2, hoje estritamente standby, em uma **futura** fonte de continuidade de snapshot controlada por autoridade persistente, fencing e hysteresis.

C3 deve provar tecnicamente, em sandbox e PostgreSQL real, que:

1. Desktop saudável continua preferencial;
2. Cloud só pode publicar depois de todos os gates de autorização, auth, freshness, persistência e hysteresis;
3. somente um writer é autoritativo por `device_id`;
4. writer antigo nunca volta a escrever depois de perder autoridade;
5. failover/failback são transações de autoridade, não comparação de timestamps;
6. restart de API/Cloud/Desktop não apaga a verdade de autoridade;
7. `enabled=false` e revogações administrativas vencem qualquer source lease;
8. PWA continua lendo apenas o último snapshot autoritativo, sem novo pareamento;
9. Cloud v1 continua **sem eventos/push**;
10. nenhuma ativação real em produção acontece apenas porque C3 foi implementado/testado.

Este plano **não autoriza implementação C3**. A implementação só pode começar após R9 independente.

---

## 2. Estado atual verificado que condiciona o desenho

### 2.1 Snapshot atual

A API mantém um único snapshot atual na linha `devices`:

- `snapshot`;
- `snapshot_schema_version`;
- `boot_id`;
- `sequence`;
- `generated_at`;
- `received_at`.

O Desktop publica em:

`POST /api/v1/devices/{device_id}/snapshot`

com autenticação `Device`.

O RPC atual `accept_device_snapshot` serializa a escrita por `device_id` e protege apenas:

- mesma `boot_id`;
- `sequence` crescente;
- retry idempotente;
- reuse mismatch.

Ele **não possui source authority/fencing cross-source**. Se o `boot_id` mudar, o contrato atual aceita o novo boot como nova sequência; isso é insuficiente para Desktop × Cloud.

### 2.2 Cadência e freshness existentes

- coleta Desktop: default 60 s;
- snapshot Mobile é emitido a cada ciclo de coleta quando Mobile Sync está configurado;
- API/PWA considera o snapshot online enquanto `age_seconds < 120`;
- `received_at` é server-side e já é a referência de freshness do Mobile.

C3 deve preservar o significado atual de `collector_online`: idade do **último snapshot autoritativo aceito**, independentemente de ele ter vindo de Desktop ou Cloud.

### 2.3 Mobile/PWA atual é strict

O frontend usa Zod `.strict()` tanto no `MobileSnapshot` quanto no `SnapshotMeta`.

Consequência arquitetural obrigatória:

> **C3 v1 não adicionará `source`, epoch, fencing ou authority fields ao JSON retornado pelo GET de snapshot atual.**

Adicionar campo ao `meta` quebraria clientes PWA já instalados/cached.

A metadata de source será persistida no backend e exposta apenas em endpoint interno/suporte versionado. Uma futura UX de source no PWA exige rollout/versionamento próprio.

### 2.4 Side effects existentes

O caminho Desktop atual dispara `detect_anchorage_entries()` após snapshot aceito.

C3 v1 é snapshot continuity **state-only**. Portanto:

- snapshot Cloud nunca dispara anchorage/maneuver event/push;
- a primeira aceitação Desktop depois de um período Cloud não pode inferir eventos atravessando a fronteira Cloud→Desktop;
- C5 continua sendo o único checkpoint futuro autorizado a tratar efeitos cross-source.

### 2.5 C2 já encerrado

C2 fornece:

- CloudBinding;
- WebPilotAuthRealm;
- SessionLease;
- `realm_epoch`;
- provider compatibility;
- collector headless;
- tombstone de rejeição semântica;
- standby sintético.

C3 **consome** esses contratos. Não reabre crypto, broker, provider generation ou parser.

---

## 3. Separação obrigatória de quatro lifecycles

Os quatro conceitos abaixo são independentes.

| Conceito | Autoridade | Escopo | Função |
|---|---|---|---|
| Auth availability | Session Broker / Postgres | por `realm_id` | diz se Cloud possui sessão WebPilot utilizável |
| Source authority | Source Authority / Postgres | por `device_id` | diz quem pode publicar estado agora |
| Snapshot generation | writer + authority grant | por writer/grant | ordena snapshots e fence writer antigo |
| Source arbitration | API/Postgres | por `device_id` | decide quando Desktop↔Cloud pode trocar |

### 3.1 `realm_epoch` não é fencing token de snapshot

`realm_epoch` continua significando exclusivamente:

> ordem server-side de SessionLeases aceitas dentro do WebPilotAuthRealm.

Ele pode mudar sem haver troca de source e pode ser compartilhado por CloudBindings diferentes do mesmo realm.

Logo, **é proibido usar `realm_epoch` como source fencing token**.

O source fencing terá contador próprio: `authority_epoch`.

O `realm_epoch` corrente pode ser registrado como observabilidade do grant Cloud, mas nunca decide sozinho autoridade.

---

## 4. Autoridade persistente por `device_id`

### 4.1 API/Postgres é o único árbitro

Desktop e Cloud nunca concluem localmente “agora sou source”.

Somente uma transação autoritativa na API/Postgres pode:

- conceder authority;
- renovar lease;
- trocar holder;
- fazer failover;
- fazer failback;
- fencear holder antigo;
- aceitar snapshot managed.

Se a API/DB estiver indisponível, **não há nova decisão de autoridade**.

### 4.2 Sources

Inicialmente existem somente:

- `desktop`;
- `cloud`.

`none` é estado de ausência de authority efetiva, não terceiro writer.

### 4.3 SourceAuthorityLease

Cada grant possui:

- `device_id`;
- `source`;
- `authority_epoch` bigint monotônico server-side por device;
- `authority_lease_id` UUID não secreto;
- `holder_instance_id` UUID;
- `granted_at`;
- `lease_expires_at`;
- `last_renewed_at`;
- reason code.

O **fencing token** é `authority_epoch`.

Regras:

1. primeiro grant managed: epoch 1;
2. renovar o mesmo holder não incrementa epoch;
3. troca Desktop→Cloud incrementa epoch;
4. troca Cloud→Desktop incrementa epoch;
5. troca de processo/instância do holder exige novo grant e incrementa epoch;
6. qualquer snapshot com epoch menor/diferente do current é rejeitado;
7. `authority_lease_id` também deve coincidir;
8. token não é segredo; autenticação continua Device/CloudBinding.

### 4.4 Identidade da instância writer

Não criar um contador paralelo desnecessário.

O `MobileSnapshot.boot_id` já representa o boot do produtor e será usado como `holder_instance_id` do Desktop.

O writer Cloud terá `boot_id` próprio por processo/runtime.

Invariante:

> dentro de um authority grant, `holder_instance_id == snapshot.boot_id`.

Se o writer reiniciar e mudar `boot_id`, precisa adquirir novo authority grant/epoch antes de publicar.

Isso impede snapshot atrasado de um boot anterior mesmo se a source continuar a mesma.

### 4.5 Ordenação dentro do grant

Dentro do mesmo:

`device_id + authority_epoch + holder_instance_id`

o `sequence` atual continua monotônico.

Portanto a ordem de aceitação é:

1. authority_epoch;
2. holder_instance_id exato;
3. sequence monotônica.

`generated_at` nunca é fencing.

### 4.6 Dois caminhos managed distintos

O contrato managed separa formalmente duas operações. Elas podem compartilhar endpoint HTTP, mas no domínio/repository/RPC são comandos distintos e mutuamente exclusivos.

#### `publish_under_current_grant`

Usado somente pelo holder atual.

Exige, além da autenticação do source:

- `source` igual ao current;
- `authority_epoch` corrente;
- `authority_lease_id` corrente;
- `holder_instance_id` corrente;
- lease ainda não expirada, grant não fenced e nenhuma transição vencedora anterior;
- `sequence` válida dentro do grant;
- gates administrativos válidos e validações próprias do snapshot candidate (`generated_at`, skew, payload, ordering).

**Write eligibility é distinta de renew eligibility.** Um holder Desktop ou Cloud com snapshot autoritativo anterior stale pode publicar um **recovery snapshot** sob o mesmo epoch/lease/instance ainda válidos, mesmo que o grant esteja temporariamente não renovável. A escrita de recuperação não exige freshness do snapshot anterior nem renew eligibility: é justamente o novo snapshot aceito que pode restabelecê-las. O DB decide tudo sob o mesmo lock, sem aceitar write de lease expirada, grant fenced ou epoch já substituído. Na aceitação, atualiza `last_authoritative_snapshot_at` e limpa `authoritative_snapshot_stale_since`; se os demais gates estiverem saudáveis, renew volta a ser elegível, preservando epoch/lease. Se outro candidate já venceu, o request antigo recebe `authority_fenced` e não altera state. Depois de expiry/fencing, somente `transition_candidate` pode adquirir novo grant, se a policy permitir.

O DB faz lock/revalidação e somente então aceita o snapshot. Nenhum client pode prolongar lease ou alterar grant localmente.

#### `transition_candidate`

Usado para:

- Desktop→Cloud failover;
- Cloud→Desktop failback;
- nova aquisição após grant expirado/fenced quando a policy permitir.

O candidate:

- é autenticado por `Device` quando Desktop e por `CloudBinding` quando Cloud;
- apresenta `source`, `holder_instance_id`, snapshot candidate e metadata permitida;
- **não fornece, deriva nem inventa** o próximo `authority_epoch` ou `authority_lease_id`.

O DB, na mesma transação:

1. locka o state autoritativo;
2. revalida todos os gates de source, auth, health, freshness, hysteresis e administração;
3. escolhe vencedor/loser;
4. se vencer, incrementa server-side `authority_epoch`, gera `authority_lease_id`, grava o novo holder e aceita o candidate como snapshot current;
5. se perder, não altera grant nem snapshot.

O resultado tipado de qualquer operação managed deve conter, no mínimo:

- `status`;
- `reason_code`;
- `authority_epoch`;
- `authority_lease_id`;
- `holder_instance_id`;
- `lease_expires_at`;
- `previous_source`;
- `source_transition`;
- `side_effect_policy`;
- `previous_snapshot_for_side_effects` somente quando a transação autorizar continuidade Desktop→Desktop.

`heartbeat/renew` do holder devolve/confirma o mesmo grant (`authority_epoch`, `authority_lease_id`, `holder_instance_id`, `lease_expires_at`) para recuperação de estado local sem depender do PWA. Heartbeat de source não-holder devolve status/reason e nenhum grant inventado.

---

## 5. Migration proposta — 021, somente local/efêmera até autorização

Nome proposto:

`021_source_authority_snapshots.sql`

Ela não será aplicada em produção durante C3 sem autorização humana separada.

### 5.1 `device_source_authority`

Uma linha por `device_id`:

- `device_id text PK/FK devices`;
- `mode legacy|managed`, default `legacy`;
- `active_source desktop|cloud|null`;
- `authority_epoch bigint not null default 0`;
- `authority_lease_id uuid null`;
- `holder_instance_id uuid null`;
- `lease_expires_at timestamptz null`;
- `granted_at timestamptz null`;
- `last_renewed_at timestamptz null`;
- `last_transition_at timestamptz null`;
- `transition_reason text`;
- `last_authoritative_snapshot_at timestamptz null`;
- `authoritative_snapshot_stale_since timestamptz null`;
- `cloud_binding_id uuid null`;
- `realm_id text null`;
- `observed_realm_epoch bigint null`;
- `updated_at timestamptz`.

Checks devem impedir combinations inválidas entre source/lease/holder.

### 5.2 `device_source_heartbeats`

Uma linha atual por `device_id + source`:

- `device_id`;
- `source`;
- `instance_id`;
- `last_heartbeat_at` server-side;
- `healthy_since`;
- `consecutive_healthy`;
- `last_collection_ok_at` server-side;
- `last_reported_generated_at` apenas diagnóstico;
- `last_candidate_generated_at` apenas para avaliar freshness do standby/candidate, nunca como fencing;
- `last_reason_code`;
- `persistent_state_ready` somente para Cloud;
- `updated_at`.

Mudança de `instance_id` zera `healthy_since` e `consecutive_healthy`.

### 5.3 `device_source_authority_transitions`

Histórico sanitizado:

- id;
- device_id;
- authority_epoch;
- previous_source;
- new_source;
- previous_instance_id;
- new_instance_id;
- reason_code;
- transitioned_at.

Nunca persistir snapshot body, cookies, headers ou credentials nessa tabela.

### 5.4 Metadata do snapshot autoritativo

Adicionar à linha `devices`:

- `snapshot_source desktop|cloud|null`;
- `snapshot_authority_epoch bigint null`;
- `snapshot_authority_lease_id uuid null`;
- `snapshot_writer_instance_id uuid null`.

As colunas são metadata de backend; **não entram automaticamente no JSON PWA**.

### 5.5 RLS/privileges

Mesmos padrões C1/C2:

- RLS ligado;
- nenhuma policy pública;
- `SECURITY DEFINER` com `search_path = pg_catalog, public`;
- objetos qualificados;
- EXECUTE revogado de PUBLIC/anon/authenticated;
- grant somente backend/service role necessário.

### 5.6 Rollout `legacy -> managed`

Migration nasce com `mode=legacy`.

Em legacy:

- endpoint Desktop atual mantém comportamento atual;
- `accept_device_snapshot` continua intacto;
- Cloud managed write é proibido;
- PWA não muda.

Ativar `managed` exige operação admin explícita e todos os pré-requisitos de C3-F.

A ativação inicial **não cria um estado managed sem holder**. O bootstrap preferencial e obrigatório no v1 é uma transação `legacy -> managed` com Desktop como primeiro holder:

1. lock de `devices` + source authority;
2. `device.enabled=true`;
3. heartbeat Desktop recente/saudável;
4. snapshot legacy Desktop atual presente, `received_at` dentro da janela configurada e `devices.boot_id == heartbeat.instance_id`;
5. nenhum gate administrativo impeditivo;
6. criar `authority_epoch=1`, novo `authority_lease_id` e `holder_instance_id=devices.boot_id`;
7. `active_source=desktop`;
8. copiar `devices.received_at` para `last_authoritative_snapshot_at`;
9. marcar metadata backend do snapshot existente como `snapshot_source=desktop`, epoch/lease/instance do grant inicial;
10. commit único e retorno do grant completo.

Se qualquer pré-condição falhar, o device permanece `legacy`; não existe ativação parcial nem managed sem holder. Isso preserva Desktop como source preferencial e fecha explicitamente o bootstrap inicial.

Não existe auto-migration de device para managed.

---

## 6. Liveness, collection health e authoritative snapshot freshness — Desktop

C3 trata três sinais independentes. Nenhum deles substitui os demais:

1. **process heartbeat/liveness** — prova que o processo Desktop ainda fala com a API;
2. **collection health** — prova que o ciclo de coleta está saudável/degradado;
3. **authoritative snapshot freshness** — prova que um snapshot Desktop do holder atual foi efetivamente aceito pelo DB e tornou-se o state que o PWA pode ler.

Um heartbeat saudável **não** atualiza `last_authoritative_snapshot_at`.

### 6.1 Heartbeat Desktop

Endpoint previsto, Desktop-only:

`POST /api/v1/devices/{device_id}/source-heartbeat`

Device auth obrigatório.

Payload mínimo:

- `source=desktop` implícito pelo endpoint;
- `instance_id = MobileSnapshot.boot_id`;
- collection state enumerado;
- último `generated_at` apenas diagnóstico.

O servidor usa **seu próprio clock** para health.

Cadência esperada: 60 s.

Classificação inicial de processo/coleta:

- HEALTHY: heartbeat age < 90 s e collection state saudável;
- DEGRADED: 90 s <= age < 120 s, ou heartbeat recente com coleta degradada;
- STALE: age >= 120 s;
- OFFLINE: age >= 300 s, somente classificação operacional.

A hysteresis de liveness permanece: STALE contínuo por mais 60 s torna o holder elegível a perder authority, desde que exista candidate vencedor válido.

### 6.2 Freshness do snapshot Desktop autoritativo

Metadata server-side obrigatória: `last_authoritative_snapshot_at`, atualizada **somente pela transação que aceita o snapshot do holder**.

Default inicial configurável:

- `desktop_authoritative_snapshot_stale_after = 120 s`;
- `authoritative_snapshot_stale_hysteresis = 60 s`.

Regras:

- enquanto `now - last_authoritative_snapshot_at < 120 s`, uma falha isolada de POST não causa failover;
- ao cruzar 120 s, registrar/persistir `authoritative_snapshot_stale_since`;
- heartbeat saudável não limpa esse estado;
- somente um novo snapshot Desktop autoritativo aceito limpa `authoritative_snapshot_stale_since`;
- durante snapshot stale, o grant Desktop deixa de ser **renovável**, mas continua **write-eligible para recovery** sob o mesmo grant não expirado/não fenced;
- recuperação aceita durante hysteresis cancela snapshot-stale sem trocar epoch/lease;
- failover por snapshot stale só se torna elegível após 60 s contínuos de stale + Cloud candidate/gates verdes;
- portanto um Desktop pode estar `HEALTHY` em liveness e ainda assim ficar `desktop_snapshot_stale` e eventualmente perder authority.

A policy de failover considera a primeira condição que completar hysteresis: liveness stale ou authoritative snapshot stale. Nenhuma delas, isoladamente, concede authority ao Cloud sem candidate transacional válido.

`stale_since`, `authoritative_snapshot_stale_since` e continuity são persistidos; restart da API não zera hysteresis.

---

## 7. Heartbeat, candidate freshness e authoritative snapshot freshness — Cloud

Endpoint previsto:

`POST /api/v1/cloud-bindings/{cloud_binding_id}/source-heartbeat`

CloudBinding auth obrigatório.

Cadência alvo Cloud: 30 s.

Para ser CLOUD_ELIGIBLE em standby, simultaneamente:

1. `device.enabled=true`;
2. CloudBinding usable;
3. realm ativo;
4. membership do device dono do binding ativa;
5. SessionLease corrente server-side utilizável;
6. provider scope compatível/verificado;
7. Cloud heartbeat age < 60 s;
8. último standby cycle/candidate health OK recebido há <=90 s;
9. persistent state gate OK;
10. authority mode = managed.

A API revalida as condições server-side. Não confiar apenas no boolean `auth_ready` enviado pelo Cloud.

Enquanto Cloud ainda é standby, ele **não possui** `last_authoritative_snapshot_at` próprio a renovar. Sua freshness é a do candidate: collection/cycle recente + `generated_at` do candidate validado quando `transition_candidate` é apresentado.

Depois que Cloud vira holder, passa a valer uma terceira condição separada: authoritative snapshot freshness.

Default inicial configurável:

- `cloud_authoritative_snapshot_stale_after = 90 s`;
- `authoritative_snapshot_stale_hysteresis = 60 s`.

Um Cloud holder só renova enquanto snapshots Cloud autoritativos continuam sendo aceitos dentro dessa janela. Heartbeat saudável + snapshot stale produz `cloud_snapshot_stale`: o grant deixa de ser renovável, mas pode aceitar recovery snapshot Cloud válido sob o mesmo epoch/lease/instance enquanto não expirado nem fenced. A aceitação restaura freshness e renovabilidade, cancelando a hysteresis. Uma falha isolada de POST não causa transição imediata.

`realm_epoch` observado é metadata diagnóstica; pode mudar por recuperação de auth sem mudar `authority_epoch`.

---

## 8. Authority lease TTL, renewal e recuperação do grant

TTL inicial da source authority lease: **180 s**.

Motivo:

- Desktop envia a cada ~60 s;
- Cloud ativo trabalha em cadência menor;
- o TTL tolera jitter sem transformar uma falha única em source transition;
- hysteresis continua sendo requisito independente.

`renew` é uma operação do **current holder**, nunca um mecanismo de aquisição.

Renew só é aceito quando:

- source;
- holder instance;
- authority epoch;
- lease id;
- authorization gates;
- process liveness;
- collection health aplicável;
- **authoritative snapshot freshness do holder**

continuam válidos.

Para Desktop holder, `last_authoritative_snapshot_at` stale torna o grant não renovável mesmo com heartbeat saudável. Para Cloud holder, vale a mesma regra com a janela Cloud.

DB indisponível => renewal falha; writer não estende lease localmente.

**Renovabilidade não é elegibilidade de escrita.** O holder corrente pode recuperar freshness publicando com grant ainda válido (epoch, lease e instância idênticos), ainda que o snapshot anterior esteja stale. O RPC aceita apenas candidate válido sob lock, atualiza `last_authoritative_snapshot_at`, limpa o stale marker e permite nova renovação se os demais gates estiverem saudáveis. Lease expirada, grant fenced ou epoch substituído não permitem `publish_under_current_grant`: somente novo `transition_candidate`, se a policy permitir.

Resposta de heartbeat/renew do holder confirma:

- `authority_epoch`;
- `authority_lease_id`;
- `holder_instance_id`;
- `lease_expires_at`;
- `status/reason_code`.

Isso permite que o writer recupere o grant corrente após perda de memória local **somente se** DB confirmar que ele ainda é o mesmo holder. Nenhum client recria grant por inferência.

---

## 9. Failover Desktop → Cloud

Failover não acontece no heartbeat sozinho.

A transição só é efetivada quando o Cloud apresenta um **snapshot candidate fresco** e todos os gates continuam verdadeiros dentro da mesma transação.

Pré-condições:

1. mode managed;
2. device enabled;
3. holder Desktop tornou-se não renovável por uma destas condições persistidas:
   - liveness STALE por >=60 s além do threshold de 120 s; ou
   - `last_authoritative_snapshot_at` stale por >=60 s após a janela de 120 s, mesmo com heartbeat saudável;
4. authority Desktop expirada/não renovável;
5. Cloud eligible em standby;
6. Cloud standby possui candidate recente;
7. candidate `boot_id == cloud instance_id`;
8. `generated_at` passa pelo freshness/skew guard;
9. DB disponível.

O request é `transition_candidate`: CloudBinding + `holder_instance_id` + snapshot candidate; **não** envia novo epoch/lease.

Transação:

1. lock device/source authority/heartbeats relevantes;
2. revalidar gates;
3. incrementar `authority_epoch`;
4. gerar novo `authority_lease_id`;
5. source = cloud;
6. holder = cloud instance;
7. persistir snapshot Cloud como current authoritative snapshot;
8. persistir snapshot source metadata;
9. registrar transition reason tipado (`desktop_stale_failover` ou `desktop_snapshot_stale_failover`);
10. atualizar `last_authoritative_snapshot_at` com o receive time server-side do snapshot vencedor e limpar o stale marker correspondente;
11. retornar o grant completo criado pelo DB + contexto transacional de side effects;
12. commit único.

Nenhuma janela intermediária “Cloud tem authority mas ainda não há snapshot Cloud”. Se o candidate perder a corrida, authority e snapshot ficam byte-for-byte inalterados.

### 9.1 Cloud snapshot é state-only

A aceitação Cloud:

- não chama `detect_anchorage_entries`;
- não cria maneuver event;
- não cria tracking event;
- não cria push;
- não altera histórico de eventos.

---

## 10. Failback Cloud → Desktop

Desktop saudável não toma authority imediatamente ao primeiro heartbeat.

Condições:

- mesmo `instance_id`;
- >=3 heartbeats Desktop saudáveis consecutivos;
- janela saudável contínua >=120 s;
- Cloud ativo há pelo menos 120 s;
- device enabled;
- candidate Desktop fresco;
- DB disponível.

A transição ocorre somente junto com um Desktop snapshot candidate válido.

O request é `transition_candidate`: Device auth + `holder_instance_id` + snapshot candidate, sem epoch/lease futuro.

Transação:

1. revalidar stability;
2. lock authority;
3. incrementar epoch;
4. gerar nova lease id;
5. source=desktop;
6. holder=Desktop boot_id;
7. persistir snapshot Desktop;
8. atualizar `last_authoritative_snapshot_at`;
9. registrar `desktop_stable_failback`;
10. retornar o grant completo + `side_effect_policy=baseline`;
11. commit.

Depois do commit:

- qualquer write Cloud com epoch antigo retorna `fenced`;
- Cloud volta a standby;
- Cloud não publica mais snapshot.

### 10.1 Side effects decididos pelo resultado transacional

O `SnapshotService` atual faz pre-read de `previous` antes do atomic accept. Esse padrão pode continuar no caminho **legacy**, mas fica **proibido como autoridade de side effects no managed path**.

O RPC managed captura sob o mesmo lock/transação o snapshot/source anterior e devolve contrato suficiente para o service:

- `previous_source`;
- `source_transition`;
- `side_effect_policy = none | baseline | desktop_continuity`;
- `previous_snapshot_for_side_effects` somente quando `desktop_continuity`.

Regras:

- qualquer snapshot Cloud => `side_effect_policy=none`;
- failback Cloud→Desktop => `baseline`;
- primeiro Desktop aceito como parte de qualquer source transition => `baseline`;
- Desktop side effects só podem ocorrer quando a transação vencedora afirmar `desktop_continuity` e fornecer o previous snapshot capturado sob lock;
- pre-read feito antes do RPC nunca pode promover `baseline` para `desktop_continuity`;
- loser de corrida não produz side effect.

Assim, concorrência não permite que um `previous` stale cause anchorage/tracking/push cross-source. Após a baseline Desktop transacional, o próximo Desktop→Desktop apropriado pode voltar ao comportamento existente.

C3 não redesenha eventos; apenas garante que sua decisão de baseline/continuidade nasce do commit vencedor. C5 continua separado.

---

## 11. Desktop retorna durante coleta Cloud

São permitidas duas ordens lineares:

### Ordem A — Cloud publica antes do failback

- Cloud ainda possui epoch N;
- snapshot Cloud N é aceito;
- Desktop completa stability;
- Desktop snapshot causa transition para N+1;
- qualquer Cloud posterior N é rejeitado.

### Ordem B — failback vence primeiro

- Desktop obtém epoch N+1 junto com seu snapshot;
- Cloud request ainda in-flight com N chega depois;
- RPC rejeita por fencing;
- nenhuma comparação de timestamps decide o vencedor.

O resultado é determinístico em PostgreSQL.

---

## 12. Snapshot disagreement Desktop × Cloud

C3 nunca mistura payloads e nunca escolhe “quem parece mais novo” por `generated_at`.

Regra:

> o snapshot aceito é sempre o snapshot do holder do authority epoch corrente.

Se Desktop standby e Cloud ativo discordarem:

- Desktop candidate não autoritativo não sobrescreve Cloud antes do failback gate;
- depois do failback, o Desktop snapshot transacionalmente passa a ser a nova verdade;
- nenhuma merge/reconciliation de eventos ocorre em C3.

Sandbox deve provar divergência proposital entre payloads e authority determinística.

---

## 13. Clock skew e snapshot atrasado

### 13.1 Authority usa somente server clock

Health, stale, hysteresis, grant e lease expiry usam `clock_timestamp()`/clock server-side.

Relógio Desktop/Cloud não decide authority.

### 13.2 `generated_at`

É metadata do conteúdo.

Guard inicial:

- mais de 60 s no futuro do server => rejeitar `snapshot_clock_ahead`;
- mais de 300 s atrás do server no momento do publish => rejeitar `snapshot_too_old`;
- dentro da janela, authority/fence/sequence continuam decidindo ordem.

Os limites devem ser configuráveis e cobertos com clock injetável em service tests.

### 13.3 Fora de ordem

Rejeitar:

- authority epoch antigo;
- authority lease id divergente;
- holder instance divergente;
- sequence menor;
- same sequence com payload diferente.

Retry exato pode ser idempotente.

Um snapshot atrasado de boot antigo nunca é aceito depois de novo authority epoch.

---

## 14. Split-brain e concorrência

O novo RPC managed deve ser a única função capaz de mudar snapshot current em mode managed.

Obrigatório PostgreSQL real:

- Desktop e Cloud candidatos simultâneos;
- dois requests Cloud concorrentes;
- failback concorrente com write Cloud;
- disable concorrente com snapshot;
- binding revoke concorrente;
- realm deactivate concorrente;
- membership revoke concorrente;
- API processes concorrentes.

Lock order deve ser documentada e única para evitar deadlock.

Resultado permitido em qualquer corrida:

- exatamente um authority epoch corrente;
- exatamente um snapshot current;
- loser recebe reason tipado;
- nunca há dois writers aceitos no mesmo epoch.

---

## 15. Precedência administrativa e fencing com escopo correto

`device.enabled=false` sempre vence e fenceia **qualquer** authority do device, Desktop ou Cloud.

As demais mudanças administrativas são Cloud-scoped:

- `CloudBinding active→revoked` fenceia somente o current grant `source=cloud` que referencia aquele `cloud_binding_id/device_id`;
- revoke da membership do **device dono do CloudBinding**, no mesmo realm, torna esse binding inutilizável e fenceia somente o Cloud grant correspondente;
- `realm active→inactive` torna Cloud inelegível e fenceia somente Cloud grants ligados àquele realm;
- nenhuma dessas três mudanças pode fencear Desktop authority por engano.

SessionLease publisher lifecycle é separado de source authority:

- revoke/disable da membership de um device que atua somente como **publisher** não fenceia automaticamente todos os Cloud grants do realm;
- broker/auth availability reavalia se existe outra SessionLease elegível;
- se outra lease elegível existir, Cloud pode recuperar auth e continuar no **mesmo source grant/authority_epoch**;
- enquanto auth estiver indisponível, Cloud não renova nem escreve; o grant pode expirar/failover pelas regras normais;
- mudança de `realm_epoch` por recuperação de auth não é source transition.

### 15.1 Triggers/RPCs propostos na migration 021

A migration 021 deve propor helpers de fencing com predicados estreitos:

- device disable: target por `device_id`, qualquer source;
- binding revoke: target somente `active_source='cloud' AND cloud_binding_id=<binding>`;
- realm deactivate: target somente `active_source='cloud' AND realm_id=<realm>`;
- owner-membership revoke: target somente o grant Cloud cujo `device_id` é o mesmo membro revogado e cujo binding pertence ao mesmo realm/device.

É proibido trigger amplo em `webpilot_auth_realm_devices`, `webpilot_session_publishers` ou `webpilot_session_leases` que fenceie todos os grants de um realm.

Toda heartbeat/grant/renew/write revalida as mesmas condições sob lock. Reativação posterior nunca ressuscita token antigo.

Os testes PostgreSQL reais devem provar:

- disable de device fenceia Desktop e Cloud;
- binding/realm/owner-membership fenceiam Cloud e preservam Desktop;
- revoke de publisher não relacionado não fenceia grant Cloud de outro device;
- outra SessionLease elegível recupera auth sem `authority_epoch` novo;
- auth totalmente indisponível bloqueia Cloud renew/write;
- lock ordering e corrida com snapshot write permanecem determinísticos.

---

## 16. Dois Desktops no mesmo WebPilotAuthRealm

Source authority é por `device_id`, nunca por realm.

Exemplo:

- Desktop A / device A;
- Desktop B / device B;
- ambos realm `webpilot-pecem`.

SessionLease B pode futuramente fornecer auth ao Cloud que coleta para binding A, se C2 considerar aquela lease válida no realm.

Isso **não** concede ao Desktop B autoridade sobre snapshot do device A.

Testes obrigatórios:

- heartbeat A não altera authority B;
- disable B não fenceia A;
- source epoch A e B são independentes;
- realm disable, por ser auth gate compartilhado, torna Cloud inelegível para ambos, sem afetar a preferência Desktop local de cada device.

---

## 17. Restart semantics

### 17.1 API restart

Toda autoridade relevante está no PostgreSQL.

Restart API:

- não zera epoch;
- não zera healthy_since/stale_since;
- não recria lease;
- não muda source.

Nenhuma truth de authority pode depender de memória FastAPI.

### 17.2 Desktop restart

Novo processo => novo `boot_id`.

O novo boot não reutiliza authority lease do boot anterior.

Fast reacquire somente depois de o holder anterior ser classificado como não saudável conforme política.

A meta é permitir novo Desktop antes do PWA ficar stale, mas nunca aceitar dois Desktop processes simultâneos.

Teste inicial:

- old Desktop holder sem heartbeat >=90 s;
- novo boot autenticado pode adquirir novo Desktop grant/epoch;
- write do boot antigo é fenced.

Se o código real mostrar que 90 s não é seguro com a cadência existente, **STOP arquitetura no C3-C** e voltar ao plano; não reduzir silenciosamente.

### 17.3 Cloud restart

Novo processo Cloud => novo boot/instance id.

Holder Cloud anterior é considerado stale após 60 s sem heartbeat.

Novo Cloud só recebe novo grant depois disso e com persistent-state/auth gates verdes.

Old container com epoch anterior permanece fenced.

### 17.4 DB outage

Durante indisponibilidade DB:

- nenhum heartbeat é confirmado;
- nenhum lease é renovado;
- nenhum failover/failback ocorre;
- nenhum writer assume localmente;
- snapshot write falha;
- clients fazem retry bounded/backoff.

Após retorno DB:

- state persistido é relido;
- lease expirada exige novo grant;
- epoch antigo nunca é revivido.

---

## 18. Persistência Cloud obrigatória antes de qualquer operação real

### 18.1 O default C2 em `/tmp` é somente desenvolvimento

Hoje:

`ALERTAM_CLOUD_SESSION_TOMBSTONES_PATH=/tmp/alertam-cloud/session-rejections.json`

Isso **não pode** ser usado para Cloud operacional.

### 18.2 Runtime alvo do primeiro operacional

O sandbox já validado é Northflank e permanece o alvo inicial proposto, sem torná-lo irreversível.

A documentação Northflank atual confirma volume persistente montável em path absoluto e Single Read/Write para workload de uma instância.

Decisão C3-P:

- serviço Cloud v1: **1 replica**;
- volume: **Single Read/Write**;
- container mount: `/var/lib/alertam-cloud`;
- `ALERTAM_CLOUD_STATE_DIR=/var/lib/alertam-cloud`;
- `ALERTAM_CLOUD_SESSION_TOMBSTONES_PATH=/var/lib/alertam-cloud/session-rejections.json`.

Não alterar o serviço Northflank nesta sessão.

### 18.3 Permissões

Imagem Cloud roda como `10001:10001`.

Gate C3-D/C3-F:

- diretório state deve ser acessível apenas ao runtime;
- target desejado: dir 0700;
- arquivos 0600;
- startup prova create/write/fsync/atomic rename/read/delete;
- nenhuma permissão ampla como workaround permanente.

### 18.4 PersistentStateGate

Antes de Cloud ser CLOUD_ELIGIBLE:

- state path existe;
- é persistente/configurado;
- store parseia;
- store permite atomic write;
- store version compatível.

Falha => reason `cloud_persistent_state_unavailable` e Cloud continua sem authority.

Não fazer fallback para `/tmp`.

### 18.5 Tombstones/pending invalidations v2

C3 deve evoluir o estado local sem segredo para distinguir:

- `pending`: semantic reject cuja invalidation broker ainda não foi confirmada;
- `confirmed`: broker confirmou estado terminal.

Campos permitidos:

- lease_id;
- realm_epoch;
- state;
- first_rejected_at;
- last_attempt_at.

Nenhum cookie/ciphertext/credential.

### 18.6 Cleanup bounded

- confirmed pode ser removido após janela de retenção definida e limite máximo;
- pending **nunca é descartado apenas para cumprir limite**;
- máximo inicial de pending: 256;
- exceder limite => persistent state `overflow` e Cloud fica inelegível até reconciliação;
- startup tenta retry bounded das pending invalidations;
- só resposta terminal/idempotente do broker promove para confirmed.

### 18.7 Backup e perda de volume

Segurança não depende exclusivamente de backup.

Operação proposta:

- backup/clone do volume antes de deploys/mudanças de formato;
- backup operacional periódico conforme capacidade da plataforma/runbook;
- teste de restore antes do primeiro go-live.

Se o volume for perdido/corrompido:

1. Cloud fica fail-closed;
2. não assume authority;
3. não inicializa store vazio automaticamente;
4. operador deve executar recovery;
5. recovery invalida/rotaciona a SessionLease potencialmente reapresentável;
6. exige nova lease/realm_epoch confirmada;
7. somente então inicializa novo state volume.

Nenhum “arquivo sumiu, então lista vazia” é permitido em runtime managed.

---

## 19. Compatibilidade PWA

### 19.1 MobileSnapshot schema

Não criar `schema_version=3` só para source metadata.

O payload de domínio continua v1/v2.

`source` é metadata de transporte/authority, não dado portuário.

### 19.2 GET atual

`GET /api/v1/devices/{device_id}/snapshot` continua respondendo exatamente:

- `snapshot`;
- `meta.received_at`;
- `meta.age_seconds`;
- `meta.collector_online`;
- `meta.stale_after_seconds`;
- `meta.device_enabled`.

Sem campos extras em C3 v1.

### 19.3 Status de source

Criar endpoint separado e autenticado, por exemplo:

`GET /api/v1/devices/{device_id}/source-status`

somente Desktop/admin/support, contendo metadata sanitizada.

PWA não consome esse endpoint em C3.

Uma futura exposição no PWA exige contrato/versionamento coordenado porque o Zod atual é strict.

### 19.4 PWA sempre recebe apenas current autoritativo

Standby/candidates nunca entram em `devices.snapshot`.

O GET atual continua lendo uma única linha/current snapshot.

Portanto o PWA não arbitra source; ele só recebe o vencedor já escolhido pela API.

---

## 20. Endpoints previstos

### Desktop

`POST /api/v1/devices/{device_id}/source-heartbeat`

`POST /api/v1/devices/{device_id}/snapshot`

O snapshot endpoint atual pode receber authority metadata via headers em managed mode, sem alterar `MobileSnapshot`:

- `X-Alertam-Authority-Epoch`;
- `X-Alertam-Authority-Lease`;
- `X-Alertam-Source-Instance`.

Em legacy mode, contrato atual permanece.

### Cloud internal

`POST /api/v1/cloud-bindings/{cloud_binding_id}/source-heartbeat`

`POST /api/v1/cloud-bindings/{cloud_binding_id}/snapshot`

**Contrato comum aos dois endpoints de snapshot (Desktop Device e Cloud CloudBinding):** em `mode=managed`, ambos exigem `X-Alertam-Authority-Operation` e suportam explicitamente os mesmos dois modos, sem alterar o `MobileSnapshot` body:

- `X-Alertam-Authority-Operation: current-grant`
  - exige `X-Alertam-Authority-Epoch`, `X-Alertam-Authority-Lease` e `X-Alertam-Source-Instance`;
  - mapeia para `publish_under_current_grant`.
- `X-Alertam-Authority-Operation: transition-candidate`
  - exige `X-Alertam-Source-Instance`;
  - **proíbe** o client de fornecer novo epoch/lease;
  - mapeia para `transition_candidate`.

Cloud route:

- CloudBinding auth;
- no query secret;
- no Mobile/PWA exposure;
- state-only;
- current-grant exige fence completo;
- transition-candidate não possui grant futuro e deixa o DB criar/retornar o grant vencedor.

Heartbeat/renew do current holder devolve/confirma o grant completo; source não-holder recebe somente status/reason e nunca um token inventado.

### Admin/support

Operação para:

- consultar source status;
- habilitar managed mode;
- voltar managed→legacy de forma fenced;
- nunca permitir “force cloud” sem todos os gates.

---

## 21. Rollback seguro

### Antes de production migration 021

Rollback = revert dos commits aprovados. DB efêmero é descartável.

### Depois de migration 021, antes de managed mode

Migration é additive; rows permanecem legacy. Rollback de aplicação não perde snapshot atual.

### Managed → legacy

Operação admin transacional:

1. fence current authority;
2. incrementa epoch;
3. limpa active source/lease;
4. mode=legacy;
5. Cloud writes ficam proibidos;
6. Desktop volta ao endpoint legacy.

Não apagar tabelas/colunas na emergência.

Down migration destrutiva fica fora do runbook.

---

## 22. Observabilidade sanitizada

Reason codes permitidos, no mínimo:

- `legacy_mode`;
- `desktop_healthy`;
- `desktop_degraded`;
- `desktop_stale`;
- `desktop_snapshot_stale`;
- `desktop_offline`;
- `cloud_auth_unavailable`;
- `cloud_binding_unusable`;
- `cloud_persistent_state_unavailable`;
- `cloud_standby_stale`;
- `cloud_snapshot_stale`;
- `failover_wait_hysteresis`;
- `failover_granted`;
- `failback_wait_stable`;
- `failback_granted`;
- `authority_lease_expired`;
- `authority_fenced`;
- `device_disabled`;
- `realm_inactive`;
- `membership_revoked`;
- `binding_revoked`;
- `db_unavailable`;
- `snapshot_clock_ahead`;
- `snapshot_too_old`;
- `snapshot_out_of_order`.

Campos permitidos:

- device_id;
- source;
- authority_epoch;
- source instance id;
- realm_id;
- observed realm_epoch;
- age/duration;
- reason;
- timestamps server-side.

Nunca logar:

- snapshot body;
- vessel rows;
- cookies;
- ciphertext;
- Authorization;
- Device secret;
- CloudBinding credential;
- raw WebPilot HTML.

---

## 23. Cenários obrigatórios e resultado esperado

### Desktop saudável → Cloud standby

- Desktop heartbeat healthy;
- authority desktop;
- Cloud eligible pode coletar standby;
- Cloud snapshot write não é tentado/aceito;
- PWA recebe Desktop.

### Perda breve de heartbeat

- passa por degraded;
- retorna antes de 120+60;
- stale hysteresis zera;
- source não muda.

### Falha isolada de snapshot POST com heartbeat saudável

- process liveness permanece healthy;
- `last_authoritative_snapshot_at` ainda está dentro da janela;
- não há failover imediato;
- próximo snapshot aceito limpa qualquer tendência de stale.

### Heartbeat saudável + snapshot Desktop autoritativo stale

- heartbeat não mascara a ausência de state novo;
- aos 120 s snapshot entra em stale;
- grant deixa de ser renovável;
- após mais 60 s contínuos e com Cloud candidate/gates verdes, Desktop torna-se failover-eligible;
- reason inclui `desktop_snapshot_stale`.

### Desktop stale

- >=120 s vira stale;
- aguarda mais 60 s;
- Cloud ainda não é authority até candidate snapshot e gates.

### Cloud sem auth válida

- Desktop stale não basta;
- Cloud continua inelegível;
- PWA fica com último snapshot e eventualmente offline/stale.

### Cloud assume

- request é `transition_candidate`, sem epoch/lease futuro;
- todos os gates são revalidados pelo DB;
- epoch incrementa e lease é criada server-side;
- candidate Cloud e transition são um commit;
- resposta devolve grant completo;
- PWA passa a receber current Cloud sem mudar contrato.

### Cloud holder heartbeat saudável + snapshot autoritativo stale

- heartbeat sozinho não mantém authority;
- grant deixa de ser renovável após a janela Cloud;
- hysteresis evita reação a uma falha isolada;
- se houver Desktop candidate elegível, a policy pode concluir failback; sem target elegível, nenhum writer assume por inferência.

### Desktop retorna durante Cloud

- heartbeats acumulam stability;
- Cloud segue authority até failback;
- no primeiro retorno não há troca imediata.

### Retorno instável

- qualquer falha/gap reseta healthy_since/consecutive;
- sem flapping.

### Failback

- >=3 heartbeats e >=120 s estáveis;
- Desktop envia `transition_candidate` sem novo epoch/lease;
- epoch incrementa e grant é criado server-side;
- snapshot Desktop gravado na mesma transaction;
- resultado retorna `side_effect_policy=baseline`.

### Desktop antigo escreve depois de perder authority

- epoch/lease/instance antigo;
- rejeição `authority_fenced`;
- snapshot current intacto.

### Cloud antigo/restartado com token velho

- novo boot não casa holder;
- token velho rejeitado;
- novo grant exige stale/restart gate.

### Dois Desktops no mesmo realm

- source authority isolada por device;
- realm auth compartilhado não compartilha snapshot authority.

### enabled=false

- heartbeat/renew/write bloqueados;
- authority atual fenced;
- nenhuma Cloud takeover;
- reenable não ressuscita token antigo.

### realm/membership/binding desabilitados

- Cloud write/renew fail-closed;
- current Cloud grant fenced;
- reenable exige grant novo;
- Desktop local continua governado apenas pelo seu device gate.

### API restart

- epoch/hysteresis/authority persistem.

### Cloud restart

- persistent state volume obrigatório;
- old holder fenced;
- novo boot só adquire quando old Cloud holder stale.

### DB temporariamente indisponível

- sem local takeover;
- sem renewal/write;
- após recovery, expired grant não ressuscita.

### Clock skew

- server clock arbitra;
- future >60 s / old >300 s rejeitados;
- nenhum timestamp local vence fencing.

### Snapshot atrasado

- epoch/instance/sequence antigos rejeitados.

### Concorrência real writers

- exatamente um commit vencedor;
- loser recebe reason tipado;
- loser não altera grant/snapshot;
- pre-read stale fora da transação não consegue produzir side effect;
- side effect Desktop só ocorre se o resultado vencedor for `desktop_continuity`.

### Bootstrap legacy → managed

- Desktop heartbeat saudável + snapshot legacy recente/matching boot;
- ativação cria Desktop epoch 1 e lease em uma única transação;
- snapshot existente é marcado backend-side como Desktop authoritative;
- qualquer ausência/stale/mismatch mantém o device em legacy.

### PWA

- somente `devices.snapshot` autoritativo;
- envelope atual inalterado.

---

## 24. Divisão futura de C3 em checkpoints

Política: cada checkpoint termina **sem commit/stage**, recebe revisão independente e somente depois do APROVADO pode ser commitado exatamente.

### C3-A — domínio, source metadata e contratos

**Gate sugerido:** R10.

**Escopo**

- enums/source reason codes;
- `SourceAuthorityRecord`;
- `SourceHeartbeatRecord`;
- `ManagedSnapshotCandidate`;
- comandos distintos `PublishUnderCurrentGrant` e `TransitionCandidate`;
- `AuthorityGrantView`;
- `ManagedSnapshotAcceptanceResult` com previous source/transition/side-effect policy;
- `AuthorityDecision`;
- interfaces repository;
- policy constants;
- contrato legacy/managed;
- desenho exato de headers/endpoints;
- contract test garantindo GET PWA byte-shape sem source fields.

**RED**

- authority/source types ausentes;
- PWA compatibility test falha ao tentar metadata source no envelope atual;
- testes provam que `realm_epoch` não satisfaz interface de fencing;
- transition candidate sem grant futuro é válido como comando, enquanto current-holder write sem epoch/lease/instance é inválido;
- contrato de bootstrap exige Desktop healthy/fresh para epoch 1;
- managed side effects não podem ser decididos por pre-read externo.

**GREEN**

Somente modelos/interfaces/policy pure functions. Nenhum SQL, endpoint writer ou Cloud publish ainda.

**Invariantes**

- source authority por device;
- realm_epoch separado;
- mode default legacy.

**Migration**

Nenhuma.

**Rollback**

Revert do checkpoint.

**STOP R10.**

---

### C3-B — migration 021 + authority lease/fencing

**Gate sugerido:** R11.

**Escopo**

- migration 021 local/efêmera;
- Memory/Postgres/Supabase repository;
- authority epoch/lease;
- current snapshot metadata;
- managed acceptance RPC;
- admin managed/legacy;
- fencing administrativo.

**RED PostgreSQL real**

- two writers;
- stale epoch;
- wrong lease id;
- wrong instance;
- boot restart;
- current-holder write exige epoch+lease+instance;
- transition candidate não envia epoch/lease e winner recebe grant completo;
- loser de transition não altera authority nem snapshot;
- corrida real recovery current-grant × transition-candidate: único vencedor sob lock; loser tipado/fenced sem overwrite;
- bootstrap legacy→managed Desktop epoch 1 transacional;
- same seq same payload idempotent;
- same seq different payload conflict;
- disable/revoke/deactivate races com matriz de escopo correta;
- publisher SessionLease revoke com outra lease elegível sem source transition;
- auth indisponível bloqueando Cloud renew/write;
- managed result devolvendo `previous_source/source_transition/side_effect_policy` sob lock;
- corrida em que pre-read externo fica stale e não gera side effect cross-source;
- API process concurrency.

**GREEN**

- transação única;
- server-side epoch;
- canonical lock order;
- RLS/privileges hardening.

**Migration**

021 aplicada apenas em PostgreSQL efêmero. Produção proibida.

**Rollback**

Mode legacy + additive schema.

**STOP R11.**

---

### C3-C — heartbeat, freshness e hysteresis

**Gate sugerido:** R12.

**Escopo**

- Desktop heartbeat endpoint;
- Cloud heartbeat endpoint;
- persistent health state;
- classifications;
- authority renewal;
- failover/failback eligibility, ainda sem Cloud snapshot writer.

**RED**

Clock injetável:

- 89/90/119/120/179/180/300 s boundaries de liveness;
- authoritative snapshot freshness boundaries Desktop e Cloud;
- heartbeat healthy + snapshot stale;
- uma falha isolada de POST sem failover;
- snapshot-stale hysteresis reset somente por snapshot autoritativo aceito;
- Desktop stale aos 120 s → recovery snapshot aos 150 s aceito no mesmo grant → renew elegível, hysteresis cancelada e nenhum failover;
- Cloud holder stale também pode recuperar com snapshot válido enquanto lease não expirou nem foi fenced;
- brief heartbeat loss;
- hysteresis reset;
- 3-heartbeat failback;
- cloud auth absent;
- DB unavailable;
- API restart preserving timers;
- two device isolation.

**GREEN**

Arbitration policy responde decisões/candidates, mas ainda não POSTa snapshot Cloud.

**Migration**

Usa 021; nenhuma nova se suficiente.

**STOP R12.**

---

### C3-D — writers controlados + persistent state Cloud

**Gate sugerido:** R13.

**Escopo**

Desktop:

- heartbeat adapter;
- authority metadata no SnapshotHttpClient;
- nenhuma mudança no MobileSnapshot body.

Cloud:

- persistent state preflight;
- state dir `/var/lib/alertam-cloud`;
- tombstone/pending v2;
- synthetic snapshot builder/writer;
- Cloud snapshot endpoint;
- **fake WebPilot only**.

**RED**

- `/tmp` recusado em operational-mode tests;
- unwritable volume => Cloud ineligible;
- corrupt/missing established state => fail-closed;
- restart preserves pending rejection;
- old Cloud token fenced;
- no events/push.

**GREEN**

Cloud writer existe apenas atrás de feature/config default OFF e sandbox.

**Northflank**

Nenhuma configuração remota nesta etapa. Só contract/runbook local.

**STOP R13.**

---

### C3-E — failover/failback sandbox e split-brain

**Gate sugerido:** R14.

**Escopo**

Docker local sintético:

- Postgres;
- API;
- fake WebPilot;
- Desktop simulator;
- Cloud;
- persistent volume;
- PWA-like reader.

**Cenário obrigatório**

1. Desktop authority/updates;
2. one missed heartbeat;
3. recover sem failover;
4. Desktop stale;
5. Cloud sem auth => no takeover;
6. auth disponível;
7. um snapshot POST Desktop falha, heartbeat continua e não há failover imediato;
8. heartbeat Desktop continua healthy mas snapshot authoritative fica stale + hysteresis; Cloud transition-candidate vence;
8a. cenário independente: Desktop stale em 120 s → recovery aceito em 150 s → mesmo epoch/lease, hysteresis cancelada, zero failover;
8b. Cloud stale → recovery válido sob grant vigente; após expiry/fence não pode recuperar;
8c. recovery current-grant × transition-candidate concorrentes → único commit vencedor, loser tipado sem overwrite;
9. conferir grant retornado pelo DB e failover sem epoch/lease inventado pelo Cloud;
10. conflicting Desktop old write fenced;
11. Desktop returns unstable => no failback;
12. Desktop stable 3 heartbeats/120 s;
13. Desktop transition-candidate não envia grant futuro;
14. Cloud write racing failback;
15. exactly one winner;
16. failback retorna baseline e zero side effect cross-source, mesmo com pre-read concorrente stale;
17. próximo Desktop→Desktop apropriado pode retornar `desktop_continuity`;
18. old Cloud write fenced;
19. Cloud holder heartbeat healthy + snapshot stale torna grant não renovável;
20. API restart;
21. Cloud restart with persistent state;
22. DB outage/recovery;
23. delayed snapshot;
24. clock skew;
25. bootstrap legacy→managed cria Desktop epoch 1 somente se healthy/fresh;
26. PWA reader always sees only current authoritative snapshot.

**Eventos**

Assert zero Cloud event/push writes.

**STOP R14.**

---

### C3-F — integração e encerramento técnico

**Gate sugerido:** R15 + gate humano separado.

**Escopo**

- regressões totais;
- Desktop make check;
- API make test-all;
- frontend tests;
- cloud-test;
- wheel contract;
- sandbox C3;
- security/redaction;
- migration list 021;
- docs/runbook;
- source status support endpoint;
- rollback drill;
- persistent-volume restore drill documental/local quando possível.

**Critérios**

- migration 021 NÃO produção;
- Cloud writer default OFF;
- managed mode default legacy;
- WebPilot real Cloud não usado;
- Northflank operacional não alterado;
- no push/deploy;
- no events/push.

**STOP R15.**

Mesmo R15 aprovado não autoriza produção automaticamente.

---

## 25. Gate operacional humano posterior ao C3 técnico

Antes do primeiro device real managed:

1. aprovação R15;
2. autorização explícita para migration 021 produção;
3. deploy API compatível;
4. Desktop compatível instalado;
5. volume Northflank persistente criado/montado;
6. permission/preflight verde;
7. backup/restore runbook validado;
8. Cloud image compatível deployada com writer ainda OFF;
9. SessionLease real operacional autorizada separadamente;
10. managed mode habilitado explicitamente para device piloto;
11. Cloud writer habilitado explicitamente;
12. smoke humano;
13. rollback pronto.

Sem esse gate, C3 continua apenas capacidade implementada/testada.

---

## 26. Security review obrigatória

Auditar:

`source`
`authority_epoch`
`authority_lease`
`snapshot`
`failover`
`failback`
`heartbeat`
`device_secret`
`cloud_binding`
`authorization`
`cookie`
`realm_epoch`
`session`
`event`
`push`

Confirmar:

- source token não vira auth secret;
- auth secret não entra em payload/log;
- no query secrets;
- no public SQL policy;
- no PWA authority endpoint;
- no Cloud event/push;
- no timestamp-only arbitration;
- no `/tmp` fallback operacional;
- no automatic managed activation.

---

## 27. Riscos principais

### Risco 1 — misturar realm_epoch e authority_epoch

Mitigação: tipos/modelos distintos e teste de compile/runtime contract.

### Risco 2 — PWA strict quebrar por campo novo

Mitigação: GET atual sem mudança de shape em C3.

### Risco 3 — evento duplicado ao trocar source

Mitigação: Cloud state-only e first Desktop-after-Cloud baseline sem side effects.

### Risco 4 — admin disable e token antigo ressuscitar

Mitigação: fencing DB-side na mesma mudança administrativa; reenable exige grant novo.

### Risco 5 — /tmp desaparecer

Mitigação: persistent volume + state gate + sem fallback + recovery procedure.

### Risco 6 — flapping

Mitigação: failover 120+60; failback 120 s + 3 heartbeats; state persistido.

### Risco 7 — clock skew

Mitigação: arbitration server-time; generated_at só freshness guard.

### Risco 8 — two Cloud replicas

Mitigação v1: uma replica + Single Read/Write volume. HA futura exige plano próprio e state DB/shared.

---

## 28. Itens explicitamente fora de escopo do C3

Mesmo durante futura implementação C3:

- evento/push Cloud;
- idempotência cross-source de eventos;
- usuário/senha WebPilot permanente;
- provider Cloud nativo de login;
- refatoração ampla Desktop;
- remoção Selenium;
- troca do PWA para novo device_id;
- novo pareamento mobile;
- C5;
- HA multi-replica Cloud;
- production migration/deploy sem gate humano.

---

## 29. Gates mínimos por checkpoint

Todo checkpoint:

- RED documentado;
- GREEN documentado;
- testes direcionados;
- regressões proporcionais;
- PostgreSQL real quando tocar authority/SQL;
- Supabase MockTransport quando tocar adapter;
- `git diff --check`;
- untracked também verificado;
- security grep;
- staged=0;
- STOP independente.

Nenhum checkpoint autoriza automaticamente o seguinte; o revisor/usuário libera explicitamente.

---

## 30. Saída esperada do C3 técnico

Quando C3-F for tecnicamente encerrado, mas antes do gate operacional:

```text
Desktop heartbeat/snapshot ───────┐
                                  │
                           Source Authority
                                  │
Cloud standby/auth ───────────────┤
                                  │
                    authority_epoch + fencing
                                  │
                         exactly one writer
                                  │
                         devices.snapshot
                                  │
                        GET atual da PWA
```

O Mobile continua enxergando um único AlertaM lógico.

**STOP C3-P:** R9-F1..F4 corrigidos documentalmente. Não implementar C3-A antes de R9.1 independente APROVADO e autorização explícita.


---

## Adendo proposto R12-F1 — identidade persistente de heartbeat por instância (2026-10-09)

**Somente documentação; sujeito a R12.1 independente.** O checkpoint funcional C3-C segue **NÃO APROVADO**. Este adendo atualiza especificamente a intenção de C3-P §5.2 (`device_source_heartbeats`) e §17 (restart semantics), caso seja aprovado; **não altera** as decisões R9..R11.2 sobre authority/fencing, write≠renew ou PWA.

R12 detectou que a chave `(device_id, source)` mistura duas verdades que precisam coexistir: heartbeat do holder e heartbeat do candidate de mesma source. Depois do candidate substituir o registro do holder, o failover pode deixar de enxergar a liveness stale real; um current-grant write posterior pode invalidar o gate do candidate sem permitir a reaquisição após novo período stale. Desktop e Cloud foram reproduzidos independentemente.

**Proposta para aprovação arquitetural:** utilizar a tabela já prevista por C3-P com **uma linha por `(device_id, source, instance_id)`**, conservando health, last heartbeat e continuity de cada instance. `device_source_authority` permanece única referência de qual dessas linhas é o holder corrente; candidate same-source tem row distinta, nunca sobrescreve a do holder. `last_authoritative_snapshot_at` permanece exclusivamente timestamp de snapshot aceito, não heartbeat. Cross-source failover usa a linha do holder atual por `active_source + holder_instance_id` e avalia independentemente authoritative snapshot stale.

**Restart/reacquisition:** a elegibilidade de novo holder dentro da mesma source exige a instance distinta, candidate válido e silêncio do holder pelo limite aprovado de 90 s Desktop / 60 s Cloud; a proposição conservadora mede o silêncio desde **a atividade server-side mais recente do holder (heartbeat da instance atual ou snapshot current-grant autoritativo aceito)**, somente para impedir takeover same-source após atividade de escrita. Depois de um write/heartbeat do holder, um gate anterior é invalidado, mas o holder continua identificável, de modo que o candidate pode tornar-se elegível de novo após o limiar completo. Isso não substitui nem prolonga heartbeat liveness para failover cross-source: snapshot fresh não mascara um holder com heartbeat >=180 s stale.

**Locking:** manter `devices → [CloudBinding/realm/membership] → heartbeat rows por (source, instance_id) em ordem estável → source authority`; usar pre-read de authority apenas para localizar a linha de holder após device lock, revalidando authority e clock após os locks. O winner da transition recalcula todos os gates server-side. `get_source_heartbeat(device, source)` deixa de ser uma consulta singular para arbitragem; adaptadores/contratos devem exigir instance explícita ou seleção do holder segundo authority. Bootstrap legacy consulta a row de `devices.boot_id`.

**Testes RED mandatórios antes de implementar:** (a) A Desktop holder heartbeat 181 s stale + snapshot fresh + B heartbeat + Cloud elegível → Cloud não deve perder failover eligibility; (b) Desktop holder A 91 s sem atividade + B eligible → A recovery/write → B reavaliado antes e depois do novo limiar de 90 s, sem perder evidência A; (c) equivalente Cloud→Cloud a 60 s; (d) concorrência PostgreSQL B transition vs A current write/heartbeat, candidate duplo, restart da API, bootstrap legacy, privilege/RLS e idempotência 001→021, sem 022. Ver **C3-C plano dedicado §28**, que define matriz completa, invariantes e critérios de R12.1.

**STOP mantido:** não tocar na migration 021, nos repositories ou testes antes de R12.1 aprovar o desenho. Se a estratégia exigir 022, migração de DB já aplicado ou revisão de thresholds, retornar a decisão arquitetural explícita; nenhum avanço tácito a C3-D.
