# SPEC 027 — Controle de checkpoints Executor ↔ Revisor

**Data de abertura:** 2026-10-08
**Status:** PREPARAÇÃO — P0 aguardando execução e R0 independente
**Repositório coordenador:** /home/ciro/dev/prog/alertamaritimoAPI
**Branch de documentação atual:** prep/spec027-cloud-infra-spike (não é a branch de implementação C1)
**Integração autoritativa API/PWA:** feat/api-bootstrap; **Desktop:** develop
**Objetivo:** um protocolo auditável de entregas incrementais, com parada obrigatória após cada checkpoint, para SPEC 027 sem efeitos operacionais prematuros.

## 1. Documentos autoritativos (ler na ordem)

1. Este controle de checkpoints.
2. specs/027-alertam-cloud-continuity.md.
3. docs/superpowers/handoffs/2026-10-08-spec027-c1-kickoff-handoff.md.
4. docs/superpowers/handoffs/2026-10-08-spec025-final-handoff.md.
5. specs/025-webpilot-http-observed-weather-shadow-migration.md e specs/030-device-operational-gate.md, **se presente**; se não existir nesse repo, localizar fonte canônica antes de projetar.
6. docs/superpowers/strategy/2026-10-02-alertam-cloud-evolution-roadmap.md.
7. docs/superpowers/plans/2026-10-06-pre-spec027-cloud-infra-spike.md e handoff correspondente.
8. Plano detalhado C1 **a ser criado no P0 e aprovado em R0**; este protocolo não o substitui.

## 2. Estado de entrada verificado (2026-10-08)

- SPEC 025 Plan 5: gate técnico MET; 25h53m, 1501 comparáveis, 1499 equivalentes, 109 limpos, nenhuma falha; 4 registros explicados de 2 episódios, hipótese forte de diferença temporal Selenium/HTTP, **não comprovada como causa-raiz**.
- Usuário aceitou a hipótese documentada e autorizou avançar o **desenvolvimento** da SPEC 027; **não** autorizou migrações de produção, WebPilot real no Cloud, publicação source=cloud, cutover ou failover real.
- Desktop: feat/spec025-plan5-shadow-evidence-gate, HEAD observado 8fa5962; develop abe386f; handoff do Desktop ainda tinha modificações não commitadas; Shadow real não deve ser interrompido.
- API/PWA: feat/api-bootstrap local 2545d37, remoto observado 3d85578 (validar na abertura; não assumir origem atualizada).
- API/PWA checkout principal: prep/spec027-cloud-infra-spike, HEAD af5e81f; há documentação SPEC025/027 e handoffs locais **não commitados**.
- Spike Northflank em worktree .worktrees/pre-spec027-cloud-infra-spike, branch feat/pre-spec027-cloud-infra-spike, HEAD documental local dc23003 (à frente do remoto), núcleo infra já no remoto no commit 9508af3; aprovado só como sandbox infra.
- Achado residual Shadow: assinatura explicada reincidente pode incrementar occurrences/last_seen sem reabrir status. Tratar como hotfix TDD Desktop separado, sem modificar aplicação em coleta por conta própria. Reexaminar reincidências.

**Regra:** nenhum Executor faz reset/checkout forçado, stash arbitrário, merge ou cherry-pick que descarte mudanças existentes. Inventariar branch, SHA, status, worktrees e mudanças antes de agir.

## 3. Protocolo obrigatório de checkpoint

**Executor:**
1. Ler este documento e a última decisão Rn; executar **somente** a etapa explicitamente liberada.
2. Começar pelos testes RED, implementar GREEN, refatorar e testar regressões proporcionais ao escopo.
3. A cada entrega, preencher o registro do checkpoint abaixo, citando base, SHA, arquivos, testes (com números), segurança, migrações preparadas/não aplicadas e pendências.
4. Parar para revisão independente; **não** iniciar a próxima etapa por iniciativa própria.
5. Se surgir bloqueio/necessidade de alterar desenho ou invariantes, registrar decisão solicitada e **parar**, sem expandir escopo.
6. Commits locais por etapa apenas quando a autorização vigente permitir; não fazer push/merge/deploy/migration em produção por implicação.

**Revisor:**
1. Reabrir a versão mais recente deste documento e dos handoffs; confirmar base real e diff do checkpoint.
2. Revisar contrato, isolamento, segurança, testes RED/GREEN, compatibilidade API/Desktop/PWA e conflitos.
3. Registrar **APROVADO**, **CORREÇÕES OBRIGATÓRIAS (R*-F1...)** ou **BLOQUEADO** com evidência e arquivos/linhas quando aplicável.
4. Autorizar explicitamente somente a próxima etapa após Rn aprovado; correções retornam ao mesmo checkpoint para Rn+1, nunca avançam automaticamente.
5. Não confundir testes skipped, revisão de plano, Docker smoke ou gate técnico MET com validação de produção.

**Retorno entre sessões:** o executor cita o mesmo path + checkpoint ID + SHA. O revisor insere parecer na seção do checkpoint; executor relê antes de continuar. O usuário serve como autorização de avanço, integração e operações.

## 4. Sequência e gates

| Ordem | Checkpoint | Entrega sob controle | Gate independente | Situação |
|---|---|---|---|---|
| 0 | P0 — Reconciliação e plano | Verificar estado cross-repo; preparar proposta de integração sem alterar produção; planejar C1 com tasks TDD e contratos | R0 aprova base e plano antes de programar | **AGUARDA EXECUTOR** |
| 1 | C1-A — Domínio/contrato | Modelo CloudBinding, associação realm/device_id, invariantes, interfaces, testes unitários; migração **somente proposta** | R1 revisa identidade, constraints, isolamento e contrato | BLOQUEADO por R0 |
| 2 | C1-B — Persistência/credenciais | Credencial própria, hash/rotação/revogação, repos/endpoints Desktop-only e testes; migração versionada **não aplicada** | R2 revisa autorização, secrets e idempotência | BLOQUEADO |
| 3 | C1-C — Gate e isolamento | Fail-closed (enabled=false, indisponível), cross-device/cross-realm, tentativas indevidas, testes adversariais | R3 revisa proibições de bypass | BLOQUEADO |
| 4 | C1-D — Integração/encerramento | Testes completos, documentação, mocks API e contratos Desktop, smoke local sem WebPilot real | R4 revisa regressão e segurança; gate humano para merge/deploy separado | BLOQUEADO |
| 5 | C2-P — Plano Auth Broker | Desenhar reuso do coletor validado, contrato SessionLease, epoch, segurança, standby | R5 (plano); **não** copiar parser/coletor | BLOQUEADO |
| 6 | C2 — Execução em checkpoints próprios | Broker federado, anti-replay e core HTTP em standby headless sem source efetivo | Revisões por subtask e gate sandbox | BLOQUEADO |
| 7 | C3-P / C3 — Autoridade e snapshots | Plano aprovado; lease/fencing, hysteresis, failover/failback, anti-split-brain; primeira versão só snapshots | Revisões por subtask, gate operacional explícito | BLOQUEADO |
| 8 | C4 — Observabilidade | Status, logs sanitizados, smoke prolongado, degradação e reconciliação | Revisão operacional humana | BLOQUEADO |
| 9 | C5 — Eventos/Push | Plano próprio de idempotência cross-source, sem duplicação | **Somente se autorizado separadamente** | FORA DA LIBERAÇÃO ATUAL |

O detalhamento e subdivisão de C1-A a C1-D podem ser aperfeiçoados pelo plano P0, **mas exigem aprovação de R0 antes da execução**. Para C2/C3, criar planos e checkpoints detalhados antes de iniciar; a aprovação de C1 não é aprovação operacional dessas fases.

### P0 — Entrega exata exigida

- Inventário verificável de branch/SHA/working tree/worktrees/estado remoto dos dois repos; não modificar o Desktop enquanto Shadow real coleta.
- Tratar integrações pendentes como **proposta de sequência**: fechamento documental/commit Plan 5; revisão e merge Desktop develop; revisão e integração spike Northflank na base feat/api-bootstrap; conciliar documentação local sem perdê-la.
- Criar plano executável docs/superpowers/plans/2026-10-08-spec027-c1-binding-realm-authority.md (nome sugerido), incluindo RED/GREEN, interfaces, testes, riscos, estratégia de migrations **sem aplicar**, impacto cross-repo, checkpoints C1-A..D e rollback.
- Justificar segurança dos endpoints e credencial; DeviceOperationalGate fail-closed e revogação; persistência por device_id, vínculo realm e controle de autorização.
- Entregar plano/diff e **PARAR para R0**. P0 não faz merge, push, deploy, migrations, WebPilot Cloud, nem implementa C1.

### Fronteiras inegociáveis até gates específicos

- Selenium permanece autoritativo no Desktop; Shadow apenas observa.
- Nunca ativar WebPilot autenticado/receber cookies reais no Northflank por simples aprovação do plano.
- Não publicar source=cloud, criar failover/failback real, eventos/Push Cloud ou alterar pareamento Mobile.
- Nunca contornar desativação administrativa; falha de checagem de autorização requer política fail-closed.
- Segredos de sessão e CloudBinding nunca em logs, UI PWA, URL, handoff, fixtures reais ou documentação.
- Nenhuma migration aplicada no Supabase produção, nem alteração do deployment Vercel/Northflank sem autorização explícita.
- Não substituir parser do Desktop por nova implementação divergente; reuso obrigatório da SPEC 025.

## 5. Modelo de registro a copiar para cada checkpoint

### [ID] — [Título]; status: AGUARDA / EM EXECUÇÃO / PRONTO PARA Rn / Rn-FIX / APROVADO

**Executor — evidência**
- Data/hora, repo, branch/worktree, base SHA, HEAD SHA, commits locais.
- Escopo entregue e não entregue; arquivos e migrations criadas (aplicação: NÃO).
- RED: comando, falhas esperadas e causa; GREEN: comando, passed/skipped/failed; regressão.
- `git status --short --branch`, `git diff --check`, diff da base; observações de segredo/segurança.
- Pendências, riscos, compatibilidade, decisões solicitadas; mudanças não relacionadas identificadas.
- Confirmação: sem push, merge, deploy, credenciais reais ou cutover, salvo autorização registrada.
- **PARECER SOLICITADO:** Rn independente; nenhuma etapa seguinte iniciada.

**Revisor — Rn**
- Data, base/HEAD realmente revisados e limites do diff.
- Achados: Rn-F1, Rn-F2 etc. (se houver); impacto, reprodução e critério de aceite.
- Testes/inspeções independentes e limitações/skips.
- Resultado: APROVADO / CORREÇÕES OBRIGATÓRIAS / BLOQUEADO.
- Próximo ID autorizado, **ou** manter mesmo checkpoint para correção; se faltar autorização humana, indicar.

**Correção**
- Executor implementa apenas achados Rn-F*, TDD; atualiza commit/testes; retorna à revisão Rn+1.
- Nenhum achado é considerado encerrado por afirmação do Executor sem verificação independente.

## 6. Livro de checkpoints (acrescentar entradas cronológicas, sem apagar decisões)

### P0 — Reconciliação + plano C1

**Status:** AGUARDA EXECUTOR.
**Executor:** pendente. **Revisor R0:** pendente.
**Próximo ato permitido:** inventário e plano C1, sem implementação nem integração.

### C1-A / C1-B / C1-C / C1-D

**Status:** BLOQUEADO até aprovação de R0; abrir seção específica em cada entrega.

### C2-P / C2 / C3-P / C3 / C4 / C5

**Status:** BLOQUEADO; usar este índice e ampliar com handoffs/planos aprovados.

## 7. Comandos mínimos de preflight e auditoria

```bash
cd /home/ciro/dev/prog/alertamaritimoAPI
git status --short --branch
git log -5 --oneline --decorate
git worktree list
git branch -vv
git diff --check

cd /home/ciro/dev/prog/alertamaritimo
git status --short --branch
git log -5 --oneline --decorate
git worktree list
```

Não executar comandos destrutivos/que alterem branch durante o preflight. Criar branch/worktree de implementação apenas **depois** de R0 e reconciliação aprovada, preservando mudanças locais.
