# SPEC 024 — Operational Timing Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistir o horário operacional ATRAC no ManeuverEvent e apresentar POB → ATRAC como duração real da movimentação no Desktop/API/PWA.

**Architecture:** O Desktop é a única fonte que interpreta `ATRAC: DD/MM - HH:MM` e emite `operational_at`/`operational_marker`. A API valida e persiste os campos opcionais no JSONB existente; o PWA apenas valida, projeta e apresenta. Eventos antigos continuam válidos com ambos os campos nulos.

**Tech Stack:** Python 3.10+, dataclasses, pytest, FastAPI/Pydantic v2, PostgreSQL JSONB, React 19, TypeScript, Zod 4, Vitest.

**Spec:** `specs/024-operational-maneuver-timing-ux-refinements.md`

## Global Constraints

- Marcador normativo inicial: somente `ATRAC`.
- `operational_at` e `operational_marker` são preenchidos juntos ou ambos são nulos.
- Timezone operacional: `America/Fortaleza`.
- Sem backfill e sem migration SQL.
- Duração válida somente quando `operational_at >= pob_at`.
- Desatracação concluída não ganha horário operacional inventado.
- `first_observed_at` e `occurred_at` mantêm seus significados atuais.

## Review Focus

- Virada de ano em `ATRAC: 31/12 - 23:50` observada em janeiro escolhe o ano de calendário mais próximo.
- ATRAC malformado ou com outro prefixo não impede a conclusão da manobra.
- Mudança de horário ATRAC entre a primeira e a segunda coleta reinicia o debounce terminal.
- Evento legado sem os novos campos continua serializando, persistindo e renderizando sem duração falsa.
- `operational_at < pob_at` não produz duração negativa nem texto enganoso.

---
### Task 1: Parser ATRAC e contrato Desktop

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/maneuver_time.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/domain/maneuvers.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_time.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_runtime_store.py`

**Interfaces:**
- Produces: `normalize_atrac_at(value: str | None, observed_at: datetime) -> str | None`.
- Produces: `ManeuverEvent.operational_at: str | None` e `operational_marker: Literal["ATRAC"] | None`.
- Consumes: regra de calendário já usada por `normalize_pob_at`.

- [ ] **Step 1: Escrever testes RED do parser e compatibilidade legada**

Cobrir `ATRAC: 29/09 - 05:28`, virada de ano, valor inválido, prefixo `FUND` e evento antigo sem campos novos.

- [ ] **Step 2: Rodar os testes focados e confirmar falha**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_time.py tests/unit/test_maneuver_runtime_store.py -q`
Expected: FAIL por parser/campos ainda inexistentes.

- [ ] **Step 3: Implementar parser e evolução do dataclass**

Adicionar a assinatura acima e os dois campos opcionais ao final de `ManeuverEvent`, incluindo `to_dict()/from_dict()`.

- [ ] **Step 4: Rodar testes focados e confirmar PASS**

Run: mesmo comando do Step 2.
Expected: PASS.

- [ ] **Step 5: Commit Desktop**

`git commit -m "feat: adiciona horário operacional ao evento de manobra"`
### Task 2: Detector terminal e duração operacional

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/maneuver_tracker.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/maneuver_details.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_tracker.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_details.py`

**Interfaces:**
- Consumes: `normalize_atrac_at(...)` da Task 1.
- Produces: COMPLETED de ATRACACAO com `operational_marker="ATRAC"` quando válido.
- Produces: `movement_duration_minutes(event: ManeuverEvent) -> int | None`.

- [ ] **Step 1: Escrever testes RED do caso FERNAO e do debounce**

Criar `test_completed_atracacao_preserves_operational_atrac_timestamp`: POB `29/09 02:30`, ATRAC `29/09 - 05:28`, primeira observação 10:45, confirmação 10:46; esperar `operational_at=2026-09-29T05:28:00-03:00`, `operational_marker="ATRAC"` e duração 178 minutos.

Adicionar teste em que ATRAC muda entre as duas observações e só a versão estável é emitida.

- [ ] **Step 2: Rodar testes e confirmar falha**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_tracker.py tests/unit/test_maneuver_details.py -q`
Expected: FAIL porque o terminal ainda ignora ATRAC.

- [ ] **Step 3: Implementar captura terminal e helper de duração**

Incluir horário operacional no fingerprint do candidato terminal quando aplicável. Desatracação e valores inválidos emitem campos nulos. O helper retorna `None` para ausentes, timestamps inválidos ou duração negativa.

- [ ] **Step 4: Rodar testes e confirmar PASS**

Run: mesmo comando do Step 2.
Expected: PASS.

- [ ] **Step 5: Commit Desktop**

`git commit -m "feat: usa ATRAC real na duração da movimentação"`
### Task 3: Contrato e round-trip na API

**Files:**
- Modify: `api/app/models/maneuver_event.py`
- Test: `api/tests/unit/test_maneuver_event_model.py`
- Test: `api/tests/integration/test_post_maneuver_event.py`
- Test: `api/tests/integration/test_get_maneuver_events.py`
- Test: `api/tests/integration/test_get_maneuver_event_detail.py`
- Test: `api/tests/integration/test_accept_maneuver_event_repository.py`

**Interfaces:**
- Consumes: payload Desktop com `operational_at` e `operational_marker`.
- Produces: os mesmos campos em POST/feed/detail sem alterar schema SQL.
- Model: `operational_at: AwareDatetime | None = None`.
- Model: `operational_marker: Literal["ATRAC"] | None = None`.

- [ ] **Step 1: Escrever testes RED do par operacional**

Criar `test_post_round_trips_operational_timing_fields`; aceitar ambos preenchidos ou ambos ausentes; rejeitar campo órfão, timestamp sem timezone e marcador diferente de ATRAC. Provar round-trip no feed e detalhe.

- [ ] **Step 2: Rodar testes focados e confirmar falha**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/api && uv run pytest tests/unit/test_maneuver_event_model.py tests/integration/test_post_maneuver_event.py tests/integration/test_get_maneuver_events.py tests/integration/test_get_maneuver_event_detail.py tests/integration/test_accept_maneuver_event_repository.py -q -W error`
Expected: FAIL nos campos ainda proibidos pelo contrato estrito.

- [ ] **Step 3: Implementar campos e validator no Pydantic**

Manter `canonical_payload()` e persistência existentes; os campos novos viajam dentro de `event_payload` JSONB.

- [ ] **Step 4: Rodar testes focados e confirmar PASS**

Run: mesmo comando do Step 2.
Expected: PASS.

- [ ] **Step 5: Commit API**

`git commit -m "feat: preserva horário operacional em ManeuverEvent"`
### Task 4: Contrato Zod e apresentação operacional no PWA

**Files:**
- Modify: `frontend/src/api/contract.ts`
- Modify: `frontend/src/features/events/alertDetailProjections.ts`
- Modify: `frontend/src/features/events/AlertDetailSheet.tsx`
- Test: `frontend/src/api/contract.test.ts`
- Test: `frontend/src/features/events/alertDetailProjections.test.ts`
- Test: `frontend/src/features/events/AlertDetailSheet.test.tsx`

**Interfaces:**
- Consumes: campos opcionais da Task 3.
- Produces: `formatMovementDuration(pobAt: string | null, operationalAt: string | null) -> string | null`.
- Mantém `formatObservedDelta` somente para comparação entre POBs, não para conclusão.

- [ ] **Step 1: Escrever testes RED do caso FERNAO**

Criar `alert_detail_completed_uses_operational_duration_not_observation_delay`; esperar título `Atracação concluída`, `ATRAC informado na planilha`, `05:28`, `Tempo da movimentação`, `2h58`, além de `Primeira observação 10:45` e `Confirmação 10:46`.

Adicionar evento legado: deve mostrar monitoramento, mas não “Diferença para o POB” nem duração inventada.

- [ ] **Step 2: Rodar Vitest focado e confirmar falha**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/api/contract.test.ts src/features/events/alertDetailProjections.test.ts src/features/events/AlertDetailSheet.test.tsx`
Expected: FAIL pelos novos campos/textos.

- [ ] **Step 3: Evoluir Zod e projeções**

Normalizar campos ausentes para null, validar o par operacional e substituir a semântica de conclusão baseada em `occurred_at - pob_at`.

- [ ] **Step 4: Atualizar a sheet sem misturar relógios**

Criar bloco principal operacional e bloco secundário “Monitoramento do AlertaM”. `occurred_at` é confirmação do sistema, não horário real da atracação.

- [ ] **Step 5: Rodar Vitest focado e confirmar PASS**

Run: mesmo comando do Step 2.
Expected: PASS.

- [ ] **Step 6: Commit frontend**

`git commit -m "feat: destaca tempo operacional da manobra no PWA"`
### Task 5: Gates cross-repo do Plano 1

**Files:**
- Test only; nenhuma mudança funcional esperada.

**Interfaces:**
- Prova o fluxo Desktop → API → PWA com o fixture FERNAO.

- [ ] **Step 1: Rodar suíte Desktop sem Xephyr**

Run: `cd /home/ciro/dev/prog/alertamaritimo && make test`
Expected: PASS.

- [ ] **Step 2: Rodar API completa com PostgreSQL efêmero**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI && make test-all`
Expected: PASS.

- [ ] **Step 3: Rodar frontend completo e build**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run && npm run build`
Expected: PASS.

- [ ] **Step 4: Provar paridade do fixture FERNAO nos três contratos**

Run Desktop: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_tracker.py -k completed_atracacao_preserves_operational_atrac_timestamp -q`
Run API: `cd /home/ciro/dev/prog/alertamaritimoAPI/api && uv run pytest tests/integration/test_post_maneuver_event.py -k post_round_trips_operational_timing_fields -q -W error`
Run PWA: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/features/events/AlertDetailSheet.test.tsx -t "operational duration"`
Expected: os três PASS usando POB 02:30, ATRAC 05:28 e duração 2h58.

- [ ] **Step 5: Verificação de diff**

Run em ambos os repositórios: `git diff --check`.
Expected: sem saída.
