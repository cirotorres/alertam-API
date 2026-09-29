# Ship Tracking — Installations & Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Tornar Ship Tracking realmente installation-scoped, persistente sem PushSubscription e capaz de entregar
ManeuverEvent/VesselTrackingEvent sem replay nem duplicação.

**Architecture:** A sessão mobile passa a assinar `device_id + installation_id`, apoiada por
`mobile_installations` independente de Web Push. `tracked_vessels` guarda a intenção e projeção mais
recente; dispatch consulta essa intenção no momento do evento, sem jobs de replay.

**Tech Stack:** FastAPI, Pydantic v2, PostgreSQL/Supabase, Web Push existente, React session client.

**Spec:** `specs/023-ship-tracking.md`

## Global Constraints

- Tracking funciona mesmo sem PushSubscription.
- O cliente nunca escolhe livremente installation_id de outra sessão.
- Tracking não expira automaticamente.
- started_at impede replay de push, não precisa apagar histórico retido anterior.
- Categoria geral + tracking para o mesmo ManeuverEvent = um único push.
- Categoria geral vence o destino: `/alertas?event=`.
- Somente tracking = `/acompanhados?track=...&event=...`.
- Não fazer commit/push sem autorização explícita.

## Review Focus

- Cookie válido de um aparelho tentando operar tracked_vessel de outro installation_id do mesmo device.
- Push desligado desde o primeiro pareamento: tracking precisa criar/persistir normalmente.
- Recriação da PushSubscription usando o mesmo installation_id sem replay de eventos antigos.
- NAME fallback recebe IMO explícito: promover apenas match exato de nome normalizado.
- Evento e started_at na mesma fronteira temporal: elegibilidade determinística e sem replay.
---

### Task 1: Mobile installation como identidade de sessão

**Files:**
- Modify: `api/app/models/mobile_session.py`
- Modify: `api/app/services/mobile_session_service.py`
- Modify: `api/app/api/v1/mobile_session.py`
- Modify: `api/app/api/v1/mobile_auth.py`
- Modify: `api/app/repositories/devices.py`
- Modify concrete repositories Memory/Postgres/Supabase.
- Create: `api/supabase/migrations/010_mobile_installations.sql`
- Modify: `frontend/src/features/pairing/mobileSessionClient.ts`
- Modify: `frontend/src/features/pairing/PairingGate.tsx`
- Modify: `frontend/src/features/push/installationId.ts`

**Interfaces:**
- Produce: `MobileSessionPrincipal(device_id: str, installation_id: UUID)`.
- `MobileSessionRequest`/`Response` include `installation_id`.
- Keep `MobileSessionAuth` returning device_id for old routes; add installation-aware dependency for tracking routes.

- [x] **Step 1:** RED para sessão criar/recuperar mesma mobile_installation e token assinar ambos IDs.
- [x] **Step 2:** RED para installation_id de outro device ser rejeitado/revogado com segurança.
- [x] **Step 3:** RED frontend para getOrCreateInstallationId ocorrer no pareamento, sem depender de enablePush.
- [x] **Step 4:** RED migration para backfill de `mobile_installations` a partir das `push_installations` existentes, preservando o mesmo UUID.
- [x] **Step 5:** Implementar migration/repository/session mantendo cookies antigos inválidos de forma segura.
- [x] **Step 6:** RED para rotação VIEW_SECRET revogar mobile_installations e trackings em transação.
- [x] **Step 7:** Rodar suites mobile session/pairing + Postgres real.
### Task 2: tracked_vessels e lifecycle installation-scoped

**Files:**
- Create: `api/app/models/tracked_vessel.py`
- Extend: `api/app/repositories/tracking.py`
- Create: `api/app/services/tracked_vessel_service.py`
- Create: `api/app/api/v1/tracked_vessels.py`
- Create: `api/supabase/migrations/011_tracked_vessels.sql`
- Modify concrete repositories and router.
- Test unit/integration/Supabase/Postgres equivalents.

**Interfaces:**
- Produce GET/POST/DELETE `/api/v1/mobile/tracked-vessels`.
- POST input: `vessel_identity,vessel_imo,vessel_name`; installation vem da sessão.
- Produce: `TrackedVessel` com started_at/active/stopped_at/last_seen_at/current.

- [x] **Step 1:** RED para criar tracking idempotente na mesma instalação e independente em instalação diferente.
- [x] **Step 2:** RED para alvo ser aceito somente se existir no snapshot atual ou em evento retido do mesmo device, semeando `current/last_seen_at` dessa evidência.
- [x] **Step 3:** RED para DELETE idempotente desativar sem apagar histórico.
- [x] **Step 4:** RED para ausência ou conclusão de manobra não expirar tracking e cookie expirado não apagar intenção.
- [x] **Step 5:** RED para NAME → IMO somente por nome normalizado exatamente igual e evidência explícita.
- [x] **Step 6:** Implementar service/repositories/endpoints com principal installation-scoped.
### Task 3: Projeção atual e timeline cloud unificada

**Files:**
- Create: `api/app/services/tracked_vessel_projection_service.py`
- Create: `api/app/services/tracked_vessel_timeline_service.py`
- Extend: `api/app/repositories/tracking.py` e concrete repositories.
- Modify ManeuverEvent/VesselTrackingEvent ingest services para alimentar projeção.
- Extend `api/app/api/v1/tracked_vessels.py`.
- Tests: unit/integration para projeção/timeline.

**Interfaces:**
- ManeuverEvent e VesselTrackingEvent atualizam `last_seen_at/current` dos trackings compatíveis.
- GET `/{tracked_vessel_id}/events` retorna union discriminada `MANEUVER|TRACKING`.
- Order: occurred_at ASC, ingested_at ASC, event_id ASC.

- [x] **Step 1:** RED para VesselTrackingEvent atualizar current/presence/status/ETA/etc de todos os trackings do navio.
- [x] **Step 2:** RED para ManeuverEvent atualizar estado operacional inferível sem criar VesselTrackingEvent.
- [x] **Step 3:** RED para timeline misturar os dois tipos e manter eventos anteriores a started_at como contexto histórico retido.
- [x] **Step 4:** RED para instalação não acessar timeline de tracking alheio.
- [x] **Step 5:** Implementar query/projeção com desempate determinístico e retenção de 30 dias.
- [x] **Step 6:** Rodar unit/integration/Postgres.
### Task 4: Feed agregado de VesselTrackingEvent para foreground

**Files:**
- Extend: `api/app/models/tracked_vessel.py`
- Extend: `api/app/services/tracked_vessel_service.py`
- Extend: `api/app/api/v1/tracked_vessels.py`
- Extend repositories tracking.
- Tests: `api/tests/integration/test_get_tracked_vessel_events_feed.py`.

**Interfaces:**
- GET `/api/v1/mobile/tracked-vessels/events?after=<ingestion_id>&limit=<n>`.
- Retorna somente VesselTrackingEvent de trackings ativos desta instalação com occurred_at >= started_at.
- Cursor usa ingestion_id da tabela vessel_tracking_events.

- [x] **Step 1:** RED para cursor crescente; `occurred_at < started_at` fica fora e `occurred_at == started_at` é elegível.
- [x] **Step 2:** RED para dois celulares do mesmo device receberem feeds diferentes conforme seus trackings.
- [x] **Step 3:** RED para tracking desativado não receber novos eventos mas histórico individual continuar consultável.
- [x] **Step 4:** Implementar feed sem incluir ManeuverEvent e sem N queries por tracked vessel.
- [x] **Step 5:** Rodar suites API focadas e Postgres real.
### Task 5: Elegibilidade de ManeuverEvent via tracking sem duplicação

**Files:**
- Modify: `api/app/services/push_dispatch_service.py`
- Extend repository tracking lookup.
- Modify/add: `api/tests/unit/test_push_dispatch_service.py`
- Modify/add integration push tests.

**Interfaces:**
- Para cada PushInstallation ativa, eligibility = categoria geral OR tracked_vessel ativo.
- Um único claim continua usando `event_id + installation_id`.
- URL: categoria geral elegível → `/alertas?event=...`; somente tracking → `/acompanhados?track=...&event=...`.

- [x] **Step 1:** RED para categoria off + tracking on ainda enviar ManeuverEvent.
- [x] **Step 2:** RED para categoria on + tracking on gerar exatamente um delivery e manter /alertas.
- [x] **Step 3:** RED para tracking iniciado depois de occurred_at não tornar evento antigo elegível.
- [x] **Step 4:** RED para PushInstallation ausente/inativa não impedir tracking salvo nem criar delivery.
- [x] **Step 5:** Implementar resolução de tracked_vessel + mensagem/destino sem alterar categorias globais.
- [x] **Step 6:** Rodar dispatch unit/integration.
### Task 6: Dispatch de VesselTrackingEvent, deliveries e revogação

**Files:**
- Extend: `api/app/services/push_dispatch_service.py` ou criar `tracking_push_dispatch_service.py`.
- Extend: `api/app/repositories/tracking.py`.
- Create: `api/supabase/migrations/012_vessel_tracking_deliveries.sql`.
- Modify VesselTrackingEvent ingest route para disparar dispatch best-effort.
- Tests unit/integration/Web Push.

**Interfaces:**
- Delivery key: tracking_event_id + installation_id.
- Estados: SENDING, DELIVERED, IGNORED_FOREGROUND, IGNORED_BEFORE_TRACKING,
  RETRY_PENDING, PERMANENT_FAILURE.
- Deep link: `/acompanhados?track=<tracked_vessel_id>&event=<event_id>`.

- [x] **Step 1:** RED para somente instalações que acompanham o navio serem candidatas.
- [x] **Step 2:** RED para foreground heartbeat suprimir Web Push e falha numa instalação não bloquear outra.
- [x] **Step 3:** RED para reativar push não reenviar eventos antigos; dispatch ocorre somente no ingest original.
- [x] **Step 4:** RED para mensagem de disappearance nunca dizer “desatracou” sem ManeuverEvent.
- [x] **Step 5:** RED para revogação/Esquecer aparelho desativar trackings e deliveries futuros.
- [x] **Step 6:** Implementar migration/repository/dispatch e rodar `make test-all`.
- [x] **Step 7:** Auto-revisar isolamento, replay e duplicação; parar antes do Plano 3 sem commit/push não autorizado.
