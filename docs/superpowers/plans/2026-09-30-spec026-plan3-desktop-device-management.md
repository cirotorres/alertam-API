# SPEC 026 — Plano 3: Desktop e gestão de aparelhos conectados

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao AlertaM Desktop uma gestão clara e assíncrona dos aparelhos conectados, com contador, janela própria Ativos/Revogados, revogação individual e ação global explícita.

**Architecture:** O Desktop ganha um transporte HTTP administrativo autenticado por `DEVICE_SECRET` e um serviço assíncrono separado do atual `MobileAccessService`. A janela **Conectar Celular** continua focada no QR; ela recebe apenas contador/atalho. A lista completa vive em um Toplevel próprio e toda atualização de Tk continua passando pela `ui_queue`.

**Tech Stack:** Python, Tkinter/ttk, urllib, pytest, Xephyr.

**Spec:** `/home/ciro/dev/prog/alertamaritimoAPI/specs/026-mobile-installation-management-safe-pairing-switch.md`

## Global Constraints

- Planos 1 e 2 da SPEC 026 devem estar concluídos antes do smoke integrado deste plano.
- Antes de tocar o Desktop, a árvore `/home/ciro/dev/prog/alertamaritimo` deve estar sem mudanças não relacionadas; o trabalho já existente de som/marcador de acompanhados precisa ser checkpointado separadamente.
- A janela Conectar Celular não lista aparelhos diretamente.
- Ela mostra somente contador + botão **Gerenciar aparelhos**.
- A lista própria possui abas **Ativos** e **Revogados**.
- Revogados exibidos pela API já estão limitados aos últimos 30 dias.
- Revogação individual nunca atualiza UI como sucesso antes da confirmação da API.
- Ação global chama-se **Revogar todos e gerar novo QR**.
- Rede nunca roda na Tk main thread.
- Falha da listagem administrativa não quebra QR/link existentes.

## Review Focus

- Janela de gerenciamento aberta durante refresh/revogação: callbacks tardios não podem tocar widget destruído.
- Listagem falha, mas QR permanece ativo: o operador ainda consegue copiar/usar o acesso.
- Revogação individual de item já revogado por outro caminho: UI converge sem erro enganoso.
- Contador desatualizado antes da rotação global: confirmação deve buscar/usar contagem atual antes de rotacionar.
- Muitos revogados/ativos: abas precisam rolar sem aumentar indefinidamente a janela.

---

### Task 1: Modelo e transporte HTTP administrativo

**Files:**
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/mobile_installations.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/infrastructure/mobile_installations_http.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_installations.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_installations_http.py`

**Interfaces:**
- Produces: `MobileInstallationSummary`, `MobileInstallationsSnapshot`.
- Produces: `MobileInstallationsHttpClient.list() -> MobileInstallationsSnapshot`.
- Produces: `MobileInstallationsHttpClient.revoke(installation_id: str) -> None`.

- [ ] **Step 1: escrever RED do parser/modelo**

Testar payload com `active_count`, ativos e revogados; timestamps opcionais/ISO; plataforma desconhecida exibida como `Outro aparelho`; UUID/código inválido gera erro de contrato.

- [ ] **Step 2: implementar dataclasses/helpers**

`MobileInstallationSummary` contém `installation_id`, `display_code`, `platform`, `active`, `created_at`, `last_seen_at`, `revoked_at`.

Adicionar helper puro `installation_label(item) -> str` que produz `iPhone/iPad · K7M4Q2`, `Android · ...` ou `Outro aparelho · ...`.

- [ ] **Step 3: escrever RED de HTTP**

GET deve usar:
`/api/v1/devices/{quoted_device_id}/mobile-installations`  
header `Authorization: Device <DEVICE_SECRET>`  
timeout limitado.

DELETE usa a mesma autenticação e URL com `installation_id` escapado.

- [ ] **Step 4: implementar transporte**

Mapear 401/403 para erro definitivo de credencial e rede/5xx/timeout para erro temporário tipado. Nunca incluir DEVICE_SECRET em repr/log de exceção.

- [ ] **Step 5: rodar testes**

Run: `uv run pytest tests/unit/test_mobile_installations.py tests/unit/test_mobile_installations_http.py -q`  
Expected: PASS.

- [ ] **Step 6: commit**

```bash
git add src/alertam/application/mobile_installations.py src/alertam/infrastructure/mobile_installations_http.py tests/unit/test_mobile_installations.py tests/unit/test_mobile_installations_http.py
git commit -m "feat: adiciona cliente de gestão de aparelhos"
```

### Task 2: Serviço assíncrono e mensagens para UI

**Files:**
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/infrastructure/mobile_installations_service.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/application/messages.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/bootstrap.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_installations_service.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_access_bootstrap.py`

**Interfaces:**
- Produces: `MobileInstallationsService.refresh() -> bool`, `revoke(installation_id) -> bool`, `stop(timeout=...)`.
- Produces UI messages `MOBILE_INSTALLATIONS_READY` e `MOBILE_INSTALLATION_ACTION` via queue.
- Bootstrap expõe callbacks `_refresh_mobile_installations`, `_revoke_mobile_installation`.

- [ ] **Step 1: RED de single-flight**

Enquanto list/revoke está em andamento, segunda operação concorrente retorna `False` e não cria nova thread.

- [ ] **Step 2: RED de resultados**

Refresh bem-sucedido entrega snapshot; falha entrega resultado de erro sanitizado. Revoke bem-sucedido deve fazer refresh subsequente ou devolver snapshot atualizado em uma única sequência controlada.

- [ ] **Step 3: implementar serviço**

Seguir padrão de `MobileAccessService`: worker daemon, callback único, stop com timeout curto, sem Tk.

- [ ] **Step 4: adicionar mensagens de aplicação**

Payloads devem carregar apenas dados/estado; widgets são atualizados exclusivamente por `MainWindow`.

- [ ] **Step 5: bootstrap**

Criar o serviço somente quando `api_base_url + device_id + device_secret` estiverem completos. Reutilizar Settings existentes; não criar nova configuração.

- [ ] **Step 6: testar fechamento**

`Application.close()` chama stop do serviço de gestão sem bloquear shutdown.

- [ ] **Step 7: rodar testes focados**

Run: `uv run pytest tests/unit/test_mobile_installations_service.py tests/unit/test_mobile_access_bootstrap.py -q`  
Expected: PASS.

- [ ] **Step 8: commit**

```bash
git add src/alertam/infrastructure/mobile_installations_service.py src/alertam/application/messages.py src/alertam/bootstrap.py tests/unit
git commit -m "feat: coordena gestão mobile fora da ui"
```

### Task 3: Manter Conectar Celular limpa

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/mobile_access_window.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/main_window.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_access_window.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_access_ui_logic.py`

**Interfaces:**
- `MobileAccessWindow(..., on_manage, on_refresh_installations, active_count_provider)`.
- Produces: `set_active_installation_count(count: int | None)`.
- Produces: botão **Gerenciar aparelhos** sem lista inline.

- [ ] **Step 1: RED de copy/layout lógico**

Provar que o texto antigo **Gerar novo acesso** não é mais usado para ação global; texto novo é **Revogar todos e gerar novo QR**.

- [ ] **Step 2: RED de contador**

`count=2` → `Aparelhos conectados: 2`; zero → `Aparelhos conectados: 0`; `None` → `Aparelhos conectados: indisponível`.

- [ ] **Step 3: implementar contador + botão**

Ao abrir Conectar Celular, disparar ensure do QR e refresh administrativo independentes. Falha do segundo não toca QR/status de acesso.

- [ ] **Step 4: RED da confirmação global com contagem**

Ao clicar na ação global, não abrir confirmação imediatamente: marcar `_pending_global_rotation=True` no MainWindow e disparar `refresh()` administrativo. Somente a resposta confirmada da API fornece `active_count=N`; então abrir a confirmação dizendo que `N` aparelhos ativos serão desconectados. Se o refresh falhar, cancelar a intenção e não rotacionar.

- [ ] **Step 5: implementar rotação global**

Somente após a confirmação baseada no refresh atual chama `on_rotate`. Após sucesso do access rotation, disparar novo refresh de instalações para contador/lista. Uma operação administrativa já em andamento deve impedir uma segunda intenção de rotação e informar que a atualização está em curso.

- [ ] **Step 6: rodar testes**

Run: `uv run pytest tests/unit/test_mobile_access_window.py tests/unit/test_mobile_access_ui_logic.py -q`  
Expected: PASS.

- [ ] **Step 7: commit**

```bash
git add src/alertam/ui/mobile_access_window.py src/alertam/ui/main_window.py tests/unit/test_mobile_access_window.py tests/unit/test_mobile_access_ui_logic.py
git commit -m "feat: integra contador de aparelhos no qr"
```

### Task 4: Janela Gerenciar aparelhos

**Files:**
- Create: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/mobile_installations_window.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/main_window.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_installations_window.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_installations_presentation.py`

**Interfaces:**
- `MobileInstallationsWindow(parent, on_refresh, on_revoke)`.
- `update(snapshot_or_error)`, `show()`, `hide()`, `visible`.
- Abas ttk.Notebook: **Ativos (N)** e **Revogados (N)**.

- [ ] **Step 1: RED de apresentação pura**

Formatar label, última atividade e revogação sem depender de Tk. Datas inválidas/ausentes mostram fallback legível.

- [ ] **Step 2: RED da estrutura**

Teste Tk/Xephyr ou helper deve provar que a janela cria duas abas e não injeta lista dentro de `MobileAccessWindow`.

- [ ] **Step 3: implementar listas roláveis**

Usar Treeview/Listbox/frame rolável compatível com estilo existente; janela possui tamanho máximo razoável e scroll para muitas linhas.

- [ ] **Step 4: RED de confirmação individual**

Selecionar/clicar Revogar mostra:
`Revogar <plataforma · código>?` e explica perda de acesso, notificações e acompanhamentos.

- [ ] **Step 5: implementar revogação**

Enquanto operação está em andamento, evitar duplo clique/repetição; somente após resultado API atualizar a lista. Em erro, manter item ativo e mostrar mensagem recuperável.

- [ ] **Step 6: lidar com janela destruída**

Callback tardio deve atualizar cache/contador no MainWindow, mas não acessar widget que já foi destruído.

- [ ] **Step 7: rodar testes**

Run: `uv run pytest tests/unit/test_mobile_installations_window.py tests/unit/test_mobile_installations_presentation.py -q`  
Expected: PASS.

- [ ] **Step 8: commit**

```bash
git add src/alertam/ui/mobile_installations_window.py src/alertam/ui/main_window.py tests/unit/test_mobile_installations_window.py tests/unit/test_mobile_installations_presentation.py
git commit -m "feat: adiciona gerenciador de aparelhos"
```

### Task 5: Integrar mensagens e manter cache consistente

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/main_window.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_access_bootstrap.py`
- Create: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_mobile_installations_ui_flow.py`

**Interfaces:**
- MainWindow mantém `_mobile_installations_snapshot` como último resultado confirmado.
- Uma atualização válida alimenta contador e janela, se visível.

- [ ] **Step 1: RED de refresh com janela fechada**

Mensagem nova atualiza cache/contador sem criar Toplevel.

- [ ] **Step 2: RED com janela aberta**

Mesma mensagem atualiza contador e as duas abas.

- [ ] **Step 3: RED de erro**

Erro administrativo preserva último snapshot confirmado na janela quando útil, marca refresh como falho e não modifica estado do QR.

- [ ] **Step 4: RED pós-revogação**

Após sucesso, item deixa Ativos e aparece em Revogados a partir do snapshot confirmado da API; nenhum movimento otimista local.

- [ ] **Step 5: implementar handler**

Adicionar branches de UIMessage na fila principal; nenhum callback de worker chama Tk diretamente.

- [ ] **Step 6: rodar testes focados**

Run: `uv run pytest tests/unit/test_mobile_installations_ui_flow.py tests/unit/test_mobile_access_bootstrap.py -q`  
Expected: PASS.

- [ ] **Step 7: commit**

```bash
git add src/alertam/ui/main_window.py tests/unit/test_mobile_installations_ui_flow.py tests/unit/test_mobile_access_bootstrap.py
git commit -m "feat: sincroniza estado dos aparelhos na ui"
```

### Task 6: Guia, gates Desktop e integração real

**Files:**
- Modify: `/home/ciro/dev/prog/alertamaritimo/src/alertam/ui/help_window.py`
- Modify: `/home/ciro/dev/prog/alertamaritimo/tests/unit/test_help_window.py`
- Create: `/home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/handoffs/2026-09-30-spec026-plan3-desktop-complete-handoff.md`

**Interfaces:**
- Produces: implementação Desktop concluída e roteiro final de smoke da SPEC 026.

- [ ] **Step 1: atualizar Guia**

Documentar **Gerenciar aparelhos**, revogação individual e **Revogar todos e gerar novo QR** sem expor termos internos como `installation_id`.

- [ ] **Step 2: rodar gate unitário/imports**

Run: `make check`  
Expected: pytest completo verde + imports OK.

- [ ] **Step 3: rodar Tk real/Xephyr**

Run conforme ambiente atual, por exemplo:
`DISPLAY=:0 XAUTHORITY=<xauth atual> make test-ui XEPHYR_N=<livre>`  
Expected: suite Tk completa verde.

- [ ] **Step 4: rodar `git diff --check` e revisar árvore**

Somente arquivos da SPEC 026 devem estar no diff deste plano.

- [ ] **Step 5: smoke cross-repo**

Com API/PWA dos Planos 1–2 publicados em ambiente de teste:
parear aparelho; conferir mesmo código na PWA/Desktop; revogar individual; re-parear com novo código; testar A→B cancelar e confirmar; testar rotação global.

- [ ] **Step 6: documentar limitações de hardware**

iOS real é obrigatório. Android pode ficar registrado como smoke pendente se não houver aparelho disponível, sem bloquear testes automatizados.

- [ ] **Step 7: criar handoff final**

Registrar versões/commits dos dois repos, migrations aplicadas, deploys, resultados de testes e smoke manual ainda pendente/concluído.

- [ ] **Step 8: commit documental do Desktop**

No repositório Desktop:
```bash
git add src/alertam/ui/help_window.py tests/unit/test_help_window.py
git commit -m "docs: atualiza guia de aparelhos conectados"
```

- [ ] **Step 9: registrar handoff no repositório API/PWA**

No repositório API/PWA, adicionar somente o handoff final em commit separado, sem misturar arquivos do Desktop:
```bash
git add docs/superpowers/handoffs/2026-09-30-spec026-plan3-desktop-complete-handoff.md
git commit -m "docs: consolida conclusão da spec 026"
```
