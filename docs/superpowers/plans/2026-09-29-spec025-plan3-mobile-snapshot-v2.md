# SPEC 025 Plan 3 — MobileSnapshot v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Evoluir o contrato meteorológico para MobileSnapshot v2 com compatibilidade v1+v2 na API/PWA, publicar v2 pelo Desktop somente depois que consumidores estiverem prontos.

**Architecture:** API e PWA passam primeiro a aceitar uma união discriminada schema_version 1|2. O v2 preserva vessels/recent_maneuvers e substitui os blocos weather/marine por atmosphere/marine com estados fresh/stale/unavailable e source/mode explícitos. Depois de validação do consumidor, o Desktop passa a serializar WeatherComposite como v2.

**Tech Stack:** Python/Pydantic/FastAPI, React/Vite/TypeScript/Zod/Vitest, Desktop Python dataclasses/pytest.

**Spec:** specs/025-webpilot-http-observed-weather-shadow-migration.md

## Global Constraints

- Dependência obrigatória: Plan 2 concluído e revisado.
- Rollout: API v1+v2 -> PWA v1+v2 -> deploy/smoke -> Desktop publica v2.
- Não remover suporte v1 nesta SPEC.
- API/PWA não recalculam freshness.
- unavailable é união discriminada; não usar objeto cheio de nulls.
- Não enviar cookies, session_generation, headers ou HTML.
- Não duplicar Open-Meteo no complementary quando ele já for primary fallback.
- TDD obrigatório.
- Não commit/push sem autorização explícita.

## Review Focus

- Snapshot v1 antigo com weather={} e marine={} deve continuar válido exatamente como antes.
- Snapshot v2 com status unavailable e campos extras deve ser rejeitado pelo contrato estrito.
- Snapshot v2 com source webpilot e mode fallback, ou source open_meteo e mode observed, deve ser rejeitado.
- PWA deve continuar usando vessels/recent_maneuvers sem casts inseguros entre v1/v2.
- Desktop não pode incrementar sequence ou publicar um v2 parcialmente construído quando WeatherComposite é inconsistente.

---

### Contrato v2 fixado por este plano

Shared fields continuam iguais ao v1:
- schema_version
- boot_id
- sequence
- generated_at
- collector
- port
- vessels
- recent_maneuvers

Weather v1 continua existindo somente no schema v1.

Atmosphere v2:

Observed primary WebPilot:
    status: "fresh" | "stale"
    source: "webpilot"
    mode: "observed"
    consulted_at: aware datetime
    observed_at: aware datetime
    wind_direction_deg: number | null
    wind_direction_cardinal: string | null
    wind_speed_current_kn: number | null
    wind_speed_mean_kn: number | null
    wind_speed_max_kn: number | null
    air_temperature_c: number | null
    apparent_temperature_c: number | null
    humidity_pct: number | null
    pressure_hpa: number | null
    pressure_6h_hpa: number | null
    precipitation_mm: number | null

Fallback primary Open-Meteo:
    status: "fresh" | "stale"
    source: "open_meteo"
    mode: "fallback"
    consulted_at: aware datetime | null
    observed_at: aware datetime | null
    air_temperature_c: number | null
    humidity_pct: number | null
    weather_code: integer | null
    wind_speed_kn: number | null
    wind_direction_deg: number | null
    wind_gust_kn: number | null
    visibility_m: number | null
    precipitation_mm: number | null

Unavailable primary:
    status: "unavailable"

Complementary Open-Meteo, only when WebPilot is primary:
    status: "fresh" | "stale"
    source: "open_meteo"
    consulted_at: aware datetime | null
    observed_at: aware datetime | null
    weather_code: integer | null
    visibility_m: number | null

Complementary unavailable:
    status: "unavailable"

Marine Open-Meteo:
    status: "fresh" | "stale"
    source: "open_meteo"
    consulted_at: aware datetime | null
    observed_at: aware datetime | null
    wave_height_m: number | null
    wave_direction_deg: number | null
    wave_period_s: number | null
    swell_height_m: number | null
    swell_direction_deg: number | null
    swell_period_s: number | null
    sea_temperature_c: number | null
    current_kn: number | null
    current_direction_deg: number | null

Marine unavailable:
    status: "unavailable"

Cross-field invariant:
- primary webpilot => complementary may be Open-Meteo or unavailable.
- primary open_meteo => complementary must be unavailable.
- primary unavailable => complementary may carry Open-Meteo only if it is intentionally useful as non-primary; default implementation for this SPEC keeps complementary unavailable to avoid contradictory state.

---

### Task 1: Modelar e validar MobileSnapshot v2 na API

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/api/app/models/mobile_snapshot.py
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/api/app/models/read_snapshot.py
- Create: /home/ciro/dev/prog/alertamaritimoAPI/api/tests/fixtures/mobile_snapshot_v2_webpilot.json
- Create: /home/ciro/dev/prog/alertamaritimoAPI/api/tests/fixtures/mobile_snapshot_v2_fallback.json
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/api/tests/unit/test_mobile_snapshot_model.py
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/api/tests/contract/test_desktop_snapshot_contract.py

**Interfaces:**
- Preserve: MobileSnapshotV1 unchanged.
- Produce: MobileSnapshotV2.
- Produce: MobileSnapshot = Annotated[MobileSnapshotV1 | MobileSnapshotV2, Field(discriminator="schema_version")]
- Produce discriminated atmosphere/marine models matching the fixed contract above.
- Read snapshot response changes snapshot field type from MobileSnapshotV1 to MobileSnapshot.

- [ ] **Step 1: Add two sanitized v2 fixtures**

webpilot fixture:
- primary webpilot/observed/fresh;
- complementary open_meteo/fresh;
- marine open_meteo/fresh.

fallback fixture:
- primary open_meteo/fallback/stale or fresh;
- complementary unavailable;
- marine fresh/unavailable as explicit case.

- [ ] **Step 2: Write failing v2 model tests**

Test names:
- test_accepts_mobile_snapshot_v2_webpilot
- test_accepts_mobile_snapshot_v2_open_meteo_fallback
- test_union_still_accepts_v1_fixture
- test_union_still_accepts_v1_with_empty_weather_and_marine_blocks
- test_v2_unavailable_block_rejects_extra_fields
- test_v2_rejects_webpilot_fallback_pair
- test_v2_rejects_open_meteo_observed_pair
- test_v2_open_meteo_primary_requires_complementary_unavailable
- test_v2_required_timestamps_are_aware
- test_v2_measurements_reject_numeric_strings

- [ ] **Step 3: Run API contract tests RED**

Run:
    cd /home/ciro/dev/prog/alertamaritimoAPI
    cd api && uv run pytest tests/unit/test_mobile_snapshot_model.py tests/contract/test_desktop_snapshot_contract.py -q

Expected: v2 tests FAIL; v1 tests remain PASS.

- [ ] **Step 4: Implement strict Pydantic v2 models and discriminated union**

Use ConfigDict(extra="forbid") everywhere. Keep v1 classes untouched except imports/type alias composition.

- [ ] **Step 5: Run model/contract tests GREEN**

Expected: both v1 and v2 pass.

- [ ] **Step 6: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: aceita MobileSnapshot v2 na API

---

### Task 2: Propagar a união v1/v2 pelo serviço e endpoints da API

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/api/app/api/v1/snapshots.py
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/api/app/services/snapshot_service.py
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/api/app/services/snapshot_read_service.py
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/api/app/models/read_snapshot.py
- Modify/Test: /home/ciro/dev/prog/alertamaritimoAPI/api/tests/unit/test_snapshot_service.py
- Modify/Test: /home/ciro/dev/prog/alertamaritimoAPI/api/tests/integration/test_post_snapshot.py
- Modify/Test: /home/ciro/dev/prog/alertamaritimoAPI/api/tests/integration/test_get_snapshot.py
- Modify/Test: /home/ciro/dev/prog/alertamaritimoAPI/api/tests/contract/test_desktop_to_mobile_roundtrip.py

**Interfaces:**
- SnapshotService accepts MobileSnapshot union.
- Repository payload remains JSON-compatible; no SQL migration required for this contract evolution.
- GET returns the same version that was persisted.

- [ ] **Step 1: Write failing service/integration tests**

Assert:
- POST v1 still succeeds;
- POST v2 succeeds;
- GET after v2 returns schema_version 2 and exact atmosphere/marine structure;
- ordering/idempotency semantics remain based on boot_id/sequence, not schema version;
- unsupported schema_version 3 returns validation error.

- [ ] **Step 2: Implement type propagation only**

Do not add migration or version conversion in backend. The API validates and persists the submitted snapshot version.

- [ ] **Step 3: Run API focused/full tests**

Run:
    cd api && uv run pytest tests/unit/test_mobile_snapshot_model.py tests/unit/test_snapshot_service.py tests/contract/test_desktop_snapshot_contract.py tests/contract/test_desktop_to_mobile_roundtrip.py tests/integration/test_post_snapshot.py tests/integration/test_get_snapshot.py -q

Then:
    cd ..
    make test

Expected: PASS.

- [ ] **Step 4: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: propaga snapshots v1 e v2 pela API

---

### Task 3: Adicionar união v1/v2 no contrato TypeScript/Zod

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/frontend/src/api/contract.ts
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/frontend/src/api/contract.test.ts
- Create: /home/ciro/dev/prog/alertamaritimoAPI/frontend/src/test/fixtures/mobile_snapshot_v2_webpilot.json
- Create: /home/ciro/dev/prog/alertamaritimoAPI/frontend/src/test/fixtures/mobile_snapshot_v2_fallback.json
- Modify: files importing MobileSnapshotV1 only where shared operational fields need union typing:
  - frontend/src/pages/MapPage.tsx
  - frontend/src/features/vessels/projections.ts
  - frontend/src/features/map/berthMap.ts
  - frontend/src/features/map/PortMap.tsx
  - corresponding tests.

**Interfaces:**
- Preserve: MobileSnapshotV1 type.
- Produce: MobileSnapshotV2 type.
- Produce: MobileSnapshot = MobileSnapshotV1 | MobileSnapshotV2.
- parseSnapshotReadResponse returns SnapshotReadResponse whose snapshot is MobileSnapshot.
- Operational projections accept MobileSnapshot because vessels/recent_maneuvers are shared.

- [ ] **Step 1: Write failing contract tests**

Cover:
- parse v1 fixture;
- parse v2 WebPilot fixture;
- parse v2 fallback fixture;
- reject schema 3;
- reject unavailable with extra fields;
- reject invalid source/mode combination;
- reject stale/fresh block missing required structural fields.

- [ ] **Step 2: Implement Zod discriminated unions**

Use z.discriminatedUnion for schema_version and status/source/mode where practical. Keep .strict().

- [ ] **Step 3: Fix shared operational type consumers**

Replace MobileSnapshotV1 annotations with MobileSnapshot only where code accesses fields common to both schemas. Do not add unsafe casts or branch on version unnecessarily.

- [ ] **Step 4: Run frontend contract/projection tests**

Run:
    cd frontend
    npm test -- --run src/api/contract.test.ts src/features/vessels/projections.test.ts src/features/map/berthMap.test.ts src/features/map/PortMap.test.tsx

Expected: PASS.

- [ ] **Step 5: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: aceita MobileSnapshot v2 no frontend

---

### Task 4: Renderizar WeatherPage v1 e v2 sem recalcular freshness

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/frontend/src/pages/WeatherPage.tsx
- Modify/Test: /home/ciro/dev/prog/alertamaritimoAPI/frontend/src/pages/pages.test.tsx
- Modify: relevant CSS file used by WeatherPage only if status/source labels need styling.

**Interfaces:**
- WeatherPage branches by snapshot.schema_version.
- v1 keeps current legacy rendering.
- v2 renders status/source/mode from payload exactly.
- PWA never computes fresh/stale from timestamps.

- [ ] **Step 1: Write failing rendering tests**

v2 WebPilot:
- shows "Estação Pecém" and "WebPilot";
- shows observed current/mean/max wind;
- shows Open-Meteo complementary section separately;
- shows Open-Meteo Marine separately.

v2 fallback:
- identifies Open-Meteo as fallback/model;
- uses wind/gust semantics, not WebPilot max-wind label;
- hides/marks complementary unavailable.

states:
- stale badge/text visible;
- unavailable renders "Dados indisponíveis" without zero values.

legacy:
- v1 page continues rendering old fixture.

- [ ] **Step 2: Implement WeatherPage v2 branch**

Remove old copy that says all conditions come via Open-Meteo when schema v2 is active. Keep legacy v1 copy if needed for backward compatibility.

- [ ] **Step 3: Run frontend page/full tests**

Run:
    npm test -- --run src/pages/pages.test.tsx src/api/contract.test.ts

Then run the project's normal frontend test command.

Expected: PASS.

- [ ] **Step 4: Build PWA**

Run:
    npm run build

Expected: successful Vite/PWA build.

- [ ] **Step 5: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: exibe fontes meteorologicas do snapshot v2

---

### Task 5: Gate de rollout — validar consumidores antes do Desktop produtor

**Files:**
- Documentation only if deployment runbook needs explicit v2 smoke notes.
- No Desktop change in this task.

**Interfaces:**
- Consumes API/PWA v1+v2 support.
- Produces explicit human approval to proceed to Desktop v2.

- [ ] **Step 1: Run API + frontend full suites**

Run:
    cd /home/ciro/dev/prog/alertamaritimoAPI
    make test
    cd frontend && npm test -- --run
    npm run build

Expected: PASS.

- [ ] **Step 2: Deploy/smoke only when user explicitly authorizes deployment**

Smoke must prove:
- current v1 Desktop remains readable;
- API endpoint accepts a synthetic/safe v2;
- PWA renders that v2 correctly.

- [ ] **Step 3: STOP for human confirmation**

Do not begin Task 6 until user confirms API/PWA consumers are ready. This is a hard rollout gate from the SPEC.

---

### Task 6: Fazer o Desktop produzir MobileSnapshot v2

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/application/mobile_snapshot.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/application/mobile_sync.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/bootstrap.py
- Modify/Test: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_snapshot.py
- Modify/Test: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_sync_coordinator.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/fixtures/mobile_snapshot_v2_expected.json or equivalent focused fixture.

**Interfaces:**
- MobileSnapshot builder now consumes WeatherComposite.
- Produce schema_version=2 with atmosphere/marine contract fixed above.
- Sequence increment remains atomic with successful build only.
- Existing vessel/recent_maneuvers payloads remain unchanged.

- [ ] **Step 1: Write failing Desktop v2 builder tests**

Cover:
- WebPilot fresh => observed primary + complementary forecast + marine;
- WebPilot stale first-problem => observed primary status stale;
- Open-Meteo fallback => fallback primary + complementary unavailable;
- no data => unavailable blocks;
- no cookie/session fields anywhere;
- to_mobile_iso preserves aware timestamps;
- sequence increments only after successful build.

- [ ] **Step 2: Implement v2 serialization**

Do not keep old weather/marine v1 fields in v2. Do not serialize session generation.

- [ ] **Step 3: Adapt MobileSyncCoordinator provider**

weather_provider returns WeatherComposite. Builder receives it directly.

- [ ] **Step 4: Run Desktop focused/full suite**

Run:
    cd /home/ciro/dev/prog/alertamaritimo
    uv run pytest tests/unit/test_mobile_snapshot.py tests/unit/test_mobile_sync_coordinator.py tests/unit/test_mobile_sync_pipeline.py -q
    uv run pytest

Expected: PASS.

- [ ] **Step 5: Cross-repo fixture verification**

Take a Desktop-produced v2 fixture and validate it with:
- API Pydantic MobileSnapshot union;
- frontend parseSnapshotReadResponse fixture/test.

No network required for this contract check.

- [ ] **Step 6: Checkpoint/commit only if explicitly authorized**

Suggested Desktop message:
    feat: publica MobileSnapshot v2 meteorologico

Suggested API/PWA message if not already committed:
    feat: suporta MobileSnapshot v2 meteorologico

---

### Task 7: Manual PWA/iOS validation reserved for execution

**Files:** none unless bugs are found.

- [ ] **Step 1: User validates real PWA after rollout**

Verify:
- source labels;
- stale/unavailable rendering;
- WebPilot observed values;
- fallback copy;
- Marine block;
- existing maps/manobras still work.

- [ ] **Step 2: Record evidence**

Do not mark manual validation complete without user feedback.

- [ ] **Step 3: STOP**

Plan 4 begins only after Plan 3 contract rollout is stable.
