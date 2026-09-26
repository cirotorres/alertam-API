# Frontend Mobile PWA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o placeholder de `frontend/` por um PWA React/TypeScript mobile-first que consome o snapshot autenticado do AlertaM, pareia por QR, faz polling seguro de 30 s e reproduz mapa/listas/ficha de navio da SPEC 020.

**Architecture:** O frontend será uma SPA Vite same-origin com a FastAPI. O pareamento fica isolado em `features/pairing`; leitura/validação e polling em `features/snapshot`; projeções operacionais em funções puras; mapa e ficha não conhecem transporte. O service worker precacheia somente shell/assets e nunca respostas autenticadas da API.

**Tech Stack:** React, TypeScript, Vite, React Router, Zod, vite-plugin-pwa, Vitest, React Testing Library, Playwright, CSS responsivo próprio.

**Spec:** `specs/020-frontend-mobile-pwa.md`

## Global Constraints

- Frontend mobile-first, responsivo e somente leitura.
- Frontend e API same-origin; chamadas usam somente `/api/v1/*`.
- Pareamento: `/#/pair/{device_id}?token={VIEW_SECRET}`; remover o token da barra de endereço imediatamente.
- Persistência local versionada em `alertam.mobile.pairing.v1`.
- Nunca expor `DEVICE_SECRET`, Supabase keys ou segredos administrativos ao frontend.
- Polling: GET imediato, 30 s enquanto visible, pausa em background e GET imediato ao retornar.
- Apenas um GET em voo; requests obsoletos são abortados.
- `meta.collector_online` é a fonte de verdade para ativo/stale.
- Service worker nunca cacheia `/api/v1/*` nem Authorization.
- Mapa usa `piers.png` e coordenadas base 500×500 da SPEC 020.
- Prioridade por berço: `DESATRACANDO > ATRACANDO > ATRACADO`.
- Drawer e bottom sheet são mutuamente exclusivos.
- Alertas é feed curto; Web Push não entra nesta implementação.
- Não consultar Wikidata/Wikimedia nem inventar foto de navio.
- TDD por task; suíte/revisão antes do próximo commit.

## Review Focus

- **Fragmento malformado/token inválido:** não persistir credencial parcial nem substituir pareamento anterior antes de validar — Task 3/9.
- **Polling duplicado por rerender/Visibility API:** manter um único timer/request por sessão — Task 5.
- **401 após rotação no Desktop:** limpar pareamento local, parar polling e pedir novo QR — Task 4/5.
- **Mapa em telas estreitas/largas:** manter pins alinhados ao `piers.png` — Task 7.
- **PWA offline:** abrir shell sem servir snapshot autenticado cacheado — Task 10.

---

## File Structure

```text
frontend/
├── public/
│   ├── assets/
│   └── icons/
├── src/
│   ├── api/
│   ├── app/
│   ├── components/
│   ├── features/
│   │   ├── pairing/
│   │   ├── snapshot/
│   │   ├── vessels/
│   │   ├── map/
│   │   └── install/
│   ├── pages/
│   ├── styles/
│   ├── test/
│   └── main.tsx
├── e2e/
├── index.html
├── package.json
├── playwright.config.ts
├── tsconfig.json
└── vite.config.ts
```

### Task 1: Scaffold React/Vite, testes e assets

**Files:**
- Replace: `frontend/index.html`
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`, `frontend/src/app/App.tsx`
- Create: `frontend/src/styles/tokens.css`, `frontend/src/styles/app.css`, `frontend/src/test/setup.ts`
- Copy Desktop assets to `frontend/public/assets/`
- Modify: `frontend/Dockerfile`

**Interfaces:**
- Produces: app React inicial renderizável por `npm run dev`, `npm test`, `npm run build`.

- [ ] **Step 1: Escrever RED `renders_alertam_shell_title`** em `src/app/App.test.tsx`, exigindo `Alerta de Movimentações Marítimas`.
- [ ] **Step 2: Rodar** `cd frontend && npm test -- --run src/app/App.test.tsx`; expected FAIL.
- [ ] **Step 3: Criar scaffold** com React/Vite/TypeScript, React Router, Zod, Vitest/RTL, Playwright e vite-plugin-pwa.
- [ ] **Step 4: Copiar** `piers.png`, `navio.png`, `navio_green.png`, `navio_red.png`, `navio_gray.png` do Desktop.
- [ ] **Step 5: Atualizar Dockerfile** com target dev Vite e target prod estático/Nginx.
- [ ] **Step 6: Rodar GREEN**: `npm test -- --run src/app/App.test.tsx && npm run build`.
- [ ] **Step 7: Commit**: `git commit -m "feat: iniciar frontend mobile React"`.

### Task 2: Contrato TypeScript runtime-safe

**Files:**
- Create: `frontend/src/api/contract.ts`, `frontend/src/api/contract.test.ts`
- Copy: `api/tests/fixtures/mobile_snapshot_v1.json` -> `frontend/src/test/fixtures/mobile_snapshot_v1.json`

**Interfaces:**
- Produces: `SnapshotReadResponse`, `MobileSnapshotV1`, `VesselV1`, `ManeuverV1`.
- Produces: `parseSnapshotReadResponse(input: unknown): SnapshotReadResponse`.

- [ ] **Step 1: RED** `parses_real_mobile_snapshot_v1` com fixture real.
- [ ] **Step 2: RED** `rejects_unknown_schema_version` alterando para versão 2.
- [ ] **Step 3: Rodar RED**: `npm test -- --run src/api/contract.test.ts`.
- [ ] **Step 4: Implementar schemas Zod** equivalentes ao contrato Pydantic, incluindo blocos vazios weather/marine.
- [ ] **Step 5: Rodar GREEN** no mesmo arquivo.
- [ ] **Step 6: Commit**: `git commit -m "feat: validar contrato do snapshot no frontend"`.

### Task 3: Pareamento por fragmento e storage

**Files:**
- Create: `frontend/src/features/pairing/pairing.ts`
- Create: `frontend/src/features/pairing/pairingStorage.ts`
- Test: `pairing.test.ts`, `pairingStorage.test.ts`

**Interfaces:**
- Produces: `type Pairing = { deviceId: string; viewSecret: string; pairedAt: string }`.
- Produces: `parsePairingFragment(hash: string)`, `clearPairingFragment(history: History)`.
- Produces: `loadPairing()`, `savePairing(pairing)`, `clearPairing()`.
- Storage key: `alertam.mobile.pairing.v1`.

- [ ] **Step 1: RED válido** para `#/pair/pecem-01?token=<43+ base64url>`.
- [ ] **Step 2: RED inválidos**: token ausente/curto, device vazio e percent-encoding inválido retornam null sem persistência.
- [ ] **Step 3: RED URL**: `replaceState` remove hash/token imediatamente.
- [ ] **Step 4: RED storage**: round-trip, JSON corrompido ignorado/removido, clear remove a chave.
- [ ] **Step 5: Implementar** parser/storage mínimo.
- [ ] **Step 6: Rodar GREEN**: `npm test -- --run src/features/pairing`.
- [ ] **Step 7: Commit**: `git commit -m "feat: implementar pareamento mobile seguro"`.

### Task 4: API client autenticado

**Files:**
- Create: `frontend/src/api/snapshotClient.ts`
- Test: `frontend/src/api/snapshotClient.test.ts`

**Interfaces:**
- Consumes: Pairing + parser da Task 2.
- Produces: `getSnapshot(pairing: Pairing, signal?: AbortSignal): Promise<SnapshotReadResponse>`.
- Produces: `AccessRevokedError`, `SnapshotUnavailableError`, `TemporaryApiError`, `UnsupportedSnapshotError`.

- [ ] **Step 1: RED URL/header**: URL relativa, Bearer, `cache:"no-store"`.
- [ ] **Step 2: RED semântica**: 401->revoked; 404->unavailable; 5xx/rede->temporary.
- [ ] **Step 3: RED segredo**: token não aparece em Error.message/console.
- [ ] **Step 4: Implementar** fetch same-origin com encodeURIComponent(deviceId) e Zod.
- [ ] **Step 5: Rodar GREEN**: `npm test -- --run src/api/snapshotClient.test.ts`.
- [ ] **Step 6: Commit**: `git commit -m "feat: adicionar cliente autenticado de snapshot"`.

### Task 5: Polling visível e sessão

**Files:**
- Create: `frontend/src/features/snapshot/useSnapshotPolling.ts`
- Create: `frontend/src/features/snapshot/SnapshotProvider.tsx`
- Test: arquivos homônimos `.test.tsx`

**Interfaces:**
- Produces `SnapshotState = { status: "loading"|"online"|"stale"|"waiting"|"offline"|"revoked"|"unsupported"; data: SnapshotReadResponse|null; refresh(): void }`.

- [ ] **Step 1: RED** GET imediato + segundo GET em 30.000 ms.
- [ ] **Step 2: RED Visibility API**: hidden pausa; visible dispara GET imediato.
- [ ] **Step 3: RED single-flight**: ticks concorrentes não iniciam segundo request; cleanup aborta.
- [ ] **Step 4: RED 401**: limpa pairing e para timer.
- [ ] **Step 5: RED stale/offline**: mantém último snapshot em memória.
- [ ] **Step 6: Implementar** hook/provider com timer único e cleanup determinístico.
- [ ] **Step 7: Rodar GREEN**: `npm test -- --run src/features/snapshot`.
- [ ] **Step 8: Commit**: `git commit -m "feat: implementar polling do snapshot mobile"`.

### Task 6: Projeções operacionais puras

**Files:**
- Create: `frontend/src/features/vessels/projections.ts`
- Test: `frontend/src/features/vessels/projections.test.ts`

**Interfaces:**
- Produces `confirmedManeuvers`, `arrivalForecast`, `departureForecast`, `anchoredVessels`, `recentAlerts`, `maneuverHistory`, `vesselByBerth`.

- [ ] **Step 1: RED quatro tabs** conforme regras exatas da SPEC 020.
- [ ] **Step 2: RED deduplicação/prioridade**: primeiro por nome; DESATRACANDO > ATRACANDO > ATRACADO.
- [ ] **Step 3: RED Alertas x Histórico**: alertas máximo 10; histórico active+completed sem limite extra.
- [ ] **Step 4: Implementar funções puras**, sem React/fetch/storage.
- [ ] **Step 5: Rodar GREEN**: `npm test -- --run src/features/vessels/projections.test.ts`.
- [ ] **Step 6: Commit**: `git commit -m "feat: adicionar projeções operacionais mobile"`.


### Task 7: Mapa responsivo e ficha do navio

**Files:**
- Create: `frontend/src/features/map/berthMap.ts`
- Test: `frontend/src/features/map/berthMap.test.ts`
- Create: `frontend/src/features/map/PortMap.tsx`
- Test: `frontend/src/features/map/PortMap.test.tsx`
- Create: `frontend/src/features/vessels/VesselSheet.tsx`
- Test: `frontend/src/features/vessels/VesselSheet.test.tsx`

**Interfaces:**
- Produces: `BERTH_POSITIONS: Record<number,{xPct:number;yPct:number}>`.
- Produces: `selectMapVessels(snapshot): MapVessel[]`.
- `PortMap` recebe `snapshot` e `onSelectVessel(vessel)`.
- `VesselSheet` recebe `vessel`, `open`, `onClose`.

- [ ] **Step 1: RED coordenadas**: berço 1 = 35%/70%; berço 10 = 22%/10%.
- [ ] **Step 2: RED prioridade/sprite**: DES->red, ATR->green, atracado->normal.
- [ ] **Step 3: RED responsivo**: pins usam percentuais relativos ao mapa, não pixels da viewport.
- [ ] **Step 4: RED VesselSheet**: renderiza campos reais e nunca fotografia genérica.
- [ ] **Step 5: Implementar** mapa/sheet; pulso CSS respeita `prefers-reduced-motion`.
- [ ] **Step 6: Rodar GREEN**: `npm test -- --run src/features/map src/features/vessels/VesselSheet.test.tsx`.
- [ ] **Step 7: Commit**: `git commit -m "feat: criar mapa responsivo e ficha do navio"`.

### Task 8: Shell, header, drawer, footer e páginas

**Files:**
- Create: `frontend/src/app/AppShell.tsx`, `frontend/src/app/router.tsx`
- Create: `frontend/src/components/Header.tsx`, `Drawer.tsx`, `BottomNav.tsx`, `StatusCards.tsx`
- Create: `frontend/src/pages/MapPage.tsx`, `AlertsPage.tsx`, `HistoryPage.tsx`, `ConfigPage.tsx`, `AboutPage.tsx`
- Create tests próximos aos componentes/páginas.
- Modify: `frontend/src/styles/app.css`

**Interfaces:**
- Consumes SnapshotProvider, projeções, PortMap, VesselSheet.
- Produces rotas `/`, `/alertas`, `/historico`, `/config`, `/sobre`.
- Produces estado exclusivo `drawerOpen` / `selectedVessel`.

- [ ] **Step 1: RED shell/header**: hambúrguer, título, sessão e última leitura real.
- [ ] **Step 2: RED drawer**: Mapa, Alertas, Histórico, Config., Instalar aplicativo, Sobre; abrir drawer fecha sheet.
- [ ] **Step 3: RED bottom nav**: quatro itens exatos e aba preservada entre polls.
- [ ] **Step 4: RED páginas**: Alertas usa feed curto; Histórico timeline; Config mostra device_id e esquecer aparelho; Sobre não expõe infra.
- [ ] **Step 5: RED estados globais**: online/stale/offline/waiting/revoked/unsupported com texto + cor.
- [ ] **Step 6: RED acessibilidade**: hambúrguer/sprites/botões têm nomes acessíveis; Esc fecha drawer/sheet; foco volta ao acionador; status não depende só de cor.
- [ ] **Step 7: Implementar CSS responsivo**: 320–480 px alvo primário, tablet expande, desktop centraliza sem dashboard paralelo, safe-area no footer; Sobre inclui atribuição Open-Meteo se weather/marine forem exibidos.
- [ ] **Step 8: Rodar GREEN**: `npm test -- --run src/app src/components src/pages`.
- [ ] **Step 9: Commit**: `git commit -m "feat: montar interface mobile do AlertaM"`.

### Task 9: PairingGate e fluxo QR -> sessão

**Files:**
- Create: `frontend/src/features/pairing/PairingGate.tsx`
- Test: `frontend/src/features/pairing/PairingGate.test.tsx`
- Modify: `frontend/src/app/App.tsx`

**Interfaces:**
- Consumes parser/storage da Task 3 e client da Task 4.
- Produces app autenticada somente após pareamento válido.
- Novo QR só substitui pairing anterior depois de validado.

- [ ] **Step 1: RED sem pairing**: orientar a abrir Conectar Celular no Desktop e escanear QR.
- [ ] **Step 2: RED QR 200**: fragmento lido e removido antes do fetch; novo pairing persiste após sucesso.
- [ ] **Step 3: RED QR 404**: pairing é válido, persiste e entra em waiting.
- [ ] **Step 4: RED QR 401/rede**: 401 não substitui pairing anterior; falha temporária oferece retry mantendo candidato só em memória.
- [ ] **Step 5: Implementar gate** sem renderizar token no DOM.
- [ ] **Step 6: Rodar GREEN**: `npm test -- --run src/features/pairing`.
- [ ] **Step 7: Commit**: `git commit -m "feat: integrar fluxo de QR ao frontend"`.

### Task 10: PWA instalável e shell offline

**Files:**
- Modify: `frontend/vite.config.ts`, `frontend/index.html`
- Create: `frontend/src/features/install/usePwaInstall.ts`
- Test: `frontend/src/features/install/usePwaInstall.test.ts`
- Create: `frontend/src/features/install/InstallHelp.tsx`
- Create: `frontend/public/icons/pwa-192.png`, `pwa-512.png`, `apple-touch-icon.png`

**Interfaces:**
- Produces: `usePwaInstall(): { state; install(): Promise<void>; isIos: boolean }`.
- Drawer consome o hook.
- vite-plugin-pwa gera manifest/service worker.

- [ ] **Step 1: RED install states**: standalone, beforeinstallprompt, iOS sem prompt, browser sem suporte.
- [ ] **Step 2: RED SW config**: `/api/v1/*` é `NetworkOnly`, sem cache autenticado.
- [ ] **Step 3: Implementar manifest/SW**: name, short_name AlertaM, display standalone, start_url `/`, ícones 192/512/apple.
- [ ] **Step 4: Implementar InstallHelp**: Chromium chama prompt por gesto; iOS mostra `Compartilhar → Adicionar à Tela de Início`.
- [ ] **Step 5: Rodar GREEN + build**: `npm test -- --run src/features/install && npm run build`; inspecionar manifest/SW.
- [ ] **Step 6: Commit**: `git commit -m "feat: tornar frontend instalável como PWA"`.

### Task 11: Docker/Compose/Vercel do frontend real

**Files:**
- Modify: `frontend/Dockerfile`, `frontend/nginx.conf`
- Modify: `docker-compose.dev.yml`, `docker-compose.prod.yml`, `Makefile`, `vercel.json`
- Modify: `INFRA_DOCKER.md`, `api/DEPLOY_VERCEL.md`
- Create: teste/config check apropriado para `vercel.json`.

**Interfaces:**
- Produces `make dev-up` com Vite real.
- Produces Vercel service frontend + service api; API rewrite tem precedência.
- Produces SPA fallback.

- [ ] **Step 1: RED Vercel**: parsear `vercel.json`; exigir `services.api.root="api/"`, frontend root `frontend/` e API rewrite antes do catch-all.
- [ ] **Step 2: Atualizar Vercel Services** mantendo `/api/v1/:path*` prioritário.
- [ ] **Step 3: Atualizar Docker dev/prod**: Vite HMR no dev, Nginx serve `dist/` no prod, proxy `/api/`.
- [ ] **Step 4: Smoke Docker**: `make dev-up`; GET `:5173/` e `:5173/api/v1/health`; `make dev-down`.
- [ ] **Step 5: Validar configs**: `make dev-config && make prod-config`.
- [ ] **Step 6: Commit**: `git commit -m "feat: integrar frontend PWA à infraestrutura"`.

### Task 12: Playwright responsivo e fluxo integrado

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/mobile.spec.ts`
- Create: `frontend/e2e/fixtures.ts`
- Modify: `frontend/package.json`

**Interfaces:**
- Usa API mock/interceptada; nunca produção.
- Prova comportamento integrado da SPEC 020.

- [ ] **Step 1: Configurar viewports** 320×568, 390×844, 768×1024 e 1280×900.
- [ ] **Step 2: E2E pairing**: abrir hash, mock GET 200, confirmar token fora da URL e dados renderizados.
- [ ] **Step 3: E2E navegação**: 4 tabs, navio/sheet, drawer fecha sheet, Alertas/Histórico/Config/Sobre.
- [ ] **Step 4: E2E estados**: 404 waiting, stale, 401 novo QR, offline temporário mantém último snapshot.
- [ ] **Step 5: E2E Visibility API**: sem polling hidden, GET imediato ao retornar visible.
- [ ] **Step 6: E2E esquecer aparelho**: confirmação remove storage e volta PairingGate.
- [ ] **Step 7: E2E shell offline**: após carregar assets/SW, colocar contexto offline e recarregar `/`; shell abre, mas nenhum snapshot autenticado é servido de cache.
- [ ] **Step 8: Rodar GREEN**: `npm run e2e`.
- [ ] **Step 9: Commit**: `git commit -m "test: validar frontend mobile ponta a ponta"`.

### Task 13: Gate final, documentação e deploy real

**Files:**
- Modify: `specs/020-frontend-mobile-pwa.md`, `specs/README.md`
- Modify docs operacionais conforme evidências reais.

**Interfaces:**
- Consumes todo o frontend final.
- Produces evidência de conclusão e checklist de deploy.

- [ ] **Step 1: Frontend completo**: `cd frontend && npm test -- --run && npm run build && npm run e2e`.
- [ ] **Step 2: API completa**: na raiz, `make test-all`; expected suíte API verde.
- [ ] **Step 3: Smoke Docker + diff**: dev-up, health via frontend, dev-down, `git diff --check`.
- [ ] **Step 4: Auto-revisão** contra critérios da SPEC 020, com foco em token, SW, 401, polling, responsividade, drawer/sheet, projections e secrets no bundle.
- [ ] **Step 5: Deploy Vercel** e validar `/`, `/api/v1/health`, reload `/alertas`, manifest e SW.
- [ ] **Step 6: Smoke real Desktop -> QR -> PWA -> GET**: token some da URL, snapshot real aparece, rotação no Desktop provoca 401 e novo QR.
- [ ] **Step 7: Validar instalação PWA manual** em Chromium móvel e, se disponível, iOS/Add to Home Screen.
- [ ] **Step 8: Marcar SPEC 020 Concluído** somente após smoke real/manual.
- [ ] **Step 9: Commit documental**: `git commit -m "docs: concluir frontend mobile PWA"`.
