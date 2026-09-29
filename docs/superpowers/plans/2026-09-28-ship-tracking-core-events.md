# Ship Tracking — Core Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Criar o pipeline confiável de VesselTrackingEvent do Desktop até a API, sem UI nem dispatch por instalação ainda.

**Architecture:** O Desktop mantém um detector puro separado de ManeuverTracker, recebe os ManeuverEvent
da mesma coleta para remover campos já cobertos semanticamente e persiste state + outbox + ledger de forma
atômica. A API aceita eventos idempotentes via Device auth, persiste por 30 dias e não redetecta mudanças.

**Tech Stack:** Python 3.12+, dataclasses, pytest, FastAPI/Pydantic v2, psycopg, Supabase/PostgREST.

**Spec:** `specs/023-ship-tracking.md`

## Global Constraints

- ManeuverEvent continua canônico para manobras.
- VesselTrackingEvent cobre somente `presence,status,section,berth,side,eta,etb_ets,pob` residuais.
- `pob_at` é normalizado no Desktop; frontend/API nunca inferem POB textual.
- Primeira coleta e primeira coleta após restart semeiam/reconciliam baseline sem replay.
- Snapshot inválido nunca vira desaparecimento.
- Ledger/outbox têm responsabilidades separadas; retenção do ledger e cloud é 30 dias.
- API offline nunca bloqueia coleta.
- Não fazer commit/push sem autorização explícita.

## Review Focus

- Mesmo navio muda POB/berço e ETA junto com ManeuverEvent: somente ETA fica em VesselTrackingEvent.
- Navio desaparece durante falha de coleta: nenhum evento de presença pode nascer.
- Restart após horas/dias: diferenças do downtime reconciliam sem replay.
- Nome fallback com novo IMO exato: identidade preservada/promovida sem fuzzy match.
- Falha de persistência local: state/eventos pendentes ficam em memória para retry sem travar coleta.
---

### Task 1: Contrato Desktop e detector residual puro

**Files:**
- Create: `src/alertam/domain/vessel_tracking.py`
- Create: `src/alertam/application/vessel_tracking_detector.py`
- Test: `tests/unit/test_vessel_tracking_models.py`
- Test: `tests/unit/test_vessel_tracking_detector.py`

**Interfaces:**
- Produce: `VesselTrackingCurrent`, `VesselObservation`, `VesselTrackingEvent`,
  `VesselTrackingState`, `VesselTrackingResult`.
- Produce: `VesselTrackingDetector.observe(snapshot: Snapshot, maneuver_events: tuple[ManeuverEvent, ...] = ()) -> VesselTrackingResult`.

- [ ] **Step 1:** Testar serialização round-trip do evento/current e identidade IMO → nome normalizado.
- [ ] **Step 2:** Testar baseline inicial sem evento e baseline de restart reconciliado sem replay.
- [ ] **Step 3:** Testar debounce: ETA estável gera um evento; oscilação que volta gera zero.
- [ ] **Step 4:** Testar múltiplos campos na mesma confirmação gerando um único evento.
- [ ] **Step 5:** Testar desaparecimento/reaparecimento e regra de intervalo longo.
- [ ] **Step 6:** Testar supressão residual: UPDATED de POB/berço não duplica; ETA/side simultâneos permanecem.
- [ ] **Step 7:** Testar promoção NAME→IMO somente quando o mesmo nome normalizado reaparece com IMO explícito; sem fuzzy match.
- [ ] **Step 8:** Implementar detector com `first_observed_at`, `occurred_at` e `maneuver_id` quando houver ManeuverEvent correlato.
- [ ] **Step 9:** Rodar `uv run pytest tests/unit/test_vessel_tracking_models.py tests/unit/test_vessel_tracking_detector.py -q`.
### Task 2: Runtime, ledger e outbox local

**Files:**
- Create: `src/alertam/application/vessel_tracking_runtime.py`
- Create: `src/alertam/application/vessel_tracking_coordinator.py`
- Create: `src/alertam/infrastructure/vessel_tracking_runtime_store.py`
- Test: `tests/unit/test_vessel_tracking_runtime_store.py`
- Test: `tests/unit/test_vessel_tracking_coordinator.py`

**Interfaces:**
- Produce: `VesselTrackingRuntime(state, outbox, event_history)`.
- Produce: `commit_transition(state, events) -> bool`, `peek_event()`, `ack_event(event_id)`,
  `events_for_vessel(identity)`.
- Produce: `VesselTrackingCoordinator.handle(snapshot, maneuver_events) -> VesselTrackingResult`.

- [ ] **Step 1:** RED para escrita atômica de state + outbox + ledger e dedupe por event_id.
- [ ] **Step 2:** RED para ACK remover só outbox e restart preservar ledger.
- [ ] **Step 3:** RED para retenção de 30 dias podar somente ledger, nunca evento ainda pendente.
- [ ] **Step 4:** RED para corrupção/falha de arquivo recuperar runtime seguro sem bloquear coleta.
- [ ] **Step 5:** RED para coordinator manter transição em memória quando persistência falha e notificar publisher só após persistência.
- [ ] **Step 6:** Implementar store/coordinator seguindo o padrão de ManeuverRuntime sem reutilizar sua outbox.
- [ ] **Step 7:** Rodar testes focados e `uv run pytest -q`.
### Task 3: Publisher FIFO e integração no ciclo Desktop

**Files:**
- Create: `src/alertam/infrastructure/vessel_tracking_event_http.py`
- Create: `src/alertam/infrastructure/vessel_tracking_event_publisher.py`
- Modify: `src/alertam/application/controller.py`
- Modify: `src/alertam/bootstrap.py`
- Test: `tests/unit/test_vessel_tracking_event_publisher.py`
- Test: `tests/unit/test_vessel_tracking_bootstrap.py`
- Test: `tests/unit/test_controller_pipeline.py`

**Interfaces:**
- Consume: ManeuverCoordinator result da mesma coleta.
- Produce: POST `/api/v1/devices/{device_id}/vessel-tracking-events` com Device auth.

- [ ] **Step 1:** RED para FIFO/retry/ACK idempotente do publisher e API offline sem bloquear thread de coleta.
- [ ] **Step 2:** RED para controller chamar tracking somente depois de ManeuverTracker e passar os ManeuverEvent da coleta.
- [ ] **Step 3:** RED para caminho de erro/timeout não chamar detector de tracking.
- [ ] **Step 4:** RED para bootstrap carregar runtime, reconciliar primeira coleta e iniciar/parar publisher junto do app.
- [ ] **Step 5:** Implementar transporte/publisher e wiring.
- [ ] **Step 6:** Rodar testes focados e suíte Desktop completa; registrar Xephyr como gate futuro de UX, não desta etapa.
### Task 4: Contrato e ingestão idempotente na API

**Files:**
- Create: `api/app/models/vessel_tracking_event.py`
- Create: `api/app/services/vessel_tracking_event_service.py`
- Create: `api/app/api/v1/vessel_tracking_events.py`
- Create: `api/app/repositories/tracking.py`
- Modify: `api/app/repositories/events.py`
- Modify: `api/app/repositories/memory.py`
- Modify: `api/app/repositories/postgres.py`
- Modify: `api/app/repositories/supabase.py`
- Modify: `api/app/api/v1/router.py`
- Create: `api/supabase/migrations/008_vessel_tracking_events.sql`
- Test: contract/unit/integration equivalents de ManeuverEvent.

**Interfaces:**
- Produce: `VesselTrackingEventIn`, `StoredVesselTrackingEvent`, `AcceptTrackingEventResult`.
- Produce repository: `accept_vessel_tracking_event_atomic(device_id, event)`.

- [ ] **Step 1:** RED Pydantic strict para contrato completo, timestamps aware e changes/current permitidos.
- [ ] **Step 2:** RED repository para ACCEPTED, DUPLICATE e CONFLICT com mesmo event_id/payload divergente.
- [ ] **Step 3:** RED HTTP para Device auth, 202/200 idempotente e conflito seguro.
- [ ] **Step 4:** Criar tabela com colunas indexáveis de identity/occurred_at + payload imutável e ingestion_id.
- [ ] **Step 5:** Implementar Memory/Postgres/Supabase mantendo o mesmo contrato.
- [ ] **Step 6:** Rodar `make test-unit`, `make test-contract`, `make test-integration`.
### Task 5: Retenção e smoke Desktop → API

**Files:**
- Create: `api/supabase/migrations/009_vessel_tracking_retention.sql`
- Create: `api/tests/unit/test_vessel_tracking_retention_sql.py`
- Modify: `api/tests/integration/test_accept_vessel_tracking_event_repository.py`
- Add/update Desktop/API contract fixture for VesselTrackingEvent.

**Interfaces:**
- Retention: eventos com `ingested_at < now() - interval '30 days'`.
- No deletion of local/cloud tracking preference; somente eventos expiram.

- [ ] **Step 1:** RED para migration de retenção não tocar ManeuverEvent/tracked preferences.
- [ ] **Step 2:** RED Postgres real para retenção e índices de `device_id + vessel_identity + ingestion_id`.
- [ ] **Step 3:** Gerar evento real pelo dataclass Desktop, validar com Pydantic API e persistir/ler no repository.
- [ ] **Step 4:** Rodar `make test-all` e a suíte Desktop completa.
- [ ] **Step 5:** Auto-revisar: nenhum novo áudio, UI ou regra de dispatch deve ter entrado neste plano.
- [ ] **Step 6:** Parar para revisão humana antes do Plano 2; não commit/push sem autorização.
