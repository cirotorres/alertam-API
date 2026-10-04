# SPEC 025 Plan 4 — Maneuver HTTP Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Criar coleta HTTP shadow das movimentações, comparar com o snapshot Selenium no domínio normalizado e persistir evidência sanitizada sem produzir qualquer efeito operacional.

**Architecture:** ManeuverShadowService recebe o Snapshot oficial Selenium de cada ciclo, faz GET autenticado via WebPilotHttpClient, extrai somente #ASPxGridView1 com HTMLParser, reutiliza parse_grid_rows e compara os dois snapshots com matching conservador. O resultado vai apenas para ShadowMetricsStore.

**Tech Stack:** Python 3.12+, html.parser, threading/queue, dataclasses/enums, pytest.

**Spec:** specs/025-webpilot-http-observed-weather-shadow-migration.md

## Global Constraints

- Dependência técnica: Plan 1 concluído. Dependência de roadmap: Plan 2 também concluído/revisado antes de iniciar a Etapa B. Plan 3 pode estar em produção em paralelo, mas shadow não depende de MobileSnapshot v2.
- O serviço shadow deve nascer headless/reutilizável o suficiente para servir de base ao futuro collector Cloud após o gate, sem importar UI/Tk nem efeitos operacionais.
- ALERTAM_WEBPILOT_SHADOW_MODE default false.
- Shadow nunca alimenta ManeuverTracker, eventos, push, áudio, histórico operacional, MobileSnapshot ou PWA.
- Reutilizar parse_grid_rows; não criar parser semântico concorrente.
- Matching: IMO válido exato primeiro, nome normalizado exato depois; sem fuzzy.
- Não usar posição, berço, POB, ETA ou status para identidade.
- Grid ausente é HTML_INVALID, não snapshot vazio válido.
- Divergência não é automaticamente "timing".
- Persistência sanitizada, pequena e sem HTML/cookies/headers.
- TDD obrigatório.
- Não commit/push sem autorização explícita.

## Review Focus

- Dois navios com mesmo nome e sem IMO devem produzir IDENTITY_AMBIGUOUS, não emparelhamento arbitrário.
- IMO inválido/placeholder não pode sobrepor um match seguro por nome.
- Mudança de ordem das linhas da grid não pode gerar divergência.
- Snapshot Selenium vazio legitimamente e HTTP vazio legitimamente deve ser comparável sem confundir ausência da grid.
- Shadow mais lento que o intervalo oficial não pode bloquear nem criar backlog ilimitado.

---

### Task 1: Extrair #ASPxGridView1 em linhas compatíveis com parse_grid_rows

**Files:**
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/infrastructure/webpilot_grid_html.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_webpilot_grid_html.py
- Reuse fixture: /home/ciro/dev/prog/alertamaritimo/tests/fixtures/grid_real_2026-09-21.html
- Modify helper only if appropriate: /home/ciro/dev/prog/alertamaritimo/tests/fixtures/html_rows.py

**Interfaces:**
- Produce: GridHtmlError(ValueError)
- Produce: extract_grid_rows(html: bytes | str, grid_id: str = GRID_ID) -> list[list[str]]

- [ ] **Step 1: Write failing extractor tests**

Cover:
- realistic fixture yields rows containing PORTO/SITUAÇÃO/data rows;
- extraction is scoped only to ASPxGridView1 even if another table exists;
- direct td children only, preserving current Selenium semantics;
- &nbsp;/whitespace normalized;
- missing grid raises GridHtmlError;
- malformed/partial grid that never opens target raises GridHtmlError.

- [ ] **Step 2: Run RED**

Run:
    cd /home/ciro/dev/prog/alertamaritimo
    uv run pytest tests/unit/test_webpilot_grid_html.py -q

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement HTMLParser extractor**

Do not interpret Navio semantics. It only emits text cells/rows.

- [ ] **Step 4: Add equivalence test against existing fixture helper**

For grid_real_2026-09-21.html:
- extract_grid_rows -> parse_grid_rows
must produce the same normalized Snapshot/navios expected by existing parser fixture tests.

- [ ] **Step 5: Run GREEN**

Run:
    uv run pytest tests/unit/test_webpilot_grid_html.py tests/unit/test_parser_fixture.py -q

Expected: PASS.

- [ ] **Step 6: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: extrai grid WebPilot por HTTP

---

### Task 2: Criar comparator de snapshots com matching conservador

**Files:**
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/application/maneuver_shadow_compare.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_shadow_compare.py

**Interfaces:**
- Produce: ShadowDivergenceType enum:
  - VESSEL_COUNT_MISMATCH
  - MISSING_VESSEL
  - EXTRA_VESSEL
  - IDENTITY_AMBIGUOUS
  - SECTION_MISMATCH
  - STATUS_MISMATCH
  - FIELD_MISMATCH
  - HTTP_ERROR
  - SESSION_EXPIRED
  - HTML_INVALID
  - PARSER_ERROR
- Produce: ShadowDivergence(type, vessel_key: str | None, field: str | None, official: str | int | None, shadow: str | int | None)
- Produce: ShadowComparison(official_count: int, shadow_count: int, comparable: bool, equivalent: bool, divergences: tuple[ShadowDivergence, ...])
- Produce: compare_snapshots(official: Snapshot, shadow: Snapshot) -> ShadowComparison

Fields compared after identity:
- secao
- situacao
- nome normalized only for reporting after match
- imo normalized
- pob
- berco
- bordo
- eta
- etb_ets
- agencia
- porto_origem
- rebocadores
- bandeira/irin if the parser currently transports them; include them as FIELD_MISMATCH rather than inventing special types.

- [ ] **Step 1: Write failing identity tests**

Cover:
- exact normalized IMO matches despite row order;
- invalid/blank IMO falls back to exact normalized name;
- normalize_valid_imo accepts only a trimmed seven-digit numeric identifier; other forms are treated as absent for matching (no checksum rule is introduced by this SPEC);
- duplicate same name with no valid IMO => IDENTITY_AMBIGUOUS;
- similar-but-not-equal names do not fuzzy match;
- berth/status/POB never create identity.

- [ ] **Step 2: Implement matching stage only**

Use deterministic maps/multimaps. Do not mutate Snapshot/Navio.

- [ ] **Step 3: Write failing field divergence tests**

Cover:
- equivalent snapshots => no divergences/equivalent true;
- two legitimately empty Snapshots => comparable/equivalent true;
- count mismatch;
- missing/extra vessel;
- section/status mismatch;
- one FIELD_MISMATCH per differing operational field;
- line order differences do not matter.

- [ ] **Step 4: Implement comparison**

comparable is true only when both inputs are valid Snapshots; ambiguity can still be a comparable cycle with divergence, unless review determines identity prevents a meaningful field comparison for that vessel.

- [ ] **Step 5: Run focused tests GREEN**

Run:
    uv run pytest tests/unit/test_maneuver_shadow_compare.py -q

Expected: PASS.

- [ ] **Step 6: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: compara snapshots Selenium e HTTP

---

### Task 3: Criar ShadowMetricsStore sanitizado e limitado

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/paths.py
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/infrastructure/shadow_metrics_store.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_shadow_metrics_store.py

**Interfaces:**
- AppPaths gains shadow_metrics_path -> data_dir / "webpilot_shadow_metrics.json"
- Produce: ShadowEvidence dataclass/json shape:
  - started_at
  - last_cycle_at
  - total_cycles
  - comparable_cycles
  - equivalent_cycles
  - consecutive_clean_comparable
  - technical_failures
  - divergence_counts: dict[str, int]
  - coverage: dict[str, bool]
  - critical_divergences: list of sanitized unique signatures, each with id/status/occurrences/first_seen/last_seen/explanation
  - critical_overflow_count: int
  - last_comparison: sanitized summary | None
  - recent_divergences: list limited to last 10
- Produce: ShadowMetricsStore.load() -> ShadowEvidence
- Produce: ShadowMetricsStore.record(comparison_or_failure, official_snapshot, coverage_events=()) -> ShadowEvidence
- Produce: ShadowMetricsStore.mark_explained(divergence_id: str, note: str) -> ShadowEvidence
- Produce: ShadowMetricsStore.reset() -> ShadowEvidence only for explicit support/test use; no automatic reset at startup.
- Critical divergence ids are deterministic hashes of the sanitized canonical signature (type + vessel key + field + compared values); keep at most 100 unique signatures. If the cap is exceeded, increment critical_overflow_count and the later gate must remain blocked until a new clean evidence window is intentionally started.

- [ ] **Step 1: Write failing persistence/retention tests**

Assert:
- atomic persistence;
- missing file -> empty evidence;
- malformed file -> safe backup/reinitialize pattern consistent with project stores;
- recent_divergences capped at 10;
- critical unique signatures capped at 100 and overflow counted;
- mark_explained changes only the matching sanitized critical record and preserves occurrence counters;
- counters and explained/open state accumulate across restart;
- no full HTML/cookies/headers in serialized structure.

- [ ] **Step 2: Implement store**

Use JSON as a text record for atomic structured persistence. Do not serialize entire Snapshot; last_comparison contains counts/status only and recent divergence entries contain sanitized fields.

- [ ] **Step 3: Write coverage tests**

Coverage flags updated from official snapshot for:
- ATRACADO;
- FUNDEADO;
- PREVISTO;
- POB present;
- empty operational fields observed;
- vessel set change can be recorded by service later as entry/exit;
- berth change/shift remain optional observational flags when detectable.

- [ ] **Step 4: Run GREEN**

Run:
    uv run pytest tests/unit/test_shadow_metrics_store.py -q

Expected: PASS.

- [ ] **Step 5: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: persiste evidencias sanitizadas do shadow

---

### Task 4: Criar ManeuverShadowService isolado em thread própria

**Files:**
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/infrastructure/maneuver_shadow.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_shadow_service.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/settings.py

**Interfaces:**
- Settings gains webpilot_shadow_mode from ALERTAM_WEBPILOT_SHADOW_MODE default False.
- Produce: WEBPILOT_MANEUVERS_URL reuse WEBPILOT_URL.
- Produce: ManeuverShadowService.__init__(client, store, on_internal_error=None, queue_size=2)
- Produce: start(), stop(), submit(official_snapshot: Snapshot) -> bool
- Internal worker flow:
  1. client.get(WEBPILOT_URL)
  2. classify transport result;
  3. extract_grid_rows
  4. parse_grid_rows(rows, agora=official_snapshot.coletado_em)
  5. compare_snapshots
  6. store.record

- [ ] **Step 1: Write failing happy-path service test**

Fake client returns realistic grid HTML. submit returns immediately; background worker eventually records one comparable/equivalent cycle.

- [ ] **Step 2: Write failing error classification tests**

Cover:
- SESSION_EXPIRED => technical failure/divergence category, no exception escape;
- TIMEOUT/HTTP_ERROR => technical failure;
- missing grid => HTML_INVALID;
- parser exception => PARSER_ERROR;
- no failure enters ManeuverTracker or any callback with operational snapshot.

- [ ] **Step 3: Implement worker**

Queue must be bounded. If producer outruns worker:
- never block caller;
- record a safe skipped/technical count or return False;
- do not grow unbounded backlog.

Do not expose any callback capable of replacing official snapshot.

- [ ] **Step 4: Write stop/lifecycle tests**

start idempotent, stop joins, disabled service not started by bootstrap later.

- [ ] **Step 5: Run focused tests**

Run:
    uv run pytest tests/unit/test_webpilot_grid_html.py tests/unit/test_maneuver_shadow_compare.py tests/unit/test_shadow_metrics_store.py tests/unit/test_maneuver_shadow_service.py -q

Expected: PASS.

- [ ] **Step 6: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: adiciona coleta shadow de movimentacoes

---

### Task 5: Integrar shadow no ciclo oficial sem efeitos colaterais

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/bootstrap.py
- Modify: /home/ciro/dev/prog/alertamaritimo/README.md
- Create/Test: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_shadow_bootstrap.py
- Modify/Test: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_controller_pipeline.py only if needed to assert official path unchanged.

**Interfaces:**
- Application owns self.maneuver_shadow: ManeuverShadowService | None.
- Application._on_collection submits the exact official Snapshot after/beside normal mobile/tracking handling, without consuming shadow output.
- Shadow service only created/started when settings.webpilot_shadow_mode is True.

- [ ] **Step 1: Write failing bootstrap isolation tests**

Assert:
- default False => no shadow service/start/request;
- True => service starts;
- _on_collection calls shadow.submit but still calls existing mobile/tracking paths exactly once;
- shadow.submit failure/False does not alter confirmed/events or scheduler;
- shutdown stops service.

- [ ] **Step 2: Implement bootstrap wiring**

Use Plan 1 WebPilotHttpClient. Do not add UI controls or status badges for shadow.

- [ ] **Step 3: Document support-only enablement**

README section:
    ALERTAM_WEBPILOT_SHADOW_MODE=true

Explain:
- disabled by default;
- comparison only;
- no operational cutover;
- metrics path under application data dir;
- no secrets in metrics.

- [ ] **Step 4: Run full Desktop suite**

Run:
    cd /home/ciro/dev/prog/alertamaritimo
    uv run pytest

Expected: PASS except existing intentional skips.

- [ ] **Step 5: Security/diff review**

Run:
    git diff --check

Inspect test fixtures/metrics code:
- no cookie values;
- no authenticated raw HTML newly committed beyond sanitized fixtures;
- no HTTP result feeding ManeuverTracker.

- [ ] **Step 6: Manual shadow smoke reserved for execution**

With explicit user approval to enable shadow:
- start Desktop;
- verify official UI/manobras behave unchanged;
- verify metrics file changes;
- disable shadow and verify no further shadow requests.

- [ ] **Step 7: STOP**

No cutover. Plan 5 only evaluates accumulated evidence.

- [ ] **Step 8: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: integra shadow HTTP sem efeito operacional
