# SPEC 025 Plan 2 — Observed Weather Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Adicionar meteorologia observada WebPilot, política de freshness/fallback e apresentação Desktop, mantendo Open-Meteo Forecast/Marine separados.

**Architecture:** Um parser puro transforma #lblDados em ObservedWeather. WebPilotWeatherService consulta o WebPilot em thread própria via WebPilotHttpClient. WeatherCoordinator combina estado WebPilot com o cache/freshness do WeatherService atual e produz um WeatherComposite explícito, consumido pelo HUD/tooltip e depois pelo MobileSnapshot v2.

**Tech Stack:** Python 3.12+, dataclasses, html.parser da stdlib, threading, pytest, Tkinter existente.

**Spec:** specs/025-webpilot-http-observed-weather-shadow-migration.md

## Global Constraints

- Dependência obrigatória: Plan 1 concluído e revisado.
- WebPilot weather consulta inicial após sessão autenticada disponível; depois cadência mínima de 900 s.
- Open-Meteo Forecast mantém cadência independente atual, aproximadamente 600 s.
- observed_at é obrigatório para leitura WebPilot válida.
- Campos opcionais ausentes/ilegíveis viram None, nunca 0.
- Primeiro ciclo problemático com cache WebPilot => mantém WebPilot stale.
- Segundo ciclo problemático consecutivo => Open-Meteo vira primary fallback.
- Startup sem WebPilot válido => fallback Open-Meteo imediato.
- Primeira nova observação WebPilot válida => recuperação imediata do primary observado.
- Falha de Open-Meteo durante fallback não ressuscita WebPilot velho.
- Não misturar campos de fontes como se fossem uma única estação.
- Nenhum trabalho de rede/parser bloqueante na Tk main thread.
- TDD obrigatório.
- Não commit/push sem autorização explícita.

## Review Focus

- Virada de data/ano em observed_at da estação deve preservar timezone operacional e não produzir timestamp naïve.
- Mesmo observed_at com valores alterados ainda é ciclo problemático; identidade temporal vem do timestamp da estação.
- #lblDados presente com rótulo desconhecido não pode invalidar os campos reconhecidos.
- Open-Meteo disponível mas stale não pode ser promovido como fresh durante fallback.
- Falha simultânea WebPilot + Open-Meteo + Marine não pode apagar último dado válido nem afetar coleta de navios.

---

### Task 1: Criar ObservedWeather e parser puro de #lblDados

**Files:**
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/domain/observed_weather.py
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/domain/webpilot_weather_parser.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/fixtures/webpilot_weather_pecem.html
- Create: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_webpilot_weather_parser.py

**Interfaces:**
- Produces: ObservedWeather dataclass frozen:
  - observed_at: datetime aware
  - consulted_at: datetime aware
  - wind_direction_deg: float | None
  - wind_direction_cardinal: str | None
  - wind_speed_current_kn: float | None
  - wind_speed_mean_kn: float | None
  - wind_speed_max_kn: float | None
  - air_temperature_c: float | None
  - apparent_temperature_c: float | None
  - humidity_pct: float | None
  - pressure_hpa: float | None
  - pressure_6h_hpa: float | None
  - precipitation_mm: float | None
- Produces: WebPilotWeatherParseError(ValueError)
- Produces: parse_webpilot_weather(html: bytes | str, consulted_at: datetime) -> ObservedWeather

- [ ] **Step 1: Add a sanitized realistic #lblDados fixture**

Fixture must contain labels representative of the real page, including:
- Atualizado em: 28/09/2026 20:30:26
- Direção do Vento: 65,00° - ENE
- Vel. Vento (Atual): 16,95 kts
- Vel. Vento (Média): 18,25 kts
- Vel. Vento (Máx): 21,61 kts
- Temperatura: 27,00 °C
- Sensação Térmica
- Umidade Relativa
- Pr.Atmosf. (Atual)
- Pr.Atmosf. (a 6h)
- precipitation example
No cookies/headers/session ids.

- [ ] **Step 2: Write failing parser tests**

Test names:
- test_parses_realistic_lbl_dados_by_labels_not_position
- test_parses_pt_br_decimal_and_thousands_separator
- test_missing_optional_field_becomes_none
- test_unknown_label_is_ignored
- test_missing_lbl_dados_raises_parse_error
- test_missing_or_invalid_observed_at_raises_parse_error
- test_consulted_at_must_be_aware
- test_observed_at_is_aware_in_america_fortaleza
- test_end_of_year_observed_at_remains_aware_and_preserves_station_date
- test_direction_preserves_degrees_and_cardinal

- [ ] **Step 3: Run parser tests RED**

Run:
    cd /home/ciro/dev/prog/alertamaritimo
    uv run pytest tests/unit/test_webpilot_weather_parser.py -q

Expected: FAIL because parser/model do not exist.

- [ ] **Step 4: Implement ObservedWeather and parse_webpilot_weather**

Use html.parser.HTMLParser to extract text only inside element id=lblDados, then semantic label matching. Normalize PT-BR numbers with thousand-dot removal and comma decimal conversion. Do not depend on line positions.

Timezone:
- parse station timestamp into America/Fortaleza;
- reuse the same fallback strategy as mobile_snapshot for Windows without IANA data if needed.

- [ ] **Step 5: Run parser tests GREEN**

Run:
    uv run pytest tests/unit/test_webpilot_weather_parser.py -q

Expected: PASS.

- [ ] **Step 6: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: interpreta meteorologia observada do WebPilot

---

### Task 2: Criar WebPilotWeatherService com polling de 15 minutos

**Files:**
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/infrastructure/webpilot_weather.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_webpilot_weather_service.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/settings.py

**Interfaces:**
- Consumes: WebPilotHttpClient.get(url)
- Consumes: parse_webpilot_weather(html, consulted_at)
- Produces: WEBPILOT_WEATHER_URL constant
- Settings gains:
  - webpilot_weather_interval_seconds default 900, min 900
  - webpilot_weather_online default True or tied to existing weather_online only if design review confirms backward compatibility
- Produces: WebPilotWeatherCycle dataclass:
  - data: ObservedWeather | None
  - problem: bool
  - reason: str | None
- Produces: WebPilotWeatherService.__init__(client, on_cycle, interval=900, now=aware_now)
- Produces: start(), stop(), request_now(), poll_once() -> WebPilotWeatherCycle

- [ ] **Step 1: Write failing service tests**

Cover:
- first request parses and emits ObservedWeather;
- authenticated HTTP error emits problem without exception escape;
- SESSION_EXPIRED after client recovery failure emits problem;
- parser error emits problem;
- service never emits fake zero data;
- interval is at least 900 seconds;
- request_now wakes background thread;
- stop joins cleanly.

- [ ] **Step 2: Implement service using Plan 1 client**

The service owns no cookies/login logic. It calls client.get, validates status OK, parses, and emits one WebPilotWeatherCycle.

- [ ] **Step 3: Add startup-session integration test**

Using fake auth coordinator and fake HTTP client:
- before a session is published, do not perform an uncontrolled busy loop;
- after Application/session callback calls request_now, first poll happens immediately.

- [ ] **Step 4: Run focused tests**

Run:
    uv run pytest tests/unit/test_webpilot_weather_parser.py tests/unit/test_webpilot_weather_service.py tests/unit/test_webpilot_auth.py tests/unit/test_webpilot_http.py -q

Expected: PASS.

- [ ] **Step 5: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: coleta meteorologia WebPilot em ciclo proprio

---

### Task 3: Criar WeatherComposite e WeatherCoordinator

**Files:**
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/application/weather_coordinator.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_weather_coordinator.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/infrastructure/weather.py only to expose source freshness/cache cleanly if current fresco/do_cache is insufficient.

**Interfaces:**
- Produces: Availability enum: FRESH, STALE, UNAVAILABLE
- Produces: AtmosphericSource enum: WEBPILOT, OPEN_METEO
- Produces: AtmosphericMode enum: OBSERVED, FALLBACK
- Produces: AtmosphericPrimary dataclass:
  - status: Availability
  - source: AtmosphericSource | None
  - mode: AtmosphericMode | None
  - observed: ObservedWeather | None
  - forecast: DadosTempo | None
- Produces: WeatherComposite dataclass:
  - primary: AtmosphericPrimary
  - forecast_status: Availability
  - forecast: DadosTempo | None
  - marine_status: Availability
  - marine: DadosMar | None
- Produces: WeatherCoordinator.handle_webpilot_cycle(cycle: WebPilotWeatherCycle) -> WeatherComposite
- Produces: WeatherCoordinator.snapshot() -> WeatherComposite
- Consumes Open-Meteo through injected provider:
  - open_meteo_cache() -> tuple[DadosTempo | None, DadosMar | None]
  - open_meteo_fresh(source: str) -> bool

- [ ] **Step 1: Write failing state-machine tests**

Scenarios:
- no WebPilot, fresh forecast => primary open_meteo/fallback/fresh;
- no WebPilot, no forecast => primary unavailable;
- valid WebPilot => primary webpilot/observed/fresh;
- one problem after valid => same WebPilot/stale;
- second consecutive problem => forecast fallback;
- repeated same observed_at counts as a problem;
- first newer observed_at recovers WebPilot immediately;
- forecast stale during fallback => primary open_meteo/fallback/stale;
- forecast absent during fallback => unavailable;
- forecast failure never revives old WebPilot as primary;
- marine freshness independent of atmosphere.

- [ ] **Step 2: Run RED and implement minimal coordinator**

Do not fetch network inside coordinator. It only receives WebPilot cycles and queries injected Open-Meteo cache/freshness.

- [ ] **Step 3: Add Review Focus tests**

Pin:
- repeated timestamp with changed numeric fields is still problematic;
- unknown/partial optional weather values do not invalidate a new timestamp;
- simultaneous absence of all sources returns explicit unavailable states.

- [ ] **Step 4: Run GREEN**

Run:
    uv run pytest tests/unit/test_weather_coordinator.py tests/unit/test_weather_service.py -q

Expected: PASS.

- [ ] **Step 5: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: coordena freshness e fallback meteorologico

---

### Task 4: Adaptar domínio de apresentação do Desktop ao WeatherComposite

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/domain/meteo.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/ui/renderers.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/application/messages.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/ui/main_window.py
- Create/Test or Modify: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_meteo.py
- Create/Test: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_weather_renderer_state.py

**Interfaces:**
- Replace UI payload meaning from raw DadosTempo|DadosMar updates to a coherent WeatherComposite snapshot.
- Produce pure presentation helpers:
  - linhas_meteo_composite(state: WeatherComposite) -> list[tuple[str, str]]
  - resumo_meteo_composite(state: WeatherComposite) -> list[str]
  - detalhes_meteo_composite(state: WeatherComposite, local: str) -> str
  - wind_direction_for_renderer(state: WeatherComposite) -> float | None

- [ ] **Step 1: Write failing pure presentation tests**

WebPilot primary:
- HUD includes current/mean/max wind concepts and temperature;
- tooltip identifies Estação Pecém / WebPilot;
- tooltip includes observed_at age/reference and optional fields.

Open-Meteo fallback:
- labels use vento/rajada, not WebPilot max wind terminology;
- tooltip identifies fallback/model.

Stale/unavailable:
- stale label is visible;
- unavailable does not display fabricated 0;
- Marine remains separately attributed.

- [ ] **Step 2: Implement pure presentation helpers**

Reuse existing cardinal/direction/formatting helpers where semantics match. Keep WMO/weather-code text only in Open-Meteo sections.

- [ ] **Step 3: Write renderer/message tests**

Assert WeatherRenderer.atualizar accepts WeatherComposite and redraws arrow from the active primary source. WEATHER_READY payload should be WeatherComposite, not a sequence of partial raw source updates.

- [ ] **Step 4: Adapt WeatherRenderer/MainWindow**

Keep visual layout compact. Do not add a large new window. Tooltip carries the expanded detail.

- [ ] **Step 5: Run UI/domain focused tests**

Run:
    uv run pytest tests/unit/test_meteo.py tests/unit/test_weather_renderer_state.py -q

Expected: PASS.

- [ ] **Step 6: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: diferencia fontes meteorologicas no Desktop

---

### Task 5: Integrar serviços no bootstrap sem afetar manobras

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/bootstrap.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/application/mobile_sync.py only to accept a weather provider returning WeatherComposite for Plan 3 compatibility; do not publish v2 yet.
- Create/Test: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_webpilot_weather_bootstrap.py
- Modify/Test: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_sync_bootstrap.py

**Interfaces:**
- Application owns:
  - self.webpilot_weather: WebPilotWeatherService | None
  - self.weather_coordinator: WeatherCoordinator | None
- Existing self.weather remains Open-Meteo WeatherService.
- MobileSync weather_provider becomes Callable[[], WeatherComposite] internally, but MobileSnapshotBuilder stays schema v1 until Plan 3; if backward compatibility requires it, adapt at the provider boundary rather than publishing v2 now.

- [ ] **Step 1: Write failing bootstrap lifecycle tests**

Assert:
- Open-Meteo starts independently as today;
- WebPilotWeatherService is created but initial request waits for authenticated session publication;
- session publication triggers request_now;
- shutdown stops both services;
- WebPilot failure still leaves Controller/Selenium collection untouched;
- _on_collection can refresh/enqueue current WeatherComposite without doing network I/O.

- [ ] **Step 2: Implement bootstrap wiring**

Plan 1 on_webpilot_session callback must:
1. publish cookies to auth coordinator;
2. wake WebPilotWeatherService.

WebPilotWeatherService on_cycle callback feeds WeatherCoordinator and enqueues UI message with composite.

Open-Meteo on_result callback should cause a new composite snapshot/redraw, not bypass the coordinator.

- [ ] **Step 3: Add mobile compatibility adapter tests**

Until Plan 3, schema v1 builder still receives existing DadosTempo/DadosMar from Open-Meteo cache. Do not silently change published contract in Plan 2.

- [ ] **Step 4: Run full Desktop suite**

Run:
    uv run pytest

Expected: full suite PASS except existing intentional skips.

- [ ] **Step 5: Manual Tk/Xephyr gate reserved for execution**

When implemented later, user performs real Tk/Xephyr validation:
- HUD remains compact;
- tooltip differentiates sources;
- no freeze during WebPilot HTTP failure/session refresh.

Do not claim this manual gate before user reports it.

- [ ] **Step 6: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: integra meteorologia observada do WebPilot
