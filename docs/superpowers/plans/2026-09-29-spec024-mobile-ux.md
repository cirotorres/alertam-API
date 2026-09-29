# SPEC 024 — Mobile UX Refinements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir identificação de acompanhados, footer, scroll de páginas e prioridade de toque das bottom sheets no PWA.

**Architecture:** Tracking continua vindo do TrackingProvider existente. As páginas Alertas/Histórico/Acompanhados recebem um modificador de superfície contínua, enquanto BottomSheetFrame centraliza o bloqueio de interação do fundo. O footer continua com cinco ações e aceita estado sem tab ativa em /acompanhados.

**Tech Stack:** React 19, React Router 7, TypeScript, CSS, Vitest/Testing Library, Playwright, iOS Safari/PWA.

**Spec:** `specs/024-operational-maneuver-timing-ux-refinements.md`

## Global Constraints

- Não adicionar sexta tab ao footer.
- Estrela de tracking é informativa e não altera status operacional.
- Sheet aberta tem prioridade total de toque sobre o fundo.
- Scroll interno e swipe-to-dismiss continuam funcionando.
- Corrigir apenas Alertas, Histórico e Acompanhados; não redefinir todas as páginas `.page-stack`.
- Preservar acessibilidade e deep links atuais.

## Review Focus

- Navio rastreado por fallback de nome também recebe estrela sem duplicar tracking.
- /acompanhados não marca Manobras nem Tempo como `aria-current`.
- Fechar uma sheet restaura o scroll anterior da página.
- Scroll no limite superior/inferior da sheet não encadeia para a página de fundo.
- Duas sheets não devem ficar abertas/interativas simultaneamente.

---
### Task 1: Estrela de acompanhamento nas listas operacionais

**Files:**
- Modify: `frontend/src/pages/MapPage.tsx`
- Modify: `frontend/src/styles/app.css`
- Test: `frontend/src/pages/pages.test.tsx`

**Interfaces:**
- Consumes: `useOptionalTracking()` e `TrackingState.isTracked(target)`.
- Produces: marcador visual `★` junto ao nome, com classe `operational-card__tracking-star`.

- [ ] **Step 1: Escrever teste RED**

Renderizar lista com StaticTrackingProvider; navio acompanhado contém ★ e navio não acompanhado não contém. Repetir com `vessel_imo=null` e tracking `NAME:<nome normalizado>` para provar o fallback por nome. O nome textual permanece intacto.

- [ ] **Step 2: Rodar teste focado e confirmar falha**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/pages/pages.test.tsx`
Expected: FAIL porque MapPage ainda ignora tracking.

- [ ] **Step 3: Implementar marca sem alterar a projeção operacional**

MapPage consulta tracking opcional e passa a identidade do VesselV1 ao `isTracked`. Usar amarelo/âmbar apenas na estrela.

- [ ] **Step 4: Rodar teste e confirmar PASS**

Run: mesmo comando do Step 2.
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat: marca navios acompanhados nas listas mobile"`
### Task 2: Footer persistente em Acompanhados sem seleção falsa

**Files:**
- Modify: `frontend/src/components/BottomNav.tsx`
- Modify: `frontend/src/app/AppShell.tsx`
- Test: `frontend/src/pages/pages.test.tsx`
- Test: `frontend/src/pages/TrackedVesselsPage.test.tsx`

**Interfaces:**
- Produces: `BottomNavProps.active: BottomNavItem | null`.
- AppShell inclui `/acompanhados` em `showBottomNav` e usa `active=null` nessa rota.

- [ ] **Step 1: Escrever teste RED da rota Acompanhados**

Esperar cinco botões do footer visíveis e nenhum com `aria-current="page"`. Clicar em “Tempo” navega para Tempo; clicar em “Manobras confirmadas” volta ao mapa.

- [ ] **Step 2: Rodar testes focados e confirmar falha**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run src/pages/pages.test.tsx src/pages/TrackedVesselsPage.test.tsx`
Expected: FAIL porque o footer não é renderizado.

- [ ] **Step 3: Implementar active nullable e whitelist da rota**

Não criar item “Acompanhados” no BottomNav.

- [ ] **Step 4: Rodar testes e confirmar PASS**

Run: mesmo comando do Step 2.
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "fix: mantém footer na página de acompanhados"`
### Task 3: Superfície contínua de scroll em páginas de histórico

**Files:**
- Modify: `frontend/src/pages/AlertsPage.tsx`
- Modify: `frontend/src/pages/HistoryPage.tsx`
- Modify: `frontend/src/pages/TrackedVesselsPage.tsx`
- Modify: `frontend/src/styles/app.css`
- Test: `frontend/e2e/mobile.spec.ts`

**Interfaces:**
- Produces: modificador comum `page-stack--continuous-scroll` somente nas três páginas.
- Mantém cards internos `.timeline li` e ciclos como unidades visuais.

- [ ] **Step 1: Escrever Playwright RED**

Em viewport mobile, iniciar gesto/scroll na margem entre conteúdo e cards; esperar que `scrollTop` da página aumente em Alertas, Histórico e Acompanhados.

- [ ] **Step 2: Rodar cenário focado e confirmar falha**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npx playwright test e2e/mobile.spec.ts -g "continuous scroll"`
Expected: FAIL no layout atual com card externo.

- [ ] **Step 3: Aplicar modificador e CSS localizado**

Remover o papel de “grande card” dessas três superfícies sem alterar Weather/Config/Mapa; preservar padding útil e espaço do footer.

- [ ] **Step 4: Rodar cenário e confirmar PASS**

Run: mesmo comando do Step 2.
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "fix: amplia superfície de rolagem das páginas mobile"`
### Task 4: Bottom sheet bloqueia fundo e restaura estado

**Files:**
- Modify: `frontend/src/components/BottomSheetFrame.tsx`
- Modify: `frontend/src/styles/app.css`
- Test: `frontend/src/components/BottomSheetFrame.test.tsx`
- Test: `frontend/src/pages/pages.test.tsx`
- Test: `frontend/e2e/mobile.spec.ts`

**Interfaces:**
- Quando `open=true`, adicionar classe documental `has-open-bottom-sheet`.
- Ao fechar ou desmontar, remover a classe sem alterar o scrollTop da página.
- CSS bloqueia toque/scroll em header, mobile-content e bottom-nav, mas preserva interação na sheet/backdrop.
- Sheet usa `overscroll-behavior-y: contain`.

- [ ] **Step 1: Escrever testes RED de lifecycle**

Vitest prova adição/remoção da classe inclusive em unmount. `pages.test.tsx` prova que abrir uma sheet fecha/neutraliza qualquer superfície concorrente, mantendo apenas um diálogo interativo. Playwright prova que gesto no backdrop/conteúdo coberto não altera scroll do fundo nem encadeia no limite da sheet.

- [ ] **Step 2: Rodar testes focados e confirmar falha**

Run Vitest: `npm test -- --run src/components/BottomSheetFrame.test.tsx src/pages/pages.test.tsx`
Run Playwright: `npx playwright test e2e/mobile.spec.ts -g "bottom sheet locks background"`
Expected: FAIL antes do bloqueio.

- [ ] **Step 3: Implementar lock centralizado em BottomSheetFrame**

Não espalhar locks pelas sheets específicas. Preservar drag, scroll interno, foco, aria-modal e backdrop.

- [ ] **Step 4: Rodar testes e confirmar PASS**

Run: mesmos comandos do Step 2.
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "fix: prioriza gestos da bottom sheet no mobile"`
### Task 5: Gates completos do Plano 2

**Files:**
- Test only.

- [ ] **Step 1: Vitest completo**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI/frontend && npm test -- --run`
Expected: PASS.

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: PASS.

- [ ] **Step 3: Playwright completo**

Run: `npm run e2e`
Expected: PASS.

- [ ] **Step 4: Smoke manual iOS/PWA**

Validar: scroll iniciado nas margens, sheet cobrindo o fundo, swipe-to-dismiss, conteúdo da sheet rolável e footer em Acompanhados.

- [ ] **Step 5: Diff check**

Run: `cd /home/ciro/dev/prog/alertamaritimoAPI && git diff --check`
Expected: sem saída.
