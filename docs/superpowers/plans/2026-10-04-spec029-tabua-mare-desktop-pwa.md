# SPEC 029 — Tábua de maré DHN Desktop + PWA — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empacotar a tábua DHN 2026 do Pecém no Desktop e no PWA, mostrar Hoje+Amanhã com próximo evento destacado e substituir o ID permanente do Desktop por `ⓘ`.

**Architecture:** Os valores anuais são dados estáticos versionados, não passam por API/Supabase/MobileSnapshot. Um JSON byte-idêntico é empacotado nos dois clientes; cada cliente possui apenas um seletor temporal local para UTC−03 e uma apresentação própria. O Desktop usa `Toplevel` reutilizável; o PWA adiciona card à WeatherPage existente.

**Tech Stack:** Python 3.10+/Tkinter/PyInstaller/pytest; React/Vite/TypeScript/Vitest; JSON estático.

**Spec:** `specs/029-tabua-mare-dhn-desktop-pwa.md`

## Global Constraints

- Fonte única de valores: PDF DHN `16 - TERMINAL PORTUÁRIO DO PECÉM  58 - 60.pdf`, SHA-256 `dad5ef1a49ddf499c25dce5488612e521c4be614dc1c465a1f6c1ecf2b49b6bd`.
- Se o PDF não estiver disponível na sessão de execução, pedir ao usuário que o reanexe antes da Task 1; não substituir por fonte web.
- PDF não é lido em runtime.
- Não alterar API backend, Supabase, MobileSnapshot, WebPilot, Open-Meteo ou contratos Weather v1/v2.
- Hoje/Amanhã sempre no fuso do Pecém UTC−03, não no timezone do aparelho.
- Não interpolar maré; não inventar quarto evento; preservar alturas negativas.
- Dataset Desktop e PWA byte-idêntico.
- 2027 ausente deve produzir indisponibilidade explícita.
- Desktop: remover ID permanente; `ⓘ` nunca mostra segredo.
- PWA: card dentro de `/tempo`; nenhum novo item de navegação.
- SPEC 029 não inicia Plan 4/Shadow.
- TDD obrigatório.
- Não commit/push sem autorização explícita.

## Review Focus

- Virada de data: 00:30 UTC deve ainda selecionar o dia anterior no Pecém quando aplicável.
- 31/12/2026 deve mostrar Hoje e indisponibilidade para 01/01/2027, sem crash/extrapolação.
- Um dia com três eventos deve renderizar três linhas, não uma linha vazia/zero.
- Altura negativa da fonte deve sobreviver JSON → parser → UI.
- PyInstaller precisa realmente carregar o JSON fora do checkout de desenvolvimento.

---

### Task 1: Normalizar e validar o dataset DHN 2026

**Files:**
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/data/tides/pecem-2026.json`
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/data/tides/pecem-2026.json`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/tides/tideDataset.test.ts`
- Create: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_tide_dataset.py`

**Interfaces:**
- Produce: JSON schema v1 definido na SPEC.
- Produce: exatamente 365 chaves `YYYY-MM-DD` para 2026.
- Produce: cópias byte-idênticas nos dois repositórios.

- [ ] **Step 1: Verificar a fonte recebida**

Calcular SHA-256 do PDF usado na sessão.

Expected:

```text
dad5ef1a49ddf499c25dce5488612e521c4be614dc1c465a1f6c1ecf2b49b6bd
```

Se não houver PDF ou o hash divergir, STOP desta task e pedir a fonte correta.

- [ ] **Step 2: Criar primeiro o dataset canônico no repositório API/PWA**

Transcrever os eventos do PDF para o JSON normalizado.

Não transcrever fases da Lua.

- [ ] **Step 3: Copiar o arquivo byte a byte para o pacote Desktop**

Não manter dois processos manuais independentes de transcrição.

- [ ] **Step 4: Escrever testes de integridade**

Nos dois repositórios, provar:
- `schema_version == 1`;
- `year == 2026`;
- 365 datas;
- datas ISO únicas;
- cada lista contém 3 ou 4 eventos;
- horários `HH:MM` estritamente crescentes no mesmo dia;
- `height_m` é número;
- metadados DHN/Carta 711/UTC−03 corretos.

Amostras obrigatórias:

```text
2026-01-01
02:38 2.62
08:36 0.48
14:57 2.89
21:19 0.16

2026-10-04
04:49 0.77
11:12 2.12
17:06 0.99
23:36 2.37

2026-10-05
06:14 0.70
12:31 2.22
18:31 0.87

2026-12-24
23:14 -0.06

2026-12-31
04:25 0.77
10:46 2.29
16:51 0.86
23:16 2.22
```

- [ ] **Step 5: Provar paridade cross-repo**

Run:

```bash
sha256sum   /home/ciro/dev/prog/alertamaritimoAPI/frontend/src/data/tides/pecem-2026.json   /home/ciro/dev/prog/alertamaritimo/src/alertam/data/tides/pecem-2026.json
```

Expected: hashes iguais.

- [ ] **Step 6: Run focused tests**

Desktop:

```bash
cd /home/ciro/dev/prog/alertamaritimo
uv run pytest tests/unit/test_tide_dataset.py -q
```

PWA:

```bash
cd /home/ciro/dev/prog/alertamaritimoAPI/frontend
npm test -- --run src/features/tides/tideDataset.test.ts
```

Expected: PASS.

---

### Task 2: Implementar domínio temporal e UX de Maré/Info no Desktop

**Files:**
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/tide_table.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/infrastructure/tide_table_resource.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/tide_window.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/widget_tooltip.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/main_window.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/bootstrap.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/alertam.spec`
- Create: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_tide_table.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_ship_tracking_ui_logic.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_pyinstaller_spec.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/tests/integration/test_tide_ui.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/tests/integration/test_ui_real.py`

**Interfaces:**
- Produce: `TideEvent(time: str, height_m: float)`.
- Produce: `TideDay(date: date, events: tuple[TideEvent, ...], available: bool)`.
- Produce: `TideView(today: TideDay, tomorrow: TideDay, next_event: tuple[date, TideEvent] | None)`.
- Produce: `select_tide_view(table, now: datetime) -> TideView`.
- Produce: `load_bundled_tide_table() -> TideTable`.
- Produce: `desktop_info_text(device_id: str, version: str) -> str`.
- `TideWindow.show(now: datetime | None = None)` reusa um único `Toplevel`.

- [ ] **Step 1: RED — seleção temporal pura**

Testar:
- hoje/amanhã em UTC−03;
- boundary próximo de meia-noite;
- próximo evento de hoje;
- depois do último evento => primeiro de amanhã;
- 31/12 => amanhã indisponível;
- dia com 3 eventos permanece com 3;
- altura negativa preservada.

- [ ] **Step 2: GREEN — implementar `tide_table.py` e loader**

Usar offset fixo `timezone(timedelta(hours=-3))`.

O loader valida schema/metadados e falha claramente se recurso empacotado estiver ausente/corrompido.

- [ ] **Step 3: RED — identidade discreta**

Atualizar teste antigo de `desktop_identifier_text` para o novo contrato:
- nenhuma label permanente de ID;
- `desktop_info_text("pecem-55ee08ee", "4.3.0")` contém produto, versão, ID e autoria;
- segredo nunca entra na função/interface.

- [ ] **Step 4: GREEN — adicionar `WidgetTooltip` e controles**

Na linha discreta existente, manter à esquerda:
- Guia;
- Conectar Celular;
- Acompanhados.

À direita, antes de `Modo compacto`:
- `🌊 Maré`;
- `ⓘ`.

Remover `desktop_id_label`.

O `ⓘ` usa hover/foco, não uma label permanente.

- [ ] **Step 5: RED — janela de maré**

Teste Tk/Xephyr:
- botão existe e fica na mesma linha discreta;
- show cria um único `Toplevel`;
- segundo show reutiliza/traz à frente;
- Hoje/Amanhã têm número exato de linhas;
- próxima maré é identificável;
- fonte DHN aparece;
- `Esc` fecha/oculta conforme padrão das janelas existentes.

- [ ] **Step 6: GREEN — implementar `TideWindow` e wiring no bootstrap**

Não fazer I/O de rede.

Se o dataset não carregar, o Desktop continua iniciando e a janela mostra indisponibilidade; não derrubar o monitor operacional.

- [ ] **Step 7: Garantir empacotamento PyInstaller**

Adicionar o JSON a `datas` no `alertam.spec`.

Teste deve provar que o spec inclui o recurso no caminho esperado.

- [ ] **Step 8: Gate Desktop**

Run:

```bash
cd /home/ciro/dev/prog/alertamaritimo
make check
DISPLAY=:0 XAUTHORITY=<auth atual> make test-ui XEPHYR_N=27
```

Expected: PASS no harness oficial.

---

### Task 3: Implementar Hoje+Amanhã na página Tempo do PWA

**Files:**
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/tides/tideTable.ts`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/tides/tideTable.test.ts`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/features/tides/TideTableCard.tsx`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/pages/WeatherPage.tsx`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/pages/pages.test.tsx`
- Modify: `/home/ciro/dev/prog/alertamaritimoAPI/frontend/src/styles/app.css`

**Interfaces:**
- Produce: `selectTideView(now: Date): TideView` com semântica equivalente ao Desktop.
- Produce: `TideTableCard({ now? }: { now?: Date })`.
- Consume: JSON estático da Task 1.

- [ ] **Step 1: RED — helper temporal TypeScript**

Testar os mesmos boundaries do Desktop, inclusive timezone do browser diferente do Pecém.

Expected: seleção continua baseada em UTC−03.

- [ ] **Step 2: GREEN — implementar helper sem rede**

Nenhuma chamada a fetch/API.

- [ ] **Step 3: RED — card da WeatherPage**

Testar:
- heading `Tábua de maré · DHN`;
- Hoje e Amanhã;
- 04/10 com quatro linhas;
- 05/10 com três linhas;
- `Próxima`;
- fonte DHN/Carta 711/UTC−03;
- 01/01/2027 indisponível no bloco Amanhã de 31/12;
- blocos WebPilot/Open-Meteo continuam presentes e separados.

- [ ] **Step 4: GREEN — renderizar `TideTableCard` após Condições marítimas**

Não adicionar item ao `BottomNav` ou Drawer.

Não usar badges fresh/stale.

- [ ] **Step 5: Gate frontend**

Run:

```bash
cd /home/ciro/dev/prog/alertamaritimoAPI/frontend
npm test -- --run src/features/tides/tideTable.test.ts src/pages/pages.test.tsx
npm test -- --run
npm run build
```

Expected: PASS.

---

### Task 4: Gate cross-repo e documentação operacional

**Files:**
- Modify only if needed: `/home/ciro/dev/prog/alertamaritimo/README.md`
- Modify only if needed: `/home/ciro/dev/prog/alertamaritimoAPI/specs/029-tabua-mare-dhn-desktop-pwa.md`
- Update execution evidence in handoff/ledger during implementation.

**Interfaces:**
- Consume: outputs Tasks 1–3.
- Produce: revisão pronta, sem dependência de backend.

- [ ] **Step 1: Repetir paridade do dataset**

Hashes devem ser iguais.

- [ ] **Step 2: Guard negativo de escopo API**

Run:

```bash
cd /home/ciro/dev/prog/alertamaritimoAPI
git diff --name-only <BASE>..HEAD
```

Nenhum arquivo sob:
- `api/app/`;
- `api/supabase/`;
- contratos `frontend/src/api/contract.ts`.

- [ ] **Step 3: Gates completos finais**

Desktop:
- `make check`;
- `make test-ui XEPHYR_N=27`.

API/PWA:
- backend não precisa de alteração; se branch tocar somente frontend/docs, rodar ao menos frontend full/build;
- se qualquer arquivo backend for alterado por necessidade inesperada, registrar ruling e rodar `make test`.

- [ ] **Step 4: Revisão independente**

Foco:
- exatidão da fonte;
- timezone;
- 31/12;
- PyInstaller;
- ausência de segredo no `ⓘ`;
- separação DHN × Open-Meteo;
- ausência de mudança de contrato/backend.

- [ ] **Step 5: STOP antes de commit/push/deploy se não houver autorização explícita**

Não usar a SPEC 029 como autorização para iniciar Plan 4/Shadow.

## Self-review do plano — 2026-10-04

- Cobertura da SPEC: dataset, Desktop, PWA, fonte, timezone, next event, ano ausente, build e segurança cobertos.
- Interfaces: Desktop e PWA dependem somente do JSON da Task 1; nenhuma tarefa depende de API runtime.
- Proporção: quatro tasks; nenhum subsistema novo de backend.
- Plano 4 da SPEC 025: permanece válido e independente; não precisa de alteração funcional.
- Risco principal: transcrição anual; mitigado por amostras fixas, 365 dias, ordenação, faixa 3–4 eventos e hash cross-repo.
