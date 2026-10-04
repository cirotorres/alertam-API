# SPEC 025 Plan 5 — Shadow Evidence/Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Avaliar evidência acumulada do shadow com gate objetivo, gerar relatório sanitizado e decidir se o collector HTTP está tecnicamente apto a ser reutilizado pela SPEC 027 — AlertaM Cloud, sem promover HTTP local nem ativar Cloud automaticamente.

**Architecture:** Um avaliador puro lê ShadowEvidence e decide se os requisitos 24h + 500 ciclos comparáveis + cobertura + 100 ciclos finais limpos foram atendidos. Um gerador de relatório transforma esse estado em resumo humano. A execução real da janela é um gate operacional separado e exige revisão humana.

**Tech Stack:** Python 3.12+, dataclasses, JSON/text output, pytest, documentação operacional.

**Spec:** specs/025-webpilot-http-observed-weather-shadow-migration.md

## Global Constraints

- Dependência obrigatória: Plan 4 concluído e shadow estável.
- Gate técnico não realiza cutover nem ativa Cloud.
- Gate MET apenas permite revisão humana para desbloquear a trilha de implementação da SPEC 027.
- 24 horas é duração mínima observada, não tempo desde instalação.
- 500 é número mínimo de ciclos comparáveis.
- Últimos 100 ciclos comparáveis consecutivos devem estar sem divergência semântica aberta.
- Divergências críticas abertas devem ser zero.
- Cenário raro não observado, como shift, é registrado; não bloqueia indefinidamente por ausência.
- Falhas técnicas não contam como ciclos equivalentes.
- Relatório não contém cookies/headers/HTML bruto.
- Não commit/push sem autorização explícita.

## Review Focus

- Reinício do Desktop no meio da janela não pode zerar contadores/evidência.
- 24h atingidas com menos de 500 comparáveis deve manter gate não atendido.
- 500 comparáveis atingidos em menos de 24h deve manter gate não atendido.
- 100 ciclos finais limpos não podem esconder uma divergência crítica ainda aberta.
- Relógio local/horário de verão não deve afetar duração: usar timestamps aware/UTC para cálculo.

---

### Task 1: Criar modelo de decisão do gate

**Files:**
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/application/shadow_gate.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_shadow_gate.py

**Interfaces:**
- Consumes: ShadowEvidence from Plan 4.
- Produce: GateStatus enum: NOT_READY, BLOCKED, MET
- Produce: GateCheck dataclass:
  - status: GateStatus
  - duration_seconds: int
  - comparable_cycles: int
  - consecutive_clean_comparable: int
  - open_critical_divergences: int
  - coverage_complete: bool
  - unmet_requirements: tuple[str, ...]
  - notes: tuple[str, ...]
- Produce: evaluate_shadow_gate(evidence: ShadowEvidence, now: datetime) -> GateCheck
- open_critical_divergences is derived from critical_divergences whose status is "open"; explained records remain auditable but do not count as open.
- critical_overflow_count > 0 forces BLOCKED because some unique critical divergence could not be retained for review.

Required thresholds:
- duration >= 24h;
- comparable_cycles >= 500;
- consecutive_clean_comparable >= 100;
- open critical divergences == 0;
- required coverage flags true.

- [ ] **Step 1: Write failing threshold tests**

Cover independently:
- 23h59m59s => NOT_READY;
- 24h with 499 comparable => NOT_READY;
- 24h + 500 + 99 clean => NOT_READY;
- all thresholds + one open critical => BLOCKED;
- all thresholds + zero open critical => MET;
- any critical_overflow_count > 0 => BLOCKED even if all retained signatures are explained.

- [ ] **Step 2: Write failing time/restart tests**

Use aware datetimes and evidence loaded from serialized store. Assert restart does not affect started_at/duration.

- [ ] **Step 3: Implement pure evaluator**

No filesystem/network. Gate decision depends only on evidence + now.

- [ ] **Step 4: Add coverage semantics tests**

Required:
- ATRACADO;
- FUNDEADO;
- PREVISTO;
- POB;
- entry_or_exit;
- empty_fields.

Optional-but-reportable:
- berth_change;
- shift;
- other rare statuses.

Optional missing flags add notes, not unmet_requirements.

- [ ] **Step 5: Run GREEN**

Run:
    cd /home/ciro/dev/prog/alertamaritimo
    uv run pytest tests/unit/test_shadow_gate.py -q

Expected: PASS.

- [ ] **Step 6: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: avalia gate tecnico do shadow

---

### Task 2: Gerar relatório de equivalência sanitizado

**Files:**
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/application/shadow_report.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_shadow_report.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/paths.py if a report path is persisted.

**Interfaces:**
- Produce: render_shadow_report(evidence: ShadowEvidence, gate: GateCheck) -> str
- Optional AppPaths property: shadow_report_path -> data_dir / "webpilot_shadow_report.txt"

Report includes:
- start/end/duration;
- total/comparable/equivalent cycles;
- technical failures;
- divergence counts;
- critical open/explained;
- coverage observed;
- scenarios not observed;
- consecutive clean count;
- gate status;
- explicit line: "Cutover: aguardando aprovação humana" when MET.

- [ ] **Step 1: Write failing report tests**

Assert exact presence of:
- "Gate técnico: atendido" only for MET;
- "Cutover: aguardando aprovação humana" for MET;
- unmet requirements for NOT_READY/BLOCKED;
- "shift não observado" note when optional coverage absent;
- no cookie/header/html fields even if fake evidence object tries to carry unknown metadata.

- [ ] **Step 2: Implement renderer**

Prefer deterministic ordering for diff/review. Keep report human-readable and compact.

- [ ] **Step 3: Add atomic write helper only if report is persisted**

Do not overwrite metrics state while rendering.

- [ ] **Step 4: Run GREEN**

Run:
    uv run pytest tests/unit/test_shadow_report.py tests/unit/test_shadow_gate.py -q

Expected: PASS.

- [ ] **Step 5: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: gera relatorio de equivalencia do shadow

---

### Task 3: Adicionar comando de suporte para consultar status/relatório

**Files:**
- Modify or Create according to existing Desktop support task pattern:
  - /home/ciro/dev/prog/alertamaritimo/tasks.ps1
  - optional /home/ciro/dev/prog/alertamaritimo/scripts/shadow_status.py
- Create/Test: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_shadow_status_command.py
- Modify: /home/ciro/dev/prog/alertamaritimo/README.md

**Interfaces:**
- Produce a read-only support command:
    .\tasks.ps1 shadow-status
- Produce an explicit review command:
    .\tasks.ps1 shadow-explain <DIVERGENCE_ID> "<nota>"
- shadow-status loads local ShadowEvidence, evaluates gate at current aware time and prints the report.
- shadow-explain only marks one retained sanitized critical divergence as explained with a human note; it never changes counters, source selection, shadow enablement or operational state.
- Neither command enables shadow, resets evidence or performs cutover.

- [ ] **Step 1: Write failing command contract test**

Static/unit tests assert:
- shadow-status target exists and invokes read-only report code;
- shadow-explain requires an existing divergence id and a non-empty note;
- explaining an id changes only that divergence review status/note;
- neither target contains reset/delete/migrate/cutover behavior;
- shadow-status exit code is 0 for a readable report even if gate is not met; gate state is informational, not CI failure.

- [ ] **Step 2: Implement read-only command**

If PowerShell cannot be executed on Ubuntu, test Python core and statically verify tasks.ps1 wiring. Real PowerShell validation remains a Windows manual gate.

- [ ] **Step 3: Document usage**

README:
- enable shadow separately;
- query with shadow-status;
- metrics/report path;
- thresholds;
- explicit statement that MET does not switch source.

- [ ] **Step 4: Run focused tests**

Run:
    uv run pytest tests/unit/test_shadow_gate.py tests/unit/test_shadow_report.py tests/unit/test_shadow_status_command.py -q

Expected: PASS.

- [ ] **Step 5: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: adiciona consulta do gate shadow

---

### Task 4: Executar validação automatizada completa antes da janela real

**Files:** test only.

- [ ] **Step 1: Run focused Plan 4+5 tests**

Run:
    uv run pytest tests/unit/test_webpilot_grid_html.py tests/unit/test_maneuver_shadow_compare.py tests/unit/test_shadow_metrics_store.py tests/unit/test_maneuver_shadow_service.py tests/unit/test_shadow_gate.py tests/unit/test_shadow_report.py -q

Expected: PASS.

- [ ] **Step 2: Run full Desktop suite**

Run:
    uv run pytest

Expected: PASS except existing intentional skips.

- [ ] **Step 3: Run diff/security review**

Run:
    git diff --check
    git status --short --branch

Inspect all shadow artifacts for secrets/raw authenticated HTML.

- [ ] **Step 4: STOP for user authorization before real operational shadow window**

Do not silently turn ALERTAM_WEBPILOT_SHADOW_MODE on.

---

### Task 5: Janela operacional real de 24h/500 ciclos

**Files:** runtime evidence only; no source edit expected.

**Precondition:** User explicitly authorizes enabling shadow on the target Desktop.

- [ ] **Step 1: Capture baseline**

Record:
- app/version/commit;
- current time aware;
- metrics file state;
- shadow setting currently false.

Do not record cookies/session values.

- [ ] **Step 2: Enable shadow explicitly**

Set support configuration:
    ALERTAM_WEBPILOT_SHADOW_MODE=true

Restart/reload only through the normal application flow.

- [ ] **Step 3: Verify first smoke cycles**

Confirm:
- official Selenium monitoring continues;
- alerts/history/PWA remain sourced from official path;
- metrics comparable/equivalent counters begin changing;
- no UI freeze;
- no credential/raw HTML appears in metrics.

If operational behavior changes, disable shadow and stop the window.

- [ ] **Step 4: Let evidence accumulate**

Target:
- >= 24 hours;
- >= 500 comparable cycles.

Do not declare success from wall-clock alone.

- [ ] **Step 5: Inspect divergences during the window**

For each critical divergence:
- preserve sanitized record;
- investigate cause;
- do not mark as timing automatically;
- only close/explain with evidence.

Implementation bugs discovered here return to the relevant plan/task with TDD; restart the clean-gate evidence as appropriate.

- [ ] **Step 6: Run shadow-status after thresholds**

Record report output and verify:
- coverage;
- open critical divergences;
- last 100 clean comparable cycles.

- [ ] **Step 7: Disable shadow if observation window is complete or if user requests**

Disabling shadow must not delete evidence.

---

### Task 6: Human gate and closure documentation

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/specs/025-webpilot-http-observed-weather-shadow-migration.md
- Modify: /home/ciro/dev/prog/alertamaritimoAPI/specs/README.md
- Create: /home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/handoffs/<date>-spec025-final-handoff.md
- Update impacted Desktop/API/PWA runbooks only with verified outcomes.

- [ ] **Step 1: Classify implementation status**

Document separately:
- completed in code;
- manually validated;
- operational evidence completed;
- deferred/future.

- [ ] **Step 2: Attach/report evidence summary**

Include sanitized figures only:
- duration;
- comparable/equivalent;
- divergences;
- coverage;
- final GateStatus.

- [ ] **Step 3: Explicitly state cutover status**

Required wording/meaning:
- Selenium remains official.
- HTTP shadow evidence is accepted/rejected/pending.
- No cutover occurred under SPEC 025.

- [ ] **Step 4: If gate MET, unlock the next roadmap item only**

Revisar a evidência com o usuário e, se aprovada, marcar a SPEC 027 como liberada para planejamento/execução. Não implementar Cloud nem cutover neste plano. Eventual cutover Selenium→HTTP do Desktop local continua sendo uma decisão separada.

- [ ] **Step 5: Checkpoint/commit documentation only if explicitly authorized**

Suggested message:
    docs: encerra evidencias da spec 025

- [ ] **Step 6: STOP**

SPEC 025 termina aqui. Com gate humano aprovado, a trilha principal segue para a SPEC 027. Qualquer cutover local continua exigindo brainstorm/spec/plan próprios.
