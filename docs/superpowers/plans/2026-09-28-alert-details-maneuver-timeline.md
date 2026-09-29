# Alert Details & Maneuver Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform each ManeuverEvent into an independently retrievable detail view with safe POB timing, a retained maneuver timeline in the PWA, and an equivalent offline detail window in the Desktop.

**Architecture:** The Desktop remains the semantic authority and enriches new ManeuverEvent records with canonical `pob_at` and `first_observed_at`, while persisting a 30-day local event ledger separate from the outbox. The API stores those immutable fields, exposes a session-scoped detail lookup by `event_id`, and returns the retained cycle ordered by `ingestion_id`. The PWA fetches detail directly from that endpoint, presents it in a reusable bottom sheet, and opens the same sheet from Alertas, Histórico, foreground notices, and push deep links.

**Tech Stack:** Python 3 / dataclasses / Tkinter / pytest; FastAPI / Pydantic / PostgreSQL-Supabase / httpx / pytest; React 19 / TypeScript / Zod / React Router / Vitest / Testing Library / Playwright.

**Spec:** `specs/022-alert-details-maneuver-timeline.md`

## Global Constraints

- AlertaM Desktop remains the only semantic authority for ManeuverEvent; API and PWA must never redetect WebPilot state.
- `occurred_at` means the collection that semantically confirmed the change after debounce, not the physical second of the maneuver.
- New events may carry `pob_at` and `first_observed_at`; historical events without either field remain valid.
- Parse POB only in the Desktop using the operational Fortaleza timezone; invalid/ambiguous text keeps `pob` and produces `pob_at = null`.
- Baseline maneuvers never receive a synthetic CONFIRMED event.
- Local and cloud ManeuverEvent retention remain 30 days; ACK removes only from outbox, never from the Desktop ledger.
- API detail lookup is session/device scoped and must return the same not-found response for expired, foreign-device, and unknown `event_id`.
- PWA is read-only and computes temporal labels only from canonical timestamps returned by the API; it must not parse textual POB.
- Existing voice, chime, Web Push eligibility, and push payload routing rules are unchanged by SPEC 022.
- Preserve strict Pydantic/Zod contracts and coordinate contract changes Desktop → API → frontend.
- Every implementation task follows TDD RED → GREEN → REFACTOR and ends with a review checkpoint.
- Do not commit or push any task without Ciro's explicit authorization, even where the normal Superpowers workflow would create intermediate commits.

## Review Focus

- POB near New Year or malformed input: select the closest safe calendar occurrence; if parsing is unsafe, preserve text and omit every derived time difference.
- Deep link to an event absent from the first feed page, expired, or owned by another device: fetch detail directly; never paginate to discover it and never leak foreign metadata.
- Baseline maneuver with no CONFIRMED event: Desktop explicitly explains that monitoring began mid-maneuver; PWA shows only the retained real events and never invents a CONFIRMED.
- ACK/restart/retention interaction: acknowledged events remain in the Desktop ledger across restart until 30 days, while stale history is pruned without affecting pending outbox order.
- iOS-style bottom-sheet interaction: downward drag closes only from top/non-interactive content, upward pull resists, internal scroll wins when content is scrolled, and URL/query state is cleaned on close.

---

### Task 1: Enrich Desktop ManeuverEvent with canonical POB time and first observation

**Files:**
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/maneuver_time.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/domain/maneuvers.py:60-154`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/maneuver_tracker.py:47-417`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_time.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_models.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_tracker.py`

**Interfaces:**
- Produce `normalize_pob_at(pob: str | None, observed_at: datetime) -> str | None`.
- Extend `Maneuver` with `pob_at: str | None = None`; persist it through `to_dict()` / `from_dict()`.
- Extend `ManeuverEvent` with `pob_at: str | None = None` and `first_observed_at: str | None = None`; persist both through `to_dict()` / `from_dict()`.
- Add private `_Candidate(fingerprint: tuple[object, ...], first_observed_at: datetime)` in `maneuver_tracker.py`.
- Change `_candidate_confirmed(key, fingerprint, observed_at) -> datetime | None`: return the first observation timestamp when confirmed, or `None` while still candidate.
- `_event(...)` receives `first_observed_at: datetime | None` and copies the maneuver's current `pob_at`.

- [ ] **Step 1: Write failing POB normalization tests**

Cover exact `DD/MM HH:MM`, invalid text, empty/null POB, timezone-aware output, and New Year selection where `31/12` observed on `01/01` resolves to the previous year while `01/01` observed on `31/12` resolves to the next year.

- [ ] **Step 2: Run the focused time tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_time.py -q`
Expected: FAIL because `normalize_pob_at` does not exist.

- [ ] **Step 3: Implement `normalize_pob_at`**

Parse only the WebPilot shape `DD/MM HH:MM`; evaluate candidate years `observed_year - 1`, `observed_year`, `observed_year + 1`; choose the valid occurrence with the smallest absolute distance to the collection timestamp; normalize to `America/Fortaleza` with seconds precision; return `None` on invalid calendar/text rather than guessing.

- [ ] **Step 4: Write failing model round-trip tests for the optional timestamps**

Assert old dictionaries without the new keys still deserialize, enriched dictionaries round-trip both timestamps, and `Maneuver.pob_at` survives persistence.

- [ ] **Step 5: Run the model tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_models.py -q`
Expected: FAIL on missing `pob_at` / `first_observed_at` fields.

- [ ] **Step 6: Extend the domain dataclasses compatibly**

Add optional defaults after existing required fields so callers/tests that construct old events remain source-compatible; serialize the keys on new runtime writes and tolerate their absence on old runtime reads.

- [ ] **Step 7: Write failing tracker tests for first observation and POB carry-forward**

Assert: two-sample CONFIRMED/UPDATED/COMPLETED/CANCELLED preserve the first candidate collection in `first_observed_at`; long-gap direct confirmation uses the confirming collection for both timestamps; UPDATE refreshes `Maneuver.pob_at`; terminal event retains the last canonical POB even when the terminal row has no POB.

- [ ] **Step 8: Run the tracker tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_tracker.py -q`
Expected: FAIL until candidate timestamps and canonical POB are carried through.

- [ ] **Step 9: Implement candidate timestamp tracking and event enrichment**

Replace the fingerprint-only candidate map with `_Candidate`; preserve the original candidate timestamp only while the fingerprint is unchanged; reset it when a candidate changes/disappears; initialize/update `Maneuver.pob_at` from the collection where the POB became the accepted state; pass the returned first-observation timestamp into each emitted event.

- [ ] **Step 10: Run focused Desktop domain tests and refactor**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_time.py tests/unit/test_maneuver_models.py tests/unit/test_maneuver_tracker.py -q`
Expected: PASS.

- [ ] **Step 11: Review checkpoint — no commit**

Inspect `git diff --check` and the task diff; confirm no voice/push behavior changed and do not commit.

### Task 2: Add a 30-day Desktop ManeuverEvent ledger separate from the outbox

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/maneuver_runtime.py:11-40`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/infrastructure/maneuver_runtime_store.py:23-211`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_runtime_store.py`

**Interfaces:**
- Extend `ManeuverRuntime` with `event_history: tuple[ManeuverEvent, ...] = ()`.
- Bump runtime file schema to v2 while explicitly accepting v1.
- Extend `ManeuverRuntimeStore.__init__(..., clock: Callable[[], datetime] | None = None)`.
- Add `events_for_maneuver(maneuver_id: str) -> tuple[ManeuverEvent, ...]`.
- `commit_transition(state, new_events)` atomically appends each new event to both FIFO outbox and retained history.
- `ack_event(event_id)` removes only the FIFO outbox head.
- Retention helper prunes history older than 30 days using aware `occurred_at` and the injected clock.

- [ ] **Step 1: Write failing ledger atomicity and ACK tests**

Assert a committed event appears in both `outbox` and `event_history`, ACK removes it only from `outbox`, restart reloads history, and `events_for_maneuver` returns only matching events in persisted order.

- [ ] **Step 2: Run the focused store tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_runtime_store.py -q`
Expected: FAIL because runtime has no ledger.

- [ ] **Step 3: Implement runtime v2 and atomic ledger writes**

Write state/outbox/history in the same temp-file + `os.replace` transaction; deduplicate by `event_id`; keep outbox FIFO semantics unchanged.

- [ ] **Step 4: Write failing backward-compatibility and retention tests**

Create a v1 runtime containing pending outbox events and assert migration preserves those concrete events in `event_history` without fabricating already-ACKed history; inject a clock and assert events older than 30 days are pruned while newer history and every pending outbox item remain.

- [ ] **Step 5: Run store tests and verify RED for migration/retention**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_runtime_store.py -q`
Expected: FAIL until v1/v2 read logic and retention exist.

- [ ] **Step 6: Implement safe v1 migration and 30-day pruning**

On v1, initialize ledger from actual pending outbox entries only; on malformed/corrupt runtime preserve current safe-baseline behavior; never drop an outbox item solely because ledger retention elapsed.

- [ ] **Step 7: Run store tests and refactor**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_runtime_store.py tests/unit/test_maneuver_coordinator.py tests/unit/test_maneuver_event_publisher.py -q`
Expected: PASS and publisher FIFO behavior unchanged.

- [ ] **Step 8: Review checkpoint — no commit**

Run `git diff --check`; inspect the persisted JSON contract and confirm ACK cannot delete history; do not commit.

### Task 3: Add the Desktop "Detalhes da manobra" projection and non-modal window

**Files:**
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/maneuver_details.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/maneuver_detail_window.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/renderers.py:419-624`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/main_window.py:103-173,639-644,934-965`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/bootstrap.py:285-305,326-376`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_details.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_presentation.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/integration/test_historico_ordem.py`

**Interfaces:**
- Create `ManeuverDetail(maneuver: Maneuver, events: tuple[ManeuverEvent, ...], baseline_without_confirmed: bool)`.
- Create `build_maneuver_detail(runtime: ManeuverRuntime, maneuver_id: str) -> ManeuverDetail | None`.
- Create `pob_delta_minutes(event: ManeuverEvent) -> int | None`; return `None` unless both canonical timestamps are present/valid.
- `HistoryRenderer(..., on_double_click: Callable[[str], None] | None = None)` binds a row's `maneuver_id` without changing selection/copy behavior.
- `MainWindow.__init__(..., maneuver_detail_provider: Callable[[str], ManeuverDetail | None] | None = None)`.
- `ManeuverDetailWindow.show(detail: ManeuverDetail) -> None` reuses one non-modal `tk.Toplevel` per MainWindow.
- Bootstrap provider builds detail from the current `ManeuverRuntimeStore.load()`; no API/network dependency.

- [ ] **Step 1: Write failing pure projection tests**

Assert timeline order follows retained ledger order, terminal delta uses `pob_at → occurred_at`, invalid/missing timestamps omit the delta, UPDATED preserves `changes`, and a runtime maneuver with no CONFIRMED event sets `baseline_without_confirmed=True`.

- [ ] **Step 2: Run the projection tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_details.py -q`
Expected: FAIL because the projection module does not exist.

- [ ] **Step 3: Implement the pure detail projection**

Find the maneuver in active/completed state, select ledger events by `maneuver_id`, keep event order, detect baseline by absence of CONFIRMED, and calculate only canonical temporal differences.

- [ ] **Step 4: Write failing renderer/MainWindow callback tests**

Assert double-click on a history row passes that row's `maneuver_id`; provider result opens/reuses the detail window; missing detail is a no-op; existing history update/finalization behavior remains unchanged.

- [ ] **Step 5: Run UI-unit tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_presentation.py -q`
Expected: FAIL until the callback/provider wiring exists.

- [ ] **Step 6: Implement the non-modal detail window**

Render vessel/IMO, maneuver type/status, berth, current POB, confirmation/terminal observation, optional first observation, safe POB delta, UPDATED before→after blocks, and all retained events; show `Esta manobra já estava em andamento quando o AlertaM iniciou.` when baseline has no CONFIRMED; use `Conclusão observada pelo AlertaM` and `Horário aproximado baseado na atualização da planilha.` for COMPLETED.

- [ ] **Step 7: Wire HistoryRenderer → MainWindow → bootstrap provider**

Bind the full history row for double click without breaking selectable `tk.Text`; keep one `ManeuverDetailWindow` instance; source data only from the local runtime ledger/state.

- [ ] **Step 8: Add/extend Xephyr integration coverage**

Simulate a retained maneuver, double-click its history row, assert a non-modal detail Toplevel appears with vessel/timeline text, and verify the normal history list remains usable.

- [ ] **Step 9: Run Desktop detail tests and refactor**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_details.py tests/unit/test_maneuver_presentation.py tests/integration/test_historico_ordem.py -q`
Expected: PASS where Tk integration is available.

- [ ] **Step 10: Review checkpoint — no commit**

Run `git diff --check`; review Desktop-only SPEC 022 coverage before touching API/PWA; do not commit.

### Task 4: Extend the API event contract and expose session-scoped event detail

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/api/app/models/maneuver_event.py:41-88`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/api/app/repositories/events.py:35-60`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/api/app/repositories/memory.py:141-205`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/api/app/repositories/postgres.py:222-330`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/api/app/repositories/supabase.py:234-340`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/api/app/services/event_detail_service.py`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/api/app/api/v1/mobile_event_details.py`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/api/app/api/v1/router.py:1-72`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/api/app/core/errors.py:104-128`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/api/supabase/migrations/007_maneuver_event_detail_index.sql`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/api/tests/fixtures/maneuver_event_v1.json`
- Test: `/home/ciro/dev/prog/alertamaritimoAPI/api/tests/unit/test_maneuver_event_model.py`
- Test: `/home/ciro/dev/prog/alertamaritimoAPI/api/tests/unit/test_event_repository_contract.py`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/api/tests/integration/test_get_maneuver_event_detail.py`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/api/tests/contract/test_desktop_maneuver_event_contract.py`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/api/tests/contract/test_maneuver_event_roundtrip.py`

**Interfaces:**
- Add `pob_at: AwareDatetime | None = None` and `first_observed_at: AwareDatetime | None = None` to `ManeuverEventIn`.
- Create `ManeuverEventDetailResponse(selected_event_id: UUID, maneuver_id: UUID, events: list[ManeuverEventFeedItem])`.
- Create repository dataclass `ManeuverEventDetail(selected_event_id: UUID, maneuver_id: UUID, events: tuple[StoredManeuverEvent, ...])`.
- Add `ManeuverEventsRepository.get_maneuver_event_detail(device_id: str, event_id: UUID) -> ManeuverEventDetail | None`.
- Create `EventDetailService.get_detail(device_id: str, event_id: UUID) -> ManeuverEventDetailResponse`.
- Create `ManeuverEventNotFoundError` with HTTP 404 and one generic recent-history message.
- Route exactly `GET /api/v1/mobile/events/{event_id}/detail`.
- Detail events are ordered by `ingestion_id ASC`; repository first verifies selected `event_id` belongs to `device_id`, then reads only that `maneuver_id`.
- Migration 007 adds `(device_id, maneuver_id, ingestion_id)` index; no new table or payload-column migration is required because timestamps live in immutable `event_payload`.

- [ ] **Step 1: Write failing API model/contract compatibility tests**

Assert enriched fixture with both timestamp fields validates and round-trips; construct a legacy payload with both keys absent and assert it still validates with fields defaulting to `None`.

- [ ] **Step 2: Run model/contract tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/api && uv run pytest tests/unit/test_maneuver_event_model.py tests/contract/test_desktop_maneuver_event_contract.py -q`
Expected: FAIL until optional fields exist.

- [ ] **Step 3: Extend Pydantic contract and fixture**

Add optional aware timestamps without changing idempotent canonical semantics; update the canonical Desktop fixture to enriched output while retaining an explicit old-payload test.

- [ ] **Step 4: Write failing repository contract tests for detail lookup**

For memory repository, store multiple events from the same cycle plus an event from another cycle/device; assert selected event resolves to exactly its same-device cycle in ingestion order; unknown/foreign event returns `None`.

- [ ] **Step 5: Run repository tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/api && uv run pytest tests/unit/test_event_repository_contract.py -q`
Expected: FAIL because `get_maneuver_event_detail` is missing.

- [ ] **Step 6: Implement memory/Postgres/Supabase detail lookup**

Use top-level `event_id`, `device_id`, and `maneuver_id` columns rather than parsing JSON to identify the cycle; fetch event payload/ingestion metadata for response; preserve existing persistence-unavailable error mapping.

- [ ] **Step 7: Add migration index and SQL-oriented tests**

Create migration 007 with only the composite lookup index; extend repository/integration tests so the query path remains device-scoped and ordered.

- [ ] **Step 8: Write failing route/service tests**

Authenticate a mobile session and assert the exact detail endpoint returns `selected_event_id`, `maneuver_id`, and all retained same-cycle events; no session → 401; unknown, expired-equivalent, and other-device IDs → identical 404 shape; repository failure → 503.

- [ ] **Step 9: Run detail endpoint tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/api && uv run pytest tests/integration/test_get_maneuver_event_detail.py -q`
Expected: FAIL until service/router/error are wired.

- [ ] **Step 10: Implement EventDetailService and router**

Reuse `MobileSessionAuth`; do not accept `device_id` from query/body; map repository `None` to the generic 404 and persistence failures to the existing 503 API error.

- [ ] **Step 11: Run focused API suite and refactor**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI && make test-unit && make test-contract && make test-integration`
Expected: PASS except explicitly environment-gated Postgres tests may SKIP.

- [ ] **Step 12: Review checkpoint — no commit**

Run `git diff --check`; confirm the API never calculates lateness/earliness and foreign event IDs reveal nothing; do not commit.

### Task 5: Add the PWA detail contract and direct event-detail client

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/api/contract.ts:218-307`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/api/contract.test.ts`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/api/maneuverEventClient.ts:1-57`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/api/maneuverEventClient.test.ts`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/events/useAlertDetail.ts`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/events/useAlertDetail.test.tsx`

**Interfaces:**
- Extend `ManeuverEventSchema` and feed item schema with normalized output fields `pob_at: string | null` and `first_observed_at: string | null`; missing legacy keys parse to `null`.
- Create `ManeuverEventDetailResponse` type/schema with `selected_event_id`, `maneuver_id`, `events`.
- Create `parseManeuverEventDetailResponse(input: unknown)`.
- Create `ManeuverEventDetailNotFoundError`.
- Create `getManeuverEventDetail(eventId: string, signal?: AbortSignal) -> Promise<ManeuverEventDetailResponse>`.
- `getManeuverEventDetail` uses `/api/v1/mobile/events/${encodeURIComponent(eventId)}/detail`, cookie credentials, and `cache: "no-store"`.
- Create hook `useAlertDetail(eventId: string | null, fetcher = getManeuverEventDetail, onAccessRevoked?)` returning `{status: "idle" | "loading" | "ready" | "not-found" | "error", detail, retry}` and aborting stale requests.

- [ ] **Step 1: Write failing Zod compatibility tests**

Assert enriched fields parse as aware ISO strings, absent legacy fields become `null`, and unexpected extra keys still fail strict parsing.

- [ ] **Step 2: Run contract tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/api/contract.test.ts`
Expected: FAIL until schemas are extended.

- [ ] **Step 3: Extend the Zod event/detail schemas**

Use nullable defaults so downstream UI never needs to distinguish `undefined` from legacy absence; preserve existing UPDATED `changes` validation.

- [ ] **Step 4: Write failing client/hook tests**

Assert direct endpoint path, cookie/no-store options, 401 → access revoked callback/error, 404 → `not-found`, 5xx/invalid JSON → recoverable error, retry refetches, and changing/clearing `eventId` aborts stale work.

- [ ] **Step 5: Run client/hook tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/api/maneuverEventClient.test.ts src/features/events/useAlertDetail.test.tsx`
Expected: FAIL until direct detail fetching exists.

- [ ] **Step 6: Implement direct client and hook**

Do not inspect/paginate the EventProvider feed to resolve a deep link; detail state comes solely from the detail endpoint.

- [ ] **Step 7: Run focused PWA data tests and refactor**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/api/contract.test.ts src/api/maneuverEventClient.test.ts src/features/events/useAlertDetail.test.tsx`
Expected: PASS.

- [ ] **Step 8: Review checkpoint — no commit**

Run `git diff --check` from monorepo root; confirm legacy event payloads remain accepted; do not commit.

### Task 6: Extract the reusable bottom-sheet interaction and build AlertDetailSheet

**Files:**
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/components/BottomSheetFrame.tsx`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/components/BottomSheetFrame.test.tsx`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/vessels/VesselSheet.tsx:25-237`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/vessels/VesselSheet.test.tsx`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/events/alertDetailProjections.ts`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/events/alertDetailProjections.test.ts`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/events/AlertDetailSheet.tsx`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/events/AlertDetailSheet.test.tsx`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/styles/app.css:119-205,1588-1973`

**Interfaces:**
- `BottomSheetFrame({open, onClose, ariaLabel, closeLabel, children})` owns backdrop, drag handle, downward dismiss, upward resistance, internal-scroll arbitration, safe-area layout, and close button.
- Migrate `VesselSheet` onto `BottomSheetFrame` without changing its public props or behavior.
- Create `formatObservedDelta(pobAt: string | null, observedAt: string) -> string | null`.
- Create `formatPobUpdateDelta(events: ManeuverEventFeedItem[], selectedIndex: number) -> string | null` using only canonical `pob_at` values.
- `AlertDetailSheet` props: `{open, state, selectedEventId, onClose, onRetry}` where `state` is the return shape of `useAlertDetail`.
- The selected event is visually marked within a timeline ordered exactly as returned by the API.

- [ ] **Step 1: Move existing VesselSheet gesture tests to a generic-frame safety net**

Before extraction, add `BottomSheetFrame` tests equivalent to current long/short downward drag, interactive-control exclusion, scrolled-content protection, upward resistance, backdrop close, and closed state.

- [ ] **Step 2: Run sheet tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/components/BottomSheetFrame.test.tsx src/features/vessels/VesselSheet.test.tsx`
Expected: new generic tests FAIL until the frame exists; existing VesselSheet tests stay GREEN.

- [ ] **Step 3: Extract `BottomSheetFrame` and migrate VesselSheet**

Move interaction mechanics, not vessel-specific content; preserve current 44px controls, iOS safe area, CSS transitions, and reduced-motion behavior.

- [ ] **Step 4: Run sheet/VesselSheet regression tests**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/components/BottomSheetFrame.test.tsx src/features/vessels/VesselSheet.test.tsx`
Expected: PASS.

- [ ] **Step 5: Write failing detail-projection tests**

Assert COMPLETED renders `Conclusão observada pelo AlertaM`, approximate-time note, and safe before/after POB delta; invalid/null canonical POB produces no delta; UPDATED renders both POB and berth changes; previous event without `pob_at` omits update delta; first observation appears only when present.

- [ ] **Step 6: Run projection tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/features/events/alertDetailProjections.test.ts`
Expected: FAIL until detail projection exists.

- [ ] **Step 7: Implement canonical-only temporal formatting**

Use `Date`/milliseconds only on API-provided aware ISO timestamps; never parse `event.pob` text; format negative/positive difference as human Portuguese (`antes` / `depois`), render an exact zero as `0 min`, and omit the difference only when canonical timestamps are unavailable/unsafe.

- [ ] **Step 8: Write failing AlertDetailSheet state/content tests**

Cover loading, recoverable error + retry, not-found message `Este alerta não está mais disponível no histórico recente.`, ready summary, selected-event highlight, keyboard-accessible close, and timeline contents when the retained cycle has no CONFIRMED event.

- [ ] **Step 9: Run component tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/features/events/AlertDetailSheet.test.tsx`
Expected: FAIL until component/CSS are implemented.

- [ ] **Step 10: Implement AlertDetailSheet on the shared frame**

Keep alert content separate from VesselSheet; apply dedicated semantic class names while sharing only the frame/gesture primitive.

- [ ] **Step 11: Run all sheet/detail tests and refactor**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/components/BottomSheetFrame.test.tsx src/features/vessels/VesselSheet.test.tsx src/features/events/alertDetailProjections.test.ts src/features/events/AlertDetailSheet.test.tsx`
Expected: PASS.

- [ ] **Step 12: Review checkpoint — no commit**

Inspect mobile CSS/gesture diff and `git diff --check`; do not commit.

### Task 7: Integrate clickable Alertas, Histórico, foreground, and direct deep links

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/pages/AlertsPage.tsx:11-65`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/pages/HistoryPage.tsx:8-50`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/app/AppShell.tsx:34-234`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/styles/app.css:520-610`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/pages/pages.test.tsx`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/app/AppShell.push.test.tsx`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/e2e/mobile.spec.ts`

**Interfaces:**
- `AppShell` owns `eventId = new URLSearchParams(location.search).get("event")`, calls `useAlertDetail`, and renders one global `AlertDetailSheet`.
- Closing the sheet removes only the `event` query parameter using React Router replace-navigation and keeps the current page (`/alertas` or `/historico`).
- Alert row whole-area activation navigates to `/alertas?event=<event_id>`.
- History event activation navigates to `/historico?event=<event_id>` and reuses the same global sheet.
- Foreground `Ver alerta` continues navigating to `/alertas?event=<event_id>`; AppShell query observation automatically opens the sheet.
- Push `notificationclick` remains unchanged because the existing payload URL already targets `/alertas?event=<event_id>`.
- Remove the old AlertsPage behavior that paginates older feed pages solely to find/highlight a deep-linked event.

- [ ] **Step 1: Replace the old pagination deep-link test with a failing direct-detail test**

Render `/alertas?event=<old-id>` while the feed does not contain that ID; inject detail fetcher returning the old event; assert the sheet opens without calling `loadOlder`/additional feed pages.

- [ ] **Step 2: Write failing click/URL/close tests**

Assert every Alertas row is one accessible full-area control, click writes `?event=`, close removes it without leaving Alertas, and the selected timeline item is highlighted in the sheet.

- [ ] **Step 3: Write failing Histórico reuse tests**

Assert clicking an event within a cycle opens the same AlertDetailSheet on `/historico?event=...`, and closing returns to clean `/historico`.

- [ ] **Step 4: Write failing foreground/not-found/retry tests**

Foreground banner navigation must open the sheet through the URL; a 404 detail must show the retained-history message without paginating; a temporary error must preserve the page and expose retry.

- [ ] **Step 5: Run page/AppShell tests and verify RED**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/pages/pages.test.tsx src/app/AppShell.push.test.tsx`
Expected: FAIL until AppShell owns detail state and page rows navigate.

- [ ] **Step 6: Implement global sheet integration and accessible row controls**

Use semantic `<button type="button">` inside each timeline list item (or an equivalent full-area accessible control); keep current feed rendering/pagination features unrelated to deep-link lookup.

- [ ] **Step 7: Add Playwright mobile flow**

Cover direct `/alertas?event=...`, sheet automatic opening, close/query cleanup, Alertas tap target, Histórico reuse, internal scroll, and backdrop/downward close at mobile viewport.

- [ ] **Step 8: Run focused unit + E2E tests and refactor**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/pages/pages.test.tsx src/app/AppShell.push.test.tsx && npm run e2e -- --grep "alert detail"`
Expected: PASS.

- [ ] **Step 9: Build the PWA**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm run build`
Expected: TypeScript and Vite build succeed; generated service worker still handles existing push URLs.

- [ ] **Step 10: Review checkpoint — no commit**

Run `git diff --check`; review route/query semantics, focus/accessibility, and absence of feed-pagination dependency; do not commit.

### Task 8: Cross-repo verification and implementation handoff

**Files:**
- No new production files; only fix regressions found by gates.
- Verify both repositories remain on their current branches unless Ciro explicitly changes strategy.

**Interfaces:**
- Desktop enriched `ManeuverEvent.to_dict()` must validate against API `ManeuverEventIn`.
- API detail response must validate against frontend `parseManeuverEventDetailResponse`.
- No task may change push eligibility/audio behavior or create a second maneuver detector.

- [ ] **Step 1: Run Desktop focused and full tests**

Run:
`cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_time.py tests/unit/test_maneuver_models.py tests/unit/test_maneuver_tracker.py tests/unit/test_maneuver_runtime_store.py tests/unit/test_maneuver_details.py tests/unit/test_maneuver_presentation.py -q`
then `make test`.
Expected: PASS.

- [ ] **Step 2: Run Desktop real-UI gate where environment permits**

Run: `cd /home/ciro/dev/prog/alertamaritimo && make test-ui XEPHYR_N=27`
Expected: PASS; if Xephyr cannot start, record the environmental limitation explicitly rather than marking UI verification passed.

- [ ] **Step 3: Run API unit/contract/integration gates**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI && make test-unit && make test-contract && make test-integration`
Expected: PASS, with only documented environment-gated DB tests skipped.

- [ ] **Step 4: Run real Postgres/Docker API gate**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI && make test-all`
Expected: PASS, including migration 007/detail repository behavior.

- [ ] **Step 5: Run frontend full suite, build, and relevant Playwright**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run && npm run build && npm run e2e`
Expected: PASS.

- [ ] **Step 6: Run cross-repo contract smoke**

Generate/serialize at least one enriched Desktop event containing `pob_at`/`first_observed_at`, validate it with API `ManeuverEventIn`, persist it, fetch `/api/v1/mobile/events/{event_id}/detail`, and validate that JSON with the frontend Zod detail schema.

- [ ] **Step 7: Run final hygiene checks**

Run `git diff --check` and `git status --short --branch` in both repositories; ensure no secret/env contents, build artifacts, or unrelated changes entered the diff.

- [ ] **Step 8: Perform final self-review against SPEC 022**

Check every acceptance criterion: clickable Alertas, direct push/foreground sheet, retained cycle timeline, safe POB delta, UPDATED before→after, approximate language, Desktop local detail, ledger survival across ACK/restart, baseline note, 30-day retention, and unchanged voice/push rules.

- [ ] **Step 9: Stop for Ciro's review — no commit/push**

Present test evidence and diffs. Do not commit, push, migrate production, or deploy until Ciro gives explicit authorization.
