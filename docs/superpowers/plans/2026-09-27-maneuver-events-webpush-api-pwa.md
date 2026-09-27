# Maneuver Events + Web Push API/PWA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistir os ManeuverEvent do Desktop de forma idempotente/ordenada, expor um feed mobile e entregar Web Push por instalação PWA com preferências independentes e sem replay de eventos antigos.

**Architecture:** A API recebe eventos autenticados pelo DEVICE_SECRET, grava cada evento uma vez com `ingestion_id` estável e serve o feed pela sessão mobile HttpOnly. Push é uma projeção separada do evento: cada instalação possui subscription/preferências próprias, e `push_deliveries` deduplica tentativas; o PWA usa EventProvider para feed foreground e um service worker `injectManifest` para push/background.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, psycopg, Supabase/PostgREST, pywebpush >=2.5,<3, React 19, TypeScript 5.9, Vite 7, vite-plugin-pwa 1.x, Workbox, Vitest, Playwright.

**Spec:** `specs/021-maneuver-events-webpush.md`
**Design canônico:** `/home/ciro/dev/prog/alertamaritimo/docs/superpowers/specs/2026-09-27-ciclo-manobras-eventos-push-design.md`

**Status de execução:** checkpoint seguro após a Task 6 em 2026-09-27. Tasks 1–6 concluídas no código local; Task 7 é a próxima. Migrations 004/005 ainda não foram executadas contra Postgres real nesta sessão porque `TEST_POSTGRES_DSN` não está configurado.

## Global Constraints

- Desktop é a única origem de ManeuverEvent; API/PWA nunca redetectam evento comparando snapshots.
- POST Desktop: `POST /api/v1/devices/{device_id}/maneuver-events` com `Authorization: Device <DEVICE_SECRET>`.
- `event_id` e `maneuver_id` são UUIDs fornecidos pelo Desktop.
- Retry idêntico do mesmo `event_id` é sucesso idempotente; conteúdo divergente retorna 409.
- UUID não é relógio; `ingestion_id` bigint monotônico define ordem estável na API.
- `maneuver_events` e `push_deliveries` têm retenção de 30 dias.
- Feed e endpoints push mobile são device-scoped pela sessão HttpOnly; body nunca escolhe outro device_id.
- PairingGate expõe `sessionReady`: recursos baseados em cookie só iniciam após criação/recuperação confirmada da sessão, evitando 401 falso durante bootstrap.
- Cada PWA mantém `installation_id` UUID próprio e independente.
- Preferências iniciais: CONFIRMED, UPDATED, COMPLETED e CANCELLED = true.
- Reativar notificações redefine `push_enabled_at`; evento com `occurred_at < push_enabled_at` nunca gera push.
- Expiração normal da sessão mobile não desativa instalação push.
- Rotação do VIEW_SECRET desativa todas as instalações daquele device_id.
- Esquecer aparelho/desativar notificações afeta somente a instalação atual.
- Foreground heartbeat: 30 s enquanto visible; freshness para suprimir push do sistema: 75 s.
- Foreground polling de eventos: 30 s, pausa hidden, fetch imediato ao voltar visible.
- Web Push padrão + VAPID; sem Firebase/OneSignal.
- Service worker migra para `injectManifest`, preservando precache/autoUpdate e API NetworkOnly.
- Nenhuma resposta autenticada de `/api/v1/*` pode ser armazenada em cache.
- Push falhar nunca apaga ManeuverEvent nem muda o ACK de persistência do evento.
- Permanent push failure (404/410) inativa somente a instalação; transitório vira RETRY_PENDING.
- Nenhum log contém DEVICE_SECRET, VIEW_SECRET, cookie, VAPID private key, endpoint completo da subscription ou payload bruto WebPilot.
- TDD obrigatório: RED → GREEN → REFACTOR.
- Nenhum commit/push automático nesta etapa sem autorização explícita do Ciro.

## Review Focus

1. API persiste evento e cai antes/durante push: retry idempotente deve completar delivery ausente sem duplicar delivery já entregue.
2. Evento antigo chega depois por outbox: entra no feed, mas `occurred_at < push_enabled_at` produz IGNORED_BEFORE_OPT_IN, nunca push.
3. Dois POSTs concorrentes do mesmo event_id: uma única linha de evento e uma única claim de delivery por instalação.
4. VIEW_SECRET rotaciona enquanto celulares existem: todas as instalações do device ficam inativas, mas outras devices não são afetadas.
5. PWA recebe push com uma janela já aberta: notificationclick navega/foca a janela correta e `/alertas?event=` consegue localizar o evento mesmo após refresh.

---

## Visão de fases

### Fase 1 — Contrato e persistência de ManeuverEvent
Tasks 1–3: DTO, migrations/repository, POST idempotente e feed autenticado.

### Fase 2 — Feed no PWA
Tasks 4–5: cliente/polling, Alertas por event_id e Histórico por maneuver_id.

### Fase 3 — Instalações e preferências push
Tasks 6–7: schema/repository, endpoints mobile, installation_id, Config e revogação.

### Fase 4 — Delivery Web Push
Tasks 8–9: VAPID/pywebpush, bookkeeping/claims e dispatcher seguro.

### Fase 5 — Service worker e integração push
Tasks 10–11: injectManifest, PushSubscription, notificationclick e lifecycle do browser.

### Fase 6 — Foreground e UX operacional
Task 12: heartbeat, supressão de system push e aviso interno.

### Fase 7 — Hardening e gates
Task 13: retenção, segurança, build, E2E, docs e revisão final.

---

### Task 1: Contrato ManeuverEvent e fixture cross-repo

**Files:**
- Create: `api/app/models/maneuver_event.py`
- Modify: `api/app/models/__init__.py`
- Create: `api/tests/fixtures/maneuver_event_v1.json`
- Create: `api/tests/contract/test_desktop_maneuver_event_contract.py`
- Create: `api/tests/unit/test_maneuver_event_model.py`
- Modify: `frontend/src/api/contract.ts`
- Modify: `frontend/src/api/contract.test.ts`

**Interfaces:**
- `ManeuverType = Literal["ATRACACAO", "DESATRACACAO"]`.
- `ManeuverEventType = Literal["CONFIRMED", "UPDATED", "COMPLETED", "CANCELLED"]`.
- `ManeuverEventIn(BaseModel)` strict, aware `occurred_at`.
- `canonical_payload() -> dict[str, object]` usa `model_dump(mode="json")`.
- Frontend exports `ManeuverEventSchema` / `ManeuverEventV1`.

- [x] **Step 1: RED:** fixture gerada a partir de `ManeuverEvent.to_dict()` real do Desktop valida no Pydantic e Zod.
- [x] **Step 2: RED:** rejeitar UUID inválido, timestamp sem offset, tipo desconhecido e campo extra.
- [x] **Step 3: RED:** UPDATED aceita somente `changes` com chaves `pob`/ `berth` e pares `from/to`; eventos não-UPDATED aceitam `changes=null`.
- [x] **Step 4: Implementar modelos mínimos e fixture canônica sem incluir campos internos do Desktop.**
- [x] **Step 5: GREEN:** `cd api && uv run pytest tests/unit/test_maneuver_event_model.py tests/contract/test_desktop_maneuver_event_contract.py -q`; `cd frontend && npm test -- --run src/api/contract.test.ts`.
- [x] **Checkpoint:** `git diff --check`; não commitar.

### Task 2: Banco e repository de eventos idempotentes

**Files:**
- Create: `api/app/repositories/events.py`
- Modify: `api/app/repositories/memory.py`
- Modify: `api/app/repositories/postgres.py`
- Modify: `api/app/repositories/supabase.py`
- Modify: `api/app/repositories/factory.py`
- Create: `api/supabase/migrations/004_maneuver_events.sql`
- Create: `api/tests/unit/test_event_repository_contract.py`
- Create: `api/tests/integration/test_accept_maneuver_event_repository.py`
- Create: `api/tests/unit/test_supabase_event_repository.py`

**Interfaces:**
- `AcceptEventStatus = ACCEPTED | IDEMPOTENT | PAYLOAD_MISMATCH | DEVICE_NOT_FOUND`.
- `StoredManeuverEvent(ingestion_id, device_id, event, ingested_at)`.
- `EventPage(events, oldest_cursor, newest_cursor, has_more_before)`.
- `ManeuverEventsRepository.accept_maneuver_event_atomic(device_id, event) -> AcceptEventResult`.
- `AlertaRepository(DevicesRepository, ManeuverEventsRepository, Protocol)` passa a ser o contrato usado pela factory após esta task.
- `list_maneuver_events(device_id, *, after=None, before=None, limit=50) -> EventPage`.
- Response order from repository is always ascending by `ingestion_id`; initial/before queries select the newest/older window and normalize to ascending.

- [x] **Step 1: RED:** Memory repository: novo event_id ACCEPTED; retry canonicalmente igual IDEMPOTENT com mesmo ingestion_id; divergente PAYLOAD_MISMATCH.
- [x] **Step 2: RED Review Focus #3:** concorrência de dois accepts idênticos cria uma linha e retorna ACCEPTED + IDEMPOTENT.
- [x] **Step 3: RED:** feed isola device_id, suporta `after`, `before`, `limit<=100`, cursor e ordem ascendente estável inclusive quando `occurred_at` é igual.
- [x] **Step 4: Migration 004:** criar `maneuver_events` com `ingestion_id bigint generated always as identity`, `event_id uuid unique`, FK device, payload jsonb e colunas/indexes úteis.
- [x] **Step 5: Migration 004:** criar RPC `accept_maneuver_event` concorrente/idempotente, comparando payload jsonb canônico; mesmo event_id divergente retorna mismatch.
- [x] **Step 6: Implementar Postgres e Supabase repository seguindo o contrato do Memory.**
- [x] **Step 7: GREEN:** unit + integration repository; testes Supabase verificam endpoint RPC/parâmetros sem rede real.
- [x] **Checkpoint:** `git diff --check`; não commitar.

### Task 3: POST Desktop + GET feed mobile

**Files:**
- Create: `api/app/services/maneuver_event_service.py`
- Create: `api/app/services/event_feed_service.py`
- Create: `api/app/api/v1/mobile_auth.py`
- Create: `api/app/api/v1/maneuver_events.py`
- Create: `api/app/api/v1/mobile_events.py`
- Modify: `api/app/api/v1/router.py`
- Modify: `api/app/core/errors.py`
- Create: `api/tests/unit/test_maneuver_event_service.py`
- Create: `api/tests/integration/test_post_maneuver_event.py`
- Create: `api/tests/integration/test_get_maneuver_events.py`

**Interfaces:**
- POST `/api/v1/devices/{device_id}/maneuver-events`.
- ACK: `{"ok":true,"status":"accepted|idempotent","ingestion_id":N,"received_at":"..."}`.
- Divergent event_id: 409 `event_id_payload_mismatch`.
- GET `/api/v1/mobile/maneuver-events?after=&before=&limit=50`.
- GET autentica exclusivamente `alertam_mobile_session`; `after` + `before` juntos = 422 seguro.
- Feed response: `events: [{ingestion_id, ingested_at, ...ManeuverEvent}], oldest_cursor, newest_cursor, has_more_before`.
- Event service recebe hook opcional `dispatch_event: Callable[[StoredManeuverEvent], None]`, inicialmente no-op; hook nunca altera o ACK de persistência.

- [x] **Step 1: RED:** Device auth inválida rejeita POST antes de processar body sensível.
- [x] **Step 2: RED:** accepted/idempotent retornam 200; mismatch retorna 409; persistência indisponível 503.
- [x] **Step 3: RED:** hook é chamado tanto em ACCEPTED quanto IDEMPOTENT, permitindo completar delivery após crash, mas exceção do hook não muda 200 do evento persistido.
- [x] **Step 4: RED:** feed exige cookie válido e nunca aceita device_id arbitrário.
- [x] **Step 5: RED:** feed pagina sem duplicar/pular ingestion_id e não vaza eventos de outro device.
- [x] **Step 6: Implementar routers/services e extrair dependency de sessão mobile reutilizável.**
- [x] **Step 7: GREEN:** testes focados + regressão de mobile session/snapshot.
- [x] **Checkpoint:** `git diff --check`; não commitar.

### Task 4: Cliente e EventProvider do PWA

**Files:**
- Create: `frontend/src/api/maneuverEventClient.ts`
- Create: `frontend/src/api/maneuverEventClient.test.ts`
- Create: `frontend/src/features/events/useEventPolling.ts`
- Create: `frontend/src/features/events/useEventPolling.test.tsx`
- Create: `frontend/src/features/events/EventProvider.tsx`
- Create: `frontend/src/features/events/EventProvider.test.tsx`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/features/pairing/PairingGate.tsx`
- Modify: `frontend/src/features/pairing/PairingGate.test.tsx`

**Interfaces:**
- `getManeuverEvents({after?, before?, limit?}, signal?) -> EventFeedResponse`, sempre `credentials:"same-origin"`, sem Authorization.
- `PairingGate` entrega `sessionReady: boolean`; true somente após POST/recovery de mobile session concluir. Snapshot com VIEW_SECRET pode continuar visível enquanto false.
- `EventState = {events,status,newEvent,loadOlder,hasMore}`.
- Poll 30 s visible; hidden suspende; visibility→visible faz GET imediato.
- Initial fetch sem cursor recebe janela recente e apenas semeia estado: não produz `newEvent`/toast retroativo. Polling seguinte usa `after=newestCursor`.
- Merge por `event_id`/ `ingestion_id`; eventos novos não substituem antigos.
- Se page `after` vier cheia (100), drenar páginas adicionais imediatamente até menos de 100 para não perder burst.

- [x] **Step 1: RED:** client usa cookie same-origin/no-store e mapeia 401 para AccessRevokedError.
- [x] **Step 2: RED:** PairingGate mantém `sessionReady=false` enquanto sincroniza cookie; recovery via cookie retorna true; falha temporária não apaga pairing válido.
- [x] **Step 3: RED:** EventProvider não faz request enquanto `sessionReady=false`; ao virar true faz initial fetch sem emitir `newEvent` para eventos já existentes, depois polling 30s, pause hidden, resume imediato e um request em voo.
- [x] **Step 4: RED Review Focus #1/#3:** retries/páginas repetidas são deduplicadas por event_id e burst >100 é drenado sem gap.
- [x] **Step 5: Implementar provider e encaixar dentro de PairingGate/SnapshotProvider, com revogação reutilizando resetPairing apenas após uma sessão previamente pronta retornar 401.**
- [x] **Step 6: GREEN:** testes PairingGate/client/provider e App.
- [x] **Checkpoint:** não alterar ainda Alertas/Histórico.

### Task 5: Alertas por evento e Histórico por ciclo

**Files:**
- Create: `frontend/src/features/events/projections.ts`
- Create: `frontend/src/features/events/projections.test.ts`
- Modify: `frontend/src/pages/AlertsPage.tsx`
- Modify: `frontend/src/pages/HistoryPage.tsx`
- Modify: `frontend/src/pages/pages.test.tsx`
- Modify: `frontend/src/styles/app.css`

**Interfaces:**
- `alertItems(events) -> newest-first`.
- `maneuverCycles(events) -> groups keyed by maneuver_id`, eventos do ciclo em ordem de ingestion_id.
- Alertas lê query `event`, aplica highlight e `scrollIntoView({block:"center"})` quando encontrado.
- History exibe uma linha/ciclo: confirmação, updates e terminal; não duplica ciclo por delivery push.

- [x] **Step 1: RED:** quatro event types têm texto operacional correto, omitindo POB/berth ausentes.
- [x] **Step 2: RED:** UPDATED renderiza `changes` before→after; POB+berth juntos permanecem um único evento.
- [x] **Step 3: RED:** Histórico agrupa CONFIRMED/UPDATED/COMPLETED do mesmo maneuver_id e mantém shift em dois grupos.
- [x] **Step 4: RED Review Focus #5:** `/alertas?event=e` destaca/rola; evento não carregado aciona carregamento older até achar ou esgotar retenção.
- [x] **Step 5: Implementar páginas/projeções; remover dependência de `recent_maneuvers` como fonte de Alertas/Histórico.**
- [x] **Step 6: GREEN:** pages/projections.
- [x] **Checkpoint:** snapshot continua fonte do mapa/footer operacional.

### Task 6: Schema e repository de push installations/deliveries

**Files:**
- Extend: `api/app/repositories/events.py`
- Modify: `api/app/repositories/memory.py`
- Modify: `api/app/repositories/postgres.py`
- Modify: `api/app/repositories/supabase.py`
- Create: `api/supabase/migrations/005_push_installations_deliveries.sql`
- Create: `api/tests/unit/test_push_repository_contract.py`
- Create: `api/tests/integration/test_push_repository.py`
- Modify: `api/tests/unit/test_access_service.py`
- Modify: `api/tests/integration/test_put_view_access.py`

**Interfaces:**
- `PushPreferences(confirmed=True, updated=True, completed=True, cancelled=True)`.
- `PushInstallation(installation_id UUID, device_id, endpoint, p256dh, auth, preferences, push_enabled_at, last_seen_at, last_foreground_at, active)`.
- `AlertaRepository` é estendido por `PushRepository`; Memory/Postgres/Supabase implementam o contrato composto.
- `PushDeliveryStatus = SENDING | DELIVERED | IGNORED_PREFERENCE | IGNORED_FOREGROUND | IGNORED_BEFORE_OPT_IN | RETRY_PENDING | PERMANENT_FAILURE`.
- Unique `(event_id, installation_id)`.
- `claim_push_delivery(event_id, installation_id) -> bool`: cria claim SENDING; RETRY_PENDING ou SENDING com lease expirado são recuperáveis; SENDING recente e estados terminais não duplicam.
- Lease de claim = 8 s; WebPushGateway usa timeout = 5 s. Isso permite ao retry Desktop de 10 s recuperar processo morto sem liberar duas claims normais simultâneas.
- `record_ignored_delivery(event_id, installation_id, status)` grava exatamente uma classificação IGNORED_* sem chamar provider.
- VIEW_SECRET rotation desativa todas as installations do device na mesma operação SQL.

- [x] **Step 1: RED:** duas instalações do mesmo device mantêm preferences/subscriptions independentes.
- [x] **Step 2: RED:** primeira ativação e reativação após disable definem novo `push_enabled_at`; atualização normal de subscription ativa preserva.
- [x] **Step 3: RED:** claim concorrente para mesmo evento×instalação só permite um sender; SENDING <8 s não é retomado e SENDING >=8 s pode ser recuperado.
- [x] **Step 4: RED Review Focus #4:** rotate VIEW_SECRET desativa todas do device e nenhuma de outro device.
- [x] **Step 5: Migration 005:** tabelas, constraints, índices, RLS/revokes, delivery unique e replacement do RPC de rotação.
- [x] **Step 6: Implementar Memory/Postgres/Supabase equivalentes.**
- [x] **Step 7: GREEN:** repository/access regressions.
- [x] **Checkpoint:** `git diff --check`.
> **Validação Task 6:** testes unitários/MockTransport e regressões de access estão verdes. O teste de integração PostgreSQL foi skip por ausência de `TEST_POSTGRES_DSN`; validar migrations 004/005 em Postgres/Supabase real antes de considerar a Etapa 2 concluída.


### Task 7: API de instalação, preferências e heartbeat

**Files:**
- Create: `api/app/models/push.py`
- Create: `api/app/services/push_installation_service.py`
- Create: `api/app/api/v1/push.py`
- Modify: `api/app/api/v1/router.py`
- Modify: `api/app/core/config.py`
- Modify: `api/app/main.py`
- Modify: `api/.env.example`
- Modify: `api/.env.prod.example`
- Create: `api/tests/unit/test_push_installation_service.py`
- Create: `api/tests/integration/test_push_installations.py`
- Modify: `api/tests/unit/test_config.py`

**Interfaces / endpoints:**
- Settings: `web_push_enabled=false`, `vapid_public_key`, secret `vapid_private_key`, `vapid_subject`, `push_foreground_fresh_seconds=75`.
- `GET /api/v1/mobile/push/vapid-public-key`.
- `GET /api/v1/mobile/push/installations/{installation_id}`.
- `PUT /api/v1/mobile/push/installations/{installation_id}` registra/reativa subscription; defaults das quatro prefs = true.
- `PATCH /api/v1/mobile/push/installations/{installation_id}/preferences`.
- `POST /api/v1/mobile/push/installations/{installation_id}/foreground`.
- `DELETE /api/v1/mobile/push/installations/{installation_id}` inativa e limpa endpoint/chaves sensíveis.
- Todos usam cookie session; installation_id de outro device responde 404 genérico.

- [ ] **Step 1: RED:** VAPID config exige public/private/subject apenas quando web_push_enabled=true; private nunca aparece em repr/response.
- [ ] **Step 2: RED:** PUT vincula device da sessão, ignora qualquer tentativa de escolher device no body e inicia quatro prefs true.
- [ ] **Step 3: RED:** PATCH muda só prefs daquela instalação; DELETE não afeta outra instalação.
- [ ] **Step 4: RED:** heartbeat atualiza last_seen/last_foreground somente da instalação ativa.
- [ ] **Step 5: RED:** sessão expirada bloqueia administração da instalação, mas não altera `active` automaticamente.
- [ ] **Step 6: Implementar endpoints/service; adicionar PATCH/DELETE ao CORS permitido.**
- [ ] **Step 7: GREEN:** API push installation + config/CORS.
- [ ] **Checkpoint:** não implementar envio ainda.

### Task 8: Gateway VAPID/pywebpush e classificação de falhas

**Files:**
- Modify: `api/pyproject.toml`
- Modify: `api/uv.lock`
- Create: `api/app/infrastructure/web_push.py`
- Create: `api/tests/unit/test_web_push_gateway.py`

**Interfaces:**
- `WebPushGateway.send(installation, payload) -> None`, com timeout de provider = 5.0 s.
- `PermanentPushError`: provider 404/410 e demais 4xx não recuperáveis.
- `TransientPushError`: timeout/network, 429, 5xx.
- Payload JSON contém apenas `event_id,title,body,url`.
- Usa `pywebpush.webpush(..., vapid_private_key, vapid_claims={"sub": subject})`.

- [ ] **Step 1: RED:** gateway monta subscription_info somente em memória e sender recebe VAPID private key sem log/repr.
- [ ] **Step 2: RED:** 404/410 → PermanentPushError; 429/5xx/network/timeout → TransientPushError; sender recebe timeout=5.0.
- [ ] **Step 3: RED:** mensagem nunca inclui endpoint/keys completos em exceção/log seguro.
- [ ] **Step 4: Adicionar `pywebpush>=2.5,<3` e implementar wrapper injetável.**
- [ ] **Step 5: GREEN:** gateway tests.
- [ ] **Checkpoint:** `uv lock` controlado; sem chamada de rede em testes.

### Task 9: PushDispatchService e delivery bookkeeping

**Files:**
- Create: `api/app/services/push_dispatch_service.py`
- Modify: `api/app/services/maneuver_event_service.py`
- Modify: `api/app/main.py`
- Create: `api/tests/unit/test_push_dispatch_service.py`
- Modify: `api/tests/integration/test_post_maneuver_event.py`

**Interfaces:**
- `PushDispatchService.dispatch_event(stored_event) -> None`.
- Para cada instalação ativa: classificar opt-in time → preference → foreground → claim → send → status.
- Foreground recente: `clock - last_foreground_at <= 75s`.
- Title/body construídos em função pura `build_push_message(event)`.
- Accepted e idempotent POST chamam dispatcher; delivery terminal impede reenvio.

- [ ] **Step 1: RED Review Focus #2:** occurred_at anterior a push_enabled_at → IGNORED_BEFORE_OPT_IN e zero send.
- [ ] **Step 2: RED:** preferência off → IGNORED_PREFERENCE; foreground 75s → IGNORED_FOREGROUND.
- [ ] **Step 3: RED:** eligible envia e marca DELIVERED; permanent inativa instalação + PERMANENT_FAILURE; transient → RETRY_PENDING.
- [ ] **Step 4: RED Review Focus #1:** evento persistido com delivery ausente + POST idempotente posterior completa delivery; DELIVERED existente não envia de novo.
- [ ] **Step 5: RED:** falha/exception do dispatcher nunca transforma ACK do evento em erro.
- [ ] **Step 6: Implementar e injetar gateway/repository/clock.**
- [ ] **Step 7: GREEN:** dispatcher + POST integration.
- [ ] **Checkpoint:** nenhum worker/Redis adicional.

### Task 10: installation_id e PushSubscription no frontend

**Files:**
- Create: `frontend/src/features/push/installationId.ts`
- Create: `frontend/src/features/push/installationId.test.ts`
- Create: `frontend/src/api/pushClient.ts`
- Create: `frontend/src/api/pushClient.test.ts`
- Create: `frontend/src/features/push/PushProvider.tsx`
- Create: `frontend/src/features/push/PushProvider.test.tsx`
- Modify: `frontend/src/app/App.tsx`

**Interfaces:**
- localStorage key `alertam.mobile.installation.v1`; UUID via `crypto.randomUUID()`.
- `enablePush()`: gesto UI → Notification.requestPermission → serviceWorker.ready → PushManager.subscribe → PUT API.
- `disablePush()`: DELETE API best-effort → `subscription.unsubscribe()`; mantém pairing.
- Provider expõe support/permission/active/preferences/error + enable/disable/updatePreference.
- Provider só ativa requests quando `sessionReady=true`; 401 após sessão pronta chama resetPairing; erro temporário mantém estado local seguro.

- [ ] **Step 1: RED:** installation_id persiste entre reloads e é apagado somente no fluxo explícito de forget.
- [ ] **Step 2: RED:** permission só é pedida por `enablePush`, nunca automaticamente ao montar provider.
- [ ] **Step 3: RED:** subscribe usa `userVisibleOnly:true` + VAPID public key convertida para Uint8Array.
- [ ] **Step 4: RED:** disable afeta só installation_id atual; API e unsubscribe são best-effort sem limpar pairing.
- [ ] **Step 5: Implementar provider/client e encaixar no App.**
- [ ] **Step 6: GREEN:** push frontend unit tests.

### Task 11: injectManifest, push e notificationclick

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/vite.config.ts`
- Create: `frontend/src/sw.ts`
- Modify: `frontend/src/features/install/pwaConfig.ts`
- Modify: `frontend/src/features/install/pwaConfig.test.ts`
- Create: `frontend/src/features/push/serviceWorkerLogic.ts`
- Create: `frontend/src/features/push/serviceWorkerLogic.test.ts`

**Interfaces:**
- VitePWA: `strategies:"injectManifest"`, `srcDir:"src"`, `filename:"sw.ts"`, `registerType:"autoUpdate"`.
- Workbox explicit deps: `workbox-core`, `workbox-precaching`, `workbox-routing`, `workbox-strategies`.
- SW: `precacheAndRoute(self.__WB_MANIFEST)`, cleanup outdated, clientsClaim/skipWaiting.
- API GET route continua NetworkOnly.
- push: parse payload seguro, showNotification(title,{body,tag:event_id,renotify:false,data:{url,event_id}}), reduzindo duplicata visual em rara reentrega após crash no boundary do provider.
- notificationclick: fechar notificação; localizar WindowClient same-origin; `navigate(url)` + `focus()`; fallback `openWindow(url)`.

- [ ] **Step 1: RED:** config prova injectManifest e NetworkOnly da API.
- [ ] **Step 2: RED:** payload inválido não quebra SW nem mostra conteúdo inventado; duas entregas do mesmo event_id usam o mesmo notification tag.
- [ ] **Step 3: RED Review Focus #5:** click prefere janela existente e navega para `/alertas?event=...`; sem janela usa openWindow.
- [ ] **Step 4: Migrar config e implementar SW/custom logic.**
- [ ] **Step 5: GREEN:** unit tests + `npm run build`; inspecionar build para `sw.js` e manifest.
- [ ] **Checkpoint:** instalação PWA anterior continua autoUpdate.

### Task 12: Config, heartbeat e aviso foreground

**Files:**
- Modify: `frontend/src/pages/ConfigPage.tsx`
- Modify: `frontend/src/pages/pages.test.tsx`
- Create: `frontend/src/features/push/useForegroundHeartbeat.ts`
- Create: `frontend/src/features/push/useForegroundHeartbeat.test.tsx`
- Modify: `frontend/src/app/AppShell.tsx`
- Modify: `frontend/src/app/AppShell.test.tsx`
- Modify: `frontend/src/features/pairing/PairingGate.tsx`
- Modify: `frontend/src/features/pairing/PairingGate.test.tsx`
- Modify: `frontend/src/styles/app.css`

**Interfaces:**
- Heartbeat somente quando push active + visible: imediato e a cada 30s; hidden pausa.
- AppShell mostra toast/banner interno para `EventState.newEvent` quando visible; ação navega `/alertas?event=<id>`.
- Config: Ativar/Desativar notificações + quatro toggles; permissão denied explica sem loop de prompt.
- Forget: primeiro disable instalação atual + clear installation_id, depois sessão/pairing; falhas de rede são best-effort.
- DemoMode nunca registra push/heartbeat real.

- [ ] **Step 1: RED:** quatro toggles aparecem ligados após primeiro opt-in e persistem resposta server.
- [ ] **Step 2: RED:** toggles mudam independentemente; desativar notificação mantém pairing.
- [ ] **Step 3: RED:** heartbeat 30s visible, zero hidden, imediato no retorno.
- [ ] **Step 4: RED:** evento novo foreground cria notice interno clicável sem chamar Notification API.
- [ ] **Step 5: RED:** Forget afeta somente instalação atual e limpa installation_id/pairing mesmo se DELETE remoto falhar.
- [ ] **Step 6: Implementar UI/hooks e CSS.**
- [ ] **Step 7: GREEN:** pages/AppShell/PairingGate/push tests.

### Task 13: Retenção, gates, E2E e documentação

**Files:**
- Create: `api/supabase/migrations/006_event_retention.sql`
- Create: `api/tests/unit/test_event_retention_sql.py`
- Modify: `specs/020-frontend-mobile-pwa.md`
- Modify: `specs/021-maneuver-events-webpush.md`
- Modify: `specs/README.md`
- Modify: `api/.env.example`, `api/.env.prod.example` se necessário
- Modify: docs/deploy relevantes
- Modify: `frontend/e2e/mobile.spec.ts`.

**Interfaces:**
- SQL cleanup function removes `push_deliveries` and `maneuver_events` older than 30 days sem tocar eventos recentes; agendamento Supabase Cron é documentado/deploy-gated.
- No cleanup no caminho crítico do POST.
- SPEC 020 recebe nota de supersessão para Alertas/Histórico/Config push.

- [ ] **Step 1: RED:** SQL retention contract contém janela 30 days e ordem delivery→event; não apaga installation ativa.
- [ ] **Step 2: API gate:** `cd api && uv run pytest -q`.
- [ ] **Step 3: Frontend gate:** `cd frontend && npm test -- --run`.
- [ ] **Step 4: Build gate:** `cd frontend && npm run build`.
- [ ] **Step 5: E2E em `frontend/e2e/mobile.spec.ts`:** feed Alertas/History; `?event` highlight; Config enable/preferences/disable com Push API fake; notificationclick logic; forget installation.
- [ ] **Step 6: Contract gate:** fixture ManeuverEvent Desktop → POST → feed sem perda; shift COMPLETED antes de CONFIRMED com mesmo occurred_at preserva ingestion order.
- [ ] **Step 7: Security review:** logs/erros não contêm secrets, cookies, VAPID private ou subscription endpoint completo.
- [ ] **Step 8: `git diff --check` + revisão linha a linha contra SPEC 021/design.**
- [ ] **Step 9: Revisão final independente quando reviewer disponível; Critical/Important voltam a RED→GREEN.**
- [ ] **Step 10: Atualizar SPEC 021 com evidência real e status; não afirmar push real em browser sem smoke real.**
- [ ] **Checkpoint final:** deixar working tree para revisão do Ciro; sem commit/push.

---

## Decisões técnicas fechadas por este plano

1. **Feed:** `GET /api/v1/mobile/maneuver-events` com `after`/ `before` por `ingestion_id`, resposta normalizada em ordem ascendente.
2. **Polling de eventos:** 30 s visible + fetch imediato no resume; bursts são drenados por cursor.
3. **installation_id:** UUID `crypto.randomUUID()` persistido em `alertam.mobile.installation.v1`.
4. **Heartbeat:** 30 s; foreground freshness = 75 s.
5. **Web Push Python:** `pywebpush>=2.5,<3` atrás de `WebPushGateway` injetável.
6. **Service worker:** `injectManifest` TypeScript + Workbox; `autoUpdate` preservado.
7. **Delivery crash-safety:** evento ACCEPTED ou IDEMPOTENT chama dispatcher; unique/claim com lease de 8 s em `push_deliveries` decide se deve enviar, não o status do POST. Exatamente-once no provider não é garantível; tag=event_id mitiga reentrega visual.
8. **Retry cloud MVP:** transitório fica `RETRY_PENDING`; idempotent re-entry pode recuperar claim. Nenhum Redis/worker obrigatório nesta etapa.
9. **Retenção:** função SQL de cleanup 30d + agendamento de deploy Supabase Cron; nunca dentro do POST de evento.
10. **Reativação:** novo opt-in após disable redefine `push_enabled_at`, evitando replay do período desligado.

## Self-review contra SPEC 021/design

- Evento idempotente e mismatch: Tasks 1–3.
- Ordem de shift/ingestion: Tasks 2, 3 e 13.
- Feed device-scoped/paginação: Tasks 2–5.
- Alertas event_id / Histórico maneuver_id: Task 5.
- Installation independente/preferências: Tasks 6, 7, 10, 12.
- No replay via push_enabled_at: Tasks 6 e 9.
- Cookie expirar não desativa push: Tasks 6–7.
- VIEW_SECRET rotation revoga todas: Task 6.
- Forget só instalação atual: Tasks 7, 10, 12.
- VAPID / WebPush: Tasks 8–9.
- Falha permanente/transitória: Tasks 8–9.
- Foreground internal vs system push: Tasks 9 e 12.
- injectManifest / notificationclick: Task 11.
- Retenção 30d: Task 13.
- Segurança/no secrets: Tasks 1, 3, 7–9, 13.
- Snapshot continua independente/latest-only: nenhuma task altera a semântica do SyncPublisher/snapshot.

## Critério de saída da Etapa 2

A Etapa 2 só pode ser considerada concluída quando:
1. Desktop ManeuverEvent roundtripa pela API e aparece no feed sem perda;
2. retry de event_id não duplica evento nem delivery;
3. PWA Alertas/Histórico não dependem mais de recent_maneuvers para eventos;
4. duas instalações têm preferências independentes;
5. push antigo não é replayado após opt-in;
6. rotação de VIEW_SECRET revoga todas as installations;
7. service worker builda via injectManifest e notificationclick navega corretamente;
8. foreground produz aviso interno e suprime system push best-effort;
9. API tests, frontend tests, build, E2E relevante e diff-check passam;
10. qualquer limitação de smoke Web Push real é reportada explicitamente.
