# SPEC 024 — Desktop UX Refinements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar o tracking e o histórico Desktop semanticamente equivalentes ao PWA após a introdução do horário operacional.

**Architecture:** O mapa mantém o tracking como marcador visual independente do estado do navio. As janelas existentes de detalhe de manobra e Acompanhados são evoluídas; nenhuma nova janela ou store é criada. As projeções reutilizam os campos e helper de duração produzidos pelo Plano 1.

**Tech Stack:** Python 3.10+, Tkinter/ttk, pytest, Xephyr.

**Spec:** `specs/024-operational-maneuver-timing-ux-refinements.md`

## Global Constraints

- Depende do Plano 1 concluído.
- Não criar nova janela de histórico.
- Estrela de tracking não interfere em pulsos vermelho/verde.
- Horário operacional é principal; horários do AlertaM são secundários.
- Eventos legados continuam legíveis.
- Tk/Xephyr é gate humano final.

## Review Focus

- Estrela âmbar permanece legível em sprite normal, verde e vermelho.
- Evento COMPLETED sem operational_at não mostra duração falsa.
- Evento com operational_at inválido não quebra a janela de detalhe.
- Timeline local preserva ordem cronológica entre MANEUVER e TRACKING.
- Navio ausente continua acessível em Acompanhados com último estado conhecido.

---
### Task 1: Estrela âmbar no mapa Desktop

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/renderers.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_ship_tracking_presentation.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/integration/test_ui_real.py`

**Interfaces:**
- Produces: constante `TRACKING_MARK_COLOR = "#f4b400"`.
- `_update_tracking_mark` usa a constante tanto na criação quanto na atualização.

- [ ] **Step 1: Escrever teste RED da cor real do Canvas**

No unitário, fixar `TRACKING_MARK_COLOR == "#f4b400"`. No teste Tk real, após renderizar navio acompanhado, obter o item em `tracking_marks` e esperar `itemcget(mark, "fill") == "#f4b400"`; repetir durante estados/pulsos verde e vermelho e confirmar que a cor do marcador não muda.

- [ ] **Step 2: Rodar testes focados e confirmar falha**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_ship_tracking_presentation.py -q`
Expected: FAIL no requisito de cor ainda branca.

- [ ] **Step 3: Implementar constante e uso no renderer**

Não alterar texto ★, posição, tamanho ou lógica de tracking.

- [ ] **Step 4: Rodar teste e confirmar PASS**

Run: mesmo comando do Step 2.
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "style: destaca acompanhamento com estrela amarela"`
### Task 2: Detalhes de manobra com relógios separados

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/maneuver_detail_window.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_maneuver_details.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/integration/test_historico_ordem.py`

**Interfaces:**
- Consumes: `movement_duration_minutes(event)`, `operational_at` e `operational_marker`.
- Produces: bloco operacional e bloco “Monitoramento do AlertaM” no texto existente.

- [ ] **Step 1: Escrever teste RED com fixture FERNAO**

Esperar POB 02:30, ATRAC 05:28, “Tempo da movimentação: 2h58”, primeira observação 10:45 e confirmação 10:46. Proibir “Diferença para o POB” na conclusão. Adicionar evento legado/operational_at inválido e confirmar que a janela continua abrindo sem duração falsa.

- [ ] **Step 2: Rodar testes focados e confirmar falha**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_maneuver_details.py tests/integration/test_historico_ordem.py -q`
Expected: FAIL nos textos atuais.

- [ ] **Step 3: Atualizar build_detail_text**

Preservar CONFIRMED/UPDATED/CANCELLED. Para COMPLETED com ATRAC, informação operacional vem antes do monitoramento.

- [ ] **Step 4: Rodar testes e confirmar PASS**

Run: mesmo comando do Step 2.
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat: separa tempo operacional e observação no histórico"`
### Task 3: Timeline local de Acompanhados enriquecida

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/tracked_vessel_details.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/tracked_vessels_window.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_tracked_vessel_details.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_ship_tracking_presentation.py`
- Test: `/home/ciro/dev/prog/alertamaritimo/tests/integration/test_ui_real.py`

**Interfaces:**
- Consumes: ManeuverEvent enriquecido pelo Plano 1.
- Produces: resumo COMPLETED com POB, ATRAC e duração quando disponíveis.
- Mantém `TimelineKind.MANEUVER`/`TRACKING` e ordenação atuais.

- [ ] **Step 1: Escrever testes RED**

COMPLETED do FERNAO gera resumo com “Atracação concluída”, “ATRAC 05:28” e “2h58”. Evento legado continua com resumo válido sem duração. Preservar teste explícito de ordem cronológica MANEUVER/TRACKING, tracking residual não duplicado e navio ausente com último estado conhecido.

- [ ] **Step 2: Rodar testes focados e confirmar falha**

Run: `cd /home/ciro/dev/prog/alertamaritimo && uv run pytest tests/unit/test_tracked_vessel_details.py tests/unit/test_ship_tracking_presentation.py -q`
Expected: FAIL no resumo operacional novo.

- [ ] **Step 3: Evoluir projeção e formatação da janela existente**

Não criar nova tela. Formatar timestamps para leitura humana em vez de exibir ISO cru quando possível.

- [ ] **Step 4: Rodar testes e confirmar PASS**

Run: mesmo comando do Step 2.
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat: enriquece timeline local de navios acompanhados"`
### Task 4: Gates finais Desktop

**Files:**
- Test only.

- [ ] **Step 1: Suíte completa sem Xephyr**

Run: `cd /home/ciro/dev/prog/alertamaritimo && make test`
Expected: PASS.

- [ ] **Step 2: Import gate**

Run: `make check`
Expected: PASS, incluindo “imports OK”.

- [ ] **Step 3: Gate Tk/Xephyr**

Run pelo usuário: `make test-ui XEPHYR_N=27`
Expected: PASS.

- [ ] **Step 4: Validação visual manual**

FERNAO ou fixture equivalente: estrela âmbar, detalhe 02:30 → 05:28 → 2h58, e Acompanhados com timeline legível.

- [ ] **Step 5: Diff check**

Run: `git diff --check`
Expected: sem saída.
