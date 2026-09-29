# Ship Tracking — Desktop & PWA UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Expor Ship Tracking ao operador no Desktop e na PWA, com ações acompanhar/parar, página Acompanhados,
timeline unificada, foreground e deep links, sem alterar semântica de manobra ou áudio.

**Architecture:** O Desktop possui tracking local independente, lendo o mesmo estado/event ledger do detector remoto
mas com lista de favoritos própria. A PWA usa TrackingProvider installation-scoped, reutiliza BottomSheetFrame e
combina o feed existente de ManeuverEvent com o feed de VesselTrackingEvent para foreground sem duplicar UX.

**Tech Stack:** Tkinter, pytest/Xephyr, React 19, TypeScript, Zod, Vitest, Playwright.

**Spec:** `specs/023-ship-tracking.md`

## Global Constraints

- Tracking Desktop e tracking PWA nunca sincronizam automaticamente.
- ★ é marcador adicional; vermelho/verde de manobra não muda.
- ETA/ETB/ETS não geram nova voz/chime Desktop.
- PWA continua read-only sobre operação; só cria/remove preferência de tracking.
- Nome sem IMO mostra fallback explicitamente e nunca usa fuzzy matching.
- Deep links determinísticos seguem a SPEC 023.
- Não fazer commit/push sem autorização explícita.

## Review Focus

- Navio acompanhado some do snapshot: deve permanecer na lista Desktop/PWA como ausente.
- Ficha aberta durante promoção NAME→IMO: botão não pode criar tracking duplicado.
- PWA offline durante toggle: UI deve reverter/mostrar erro sem apagar tracking já confirmado.
- Foreground recebe ManeuverEvent e tracking simultaneamente: apenas um aviso relevante.
- Longa timeline no iPhone: scroll interno não pode disparar fechamento acidental.
---

### Task 1: Tracking local Desktop e persistência de favoritos

**Files:**
- Create: `src/alertam/application/local_vessel_tracking.py`
- Create: `src/alertam/infrastructure/local_tracked_vessels_store.py`
- Modify: `src/alertam/bootstrap.py`
- Test: `tests/unit/test_local_vessel_tracking.py`
- Test: `tests/unit/test_local_tracked_vessels_store.py`

**Interfaces:**
- Produce: `LocalTrackedVessel` e `LocalVesselTrackingService`.
- Methods: `start(ship, observed_at)`, `stop(identity)`, `is_tracked(identity)`, `update_snapshot(snapshot)`, `list_active()`.
- Persistência independente de tracking PWA, sem TTL.

- [ ] **Step 1:** RED acompanhar/persistir/reabrir e parar manualmente.
- [ ] **Step 2:** RED ausência atualizar present=false/last_seen sem desativar.
- [ ] **Step 3:** RED NAME → IMO preservar um único favorito por match exato.
- [ ] **Step 4:** RED snapshot com navio presente atualizar status/berth/pob/last_seen.
- [ ] **Step 5:** Implementar store atômico e service.
- [ ] **Step 6:** Rodar testes focados + suíte Desktop.
### Task 2: Desktop — ficha, janela Acompanhados, estrela e timeline local

**Files:**
- Modify: `src/alertam/ui/ship_info_window.py`
- Create: `src/alertam/ui/tracked_vessels_window.py`
- Create: `src/alertam/application/tracked_vessel_details.py`
- Modify: `src/alertam/ui/main_window.py`
- Modify: `src/alertam/ui/renderers.py`
- Modify: `src/alertam/bootstrap.py`
- Test unit + integration Tk/Xephyr.

**Interfaces:**
- ShipInfoWindow recebe estado/callbacks tracking e mostra ☆/★.
- Acompanhados é Toplevel único não modal.
- Timeline local une ManeuverEvent ledger + VesselTrackingEvent ledger por occurred_at/observed order.

- [ ] **Step 1:** RED botão ☆ acompanhar → ★ e fallback por nome visível quando IMO ausente.
- [ ] **Step 2:** RED janela listar presente/ausente, último status/berço/POB/visto e parar acompanhamento.
- [ ] **Step 3:** RED timeline local conter ambos tipos sem duplicar mudança de manobra.
- [ ] **Step 4:** RED estrela nas listas/mapa/tooltip sem alterar cores operacionais.
- [ ] **Step 5:** Implementar wiring e atualização em SNAPSHOT_READY.
- [ ] **Step 6:** Rodar `make test` e `make test-ui XEPHYR_N=27`.
### Task 3: Tracking client/provider PWA

**Files:**
- Create: `frontend/src/api/trackingClient.ts`
- Create: `frontend/src/features/tracking/TrackingProvider.tsx`
- Create: `frontend/src/features/tracking/useTrackingPolling.ts`
- Modify: `frontend/src/app/App.tsx`
- Add tests client/provider/polling.

**Interfaces:**
- Client: list/start/stop/getTimeline/getTrackingEvents(after).
- Provider: `trackings`, `isTracked(identity)`, `startTracking(target)`, `stopTracking(id)`,
  `newTrackingEvent`, refresh/retry state.
- Poll do feed agregado usa cursor e cadência de 30 s, igual ao polling mobile atual.

- [ ] **Step 1:** RED Zod strict para tracked vessel, tracking event e timeline union discriminada.
- [ ] **Step 2:** RED start/stop idempotente, 401 reset pairing, 503 erro recuperável.
- [ ] **Step 3:** RED polling cursor sem replay na montagem e emitindo somente evento novo posterior.
- [ ] **Step 4:** RED push off não impedir list/start/stop.
- [ ] **Step 5:** Implementar TrackingProvider acima de AppRoutes e abaixo da sessão.
- [ ] **Step 6:** Rodar Vitest focado + build.
### Task 4: Ações acompanhar na VesselSheet e AlertDetailSheet

**Files:**
- Modify: `frontend/src/features/vessels/VesselSheet.tsx`
- Modify: `frontend/src/features/events/AlertDetailSheet.tsx`
- Modify: `frontend/src/app/AppShell.tsx`
- Modify tests das duas sheets.

**Interfaces:**
- VesselSheet target vem do VesselV1 atual.
- AlertDetailSheet target vem do evento selecionado, mesmo que navio não esteja no snapshot.
- Botão: ☆ Acompanhar navio / ★ Acompanhando / Parar de acompanhar.

- [ ] **Step 1:** RED VesselSheet acompanhar/parar e estado loading/erro.
- [ ] **Step 2:** RED AlertDetailSheet acompanhar navio ausente usando vessel_identity/IMO/name do evento.
- [ ] **Step 3:** RED navio sem IMO mostrar nota discreta de identidade por nome.
- [ ] **Step 4:** RED promoção para IMO não criar segundo botão/segundo tracking.
- [ ] **Step 5:** RED falha/offline no toggle manter o último estado confirmado e mostrar erro recuperável, sem falso sucesso otimista.
- [ ] **Step 6:** Implementar callbacks/provider sem acoplar rede às sheets.
- [ ] **Step 7:** Rodar sheets/provider tests + build.
### Task 5: Página Acompanhados, timeline unificada e deep links

**Files:**
- Create: `frontend/src/pages/TrackedVesselsPage.tsx`
- Create: `frontend/src/features/tracking/TrackedVesselSheet.tsx`
- Create: `frontend/src/features/tracking/trackingProjections.ts`
- Modify: `frontend/src/components/Drawer.tsx`
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/app/AppShell.tsx`
- Add page/sheet/E2E tests.

**Interfaces:**
- Route: `/acompanhados`.
- Query: `?track=<tracked_vessel_id>&event=<event_id>`.
- Timeline usa union MANEUVER/TRACKING ordenada pela API e destaca event opcional.

- [ ] **Step 1:** RED drawer/route e lista somente trackings da instalação atual.
- [ ] **Step 2:** RED navio ausente continuar listado com último estado conhecido.
- [ ] **Step 3:** RED abrir item carregar timeline única com ETA/status + manobras.
- [ ] **Step 4:** RED deep link selecionar tracking/event correto e fechar remover query sem sair da página.
- [ ] **Step 5:** RED drag/scroll/ARIA reutilizando BottomSheetFrame.
- [ ] **Step 6:** Implementar página, sheet e projeções.
### Task 6: Foreground, destino de ManeuverEvent e gates cross-repo

**Files:**
- Modify: `frontend/src/app/AppShell.tsx`
- Modify foreground tests.
- Modify: `frontend/e2e/mobile.spec.ts`
- Cross-repo smoke temporary tests/scripts only; no fixture temporária deve ficar esquecida.

**Interfaces:**
- newTrackingEvent → aviso interno com `/acompanhados?track=...&event=...`.
- new ManeuverEvent + categoria geral ON → /alertas.
- new ManeuverEvent + categoria geral OFF + tracking ON → /acompanhados.
- Nunca dois avisos para a mesma ocorrência semântica.

- [ ] **Step 1:** RED foreground VesselTrackingEvent com tracking correto e sem Web Push do sistema.
- [ ] **Step 2:** RED escolha de destino de ManeuverEvent usando usePush.preferences + TrackingProvider.
- [ ] **Step 3:** RED reativar push não produzir aviso retroativo no provider.
- [ ] **Step 4:** Rodar Desktop focused + `make test` + Xephyr.
- [ ] **Step 5:** Rodar API unit/contract/integration + `make test-all`.
- [ ] **Step 6:** Rodar frontend Vitest completo + build + Playwright completo.
- [ ] **Step 7:** Smoke Desktop VesselTrackingEvent → API → tracked feed/timeline → Zod PWA.
- [ ] **Step 8:** Auto-revisar critérios da SPEC 023, `git diff --check` e árvores dos dois repos.
- [ ] **Step 9:** Parar para revisão humana; não commit/push sem autorização explícita.
