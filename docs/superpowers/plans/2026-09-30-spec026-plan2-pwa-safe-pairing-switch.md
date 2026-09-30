# SPEC 026 — Plano 2: PWA, identidade do aparelho e troca segura de QR

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a PWA identificar a própria instalação, exibir código/plataforma, tratar revogação e trocar de Desktop com confirmação sem destruir o pareamento atual antes do sucesso.

**Architecture:** `PairingGate` continua sendo a autoridade do estado de pareamento, mas passa a separar claramente estado ativo de candidato. Clientes de sessão/validação/switch ficam fora do componente; metadados da instalação têm storage próprio; Push reaproveita a subscription existente após switch sem migrar Ship Tracking.

**Tech Stack:** React, TypeScript, Vite, Vitest, Testing Library, Service Worker/Web Push.

**Spec:** `specs/026-mobile-installation-management-safe-pairing-switch.md`

## Global Constraints

- Plano 1 da SPEC 026 deve estar concluído e a API correspondente disponível no ambiente de teste.
- QR candidato nunca substitui pairing ativo antes de validação + confirmação + sucesso/reconciliação.
- Desktop diferente exige confirmação explícita.
- Mesmo `device_id` não mostra diálogo de troca.
- Instalação revogada não reutiliza o UUID antigo.
- `display_code` é apenas apresentação; UUID não aparece na Config.
- Acompanhamentos não migram entre Desktops.
- Preferência de Push pode ser reaplicada; falha de Push não desfaz switch.
- Revogação deve levar à tela explícita “Acesso revogado”.
- Fragmento do QR continua sendo limpo da URL antes de rede.

## Review Focus

- Resposta perdida após switch já confirmado no servidor: retry com mesmo `switch_id` deve convergir para B.
- QR inválido ou rede indisponível durante validação: pairing A e installation A permanecem intocados.
- Mesmo Desktop com instalação ainda ativa: não criar UUID/código novo desnecessariamente.
- Mesmo Desktop após revogação: gerar novo UUID em vez de ressuscitar o anterior.
- Browser sem detecção confiável de plataforma: enviar `other` e continuar funcional.

---

### Task 1: Plataforma e metadados persistentes da instalação

**Files:**
- Create: `frontend/src/features/pairing/devicePlatform.ts`
- Create: `frontend/src/features/pairing/devicePlatform.test.ts`
- Create: `frontend/src/features/pairing/installationMetadata.ts`
- Create: `frontend/src/features/pairing/installationMetadata.test.ts`
- Modify: `frontend/src/features/push/installationId.ts`
- Modify: `frontend/src/features/push/installationId.test.ts`

**Interfaces:**
- Produces: `detectDevicePlatform(): "ios" | "android" | "other"`.
- Produces: `InstallationMetadata { installationId, displayCode, platform }` com load/save/clear.
- Produces: `createFreshInstallationId(randomUUID?) -> string` sem persistir até promoção explícita.

- [ ] **Step 1: escrever RED de plataforma**

Cobrir iPhone/iPad, Android, iPadOS desktop-like com touch e fallback `other`.

- [ ] **Step 2: implementar `detectDevicePlatform`**

Não coletar modelo, serial ou fingerprint. O helper retorna apenas as três categorias aprovadas.

- [ ] **Step 3: escrever RED do storage de metadata**

Persistir/restaurar `installationId + displayCode + platform`; payload inválido é descartado.

- [ ] **Step 4: implementar metadata storage e fresh UUID**

Manter `alertam.mobile.installation.v1` como UUID atual por compatibilidade; metadata usa uma chave própria versionada. `createFreshInstallationId` não sobrescreve a atual antes de sucesso.

- [ ] **Step 5: rodar testes focados**

Run: `cd frontend && npm test -- --run src/features/pairing/devicePlatform.test.ts src/features/pairing/installationMetadata.test.ts src/features/push/installationId.test.ts`  
Expected: PASS.

- [ ] **Step 6: commit**

```bash
git add frontend/src/features/pairing frontend/src/features/push/installationId.ts frontend/src/features/push/installationId.test.ts
git commit -m "feat: identifica instalação mobile na pwa"
```

### Task 2: Cliente de sessão, validação, heartbeat e switch

**Files:**
- Modify: `frontend/src/features/pairing/mobileSessionClient.ts`
- Modify: `frontend/src/features/pairing/mobileSessionClient.test.ts`

**Interfaces:**
- Produces: `MobileSessionInfo { deviceId, installationId, displayCode, platform }`.
- Produces: `createMobileSession(pairing, options?: { installationId?: string; platform?: DevicePlatform }) -> Promise<MobileSessionInfo>`; UUID gerado internamente só é persistido após resposta válida.
- Produces: `recoverMobileSession() -> Promise<{ pairing: Pairing; session: MobileSessionInfo } | null>`.
- Produces: `validatePairingCandidate(pairing) -> Promise<{ deviceId: string }>`.
- Produces: `switchMobileSession(candidate, draft) -> Promise<MobileSessionInfo>`.
- Produces: `touchMobileSession(platform) -> Promise<void>`.

- [ ] **Step 1: RED para request/response novos de sessão**

Provar que create envia `platform`, valida os quatro campos da resposta e só persiste UUID/metadata depois de resposta consistente.

- [ ] **Step 2: RED para recovery**

Recovery deve persistir `installation_id`, `display_code`, `platform` retornados pelo servidor e devolver pairing cookie-only.

- [ ] **Step 3: RED para validate side-effect free**

`validatePairingCandidate` usa `POST /api/v1/mobile/pairing/validate`, Bearer do QR, e não altera localStorage.

- [ ] **Step 4: RED para switch**

Request inclui novo UUID, plataforma e `switch_id`; sucesso retorna metadata B; 401 vira `AccessRevokedError`; 5xx/rede vira `TemporaryApiError`.

- [ ] **Step 5: RED para heartbeat**

Heartbeat usa cookie same-origin e nunca cria/regrava pairing. 401 propaga AccessRevoked.

- [ ] **Step 6: implementar clientes**

Manter toda validação de JSON em type guards locais; não aceitar resposta cujo `device_id` ou `installation_id` diverja do request esperado. `clearMobileSession()` limpa somente o cookie remoto em best effort; o PairingGate será o único dono da limpeza de UUID e metadados locais.

- [ ] **Step 7: rodar testes**

Run: `cd frontend && npm test -- --run src/features/pairing/mobileSessionClient.test.ts`  
Expected: PASS.

- [ ] **Step 8: commit**

```bash
git add frontend/src/features/pairing/mobileSessionClient.ts frontend/src/features/pairing/mobileSessionClient.test.ts
git commit -m "feat: adiciona contratos de sessão e troca mobile"
```

### Task 3: Estado candidato e confirmação no PairingGate

**Files:**
- Modify: `frontend/src/features/pairing/PairingGate.tsx`
- Modify: `frontend/src/features/pairing/PairingGate.test.tsx`

**Interfaces:**
- Consumes: clientes da Task 2 e `createFreshInstallationId`.
- Produces: callbacks distintos `resetPairing()` e `handleAccessRevoked()` para os filhos.
- Produces: modo explícito `confirm-switch`, `temporary-switch` e `revoked`.
- `PairingGate` deixa de usar `getSnapshot`/`fetcher` como validador de QR; snapshot volta a ser responsabilidade exclusiva do `SnapshotProvider`. Nos testes, injetar `candidateValidator`, `sessionCreator`, `sessionSwitcher`, `sessionRecoverer` e `sessionClearer`.

- [ ] **Step 1: RED — QR B inválido preserva A**

Com A persistido e hash de B na URL, validator rejeita; UI continua em A e storage permanece exatamente A.

- [ ] **Step 2: RED — B válido pede confirmação**

Validator resolve B; nenhum create/switch ainda foi chamado; tela mostra Atual A, Novo B, botões Cancelar/Trocar.

- [ ] **Step 3: RED — cancelar**

Clique Cancelar descarta candidato, não gera UUID, não chama switch e mantém APP A.

- [ ] **Step 4: RED — confirmar sucesso**

Ao confirmar, criar `newInstallationId` e `switch_id` uma vez, chamar switch e somente após resposta promover pairing B + metadata B.

- [ ] **Step 5: RED — erro temporário/retry**

Primeiro switch falha temporariamente; A continua renderizado/armazenado e draft mantém os mesmos IDs. Retry reutiliza exatamente `newInstallationId + switch_id` e promove B no sucesso.

- [ ] **Step 6: RED — mesmo Desktop**

QR com mesmo `device_id` não mostra confirmação. Se existe pairing ativo e a sessão atual é válida, reutiliza instalação atual. Se validator prova QR válido mas create rejeita UUID revogado, gerar UUID novo e repetir uma única vez. Quando não existe pairing ativo e o usuário escaneia um QR, gerar um UUID candidato novo após a validação; não reutilizar um UUID órfão que tenha sobrado no storage.

- [ ] **Step 7: implementar state machine**

Limpar fragmento imediatamente; validar pelo endpoint dedicado antes de qualquer mutação; candidato fica somente em memória; promotion é o único ponto que grava pairing/installation metadata. Remover o caminho especial de `SnapshotUnavailableError` da validação de QR, pois ausência de snapshot não invalida o acesso.

- [ ] **Step 8: separar revogação de “Esquecer”**

`resetPairing` continua sendo ação manual. `handleAccessRevoked` limpa pairing/UUID/metadata e deixa `mode="revoked"`, exibindo copy da SPEC.

- [ ] **Step 9: rodar PairingGate tests**

Run: `cd frontend && npm test -- --run src/features/pairing/PairingGate.test.tsx`  
Expected: PASS.

- [ ] **Step 10: commit**

```bash
git add frontend/src/features/pairing/PairingGate.tsx frontend/src/features/pairing/PairingGate.test.tsx
git commit -m "feat: confirma troca segura entre alertam"
```

### Task 4: Propagar sessão e identidade pela árvore React

**Files:**
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/app/AppShell.tsx`
- Modify: `frontend/src/app/AppShell.test.tsx`
- Modify: `frontend/src/pages/ConfigPage.tsx`
- Create: `frontend/src/pages/ConfigPage.test.tsx`

**Interfaces:**
- Consumes: `MobileSessionInfo` promovido pelo PairingGate.
- Produces: `ShellOutletContext.installation`.
- Providers recebem `handleAccessRevoked`, enquanto Config “Esquecer” recebe `resetPairing`.

- [ ] **Step 1: RED da árvore de callbacks**

Provar que Snapshot/Event/Tracking/Push usam callback de revogação, não o reset manual genérico.

- [ ] **Step 2: propagar `sessionInfo` e resetar estado por instalação**

Alterar render callback de PairingGate para fornecer pairing, reset manual, sessionReady, accessRevoked e metadata da instalação. A árvore `SnapshotProvider → EventProvider → TrackingProvider → PushProvider → AppRoutes` deve ser remontada com `key={sessionInfo.installationId}` quando a instalação muda; isso elimina estado de A ao promover B e impede migração acidental de tracking/eventos.

- [ ] **Step 3: RED da Config**

Exigir:
`Este aparelho → iPhone/iPad · K7M4Q2`  
`AlertaM conectado → pecem-...`  
e ausência do UUID técnico no texto visível.

- [ ] **Step 4: implementar Config**

Remover o rótulo ambíguo `Dispositivo`; manter versão, sincronização e controles de Push.

- [ ] **Step 5: ajustar “Esquecer este aparelho”**

Config chama `push.disablePush()` em best effort e depois delega a limpeza ao `resetPairing`; `PairingGate` é o único dono da limpeza de pairing + UUID + metadata + cookie/session. Não duplicar `clearPairing()`/`clearInstallationId()` dentro da página.

- [ ] **Step 6: rodar testes**

Run: `cd frontend && npm test -- --run src/app/AppShell.test.tsx src/pages/ConfigPage.test.tsx`  
Expected: PASS.

- [ ] **Step 7: commit**

```bash
git add frontend/src/app frontend/src/pages/ConfigPage.tsx frontend/src/pages/ConfigPage.test.tsx
git commit -m "feat: exibe identidade do aparelho na pwa"
```

### Task 5: Heartbeat de instalação sem acoplar ao Push

**Files:**
- Create: `frontend/src/features/pairing/useMobileSessionHeartbeat.ts`
- Create: `frontend/src/features/pairing/useMobileSessionHeartbeat.test.tsx`
- Modify: `frontend/src/app/AppShell.tsx`

**Interfaces:**
- Consumes: `touchMobileSession`, `sessionReady`, `handleAccessRevoked`.
- Produces: heartbeat imediato quando visível + aproximadamente a cada 5 min enquanto visível.

- [ ] **Step 1: RED com fake timers**

Sessão pronta/aba visível chama heartbeat na entrada e após 5 min; aba oculta não continua disparando.

- [ ] **Step 2: RED de falha temporária**

Erro de rede é ignorado para disponibilidade do app; próximo intervalo tenta novamente.

- [ ] **Step 3: RED de 401**

AccessRevoked chama o callback de revogação uma vez.

- [ ] **Step 4: implementar hook**

Não reutilizar `useForegroundHeartbeat` de Push: aquele hook representa estado de foreground para supressão de Push e tem responsabilidade diferente.

- [ ] **Step 5: integrar em AppShell**

Ativar somente fora do demo e com sessão pronta.

- [ ] **Step 6: rodar testes**

Run: `cd frontend && npm test -- --run src/features/pairing/useMobileSessionHeartbeat.test.tsx src/app/AppShell.test.tsx`  
Expected: PASS.

- [ ] **Step 7: commit**

```bash
git add frontend/src/features/pairing/useMobileSessionHeartbeat.ts frontend/src/features/pairing/useMobileSessionHeartbeat.test.tsx frontend/src/app/AppShell.tsx
git commit -m "feat: atualiza atividade da instalação mobile"
```

### Task 6: Reaplicar Push após troca sem migrar tracking

**Files:**
- Create: `frontend/src/features/push/pushPreferenceStorage.ts`
- Create: `frontend/src/features/push/pushPreferenceStorage.test.ts`
- Modify: `frontend/src/features/push/PushProvider.tsx`
- Modify: `frontend/src/features/push/PushProvider.test.tsx`

**Interfaces:**
- Produces: snapshot local não sensível `{ optedIn, preferences }`.
- `PushProvider` é remontado quando `installationId` muda pela key definida na Task 4; no mount da nova instalação, pode reusar subscription existente e aplicar preferências salvas.

- [ ] **Step 1: RED de persistência das preferências**

Ativar/desativar tipos atualiza storage. “Esquecer aparelho” pode limpar opt-in; switch não limpa.

- [ ] **Step 2: RED de rebind após switch**

Com `optedIn=true`, permissão granted e browser subscription existente, nova instalação sem Push no servidor deve chamar register para o UUID B e reaplicar preferências.

- [ ] **Step 3: RED de falha no rebind**

Falha deixa app em B, Push inactive/error, sem chamar reset/switch rollback.

- [ ] **Step 4: implementar sem unsubscribe na troca**

Backend já desativa A. A PWA só reutiliza a subscription browser existente para B.

- [ ] **Step 5: provar tracking/eventos não migram**

Adicionar teste de integração da árvore de providers provando que a mudança de `installationId` remonta Tracking/Event providers e não conserva estado de A em B.

- [ ] **Step 6: rodar testes Push + App**

Run: `cd frontend && npm test -- --run src/features/push/PushProvider.test.tsx src/app/App.push.test.tsx`  
Expected: PASS.

- [ ] **Step 7: commit**

```bash
git add frontend/src/features/push frontend/src/app/App.push.test.tsx
git commit -m "feat: reaplica push após troca de alertam"
```

### Task 7: Gate PWA, build e handoff

**Files:**
- Create: `docs/superpowers/handoffs/2026-09-30-spec026-plan2-pwa-complete-handoff.md`

**Interfaces:**
- Produces: PWA pronta para o Desktop administrativo do Plano 3.

- [ ] **Step 1: rodar suite frontend completa**

Run: `cd frontend && npm test -- --run`  
Expected: todos os testes verdes.

- [ ] **Step 2: build de produção**

Run: `cd frontend && npm run build`  
Expected: build Vite/PWA concluído.

- [ ] **Step 3: verificar URL/segredos**

Confirmar que VIEW_SECRET é removido do fragmento antes de requests/render e não aparece em mensagens de erro/storage além do pairing já previsto.

- [ ] **Step 4: `git diff --check`**

Expected: sem whitespace errors.

- [ ] **Step 5: criar handoff**

Registrar novos contratos, states do PairingGate, callback de revogação, metadata storage, heartbeat, Push rebind e resultados.

- [ ] **Step 6: commit final**

```bash
git add docs/superpowers/handoffs/2026-09-30-spec026-plan2-pwa-complete-handoff.md
git commit -m "docs: consolida troca segura na pwa"
```
