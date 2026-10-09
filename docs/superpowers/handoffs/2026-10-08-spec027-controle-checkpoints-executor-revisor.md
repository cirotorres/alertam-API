# SPEC 027 — Controle de checkpoints Executor ↔ Revisor

**Data de abertura:** 2026-10-08
**Status:** C2-B **APROVADO EM R7.2 — AGUARDA COMMITS EXATOS + REBUILD DO WHEEL PÓS-COMMIT**; C2-C bloqueado até verificação pós-commit
**Repositório coordenador:** /home/ciro/dev/prog/alertamaritimoAPI
**Base reconciliada:** API/PWA `feat/api-bootstrap@23a78bebdf46062eef937966101246567cd963de`; Desktop `develop@9e5b5e1a33cb7d61db200866aea683a6334de922`. **Feature:** `feat/spec027-cloud`, criada a partir de `23a78be` em `/home/ciro/dev/prog/alertamaritimoAPI/.worktrees/spec027-cloud`. **C1-A functional HEAD após correções R1:** `17afb4e19e21ce93e8eb1b8b0c8bfe47ebcf3364`; o commit documental deste registro será seu sucessor local.
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
8. `docs/superpowers/plans/2026-10-08-spec027-c1-binding-realm-authority.md` — plano executado e C1 tecnicamente encerrado em R4.
9. `docs/superpowers/plans/2026-10-08-spec027-c2-auth-broker-session-lease.md` — C2-P corrigido após R5-F1..F4; execução bloqueada até R5.1.

## 2. Estado de entrada verificado (2026-10-08)

- SPEC 025 Plan 5: gate técnico MET; 25h53m, 1501 comparáveis, 1499 equivalentes, 109 limpos, nenhuma falha; 4 registros explicados de 2 episódios, hipótese forte de diferença temporal Selenium/HTTP, **não comprovada como causa-raiz**.
- Usuário aceitou a hipótese documentada e autorizou avançar o **desenvolvimento** da SPEC 027; **não** autorizou migrações de produção, WebPilot real no Cloud, publicação source=cloud, cutover ou failover real.
- Desktop: feat/spec025-plan5-shadow-evidence-gate, HEAD após organização 9e5b5e1 (documentação R2/Task 5 commitada); develop abe386f; checkout limpo, branch Plan 5 não integrada, Shadow real não deve ser interrompido.
- API/PWA: ao iniciar a correção R0.1-F1/F2, o HEAD observado era `feat/api-bootstrap@6eab67b`, limpo e sem push; esse SHA é **histórico de auditoria, não alvo fixo de integração**.
- Auditoria histórica mais recente: `git merge-base 6eab67b dc23003` = `af5e81f4bb7c10ac7f0c07712f84f107c4a41aa4`; `git merge-tree --write-tree 6eab67b dc23003` = `3ab100bc0d01c01d85543ceb6c3d39594581eacb`, PASS. Na reconciliação real, repetir ambos contra o HEAD corrente naquele momento.
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
6. **Não fazer commit antes da aprovação independente do checkpoint.** O Executor entrega o working tree sem commit para revisão; se houver achados, corrige o mesmo working tree e retorna à re-revisão. Após APROVADO, o Revisor autoriza o commit exato do diff revisado. Push/merge/deploy/migration em produção continuam exigindo autorização própria.

**Revisor:**
1. Reabrir a versão mais recente deste documento e dos handoffs; confirmar base real e diff do checkpoint.
2. Revisar contrato, isolamento, segurança, testes RED/GREEN, compatibilidade API/Desktop/PWA e conflitos.
3. Registrar **APROVADO**, **CORREÇÕES OBRIGATÓRIAS (R*-F1...)** ou **BLOQUEADO** com evidência e arquivos/linhas quando aplicável.
4. Autorizar explicitamente somente a próxima etapa após Rn aprovado; correções retornam ao mesmo checkpoint para Rn+1, nunca avançam automaticamente.
5. Não confundir testes skipped, revisão de plano, Docker smoke ou gate técnico MET com validação de produção.

**Retorno entre sessões:** o executor cita o mesmo path + checkpoint ID + HEAD aprovado de entrada. O revisor insere parecer na seção do checkpoint; executor relê antes de continuar. O usuário serve como autorização de avanço, integração e operações.

**Política de commit revisada em 2026-10-08 pelo usuário:** commits de implementação/checkpoint só são feitos **depois** da aprovação independente. O estado entregue a Rn deve permanecer no working tree, sem commit. Se Rn encontrar falhas, o Executor corrige o mesmo diff e retorna para Rn+1; somente após `APROVADO` o commit exato do conteúdo revisado é autorizado. Commits históricos anteriores a esta regra permanecem como estão; não reescrever histórico.

## 4. Sequência e gates

| Ordem | Checkpoint | Entrega sob controle | Gate independente | Situação |
|---|---|---|---|---|
| 0 | P0 — Reconciliação e plano | Verificar estado cross-repo; preparar proposta de integração sem alterar produção; planejar C1 com tasks TDD e contratos | R0/R0.1/R0.2 aprovam base e plano antes de programar | **APROVADO EM R0.2** |
| 1 | C1-A — Domínio/contrato | Modelo CloudBinding, associação realm/device_id, invariantes, interfaces, testes unitários; migração **somente proposta** | R1/R1.1 revisam identidade, constraints, isolamento e contrato | **APROVADO EM R1.1** |
| 2 | C1-B — Persistência/credenciais | Credencial própria, hash/rotação/revogação, repos/endpoints Desktop-only e testes; migração versionada **não aplicada** | R2/R2.1 revisam autorização, secrets e idempotência | **APROVADO EM R2.1 — commit a4e1af85872308a907afb85d53f8cebac3dae6b5** |
| 3 | C1-C — Gate e isolamento | Fail-closed (enabled=false, indisponível), cross-device/cross-realm, tentativas indevidas, testes adversariais | R3 revisa proibições de bypass | **APROVADO EM R3 — commit 25485bba0143fd0c1659a88df89743db629951c2** |
| 4 | C1-D — Integração/encerramento | Testes completos, documentação, mocks API e contratos Desktop, smoke local sem WebPilot real | R4 revisa regressão e segurança; gate humano para merge/deploy separado | **APROVADO EM R4 — commit final C1 `61342b2ac47ffa48bfe90787b8aa2afb4bb4cda8`** |
| 5 | C2-P — Plano Auth Broker | Desenhar reuso do coletor validado, contrato SessionLease, epoch, segurança, standby | R5/R5.1 (plano); **não** copiar parser/coletor | **APROVADO EM R5.1 — commit `7c9f19516673c80860b144b9f421aaea0810e423`** |
| 6 | C2 — Execução em checkpoints próprios | Broker federado, anti-replay e core HTTP em standby headless sem source efetivo | R6/R7/R8; commit somente após cada aprovação | **C2-B APROVADO EM R7.2 — aguarda commits exatos + rebuild wheel pós-commit; C2-C bloqueado** |
| 7 | C3-P / C3 — Autoridade e snapshots | Plano aprovado; lease/fencing, hysteresis, failover/failback, anti-split-brain; primeira versão só snapshots | Revisões por subtask, gate operacional explícito | BLOQUEADO |
| 8 | C4 — Observabilidade | Status, logs sanitizados, smoke prolongado, degradação e reconciliação | Revisão operacional humana | BLOQUEADO |
| 9 | C5 — Eventos/Push | Plano próprio de idempotência cross-source, sem duplicação | **Somente se autorizado separadamente** | FORA DA LIBERAÇÃO ATUAL |

O detalhamento e subdivisão de C1-A a C1-D podem ser aperfeiçoados pelo plano P0, **mas agora exigem aprovação de R0.2 antes da execução**. Para C2/C3, criar planos e checkpoints detalhados antes de iniciar; a aprovação de C1 não é aprovação operacional dessas fases.

### Estratégia simplificada de branch/worktree

A SPEC 027 usa **uma branch longa de feature por repositório**, e não uma branch por fase/checkpoint:

- API/PWA/Cloud: `feat/spec027-cloud`, criada somente após aprovação R0.2 e reconciliação efetiva do HEAD corrente de `feat/api-bootstrap` com o spike Northflank.
- Desktop: usar também `feat/spec027-cloud` **somente quando surgir a primeira alteração Desktop da SPEC 027**, criada a partir de `develop` já contendo o fechamento da SPEC 025.
- C1, C2, C3 e C4 avançam na mesma branch, separados por commits e checkpoints independentes R1...Rn.
- Preferir uma única worktree `.worktrees/spec027-cloud` por repo quando necessário; não criar worktree por subetapa.
- Ao final de cada checkpoint: testes + handoff/checkpoint atualizado + `git diff --check` + **STOP para revisor, sem commit**. O commit só acontece **depois da aprovação independente** daquele checkpoint. **A revisão é o isolamento; a branch não precisa mudar.**
- Sincronizações com a branch-base acontecem apenas em pontos planejados, com working tree limpa e revisão de conflito; não fazer rebase/merge oportunista no meio de um checkpoint.
- A branch antiga `feat/pre-spec027-cloud-infra-spike` só pode ser integrada/removida após aprovação R0.2 e execução explícita da reconciliação.
- C5 Eventos/Push permanece fora desta branch inicial por ser evolução opcional com plano/autorização próprios; se for aprovada futuramente, decide-se naquele momento se continua na SPEC 027 ou abre feature separada.

### P0 — Entrega exata exigida

- Inventário verificável de branch/SHA/working tree/worktrees/estado remoto dos dois repos; não modificar o Desktop enquanto Shadow real coleta.
- Tratar integrações pendentes como **proposta de sequência**: o commit documental Plan 5 (9e5b5e1) já existe; revisar e integrar Plan 5 em Desktop develop sem interromper Shadow; revisar e integrar spike Northflank (dc23003) em feat/api-bootstrap; reconciliar a branch documental divergente docs/pre-plan4-gate-alignment (ecb7b37) sem perda.
- Criar plano executável docs/superpowers/plans/2026-10-08-spec027-c1-binding-realm-authority.md (nome sugerido), incluindo RED/GREEN, interfaces, testes, riscos, estratégia de migrations **sem aplicar**, impacto cross-repo, checkpoints C1-A..D e rollback. O plano deve assumir **uma única branch `feat/spec027-cloud` para C1→C4**, sem criar branches por checkpoint.
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
- Data/hora, repo, branch/worktree e **HEAD aprovado de entrada**; durante a entrega, alterações funcionais/documentais do checkpoint permanecem sem commit até o parecer.
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

**Status:** APROVADO EM R0.2.
**Executor:** P0, correções R0 e correções R0.1 concluídos documentalmente em 2026-10-08. **Revisor R0.2:** aprovado.
**Próximo ato permitido:** executar a reconciliação Git aprovada, rodar regressões da base reconciliada, registrar os SHAs finais e então criar `feat/spec027-cloud`; somente depois iniciar C1-A. Push/deploy/migration produção continuam proibidos.

**Estado Git auditado**
- API/PWA: **não há SHA de integração congelado**. O HEAD observado ao iniciar esta correção foi `6eab67b`, mas a reconciliação deverá usar o HEAD corrente de `feat/api-bootstrap` imediatamente antes do merge, contendo `8eeeffc`, `6eab67b` e todos os commits documentais posteriores aprovados. O Executor registrará o SHA completo real e repetirá `merge-base/merge-tree` nesse SHA.
- Spike: `feat/pre-spec027-cloud-infra-spike@dc23003`, worktree limpa; remoto da branch em `9508af3`. O commit `dc23003` fecha documentalmente o spike homologado Northflank.
- Desktop checkout principal: `feat/spec025-plan5-shadow-evidence-gate@9e5b5e1`, limpo; `develop@abe386f` e `origin/develop@abe386f`.
- Worktrees sujas não relacionadas foram identificadas e preservadas: API `/home/ciro/dev/prog/.worktrees/alertamaritimoAPI-spec029`; Desktop `/home/ciro/dev/prog/.worktrees/alertamaritimo-win-updater-provisioning`; externos `~/.cache/claude-hfi/.../elm` e `.../oak`. `/home/ciro/dev/prog/alertamaritimo/.worktrees/spec028-plan1` está limpo porém não integrado e também foi preservado.
- A fonte canônica da SPEC 030 foi localizada no repo Desktop: `/home/ciro/dev/prog/alertamaritimo/specs/030-device-admin-operational-gate.md`; ela foi lida integralmente e usada no desenho fail-closed de C1.

**Auditoria Plan 5 Desktop**
- Plan 5 é descendente linear de `develop@abe386f`; `develop` não possui commits exclusivos contra a branch.
- `git merge-tree --write-tree develop feat/spec025-plan5-shadow-evidence-gate`: PASS, sem conflito.
- Integração proposta pós-R0: fast-forward de `develop` para `9e5b5e1` em checkout/worktree separado, sem trocar/interromper o checkout do Shadow real.
- Achado residual de reincidência de divergence explained permanece hotfix Desktop separado; não entra em C1 e não exige parar Shadow.

**Auditoria spike Northflank**
- Merge-base com a base API atual: `af5e81f`.
- Spike possui `146f09b`, `0eccfa1`, `9558f29`, `9508af3`, `dc23003`; base API possui commits posteriores próprios.
- `git merge-tree --write-tree feat/api-bootstrap feat/pre-spec027-cloud-infra-spike`: PASS, sem conflito.
- Integração proposta pós-R0: merge real do spike em `feat/api-bootstrap`, regressões locais, sem push/deploy.
- O serviço sandbox Northflank permanece somente health/readiness; nenhum secret operacional ou WebPilot real foi usado.

**Reconciliação docs/pre-plan4-gate-alignment**
- `docs/pre-plan4-gate-alignment@ecb7b37` não deve ser mergeada.
- Os três planos alterados por `ecb7b37` são byte-identical à base atual.
- Handoff, roadmap e SPECs atuais contêm o conteúdo útil da branch e revisões posteriores (SPEC029, spike, gate MET).
- Merge direto hoje produziria conflitos add/add/content sem acrescentar semântica nova.
- Proposta pós-R0: remover worktree/branch documental somente após uma última verificação; nenhuma alteração local será perdida.

**Plano C1 produzido**
- `docs/superpowers/plans/2026-10-08-spec027-c1-binding-realm-authority.md`.
- C1-A: domínio/interfaces/invariantes.
- C1-B: migration 019 apenas local, repositories, credencial e endpoints Desktop-only.
- C1-C: fail-closed, credential authority, cross-device/cross-realm e revogações.
- C1-D: contratos, smoke/regressões, auditoria de segurança e encerramento.
- TDD RED→GREEN obrigatório; STOP R1/R2/R3/R4.
- Uma única branch `feat/spec027-cloud`; nenhuma branch por checkpoint/fase.
- C1 não ativa runtime Cloud operacional e, por default, não altera Desktop runtime.

**Decisões P0 submetidas a R0**
1. Aprovar a sequência de reconciliação Git acima.
2. Aprovar não mergear `ecb7b37`, por estar superseded.
3. Aprovar o contrato C1: credencial Cloud própria de alta entropia, plaintext somente em request HTTPS, hash-only persistido, write-only em response.
4. Aprovar WebPilotAuthRealm administrado fora do PWA e autorização explícita device↔realm.
5. Aprovar `GET cloud-binding` consultável por secret válido mesmo com device disabled, mas todas as mutações e qualquer uso da binding fail-closed quando disabled/unavailable.
6. Aprovar migration proposta `019_cloud_binding_realm.sql` somente para testes locais/efêmeros durante C1; produção continua proibida.
7. Aprovar que C2 SessionLease/Auth Broker e C3 source/failover permaneçam fora de C1.

**Verificação P0**
- `git diff --check`: limpo no API/PWA antes do commit documental.
- `git merge-tree` repetido: Plan 5→develop e spike→feat/api-bootstrap sem conflitos.
- `feat/spec027-cloud` inexistente nos dois repos.
- Nenhuma suíte funcional foi rerodada no P0 porque o único diff produzido é documental/plano; regressões funcionais são gate da base reconciliada pós-R0 antes de criar a feature.

**Reconciliação pós-R0.2 — executada localmente**
- **Desktop:** o checkout principal permaneceu em `feat/spec025-plan5-shadow-evidence-gate@9e5b5e1`. Em worktree temporário separado, `develop@abe386f` recebeu fast-forward `--ff-only` para **`9e5b5e1`**; o worktree temporário foi removido depois. Nenhum checkout/reset no diretório onde o AlertaM real roda.
- **Shadow:** processos observados antes e depois da reconciliação/C1-A continuam ativos no checkout principal: PID 45750 (`uv run python -m alertam`) e PID 45758 (Python do `.venv` do Desktop). Não foram interrompidos.
- **API/PWA — SHA real pré-merge:** `081aeca114e022800da28e470032c876f8152a48`.
- Spike: `dc230037a4da22f5fc11ac4fedbaebc0c95c21f8`.
- `git merge-base 081aeca dc23003` = `af5e81f4bb7c10ac7f0c07712f84f107c4a41aa4`.
- `git merge-tree --write-tree 081aeca dc23003` = `19f3678a008ffd7e0f1b97c43d7b28ec895a3afa`, **PASS sem conflito**.
- Integração local do spike concluída por merge commit **`23a78bebdf46062eef937966101246567cd963de`** em `feat/api-bootstrap`; nenhum push/deploy.
- Limpeza: worktree/branch local do spike removidos após prova de ancestralidade; `docs/pre-plan4-gate-alignment@ecb7b37` removida como superseded já aprovado em R0/R0.2. Remoto não foi alterado.
- Preservados integralmente: API SPEC029 com handoff modificado; Desktop updater com handoff modificado; worktrees HFI elm/oak com mudanças locais; `spec028-plan1-desktop`; branch/check-out Plan 5 do Shadow.

**Regressões da base reconciliada — GREEN**
- API `make test`: **472 passed / 34 skipped / 0 failed** (contagem extraída do progresso do pytest, pois o modo quiet não imprimiu resumo).
- Cloud `make cloud-test`: **9 passed / 0 failed**.
- Cloud `make cloud-smoke`: `/healthz=200`, `/readyz=200`, UID 10001, mounts vazios, restart healthy, filesystem diff vazio, logs sanitizados.
- PWA `npm test -- --run`: **50/50 arquivos, 290/290 testes passed**.
- Desktop `make check`: **1073 passed / 84 skipped / 0 failed**; `imports OK`.
- Nenhuma regressão relevante encontrada; gate para criação da feature satisfeito.

**Feature branch/worktree**
- Criada uma única branch **`feat/spec027-cloud`** a partir de `feat/api-bootstrap@23a78be`.
- Worktree: `/home/ciro/dev/prog/alertamaritimoAPI/.worktrees/spec027-cloud`.
- Nenhuma branch separada C1-A/B/C/D foi criada.

### C1-A — Domínio, interfaces e invariantes

**Status:** APROVADO EM R1.1.
**Base:** `23a78bebdf46062eef937966101246567cd963de`.
**C1-A code HEAD inicial:** `36b3c9b96ecfe8e88b6471f57ce0564a9e87850f`; **correção R1 aprovada:** `17afb4e19e21ce93e8eb1b8b0c8bfe47ebcf3364`.
**Commits:** `36b3c9b feat(cloud): define binding and realm domain contracts`; `17afb4e fix(cloud): harden c1-a binding invariants`.

**Arquivos**
- criado `api/app/repositories/cloud_bindings.py`;
- modificado `api/app/repositories/memory.py`;
- criado `api/tests/unit/test_cloud_binding_contract.py`;
- criado `api/tests/unit/test_cloud_binding_memory_repository.py`;
- `api/app/repositories/events.py` permaneceu intocado: composição no protocolo agregado não foi necessária para o contrato C1-A e não foi antecipada.

**TDD RED**
1. Contrato: `test_cloud_binding_contract.py` falhou na coleta com `ModuleNotFoundError: app.repositories.cloud_bindings`, exatamente porque o módulo ainda não existia.
2. MemoryRepository: primeiro RED mostrou ausência de `CloudBindingConflictError`; após adicionar apenas o erro tipado, novo RED apresentou **6 falhas** por ausência dos métodos de realm/binding no repository de memória.
3. Hardening de invariantes ainda dentro de C1-A: novo RED apresentou **4 falhas** — três estados inválidos de `CloudBindingRecord` não levantavam erro e `revoke_cloud_binding` ainda mutava com device desabilitado.

**GREEN**
- contrato inicial: **4/4 passed**;
- invariantes iniciais MemoryRepository: **6/6 passed**;
- conjunto final de testes novos C1-A: **14/14 passed**;
- regressões focadas existentes `test_memory_repository.py + test_devices_repository_contract.py`: **7/7 passed**;
- suíte API completa após a última correção: **486 passed / 34 skipped / 0 failed**;
- `git diff --check`: limpo antes do commit funcional.

**Contrato/invariantes entregues**
- `WebPilotAuthRealmRecord`, `RealmDeviceAuthorizationRecord`, `CloudBindingRecord`, `CloudBindingStatus` e `CloudBindingsRepository`;
- `credential_hash` excluído de `repr`;
- `credential_version >= 1` e coerência `status ↔ revoked_at` validadas no record;
- autorização realm↔device em memória;
- no máximo um binding ativo por device, com conflito tipado para segunda configuração diferente;
- ensure/rotate/revoke idempotentes conforme o escopo C1-A, histórico preservado após revoke e rebind;
- create/rotate/revoke fail-closed quando a autoridade corrente do device/realm/membership não está válida;
- operações isoladas por `device_id`;
- nenhum SessionLease, cookie, `source=cloud`, WebPilot real, snapshot Cloud ou failover introduzido.

**Fora do escopo / pendências**
- C1-B **não iniciado**.
- Migration 019 **não criada e não aplicada**.
- Nenhum Postgres/Supabase, endpoint, serviço de credencial, admin script ou runtime Cloud operacional foi implementado.
- Push/deploy continuam inexistentes.
- Próximo ato permitido: **R1 independente sobre C1-A**. Nenhuma etapa C1-B pode começar antes do parecer.

**PARECER SOLICITADO:** **R1 independente** — revisar `23a78be..36b3c9b` e este registro.

### R1 independente — revisão C1-A (2026-10-08)

**Resultado:** CORREÇÕES OBRIGATÓRIAS. C1-A está estruturalmente bem delimitado e as regressões estão verdes, porém dois defeitos de domínio/idempotência precisam ser corrigidos antes de liberar C1-B.

**Evidência independente**
- Base/feature confirmadas: `feat/api-bootstrap@23a78be` → `feat/spec027-cloud`; commit funcional `36b3c9b`, seguido somente do checkpoint documental `44b7ee0`.
- Diff funcional revisado: apenas `cloud_bindings.py`, `memory.py` e dois testes C1-A; nenhum endpoint, service, migration, WebPilot/SessionLease, `source=cloud` ou runtime Cloud operacional foi antecipado.
- `git diff --check 23a78be..36b3c9b`: PASS.
- Testes independentes C1-A: **14/14 passed**.
- Regressões focadas existentes: **7/7 passed**.
- Suíte API completa independente: exit code 0, sem falhas.
- Desktop `develop` está em `9e5b5e1`; processo Shadow segue ativo nos PIDs observados 45750/45758.
- Reconciliação do spike está correta: merge commit `23a78be` tem pais `081aeca` e `dc23003`; feature nasce exatamente desse merge.

**R1-F1 — `CloudBindingRecord` aceita status runtime inválido e permite furar o invariante**
`CloudBindingRecord.__post_init__` usa identidade contra `CloudBindingStatus`, mas dataclass/type hints não validam o tipo em runtime. Prova independente: foram aceitos sem exceção `status="active"` com `revoked_at` preenchido, `status="revoked"` com `revoked_at=None` e até `status="garbage"`. Isso permite que futuras mappings Postgres/Supabase construam um record inválido e burlem exatamente o invariante `status ↔ revoked_at`.

**Critério de aceite R1-F1:** TDD RED primeiro; o record deve rejeitar status que não seja `CloudBindingStatus` (ou exigir conversão explícita validada antes de construí-lo) e continuar rejeitando as combinações inválidas ACTIVE/REVOKED. Cobrir ao menos os três casos reproduzidos acima. Não mascarar valor inválido por coerção silenciosa permissiva.

**R1-F2 — retry de revoke pode devolver binding histórico errado após rebind no mesmo timestamp**
Quando não há binding ativo, `revoke_cloud_binding()` tenta descobrir o último histórico ordenando por `(created_at, UUID)`. UUID não é ordem temporal. Prova independente com clock fixo e UUIDs adversariais:
1. cria/revoga binding A;
2. cria/revoga binding B no mesmo timestamp;
3. retry de revoke retorna **A**, embora a operação imediatamente anterior tenha revogado **B**.
Isso viola a idempotência do retry do lifecycle corrente e pode fazer backends divergir quando timestamps empatam.

**Critério de aceite R1-F2:** TDD RED reproduzindo dois ciclos revoke→rebind→revoke no mesmo timestamp com IDs cuja ordem lexical contrarie a ordem de criação. O retry deve retornar o binding do **último lifecycle revogado (B)**, sem usar UUID como substituto de temporalidade. Preservar histórico e isolamento por device.

**Demais pontos R1**
- Escopo C1-A: **APROVADO**.
- Reconciliação Git/base: **APROVADA**.
- TDD apresentado: **aceito**, mas deve ser estendido pelos RED de R1-F1/F2.
- Nenhuma migration 019 foi criada/aplicada: **correto**.
- C1-B permanece **BLOQUEADO**.

**Próximo passo autorizado:** Executor corrige somente R1-F1 e R1-F2 com TDD, roda testes C1-A + regressões focadas + suíte API completa + `git diff --check`, faz commit funcional local e atualiza este checkpoint. Parar para **R1.1 independente**. Não iniciar C1-B, não criar migration 019, não push/deploy e não tocar no Shadow.

### Correções R1-F1/F2 — Executor (2026-10-08)

**Status:** PRONTO PARA R1.1 INDEPENDENTE. Escopo restrito aos dois achados R1; C1-B permanece bloqueado.

**Base da correção**
- branch/worktree: `feat/spec027-cloud` em `/home/ciro/dev/prog/alertamaritimoAPI/.worktrees/spec027-cloud`;
- HEAD de entrada: `3b6d087beec16be314a08a2122833a3033082ddf` (parecer R1 documental);
- base C1-A: `23a78bebdf46062eef937966101246567cd963de`;
- commit funcional da correção: **`17afb4e19e21ce93e8eb1b8b0c8bfe47ebcf3364`** — `fix(cloud): harden c1-a binding invariants`.

**R1-F1 — status runtime inválido — RED→GREEN**
- RED adicionado em `test_cloud_binding_contract.py` cobrindo exatamente:
  - `status="active"` com `revoked_at` preenchido;
  - `status="revoked"` com `revoked_at=None`;
  - `status="garbage"`.
- RED observado: **3 falhas `Failed: DID NOT RAISE ValueError`**, confirmando que type hints/identidade do enum não protegiam runtime.
- GREEN mínimo: `CloudBindingRecord.__post_init__` agora rejeita qualquer `status` que não seja instância de `CloudBindingStatus`, sem coerção silenciosa; os checks existentes `ACTIVE ↔ revoked_at is None` e `REVOKED ↔ revoked_at is not None` permanecem.
- Resultado: os três casos inválidos são rejeitados e os estados enum válidos continuam cobertos pelos testes existentes.

**R1-F2 — retry de revoke com timestamp empatado — RED→GREEN**
- RED adicionado em `test_cloud_binding_memory_repository.py` com clock fixo e UUIDs adversariais:
  - primeiro lifecycle: `ffffffff-ffff-ffff-ffff-ffffffffffff`;
  - segundo lifecycle: `00000000-0000-0000-0000-000000000001`;
  - sequência: create A → revoke A → rebind B → revoke B → retry revoke, tudo no mesmo timestamp.
- RED observado: retry devolveu **A** em vez de **B**, reproduzindo a ordenação incorreta por UUID.
- GREEN mínimo: o retry não ordena mais histórico por `(created_at, UUID)`; usa a ordem de inserção do histórico interno já preservada pelo repository de memória, de modo que o último binding criado/revogado do device é o lifecycle corrente.
- Histórico e isolamento por `device_id` permanecem preservados.

**Verificação após correções**
- testes C1-A: **18/18 passed**;
- regressões focadas existentes `test_memory_repository.py + test_devices_repository_contract.py`: **7/7 passed**;
- suíte API completa: **490 passed / 34 skipped / 0 failed**;
- `git diff --check`: PASS antes do commit funcional;
- diff funcional: somente `cloud_bindings.py`, `memory.py` e os dois testes C1-A.

**Fronteiras preservadas**
- C1-B **não iniciado**;
- migration 019 **não criada/aplicada**;
- nenhum endpoint/Postgres/Supabase/admin script/runtime Cloud operacional novo;
- nenhum push/deploy;
- Shadow não foi interrompido ou alterado.

**PARECER SOLICITADO:** **R1.1 independente** sobre R1-F1/F2 e o commit funcional `17afb4e`. Nenhuma etapa C1-B iniciada.

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

## 8. Organização Git pré-P0 (2026-10-08)

**Ação de manutenção autorizada pelo usuário antes de iniciar P0; não equivale a aprovação R0.**

- API/PWA: documentos SPEC 025/027 e handoffs de checkpoints antes soltos foram commitados em **3253e44** (docs: registra aceite shadow e checkpoints para spec027), na branch documental prep/spec027-cloud-infra-spike.
- A documentação completa dessa branch (incluindo commits 4084279 e af5e81f) foi incorporada por **fast-forward local** em feat/api-bootstrap, agora **3253e44**, working tree limpa, 4 commits à frente do remoto; prep/spec027-cloud-infra-spike foi apagada após integração comprovada.
- Desktop: handoff de R2/Task 5 previamente modificado foi preservado e commitado em **9e5b5e1**, branch feat/spec025-plan5-shadow-evidence-gate; checkout limpo. **Plan 5 permanece fora do develop e processo Shadow segue em execução.**
- Desktop, branches locais comprovadamente ancestrais de develop excluídas: feat/spec025-plan4-maneuver-shadow; hotfix/pre-plan4-device-operational-gate; hotfix/ship-photo-wikidata-priority; hotfix/version-test-alignment; ui/pre-plan4-desktop-adjustments; feat/spec029-tabua-mare-dhn (após remover worktree limpo).
- API/PWA, branch local comprovadamente ancestral de feat/api-bootstrap excluída: feat/spec030-device-operational-gate (após remover worktree limpo).
- Total da manutenção: **8 branches locais excluídas**, sendo 2 worktrees limpos removidos e nenhuma branch remota excluída.
- **Preservar por não estar integrado:** Desktop feat/spec025-plan5-shadow-evidence-gate, spec028-plan1-desktop (worktree limpo, commits não integrados).
- **Preservar por mudanças não commitadas:** Desktop fix/windows-updater-provisioning (handoff modificado); worktrees externos hfi/.../elm e hfi/.../oak (múltiplos arquivos modificados); API/PWA feat/spec029-tabua-mare-dhn (handoff modificado).
- **Preservar até reconciliação P0:** API/PWA docs/pre-plan4-gate-alignment em ecb7b37 (commit documental próprio não integrado) e feat/pre-spec027-cloud-infra-spike em dc23003 (shell Northflank pronto, commit documental local adiante do remoto).
- Nenhum push, fetch forçado, reset, stash, deploy, migration, Cloud operacional ou cutover. Limpeza foi feita somente com merge fast-forward para documentos, git branch -d e git worktree remove sem force.

**P0 ainda precisa** revisar o diff da documentação ecb7b37 e a integração do spike dc23003, definir base do plano C1 e obter R0 independente. Não apagar branch/worktree cujo HEAD ou mudanças locais não estejam integrados.


### R0 independente — revisão do P0 e Plano C1 (2026-10-08)

**Resultado:** CORREÇÕES OBRIGATÓRIAS antes de liberar C1-A. O desenho geral e a reconciliação Git estão aprováveis; os achados abaixo são de endurecimento/consistência do plano, não pedem implementação funcional ainda.

**Evidência independente confirmada pelo Revisor**
- P0 respeitou o escopo: commit `3b7c932` altera apenas o documento central e cria o plano C1; nenhuma implementação, migration, deploy, branch `feat/spec027-cloud` ou integração foi executada.
- Desktop Plan 5 continua descendente linear de `develop@abe386f`; fast-forward é tecnicamente possível.
- `git merge-tree --write-tree feat/api-bootstrap feat/pre-spec027-cloud-infra-spike` também PASS na base atual `feat/api-bootstrap@3b7c932`.
- Os três planos antigos alterados por `ecb7b37` são byte-identical às versões atuais; não mergear `docs/pre-plan4-gate-alignment` continua a decisão correta, preservando apenas o handoff como histórico até a limpeza aprovada.
- A próxima migration disponível é realmente `019`; a sequência atual termina em `018_device_admin_metadata.sql`.
- O contrato proposto de GET de metadata quando `enabled=false` é compatível com a SPEC 030 e com `DeviceAuthService.authenticate_status()`: secret correto pode consultar status, enquanto autenticação operacional continua bloqueada.
- A estratégia de uma única branch `feat/spec027-cloud` para C1→C4 foi preservada.

**R0-F1 — base API stale no plano/checkpoint**
O plano ainda manda integrar o spike em `feat/api-bootstrap@8177332`, mas o próprio P0 foi commitado e o HEAD real agora é `3b7c932`. Atualizar todas as referências de base para o HEAD real após o P0 e registrar novamente o `merge-tree` nessa base. O Revisor já repetiu a simulação em `3b7c932` e ela passou sem conflito, mas o documento deve refletir o estado executável real.

**Critério de aceite F1:** plano e checkpoint apontam para `feat/api-bootstrap@3b7c932` (ou para SHA posterior contendo apenas a correção R0), com merge-base/merge-tree registrados novamente; nenhuma integração real ainda.

**R0-F2 — contrato de força/formato da Cloud credential ausente**
O plano exige credencial de alta entropia e sugere `secrets.token_urlsafe(32)`, porém a API aceitaria qualquer `SecretStr`, inclusive segredo curto/fraco ou payload excessivo. Como o servidor não consegue provar entropia aleatória, ele deve ao menos impor contrato sintático e limites coerentes com a geração oficial.

**Critério de aceite F2:** definir e testar no plano tamanho mínimo/máximo e formato aceito (por exemplo base64url/url-safe compatível com `token_urlsafe(32)`), rejeitando segredo curto, vazio, whitespace/malformado e tamanho abusivo. Manter CSPRNG no cliente como obrigação explícita e hash-only no servidor.

**R0-F3 — lifecycle de WebPilotAuthRealm incompleto**
O domínio possui `realm.active` e a autorização central nega realm inativo, mas o plano administrativo oferece somente ensure/create, authorize device e revoke device authorization. Não há operação controlada para desativar/reativar o próprio realm.

**Critério de aceite F3:** ou (preferido) adicionar ao contrato/admin script operações explícitas e idempotentes para ativar/desativar realm, com testes e efeito imediato no `authenticate_cloud_binding`; ou remover `active` do escopo C1 e justificar a postergação. Não deixar estado persistente sem caminho administrativo definido.

**R0-F4 — PostgreSQL real não pode ser opcional no gate C1-B**
C1-B depende de partial unique index, FKs, RLS, grants e RPCs transacionais que revalidam `devices.enabled`, realm e membership imediatamente antes da mutação. MockTransport não prova essas propriedades. O plano atualmente admite que Postgres “pode skip sem TEST_POSTGRES_DSN” e deixa `make test-all` condicionado a Docker disponível.

**Critério de aceite F4:** tornar obrigatório, antes de R2, executar a migration 019 e os testes de integração/RPC em PostgreSQL efêmero/local real. Se o ambiente não puder fornecer Postgres/Docker, C1-B fica BLOQUEADO para R2; skip deve ser registrado como bloqueio, não aprovação.

**R0-F5 — endurecimento SQL/invariantes precisa ficar explícito**
A migration proposta prevê RPCs mutantes e RLS, mas o plano não exige explicitamente o padrão de segurança já usado nas migrations atuais para funções `SECURITY DEFINER`: `SET search_path = public`/objetos qualificados, além dos revokes. Também faltam checks relacionais explícitos entre `status` e `revoked_at` e unicidade/lifecycle claro da membership realm↔device.

**Critério de aceite F5:** acrescentar testes/DDL exigindo:
- qualquer função `SECURITY DEFINER` com search_path fixo e objetos qualificados;
- EXECUTE revogado de PUBLIC/anon/authenticated e concedido somente ao papel backend necessário;
- `cloud_bindings.status='active'` implica `revoked_at IS NULL`; `status='revoked'` implica `revoked_at IS NOT NULL`;
- membership realm↔device com chave/unique determinística e sem duplicatas ativas;
- reautorização/revogação idempotentes com timestamps coerentes.

**Parecer R0**
- Reconciliação Git proposta: **APROVADA conceitualmente**, condicionada a F1 documental.
- Não mergear `ecb7b37`: **APROVADO**.
- Estratégia de branch única `feat/spec027-cloud`: **APROVADA**.
- Fronteiras C1/C2/C3 e preservação do Shadow/Selenium: **APROVADAS**.
- Plano C1: **NÃO LIBERADO AINDA** por R0-F1..F5.
- C1-A permanece **BLOQUEADO**.

**Próximo passo autorizado:** Executor corrige somente R0-F1..R0-F5 no plano/checkpoint, faz `git diff --check`, commit documental local e para para **R0.1 independente**. Não integrar branches, não criar `feat/spec027-cloud`, não implementar C1-A, não push/deploy/migration.

### Correções R0-F1..R0-F5 — Executor (2026-10-08)

**Status:** PRONTO PARA R0.1 INDEPENDENTE. Escopo limitado ao plano C1 e a este checkpoint; nenhuma integração/implementação foi executada.

**R0-F1 — base API real e simulação do spike — CORRIGIDA**
- Base limpa observada ao iniciar a correção: `feat/api-bootstrap@20c85768faa18221c4e97611b96d91fef0aecc91`, sucessora documental de `3b7c932`.
- Spike: `dc230037a4da22f5fc11ac4fedbaebc0c95c21f8`.
- `git merge-base 20c8576 dc23003` = `af5e81f4bb7c10ac7f0c07712f84f107c4a41aa4`.
- `git merge-tree --write-tree 20c8576 dc23003` = `f6d55bd52048d183895f72be70fcb32ce8819617`, PASS sem conflito.
- Plano atualizado para essa base real. Nenhum merge foi executado.

**R0-F2 — força/formato da Cloud credential — CORRIGIDA**
- Geração oficial obrigatória no cliente: CSPRNG `secrets.token_urlsafe(32)` ou equivalente com >=32 bytes aleatórios.
- Enforcement server-side: regex `^[A-Za-z0-9_-]{43,86}$`, sem padding/whitespace/normalização silenciosa.
- Plano exige rejeição de vazio, curto, >86, whitespace, `=`, caractere inválido e payload abusivo antes de hash/repository.
- `SecretStr`, hash-only e não exposição em response/log continuam obrigatórios.

**R0-F3 — lifecycle WebPilotAuthRealm.active — CORRIGIDA**
- Realm nasce ativo; `activate`/`deactivate` são operações administrativas explícitas e idempotentes.
- Deactivate preserva binding/membership, mas bloqueia imediatamente `authenticate_cloud_binding`.
- Reactivate só restaura uso se device, membership e binding continuam válidos.
- Plano inclui testes de chamadas repetidas e efeitos imediatos.

**R0-F4 — PostgreSQL real no C1-B — CORRIGIDA**
- PostgreSQL efêmero/local real com migration 019 aplicada tornou-se gate obrigatório antes de R2.
- `TEST_POSTGRES_DSN` ausente, Docker/Postgres indisponível ou skip dos testes SQL C1-B => checkpoint BLOQUEADO.
- Supabase MockTransport permanece complementar; não substitui prova real de FKs/index/RLS/grants/RPCs.

**R0-F5 — hardening SQL e invariantes — CORRIGIDA**
- `SECURITY DEFINER` exige `search_path` fixo e objetos `public.*` qualificados.
- `EXECUTE` deve ser revogado de `PUBLIC`, `anon`, `authenticated` e concedido somente ao backend necessário.
- Binding: `active => revoked_at IS NULL`; `revoked => revoked_at IS NOT NULL`; versão positiva.
- Membership: PK/unique `(realm_id, device_id)`, sem duplicatas; authorize/revoke/reauthorize idempotentes e timestamps coerentes.
- Plano exige RPCs atômicas também para membership e activate/deactivate realm.

**Escopo preservado:** C1-A continua BLOQUEADO. Não integrar branches, não criar `feat/spec027-cloud`, não fazer push/deploy/migration e não tocar no Shadow.

**PARECER SOLICITADO:** **R0.1 independente** sobre R0-F1..R0-F5; nenhuma etapa seguinte iniciada.

### R0.1 independente — re-revisão das correções R0-F1..F5 (2026-10-08)

**Resultado:** R0-F2, R0-F3, R0-F4 e R0-F5 ENCERRADOS. Restam **dois ajustes documentais finais** antes de liberar a reconciliação e o C1-A.

**Evidência independente**
- Commit revisado: `8eeeffc` (`docs: address spec027 r0 findings`), somente plano C1 + documento central; `git diff --check 20c8576..8eeeffc` PASS.
- Nenhuma branch `feat/spec027-cloud`, implementação, migration, merge, push ou deploy foi criada/executada.
- Repetido contra o HEAD corrigido `8eeeffc`: `git merge-base 8eeeffc dc23003` = `af5e81f4bb7c10ac7f0c07712f84f107c4a41aa4`; `git merge-tree --write-tree 8eeeffc dc23003` = `b7bb6d37da3ab12b101a58396f75963f467b96da`, PASS sem conflito.
- PostgreSQL real ficou explicitamente obrigatório para C1-B/R2 e o Makefile atual possui `make test-all` com Postgres efêmero em Docker.
- Hardening SQL, lifecycle de membership e coerência `status/revoked_at` estão explicitamente exigidos no plano.

**R0-F2 — ENCERRADA**
Contrato server-side agora exige base64url sem padding, 43..86 caracteres, rejeição explícita de vazio/curto/whitespace/padding/caractere inválido/payload acima do limite, com CSPRNG obrigatório no cliente e hash-only no servidor. Observação não bloqueante: ao implementar, manter o gerador canônico `token_urlsafe(32)`; se forem aceitos geradores equivalentes maiores, documentar que o formato final precisa respeitar o máximo de 86 caracteres.

**R0-F3 — ENCERRADA**
`WebPilotAuthRealm.active` agora possui activate/deactivate administrativos, idempotentes, preservando membership/binding e alterando imediatamente a usabilidade do realm.

**R0-F4 — ENCERRADA**
PostgreSQL efêmero/local real com migration 019 aplicada é gate obrigatório. Ausência de DSN/Docker/Postgres ou skip dos testes C1-B bloqueia R2.

**R0-F5 — ENCERRADA**
O plano agora exige `SECURITY DEFINER` com search_path fixo, objetos `public.*` qualificados, revogação de EXECUTE de PUBLIC/anon/authenticated, grants mínimos de backend, checks status/revoked_at, PK/unique determinística de membership e lifecycle idempotente.

**R0.1-F1 — referência executável da base ainda não deve congelar o SHA pré-correção**
A correção registrou corretamente a simulação feita em `20c8576`, mas o commit documental `8eeeffc` agora também faz parte obrigatória da base que será reconciliada; qualquer parecer R0.2 também criará novo sucessor documental. O plano não deve mandar integrar o spike literalmente sobre `20c8576`.

**Critério de aceite R0.1-F1:** definir a base de integração como **o HEAD corrente de `feat/api-bootstrap` no momento da reconciliação, contendo `8eeeffc` e todos os commits documentais de revisão posteriores**, registrar SHA real imediatamente antes do merge e repetir `merge-base/merge-tree` nesse SHA. Manter os resultados em 20c8576/8eeeffc como histórico de auditoria, não como alvo fixo.

**R0.1-F2 — B9 depende de função que só nasce no C1-C**
No C1-B/Step B9 o plano exige provar que activate/deactivate bloqueiam/restauram `authenticate_cloud_binding()`; porém essa função só é criada no C1-C/Steps C1-C1/C2. Executar B9 literalmente obrigaria antecipar código de C1-C antes de R2, violando os checkpoints.

**Critério de aceite R0.1-F2:** no B9 testar somente lifecycle administrativo/persistente do realm (active, idempotência, timestamps, projection/usable se já existir) sem criar `authenticate_cloud_binding`. Mover a prova comportamental “deactivate bloqueia / activate restaura `authenticate_cloud_binding`” para C1-C, após a função nascer. Não antecipar C1-C em C1-B.

**Parecer R0.1**
- R0-F2..F5: **ENCERRADOS**.
- R0-F1: conteúdo técnico aceito; referência de base precisa do ajuste R0.1-F1 acima.
- Plano C1: **ainda não liberado**, exclusivamente por R0.1-F1 e R0.1-F2.
- C1-A permanece **BLOQUEADO**.
- Nenhuma nova mudança funcional foi solicitada.

**Próximo passo autorizado:** corrigir somente R0.1-F1 e R0.1-F2 no plano/checkpoint, rodar `git diff --check`, fazer commit documental local e parar para **R0.2 independente**. Não integrar branches, não criar `feat/spec027-cloud`, não implementar C1-A, não push/deploy/migration e não tocar no Shadow.

### Correções R0.1-F1/F2 — Executor (2026-10-08)

**Status:** PRONTO PARA R0.2 INDEPENDENTE. R0-F2..F5 permanecem encerrados; nenhuma mudança funcional nova foi introduzida.

**R0.1-F1 — base dinâmica de reconciliação — CORRIGIDA**
- O plano não fixa mais `20c8576`, `8eeeffc` ou `6eab67b` como alvo de integração; esses SHAs permanecem somente como histórico de auditoria.
- Regra executável: usar o HEAD corrente de `feat/api-bootstrap` imediatamente antes do merge, contendo obrigatoriamente `8eeeffc`, `6eab67b` e commits documentais posteriores aprovados.
- O Executor deve registrar o SHA completo real imediatamente antes do merge e repetir `git merge-base <SHA_REAL> dc23003` e `git merge-tree --write-tree <SHA_REAL> dc23003`; conflito bloqueia a integração.
- Histórico mais recente antes desta correção: `6eab67b` com merge-base `af5e81f4bb7c10ac7f0c07712f84f107c4a41aa4` e merge-tree `3ab100bc0d01c01d85543ceb6c3d39594581eacb`, PASS.

**R0.1-F2 — dependência prematura de authenticate_cloud_binding — CORRIGIDA**
- C1-B/B9 agora testa somente lifecycle administrativo/persistente de realm/membership: active, activate/deactivate, authorize/revoke/reauthorize, idempotência, ausência de duplicatas e timestamps/projection coerentes.
- B9 proíbe explicitamente criar ou chamar `authenticate_cloud_binding()`.
- A prova comportamental “deactivate bloqueia / activate restaura `authenticate_cloud_binding`” foi movida para C1-C, após a função nascer em C1-C1/C2.
- Nenhum código C1-C é antecipado para C1-B.

**Escopo preservado:** nenhuma integração, branch `feat/spec027-cloud`, C1-A, push, deploy, migration ou alteração do Shadow foi executada.

**PARECER SOLICITADO:** **R0.2 independente** sobre R0.1-F1/F2; nenhuma etapa seguinte iniciada.

### R0.2 independente — encerramento do P0 (2026-10-08)

**Resultado:** APROVADO. R0.1-F1 e R0.1-F2 encerrados; todos os achados R0/R0.1 estão fechados.

**Evidência independente**
- Commit revisado: `42ac4c1` (`docs: address spec027 r0.1 findings`), somente plano C1 + documento central.
- `git diff --check 6eab67b..42ac4c1`: PASS.
- `feat/spec027-cloud` continua inexistente; nenhuma implementação, migration, merge, push ou deploy foi executada.
- Simulação repetida na base documental atual `42ac4c1`: `git merge-base 42ac4c1 dc23003` = `af5e81f4bb7c10ac7f0c07712f84f107c4a41aa4`; `git merge-tree --write-tree 42ac4c1 dc23003` = `509c36cf417810d21a165efdfc6da3c16614e17c`, PASS sem conflito.

**R0.1-F1 — ENCERRADA**
O plano agora usa como alvo o HEAD corrente de `feat/api-bootstrap` imediatamente antes da reconciliação, exige registrar o SHA completo real e repetir `merge-base/merge-tree`; SHAs anteriores ficaram apenas como histórico de auditoria.

**R0.1-F2 — ENCERRADA**
C1-B/B9 ficou restrito ao lifecycle administrativo/persistente de realm/membership e proíbe criar/chamar `authenticate_cloud_binding()`. A prova comportamental deactivate/activate sobre essa função foi movida para C1-C, após a função nascer.

**Parecer R0.2**
- P0: **APROVADO**.
- Plano C1: **APROVADO PARA EXECUÇÃO POR CHECKPOINTS**.
- Estratégia de branch única `feat/spec027-cloud`: **APROVADA**.
- Reconciliação Git proposta: **AUTORIZADA LOCALMENTE**, com nova verificação do SHA/merge-tree imediatamente antes do merge.
- C1-A: **LIBERADO somente após** (1) reconciliação Git, (2) regressões verdes na base reconciliada, (3) registro dos SHAs finais e (4) criação da branch/worktree `feat/spec027-cloud`.
- C1-B/C/D continuam bloqueados pelos respectivos gates R1/R2/R3.
- Push, deploy, migration de produção, WebPilot real no Cloud, SessionLease real, `source=cloud`, failover/failback e cutover continuam proibidos.

**Próximo passo autorizado ao Executor:** executar a reconciliação Git exatamente como planejada, preservar o Shadow, rodar regressões da base reconciliada e, se verdes, criar `feat/spec027-cloud` e executar **somente C1-A** com TDD. Ao final, atualizar este documento e parar para **R1 independente**.

### R1.1 independente — encerramento do C1-A (2026-10-08)

**Resultado:** APROVADO. R1-F1 e R1-F2 encerrados; C1-A liberado e C1-B autorizado conforme o plano.

**Evidência independente**
- Commit funcional revisado: `17afb4e` (`fix(cloud): harden c1-a binding invariants`), seguido apenas do registro documental `436a754`.
- Diff funcional R1→R1.1 limitado a `cloud_bindings.py`, `memory.py` e os dois testes C1-A; nenhum endpoint, migration, Postgres/Supabase, admin script ou runtime Cloud operacional foi antecipado.
- `git diff --check 3b6d087..17afb4e`: PASS.
- Testes C1-A independentes: **18/18 passed**.
- Regressões focadas existentes: **7/7 passed**.
- Suíte API completa independente: exit code 0, sem falhas.
- Migration `019_cloud_binding_realm.sql`: ausente, como exigido antes de C1-B.
- Shadow permanece ativo nos PIDs observados 45750/45758.

**R1-F1 — ENCERRADO**
`CloudBindingRecord.__post_init__` agora rejeita qualquer `status` que não seja instância de `CloudBindingStatus`. Reprodução independente confirmou rejeição de `"active"`, `"revoked"` e `"garbage"` passados como strings, enquanto estados enum válidos continuam aceitos e sujeitos ao invariante `status ↔ revoked_at`.

**R1-F2 — ENCERRADO**
O retry de revoke não ordena mais histórico por `(created_at, UUID)`. O `MemoryDeviceRepository`, sob lock, preserva a ordem de inserção dos lifecycles; reprodução independente com clock fixo e UUIDs adversariais confirmou que o retry retorna o segundo/último binding revogado. Histórico e isolamento por `device_id` permanecem preservados.

**Parecer R1.1**
- C1-A: **APROVADO**.
- R1-F1/F2: **ENCERRADOS**.
- C1-B: **LIBERADO para execução conforme o plano C1-B/B1..B10**.
- C1-C continua bloqueado até R2.
- Em C1-B, PostgreSQL efêmero/local real com migration 019 aplicada em ambiente de teste é gate obrigatório; qualquer skip desses testes bloqueia R2.
- Migration 019 pode ser criada e aplicada somente em ambiente local/efêmero de teste; **produção continua proibida**.
- Push, deploy, WebPilot real no Cloud, SessionLease real, `source=cloud`, failover/failback e cutover continuam proibidos.

**Próximo passo autorizado:** Executor executa somente C1-B com TDD, incluindo migration 019 local, repository Postgres/Supabase, service/model de credencial, endpoints Desktop-only e autoridade administrativa de realm conforme plano; roda obrigatoriamente Postgres real efêmero/local + MockTransport + regressões; registra RED/GREEN e para para **R2 independente com o working tree sem commit**. Não iniciar C1-C. **Somente após R2 APROVADO** será autorizado o commit do diff exatamente revisado.

### C1-B — Executor; working tree sem commit (2026-10-08)

**Status:** **PRONTO PARA R2 INDEPENDENTE**. B1→B10 concluídos; todos os gates obrigatórios estão verdes. C1-C não foi iniciado.

**Entrada e política de checkpoint**
- branch/worktree: `feat/spec027-cloud` em `/home/ciro/dev/prog/alertamaritimoAPI/.worktrees/spec027-cloud`;
- HEAD aprovado de entrada permanece **`570ba3513b2dc34513f80dcab48e722405588f00`** (`docs: aprova c1-a em r1.1`);
- duas alterações documentais já existiam no working tree ao iniciar C1-B: handoff + plano atualizando a política para **revisão antes de commit**; foram preservadas;
- nenhum `git add`, nenhum commit C1-B, nenhum push e nenhum deploy;
- todo o C1-B funcional, testes, migration 019 e este registro permanecem no working tree para revisão exata em R2.

**B1→B2 — migration 019 RED→GREEN**
- RED inicial: `test_cloud_binding_sql.py` falhou com `FileNotFoundError` porque `019_cloud_binding_realm.sql` não existia.
- GREEN: criada **somente localmente/efêmera** `api/supabase/migrations/019_cloud_binding_realm.sql`.
- três tabelas: `webpilot_auth_realms`, `webpilot_auth_realm_devices`, `cloud_bindings`;
- FKs para device/realm, PK membership `(realm_id, device_id)`, check temporal, `credential_version > 0`, coerência `status ↔ revoked_at` e unique parcial de binding ativo/device;
- `lifecycle_order` persistente evita usar UUID/timestamp como ordenação de lifecycle;
- RLS habilitado, sem policy pública;
- funções `SECURITY DEFINER` com `SET search_path = pg_catalog, public`, objetos `public.*` qualificados;
- EXECUTE revogado de `PUBLIC`, `anon`, `authenticated` e concedido somente a `service_role`;
- RPCs atômicas/idempotentes para authorize/revoke membership, activate/deactivate realm e ensure/rotate/revoke binding;
- hardening concorrente adicional: RED estrutural exigiu tratamento explícito de `unique_violation` no `ensure_cloud_binding`; GREEN converte corrida para idempotência quando realm/hash coincidem ou `cloud_binding_conflict` quando divergem;
- migration **não aplicada em produção**; executada somente no PostgreSQL Docker efêmero de teste.

**B3→B4 — repositories Postgres/Supabase RED→GREEN**
- Supabase RED: **2 falhas** por ausência dos métodos Cloud/realm.
- PostgreSQL RED real: migration 019 aplicou com sucesso e houve **3 falhas** por métodos de repository ausentes.
- implementados `PostgresDeviceRepository`, `SupabaseDeviceRepository` e contrato agregado `AlertaRepository` para realm, membership e CloudBinding.
- Postgres usa RPCs SQL transacionais; Supabase usa REST/RPC com server key e `MockTransport` nos testes.
- conflitos são tipados; falhas de persistência são sanitizadas e não propagam detalhes do backend.
- repositories recebem/persistem somente `credential_hash`; plaintext da Cloud credential não entra nos backends.
- `MemoryDeviceRepository` recebeu as mesmas operações administrativas e preserva ordem de lifecycle por inserção, sem UUID como desempate temporal.

**B5→B6 — Cloud credential/service RED→GREEN**
- RED inicial: modelo/service CloudBinding ausentes; RED subsequente identificou vazamento do input inválido no `ValidationError` do Pydantic.
- GREEN: `SecretStr` + `ConfigDict(hide_input_in_errors=True)`, regex estrita `^[A-Za-z0-9_-]{43,86}$`, sem trim/coerção silenciosa.
- `secrets.token_urlsafe(32)`/43 chars validado como formato canônico; máximo 86 permitido.
- vazio, `<43`, `>86`, whitespace, padding `=` e caracteres fora de base64url são rejeitados antes do hash/repository.
- service faz `hash_secret()` antes da persistência; ensure same realm+secret é idempotente; ensure diferente conflita sem mutação; rotate same secret não incrementa; rotate new incrementa uma vez; revoke é idempotente.
- responses não contêm `credential` nem `credential_hash`.

**B7→B8 — endpoints Desktop-only RED→GREEN**
- RED inicial: rotas retornavam 404 porque ainda não existiam.
- implementados somente `GET/PUT /api/v1/devices/{device_id}/cloud-binding`, `POST .../rotate` e `DELETE /api/v1/devices/{device_id}/cloud-binding`.
- somente esquema `Device` autentica; Bearer/view token e secret incorreto retornam 401.
- GET usa `authenticate_status()`: com secret correto e `enabled=false`, metadata segue disponível com `device_enabled=false` e `usable=false`.
- mutações usam `authenticate()`: `enabled=false` é fail-closed.
- realm/membership sem autoridade: 403; binding ausente: 404; conflito: 409; credential inválida: 422.
- persistence failure: 503, inclusive falha durante mutação, sem estado parcial.
- testes capturam logs HTTP e confirmam ausência de DEVICE_SECRET/Cloud credential; responses e reprs também não expõem plaintext/hash.
- nenhuma rota PWA/Mobile foi criada.

**B9 — autoridade administrativa de realm**
- RED inicial: `scripts.admin_cloud_realm` ausente.
- GREEN: ensure/create realm ativo por default, activate/deactivate idempotentes, authorize/revoke/reauthorize membership idempotentes, sem duplicação e com timestamps coerentes.
- usa credencial administrativa/backend já existente; imprime somente IDs/status; nunca cria CloudBinding nem Cloud credential.
- `_DEPENDENCY_PROBES` de `admin_device.py` agora protege `webpilot_auth_realm_devices.device_id` e `cloud_bindings.device_id` contra compensação/deleção indevida.
- **`authenticate_cloud_binding()` não existe nem é chamado**; continua reservado exclusivamente ao C1-C.

**B10 — gates finais**
- testes C1-A/C1-B direcionados locais: **39 passed / 0 skipped / 0 failed**.
- `tests/unit + tests/integration/test_cloud_binding_api.py`: **382 passed / 0 skipped / 0 failed**.
- PostgreSQL C1-B real efêmero (`test_cloud_binding_postgres.py`): **4 passed / 0 skipped / 0 failed**.
- no PostgreSQL real: migration 019 aplicada; lifecycle realm/membership/binding; fail-closed; RLS ativo; nenhuma policy pública; EXECUTE negado a `anon/authenticated` e permitido a `service_role`; constraints exercitadas.
- `make test` local: **511 passed / 38 skipped / 0 failed**; skips são integrações PostgreSQL fora do container sem `TEST_POSTGRES_DSN`.
- `make test-all` final no Docker/PostgreSQL 16 real: **549 passed / 0 skipped / 0 failed**.
- `git diff --check`: **PASS**.
- staged changes: **nenhuma** (`git diff --cached --stat` vazio).
- branch remota `origin/feat/spec027-cloud`: inexistente.

**Dívida pré-existente do harness descoberta e corrigida apenas para viabilizar B10**
- primeira execução de `make test-all` no C1-B: **524 passed / 25 failed**.
- uma worktree temporária detached no HEAD limpo de entrada `570ba35` reproduziu os **mesmos 25 failures / 499 passes**, provando que não eram regressão do C1-B.
- causa: fixtures PostgreSQL legadas montavam schemas parciais incompatíveis com o repository já existente no HEAD.
- alinhamento mínimo de oito fixtures: migration 018 em 8 fixtures, migration 017 em 4, migration 013 em 2 e `display_code` explícito válido no helper antigo de `tracked_vessels`.
- esses ajustes alteram somente o harness de testes; nenhum runtime/contrato produtivo foi modificado por esse saneamento.
- após o alinhamento, `make test-all` passou integralmente em **549/549**.
- worktree temporária de baseline removida; nenhum branch foi criado para essa prova.

**Arquivos C1-B no working tree**
- migration local `019_cloud_binding_realm.sql`;
- repositories `cloud_bindings.py`, `postgres.py`, `supabase.py`, `memory.py`, composição `events.py`;
- modelos/service/errors CloudBinding;
- router/endpoint Desktop-only;
- `admin_cloud_realm.py` e guard de compensação em `admin_device.py`;
- testes SQL, PostgreSQL real, Supabase MockTransport, credential/service, API e admin;
- ajustes mínimos das oito fixtures PostgreSQL legadas descritos acima;
- documentação do checkpoint/política de commit ainda sem commit.

**Segurança e fronteiras**
- secrets fora de response/log/repr/error;
- nenhum secret/cookie real usado;
- `enabled=false` preservado fail-closed para mutações;
- migration 019 aplicada **somente** em PostgreSQL local/efêmero de teste;
- nenhuma migration de produção, `prod-migrate`, push ou deploy;
- nenhum WebPilot real no Cloud, SessionLease real, `source=cloud`, failover/failback ou cutover;
- C1-C não iniciado e `authenticate_cloud_binding()` não antecipado;
- processo Shadow não foi manipulado; última observação mostrou `uv run python -m alertam`/Python ativos nos PIDs 14865/14873.

**Estado para revisão**
- HEAD continua `570ba3513b2dc34513f80dcab48e722405588f00`;
- working tree contém todo o diff funcional/testes/documentação C1-B;
- **nenhum arquivo staged e nenhum commit C1-B foi criado**, conforme política vigente;
- se R2 encontrar achados, corrigir o mesmo working tree e retornar para re-revisão ainda sem commit;
- somente após **R2 APROVADO** poderá ser feito o commit exato do diff revisado;
- C1-C permanece bloqueado.

**PARECER SOLICITADO:** **R2 independente** sobre o working tree C1-B completo. Nenhuma etapa C1-C iniciada.

### R2 independente — revisão C1-B (2026-10-08)

**Resultado:** CORREÇÕES OBRIGATÓRIAS. O C1-B está amplamente aderente ao plano, com gates e regressões verdes, mas dois defeitos de robustez/atomicidade precisam ser corrigidos antes de liberar C1-C ou autorizar commit.

**Evidência independente**
- Working tree revisado diretamente sobre HEAD aprovado de entrada `570ba3513b2dc34513f80dcab48e722405588f00`; nenhum commit/stage C1-B foi criado.
- `git diff --check`: PASS.
- testes C1-B direcionados independentes: **21/21 passed**.
- `make test-all` independente com PostgreSQL 16 real: **549 passed / 0 skipped / 0 failed**.
- ajustes das oito fixtures PostgreSQL legadas foram revisados: apenas completam migrations já exigidas pelo repository atual e, em `tracked_vessels`, fornecem `display_code` válido; não foi identificado enfraquecimento de assertion/expectativa funcional.
- Migration 019 permanece somente local; nenhum push/deploy/prod-migrate/WebPilot real/SessionLease/source=cloud/failover/cutover.

**R2-F1 — mapping de RPC Supabase malformado escapa sem sanitização**
`_cloud_rpc_row()` valida apenas que o HTTP 200 contenha uma lista com um dict; a conversão do dict para `WebPilotAuthRealmRecord`, `RealmDeviceAuthorizationRecord` ou `CloudBindingRecord` acontece fora do bloco que traduz falhas de persistência. Assim, um payload 200 estruturalmente incompleto pode vazar `ValueError`/`KeyError` cru para service/API/admin em vez de `PersistenceUnavailableError` sanitizado.

**Reprodução independente:** MockTransport retornando `[{'unexpected':'shape'}]` produziu:
- `rotate_cloud_binding` → `ValueError('Timestamps de binding ausentes.')`;
- `revoke_cloud_binding` → `ValueError('Timestamps de binding ausentes.')`;
- `authorize_realm_device` → `ValueError('authorized_at ausente.')`;
- `set_webpilot_auth_realm_active` → `ValueError('Timestamps de realm ausentes.')`.

Isso contradiz o requisito B3/B4 de mapping seguro e persistence error sanitizado.

**Critério de aceite R2-F1:** TDD RED cobrindo HTTP 200/RPC malformado para binding, realm e membership; todos os erros de mapping/parsing de respostas persistidas devem sair do repository como `PersistenceUnavailableError`, sem detalhes do backend/payload. Não esconder `CloudBindingConflictError` tipado. Cobrir ensure/rotate/revoke e operações administrativas relevantes.

**R2-F2 — corrida administrativa permite criar binding ativo após a membership já ter sido revogada**
O plano exige explicitamente que o mesmo RPC revalide `devices.enabled`, realm ativo e membership ativa imediatamente antes da mutação, porque o check HTTP/service não é autoridade suficiente contra corrida administrativa. O `ensure_cloud_binding()` atual faz a checagem de autoridade e depois, em instruções separadas, consulta/insere em `cloud_bindings`; não há lock/revalidação que serialize a autoridade com a mutação.

**Reprodução independente em PostgreSQL 16 real:** foi instalado apenas no banco efêmero um trigger de teste que pausa exatamente o INSERT de `cloud_bindings` por advisory lock. A chamada `ensure_cloud_binding()` passou pelas checagens, ficou pausada no INSERT; em outra transação a membership foi revogada e commitada; ao liberar o INSERT, o RPC retornou linha e persistiu **1 binding ativo**, enquanto `revoked_at` da membership já estava preenchido.

Resultado observado:
- `ENSURE_PAUSED_AT_INSERT=True`;
- `MEMBERSHIP_REVOKED=True`;
- `ENSURE_RESULT_IS_ROW=True`;
- estado final: membership revogada + `(1, True)` para count/active binding.

**Critério de aceite R2-F2:** criar RED de concorrência real em PostgreSQL efêmero e corrigir a autoridade transacional dos RPCs de binding. A solução deve serializar/revalidar `device enabled`, `realm active` e `membership active` no ponto da mutação, de modo que uma mudança administrativa concorrente tenha ordem linear clara e nunca resulte em mutação autorizada depois da revogação efetiva. Revisar **ensure, rotate e revoke**, não apenas ensure. Preferir row locks/SQL atômico ou mecanismo equivalente; não confiar somente no pre-check do service. Adicionar teste real que reproduza ao menos a corrida membership revoke vs ensure e testes proporcionais para os outros RPCs/autoridades afetados.

**Demais pontos R2**
- contrato de credencial/SecretStr e redaction: **aceitos**;
- endpoints Desktop-only, GET status com disabled e mutações fail-closed: **aceitos no escopo atual**;
- migration 019: constraints, RLS, grants/revokes e lifecycle_order: **aceitos**, condicionados à correção R2-F2 de atomicidade;
- Postgres real e MockTransport: gates executados e verdes;
- harness legado: saneamento **aceito**;
- C1-C permanece **BLOQUEADO**.

**Próximo passo autorizado:** Executor corrige somente R2-F1 e R2-F2 com TDD no mesmo working tree, ainda **sem commit/stage**; reroda testes direcionados, PostgreSQL real (incluindo teste de concorrência), `make test-all` e `git diff --check`; atualiza este checkpoint e para para **R2.1 independente**. Não iniciar C1-C, não push/deploy/prod-migrate e não tocar no Shadow.

### Correções R2-F1/F2 — Executor (2026-10-08)

**Status:** PRONTO PARA R2.1 INDEPENDENTE. Escopo restrito a R2-F1 e R2-F2; C1-C permanece bloqueado. Working tree segue sem commit e sem stage.

**R2-F1 — sanitização Supabase — RED→GREEN**
- RED adicionado em `test_supabase_cloud_binding_repository.py` para HTTP 200 com payload estruturalmente malformado em:
  - `set_webpilot_auth_realm_active`;
  - `authorize_realm_device`;
  - `revoke_realm_device`;
  - `ensure_cloud_binding`;
  - `rotate_cloud_binding`;
  - `revoke_cloud_binding`.
- RED observado: **6 falhas**, com `ValueError` cru escapando dos mappers de realm, membership e binding, reproduzindo R2-F1.
- GREEN mínimo: introduzido `_mapped_cloud_rpc()`; `_cloud_rpc_row()` continua responsável por transporte/HTTP e preserva `CloudBindingConflictError` tipado, enquanto apenas `KeyError/TypeError/ValueError` de mapping/parsing são convertidos em `PersistenceUnavailableError`.
- MockTransport final: **8 passed / 0 skipped / 0 failed**.
- payload de backend usado no RED não aparece na mensagem de `PersistenceUnavailableError`.

**R2-F2 — atomicidade administrativa — RED→GREEN**
- RED real em PostgreSQL 16 efêmero com trigger de teste que pausa a escrita em `cloud_bindings` por advisory lock.
- Três corridas reproduzidas antes da correção:
  - `ensure_cloud_binding` × revoke de membership;
  - `rotate_cloud_binding` × deactivate de realm;
  - `revoke_cloud_binding` × `devices.enabled=false`.
- RED observado: **3 falhas**; em todos os casos a alteração administrativa concluía enquanto a mutação do binding permanecia pausada.
- GREEN: `ensure`, `rotate` e `revoke` agora leem/revalidam sob `FOR UPDATE` e mantêm locks de transação sobre:
  - linha de `devices` e `enabled`;
  - linha de `webpilot_auth_realms` e `active`;
  - linha de `webpilot_auth_realm_devices` e `revoked_at`.
- A mutação só prossegue após essas três autoridades serem válidas sob lock; mudanças administrativas concorrentes têm ordem linear clara:
  - se a alteração administrativa vencer antes do lock, a RPC observa o novo estado e falha fechada;
  - se a RPC adquirir o lock primeiro, a alteração administrativa espera o commit da mutação.
- `ensure` mantém o tratamento de `unique_violation` para idempotência/conflito concorrente.
- `rotate` e `revoke` também foram revisados, não apenas `ensure`.
- PostgreSQL real final: **7 passed / 0 skipped / 0 failed**, incluindo os três novos testes de concorrência.

**Gates após R2-FIX**
- testes C1-B direcionados locais: **45 passed / 0 skipped / 0 failed**;
- Supabase MockTransport: **8 passed / 0 skipped / 0 failed**;
- PostgreSQL real `test_cloud_binding_postgres.py`: **7 passed / 0 skipped / 0 failed**;
- `make test-all` com PostgreSQL real: **558 passed / 0 skipped / 0 failed**;
- `git diff --check`: PASS;
- staged files: **0**;
- HEAD permanece `570ba3513b2dc34513f80dcab48e722405588f00`.

**Fronteiras preservadas**
- nenhum commit e nenhum stage;
- C1-C não iniciado e `authenticate_cloud_binding()` continua ausente;
- nenhuma migration aplicada em produção;
- nenhum push/deploy/prod-migrate;
- nenhum WebPilot real, SessionLease real, `source=cloud`, failover/failback ou cutover;
- Shadow não foi manipulado; permaneceu ativo durante a observação.

**PARECER SOLICITADO:** **R2.1 independente** sobre R2-F1/R2-F2 e o working tree C1-B completo. Nenhuma etapa C1-C iniciada.

### R2.1 independente — encerramento do C1-B (2026-10-08)

**Resultado:** APROVADO. R2-F1 e R2-F2 encerrados; C1-B aprovado para commit exato do working tree revisado. C1-C só pode começar depois desse commit e com o working tree limpo.

**Evidência independente**
- Working tree revisado diretamente sobre HEAD aprovado de entrada `570ba3513b2dc34513f80dcab48e722405588f00`; nenhum commit/stage C1-B existia durante a revisão.
- Probe independente Supabase com HTTP 200 malformado confirmou `PersistenceUnavailableError` sanitizado para set realm, authorize/revoke membership e ensure/rotate/revoke binding; payload sensível não apareceu no erro.
- `CloudBindingConflictError` permanece tipado em resposta de conflito.
- Testes dirigidos unit/API independentes após a correção: **27/27 passed**.
- PostgreSQL 16 real, `test_cloud_binding_postgres.py`: **7/7 passed**, incluindo as três corridas administrativas.
- `make test-all` independente: **558 passed / 0 skipped / 0 failed**.
- `git diff --check`: PASS; staged files: 0.
- Migration 019 permanece somente no working tree/local e foi exercitada apenas em PostgreSQL efêmero; nada foi aplicado em produção.

**R2-F1 — ENCERRADO**
`SupabaseDeviceRepository._mapped_cloud_rpc()` agora encapsula o mapping/parsing das respostas RPC e converte `KeyError`/`TypeError`/`ValueError` em `PersistenceUnavailableError`, preservando o erro de conflito tipado produzido pela camada de transporte/RPC. A reprodução independente que antes vazava `ValueError` agora retorna apenas erro sanitizado.

**R2-F2 — ENCERRADO**
`ensure_cloud_binding`, `rotate_cloud_binding` e `revoke_cloud_binding` agora adquirem locks transacionais e revalidam `devices.enabled`, `webpilot_auth_realms.active` e membership ativa antes da mutação. Os testes concorrentes reais demonstram linearização: quando a RPC de binding já adquiriu a autoridade, a mutação administrativa concorrente espera; quando a autoridade já está revogada/inativa antes da RPC, os testes fail-closed existentes continuam bloqueando a mutação.

**Parecer R2.1**
- C1-B: **APROVADO**.
- R2-F1/F2: **ENCERRADOS**.
- Commit do checkpoint: **AUTORIZADO agora**, contendo exatamente o diff revisado neste working tree, inclusive migration/testes/documentação e o saneamento de fixtures já aceito.
- Mensagem sugerida: `feat(cloud): add binding persistence and desktop admin API`.
- Após o commit, confirmar working tree limpo e registrar o novo SHA como base de entrada do C1-C.
- C1-C: **LIBERADO somente após** esse commit; executar conforme Steps C1→C6 do plano e parar para R3 independente, novamente sem commit.
- Migration 019 em produção, push, deploy, WebPilot real no Cloud, SessionLease real, `source=cloud`, failover/failback e cutover continuam proibidos.

**Próximo passo autorizado:** Executor deve (1) fazer um único commit local do diff C1-B exatamente aprovado; (2) confirmar `git status` limpo e registrar SHA; (3) executar somente C1-C com TDD no mesmo branch/worktree; (4) deixar o C1-C sem commit/stage e parar para **R3 independente**. Não iniciar C1-D.

### C1-C — Base de entrada após commit C1-B (2026-10-08)

- C1-B aprovado em R2.1 foi commitado exatamente como revisado em **`a4e1af85872308a907afb85d53f8cebac3dae6b5`** — `feat(cloud): add binding persistence and desktop admin API`.
- `git status` imediatamente após o commit: **limpo**.
- Este SHA é a **base aprovada de entrada do C1-C**.
- C1-C será entregue novamente sem commit/stage e deve parar em R3 independente.

### C1-C — Executor; working tree sem commit (2026-10-08)

**Status:** **PRONTO PARA R3 INDEPENDENTE**. Steps C1→C6 concluídos; C1-D não iniciado.

**Base de entrada**
- C1-B aprovado em R2.1 foi commitado exatamente em `a4e1af85872308a907afb85d53f8cebac3dae6b5` — `feat(cloud): add binding persistence and desktop admin API`.
- `git status` estava limpo imediatamente após o commit.
- Esse SHA é a base aprovada do C1-C e continua sendo o HEAD; todo o C1-C permanece somente no working tree.
- nenhum commit e nenhum stage C1-C.

**C1 — RED: autoridade da Cloud credential**
- criado `tests/unit/test_cloud_binding_authorization.py`.
- RED inicial: **8/8 falhas**, todas porque `CloudBindingService.authenticate_cloud_binding()` não existia.
- casos cobertos: sucesso; hash errado; binding revogado; device disabled; realm inactive; membership revoked; persistence unavailable; deactivate/activate idempotente.
- retorno autorizado exigido sem secret/hash, somente `cloud_binding_id`, `device_id` e `realm_id`.

**C2 — GREEN: verificador central fail-closed**
- criado `AuthorizedCloudBinding`, contendo somente IDs/realm.
- criado `CloudBindingAuthorityRecord`; `credential_hash` usa `repr=False`.
- `authenticate_cloud_binding(cloud_binding_id, credential)` agora:
  - obtém uma projeção coerente de autoridade do repository;
  - exige binding `active`;
  - exige `device.enabled=true`;
  - exige realm `active=true`;
  - exige membership ativa;
  - valida credential com `verify_secret()`;
  - qualquer condição inválida nega com o mesmo erro genérico, sem revelar qual autoridade falhou;
  - `PersistenceUnavailableError` vira `PersistenceUnavailableApiError` fail-closed/503-equivalente.
- GREEN do arquivo de autorização: **8/8 passed**.
- prova B9 movida corretamente para C1-C: deactivate realm bloqueia imediatamente; activate restaura somente quando binding/device/membership continuam válidos.

**Projection de autoridade nos repositories**
- novo contrato `get_cloud_binding_authority(cloud_binding_id)`.
- Memory: projeção produzida sob o mesmo lock.
- PostgreSQL/Supabase: nova RPC backend-only `public.get_cloud_binding_authority(uuid)`, com uma única leitura de binding/device/realm/membership.
- RPC `SECURITY DEFINER`, `SET search_path = pg_catalog, public`, EXECUTE revogado de `PUBLIC/anon/authenticated` e concedido somente a `service_role`.
- nenhuma rota HTTP/PWA/Mobile foi criada para essa RPC/projeção.
- mapper Supabase ganhou RED adicional: string `"false"` não pode ser convertida implicitamente para truthy. RED falhou como esperado; GREEN exige `bool` real para `device_enabled`, `realm_active` e `membership_active`.

**C3 — isolamento cross-device**
- criado `tests/integration/test_cloud_binding_adversarial.py`.
- secret do device A contra path B retorna 401 antes de leitura/mutação;
- PUT/GET de B com secret A não revela se B possui binding: mesma resposta de autenticação inválida usada para device inexistente;
- rotate/delete de B com secret A não alteram B;
- credential A contra `binding_id` B, e vice-versa, são negadas;
- binding/version/status do outro device permanecem intactos.

**C4 — cross-realm e revogações**
- device sem membership ativa não binda outro realm;
- deactivate realm invalida autenticação sem apagar binding/membership;
- deactivate/activate repetidos permanecem idempotentes;
- reactivate restaura uso somente com demais autoridades válidas;
- revoke membership invalida imediatamente e revoke repetido preserva timestamp;
- reauthorize restaura a mesma associação e torna binding ainda ativo utilizável;
- `enabled=false` invalida imediatamente; re-enable restaura apenas quando realm/membership/binding permanecem válidos;
- binding explicitamente revogado permanece inutilizável após re-enable e realm deactivate/reactivate.

**C5 — logs/serialization**
- testes provam ausência de plaintext Cloud credential, `credential_hash`, DEVICE_SECRET e Supabase server key em reprs/exceptions/logs exercitados;
- `AuthorizedCloudBinding` não contém campo de credential/hash;
- `CloudBindingAuthorityRecord` oculta hash no repr;
- payload RPC Supabase malformado continua sanitizado como `PersistenceUnavailableError`.

**C6 — GREEN/refactor**
- implementação limitada ao serviço/repositories/migration 019 local e testes C1-C;
- nenhuma alteração em `cloud/`, WebPilot, SessionLease, snapshot, source arbitration, failover/failback ou cutover;
- contrato C1 do repository foi atualizado somente para reconhecer `get_cloud_binding_authority`.

**Gates C1-C**
- autorização unitária: **8 passed / 0 skipped / 0 failed**;
- adversarial cross-device/cross-realm/logs: **3 passed / 0 skipped / 0 failed**;
- conjunto direcionado C1-C/C1-B relacionado após hardening final: **58 passed / 0 skipped / 0 failed**;
- PostgreSQL 16 real `test_cloud_binding_postgres.py`: **7 passed / 0 skipped / 0 failed**, incluindo projection/grants e as corridas administrativas já aprovadas no C1-B;
- `make test-all` final, após o último hardening Supabase: **571 passed / 0 skipped / 0 failed**;
- migration 019 exercitada somente em PostgreSQL efêmero/local; **não aplicada em produção**.

**Fronteiras preservadas**
- C1-D não iniciado;
- nenhum commit/stage C1-C;
- nenhum push/deploy/prod-migrate;
- nenhum WebPilot real no Cloud;
- nenhum SessionLease real;
- nenhum `source=cloud`;
- nenhum failover/failback;
- Shadow não foi manipulado e permaneceu ativo durante as observações.

**PARECER SOLICITADO:** **R3 independente** sobre o working tree C1-C baseado em `a4e1af85872308a907afb85d53f8cebac3dae6b5`. Não iniciar C1-D antes do parecer.

### R3 independente — encerramento do C1-C (2026-10-08)

**Resultado:** APROVADO. O working tree C1-C baseado em `a4e1af85872308a907afb85d53f8cebac3dae6b5` atende ao plano, aos gates de isolamento/fail-closed e às fronteiras de escopo.

**Evidência independente**
- Working tree revisado sem commit/stage; HEAD permaneceu `a4e1af85872308a907afb85d53f8cebac3dae6b5` durante a revisão.
- Diff C1-C restrito a service/repositories, migration 019 local, testes de autoridade/adversariais e documentação; nenhuma alteração em `cloud/`, frontend, rotas operacionais, WebPilot, SessionLease, snapshots ou source arbitration.
- Testes dirigidos C1-C independentes: **32/32 passed**.
- PostgreSQL 16 real `test_cloud_binding_postgres.py`: **7/7 passed**.
- `make test-all` independente: **571 passed / 0 skipped / 0 failed**.
- `git diff --check`: PASS; staged files: 0.
- Shadow permaneceu ativo nos PIDs observados 14865/14873.

**Autoridade e fail-closed**
- `authenticate_cloud_binding()` usa uma projeção única de autoridade e só autoriza binding ACTIVE com device enabled, realm active, membership ativa e credential válida.
- persistence unavailable é convertido para erro 503-equivalente fail-closed.
- `AuthorizedCloudBinding` retorna somente binding/device/realm; hash não é exposto.
- `CloudBindingAuthorityRecord.credential_hash` está oculto de `repr`.
- Supabase rejeita flags de autoridade que não sejam booleanas reais; payload malformado continua sanitizado.

**Isolamento e revogações**
- cross-device por path/secret e por binding_id/credential: aprovado.
- cross-realm sem membership: bloqueado.
- deactivate/activate de realm, revoke/reauthorize membership e enabled=false/re-enable respeitam imediatamente a autoridade corrente.
- binding explicitamente revogado não volta a ser utilizável por re-enable ou reactivate.
- nenhuma evidência de bypass por conflito ou existência de outro device foi encontrada.

**Persistência/SQL**
- `get_cloud_binding_authority(uuid)` está backend-only, `SECURITY DEFINER`, com `search_path` fixo, EXECUTE revogado de PUBLIC/anon/authenticated e concedido a `service_role`.
- PostgreSQL mapper e Supabase mapper convertem status para `CloudBindingStatus`; projection real foi exercitada no banco efêmero.
- migration 019 continua sem aplicação em produção.

**Parecer R3**
- C1-C: **APROVADO**.
- Commit do checkpoint: **AUTORIZADO agora**, contendo exatamente o diff C1-C revisado.
- Mensagem sugerida: `test(cloud): enforce binding authority and isolation`.
- Após o commit, confirmar working tree limpo e registrar o novo SHA como base de entrada do C1-D.
- C1-D: **LIBERADO somente após** esse commit, conforme Steps D1→D5 do plano.
- Desktop runtime continua sem alteração por default; só criar cliente Desktop se surgir necessidade explícita durante R4.
- Push, deploy, migration produção, WebPilot real no Cloud, SessionLease real, `source=cloud`, failover/failback, cutover e C2 continuam proibidos.

**Próximo passo autorizado:** Executor deve (1) fazer um único commit local do diff C1-C exatamente aprovado; (2) confirmar `git status` limpo e registrar SHA; (3) executar somente C1-D; (4) manter todo o C1-D sem commit/stage; (5) rodar contract tests, `make cloud-test`, `make cloud-smoke` se Docker disponível, `make test`, frontend tests, `make test-all`, `make migrate-list`, security audit e `git diff --check`; (6) atualizar este documento e parar para **R4 independente**. Não iniciar C2-P/C2.

### C1-D — Executor; integração local e encerramento C1 (2026-10-08)

**Status:** **PRONTO PARA R4 INDEPENDENTE**. Steps D1→D5 concluídos. C2-P/C2 não iniciados. Working tree permanece sem commit/stage.

**Base aprovada de entrada**
- C1-C aprovado em R3 foi commitado exatamente como revisado em **`25485bba0143fd0c1659a88df89743db629951c2`** — `test(cloud): enforce binding authority and isolation`.
- `git status` imediatamente após o commit: **limpo**.
- esse SHA é a base aprovada do C1-D e continua sendo o HEAD; todo o C1-D permanece somente no working tree.

**Cadeia funcional C1**
- base reconciliada API/PWA: `23a78bebdf46062eef937966101246567cd963de`;
- C1-A domínio: `36b3c9b` — `feat(cloud): define binding and realm domain contracts`;
- C1-A hardening R1: `17afb4e` — `fix(cloud): harden c1-a binding invariants`;
- C1-A aprovação R1.1 registrada em `570ba35`;
- C1-B: **`a4e1af85872308a907afb85d53f8cebac3dae6b5`** — `feat(cloud): add binding persistence and desktop admin API`;
- C1-C: **`25485bba0143fd0c1659a88df89743db629951c2`** — `test(cloud): enforce binding authority and isolation`;
- C1-D: **sem commit**, aguardando R4 independente.

**D1 — contract RED→GREEN para Desktop**
- criado `api/tests/contract/test_cloud_binding_desktop_contract.py`;
- o contrato prova:
  - endpoints apenas em `/api/v1/devices/{device_id}/cloud-binding` e `.../rotate`;
  - nenhuma rota `/api/v1/mobile/*` de CloudBinding;
  - `credential` marcada como `writeOnly: true` no OpenAPI;
  - response estável com exatamente `cloud_binding_id/device_id/realm_id/credential_version/status/device_enabled/realm_authorized/usable`;
  - nenhuma response contém `credential` ou `credential_hash`;
  - códigos HTTP runtime previsíveis para 401/403/404/409/422/503.
- RED real: **1 falha / 3 passes**; o runtime já devolvia os códigos corretos, mas o OpenAPI documentava apenas 200/422.
- GREEN mínimo: adicionada apenas documentação `responses={...}` às quatro operações Desktop em `api/app/api/v1/cloud_bindings.py`; nenhum comportamento runtime ou contrato Mobile/PWA foi alterado.
- contract tests finais: **4 passed / 0 skipped / 0 failed**.

**D2 — isolamento do Cloud shell**
- `make cloud-test`: **9/9 passed**;
- `make cloud-smoke`: PASS;
- smoke confirmou:
  - `/healthz=200`;
  - `/readyz=200`;
  - UID **10001**;
  - mounts vazios;
  - restart saudável;
  - filesystem diff vazio;
  - logs sanitizados.
- testes do shell continuam provando runtime sem dependências operacionais e contrato HTTP apenas health/readiness.
- nenhuma importação/rota C1 foi adicionada ao `cloud/`.

**D3 — regressões**
- `make test`: **534 passed / 41 skipped / 0 failed**;
  - skips são integrações PostgreSQL quando executadas sem `TEST_POSTGRES_DSN` no processo local;
  - o gate SQL obrigatório foi executado separadamente no container real abaixo.
- frontend:
  - primeira tentativa não iniciou os testes porque `vitest` não existia no `node_modules` da worktree;
  - executado `npm ci` usando o `frontend/package-lock.json` existente, sem alterar arquivos versionados;
  - `npm test -- --run`: **50 test files / 290 tests passed**.
- `make test-all` em PostgreSQL 16 efêmero real: **575 passed / 0 skipped / 0 failed**.
- `make migrate-list`: lista migrations **001→019**, incluindo `019_cloud_binding_realm.sql`.
- migration 019 foi exercitada somente pelo ambiente PostgreSQL local/efêmero de testes.
- **migration 019 NÃO foi aplicada em produção**; nenhum `prod-migrate` foi executado.
- `git diff --check 23a78be..HEAD`: PASS para todo o C1 já commitado.
- `git diff --check`: PASS para o working tree C1-D.

**Desktop / Shadow**
- nenhuma implementação Desktop runtime foi criada;
- nenhum branch Desktop SPEC027 foi criado neste checkpoint;
- checkout observado do Desktop permanece `feat/spec025-plan5-shadow-evidence-gate@9e5b5e1a33cb7d61db200866aea683a6334de922`;
- Shadow permaneceu ativo nos processos observados PID 14865/14873;
- Shadow não foi parado, reiniciado, sinalizado ou modificado;
- Selenium permanece a fonte oficial/operacional; C1 não faz cutover de coleta.

**D4 — security audit do diff C1 completo**
- auditados termos `cookie|sessionlease|source=cloud|device_secret|credential_hash|authorization` no diff desde `23a78be`;
- ocorrências funcionais são apenas as esperadas:
  - parsing do header `Authorization: Device ...`;
  - `credential_hash` hash-only em repository/SQL;
  - asserts de redaction.
- únicos valores secret-like adicionados são **sintéticos de teste**, como `desktop-secret[-a/-b]`, `view-secret` e `sb_secret_backend`; nenhum valor real foi identificado em fixture/handoff.
- nenhum cookie WebPilot, SessionLease, `source=cloud`, WebPilot token ou material de sessão foi introduzido.
- contract test confirma nenhuma rota CloudBinding Mobile/PWA.
- migration 019:
  - RLS permanece habilitado;
  - nenhuma `CREATE POLICY` pública;
  - EXECUTE das RPCs revogado de PUBLIC/anon/authenticated;
  - EXECUTE concedido somente a `service_role`.
- credential continua write-only; metadata/serialization/logs permanecem sem plaintext/hash.
- Cloud shell continua sem WebPilot, SessionLease, CloudBinding operacional, snapshot ou source arbitration.

**D5 — encerramento C1**
- C1 entrega apenas realm persistente, membership administrativa, CloudBinding persistente, credential própria hash-only, endpoints Desktop-only, verificador central fail-closed, isolamento/adversarial e contratos locais.
- C1 **não entrega** Auth Broker, SessionLease, cookies WebPilot, collector Cloud, snapshots Cloud, `source=cloud`, failover/failback, eventos/push ou cutover.
- C2-P/C2 permanecem **BLOQUEADOS**; nenhuma etapa foi iniciada.
- push, deploy, migration de produção e merge da feature não foram executados.
- working tree C1-D contém somente:
  - documentação OpenAPI dos erros das rotas CloudBinding Desktop;
  - contract test Desktop;
  - este registro de encerramento.

**Estado para revisão**
- HEAD/base C1-D: **`25485bba0143fd0c1659a88df89743db629951c2`**;
- nenhum commit C1-D;
- nenhum arquivo staged;
- migration 019 não aplicada em produção;
- C2-P/C2 não iniciados.

**PARECER SOLICITADO:** **R4 independente** sobre o working tree C1-D e encerramento completo do C1. R4 não autoriza automaticamente commit/merge/push/deploy/migration produção/C2.

### R4 independente — encerramento do C1 (2026-10-08)

**Resultado:** APROVADO. C1-D atende ao plano; C1 está tecnicamente encerrado na `feat/spec027-cloud`, sujeito apenas ao commit local exato deste checkpoint. Isso não autoriza merge/push/deploy/migration produção nem C2.

**Evidência independente**
- HEAD/base durante a revisão: `25485bba0143fd0c1659a88df89743db629951c2`; working tree C1-D sem commit/stage.
- Escopo C1-D confirmado: apenas documentação OpenAPI em `cloud_bindings.py`, contract test Desktop novo e este handoff.
- Contract + integração/autoridade direcionados: **20/20 passed**.
- `make cloud-test`: **9/9 passed**.
- `make cloud-smoke`: PASS — health/readiness, UID 10001, mounts vazios, restart saudável, filesystem diff vazio e logs sanitizados.
- `make migrate-list`: migrations **001→019**, incluindo `019_cloud_binding_realm.sql`.
- frontend independente: **50 files / 290 tests passed**; houve warning React `act(...)` em teste existente, não relacionado ao C1-D e sem falha.
- `make test`: exit code 0; skips locais são os testes PostgreSQL sem `TEST_POSTGRES_DSN`, conforme desenho.
- `make test-all` independente em PostgreSQL 16 real: **575 passed / 0 skipped / 0 failed**.
- `git diff --check 23a78be..HEAD`, working tree e contract test untracked: PASS.
- nenhum arquivo staged; branch segue local sem upstream configurado.
- Shadow permaneceu ativo nos PIDs observados 14865/14873.

**Contrato Desktop / PWA**
- credential continua write-only no OpenAPI.
- response CloudBinding permanece limitada a metadata sem plaintext/hash.
- rotas CloudBinding continuam somente em `/api/v1/devices/{device_id}`; nenhuma rota Mobile/PWA foi criada.
- erros Desktop 401/403/404/409/422/503 estão documentados; cobertura runtime existente confirma 409/503 e redaction.

**Cloud shell / segurança**
- shell Cloud continua restrito a health/readiness; nenhuma dependência operacional ou rota C1 foi introduzida em `cloud/`.
- auditoria do C1 completo não encontrou SessionLease, cookie WebPilot, `source=cloud`, failover/failback ou material real de sessão em código funcional.
- ocorrências de `credential_hash` permanecem hash-only/repository/SQL/testes de redaction; valores `desktop-secret`, `view-secret` e `sb_secret_backend` são sintéticos de teste.
- migration 019 segue com RLS e RPCs backend-only aprovados nos gates anteriores e **não foi aplicada em produção**.

**Parecer R4**
- C1-D: **APROVADO**.
- C1: **TECNICAMENTE ENCERRADO**.
- Commit C1-D: **AUTORIZADO agora**, contendo exatamente o diff revisado e este parecer.
- Mensagem sugerida: `test(cloud): finalize c1 desktop contract and closure`.
- Após o commit: confirmar working tree limpo e registrar o SHA final do C1.
- C2-P: **LIBERADO somente após** esse commit; C2 implementação continua bloqueada até R5 aprovar o plano.
- Para reduzir burocracia sem perder segurança, C2-P deve propor **poucos checkpoints maiores e orientados a risco** (preferencialmente 2–3 checkpoints de execução para C2), mantendo revisão independente antes de cada commit.
- Não fazer merge da feature, push, deploy, migration produção, WebPilot real no Cloud, SessionLease real, `source=cloud`, failover/failback ou cutover por implicação desta aprovação.

**Próximo passo autorizado:** Executor deve (1) fazer um único commit local do C1-D exatamente aprovado; (2) confirmar working tree limpo e registrar SHA final do C1; (3) preparar **somente C2-P — plano executável do Auth Broker/SessionLease**, sem implementar C2; (4) desenhar reuso do coletor HTTP já validado, contrato SessionLease, publisher identity/local generation, `realm_epoch`, anti-replay, expiração/revogação, standby headless e testes/gates; (5) estruturar C2 em poucos checkpoints maiores onde seguro; (6) atualizar o handoff e parar para **R5 independente**, sem commit do C2-P até aprovação. C2 funcional não começa antes de R5.

### C1 final + C2-P — Executor (2026-10-08)

**C1 final**
- R4 aprovou o C1-D exatamente como revisado.
- commit local único do C1-D: **`61342b2ac47ffa48bfe90787b8aa2afb4bb4cda8`** — `test(cloud): finalize c1 desktop contract and closure`.
- `git status` imediatamente após o commit: **limpo**.
- esse SHA é o encerramento técnico local do C1 e a base documental do C2-P.
- nenhum merge/push/deploy/prod-migrate foi executado.

**C2-P preparado**
- plano: `docs/superpowers/plans/2026-10-08-spec027-c2-auth-broker-session-lease.md`;
- nenhum código C2 foi implementado;
- nenhum arquivo staged;
- plano organizado em **3 checkpoints maiores**, conforme orientação R4:
  1. **C2-A → R6:** broker/persistência/crypto/anti-replay/endpoints;
  2. **C2-B → R7:** publisher Desktop + reuso do collector + Cloud standby;
  3. **C2-C → R8:** multi-provider, sandbox sintético, restart/observabilidade e fechamento.

**Decisões centrais do plano**
- broker autoritativo na API/Postgres;
- publisher Desktop = `realm_id + device_id + publisher_id`;
- `local_generation` monotônica somente dentro do mesmo `publisher_id`;
- perda do estado local exige rotação explícita do publisher, não rollback de generation;
- `realm_epoch` monotônico é atribuído exclusivamente pelo broker e ordena sessões entre publishers;
- material de sessão é cifrado em repouso; cookies nunca ficam plaintext no banco/logs/responses;
- publisher Desktop usa Device auth + membership ativa;
- Cloud consumer usa CloudBinding e `authenticate_cloud_binding()`;
- expiração nominal, revogação e invalidação semântica são fail-closed;
- login WebPilot invalida imediatamente o epoch usado e permite no máximo um retry após mudança efetiva da lease.

**Reuso do collector**
- C2 não copia parser/HTTP/auth para `cloud/`;
- fonte canônica permanece no repo Desktop;
- estratégia proposta: buildar wheel do SHA Desktop revisado e injetá-lo no build/test local do Cloud;
- Cloud importa o núcleo headless existente;
- testes de import closure devem provar ausência de inicialização Selenium/Tk/browser;
- se o wheel completo inviabilizar o container, Executor deve **parar e pedir decisão de arquitetura**, em vez de criar fork silencioso.

**Standby / fronteira C2 × C3**
- Cloud C2 pode consumir lease e executar fetch/parse em standby com fake WebPilot/transport sintético;
- nenhum snapshot Cloud é publicado;
- nenhum `source=cloud`;
- nenhum failover/failback;
- nenhum source arbitration/fencing/hysteresis;
- nenhum evento/push Cloud;
- WebPilot real no Cloud permanece proibido por default;
- C3 só começa depois de C2 concluído e de um **C3-P** separado.

**Persistência proposta**
- próxima migration prevista: `020_webpilot_session_broker.sql`, inicialmente somente local/efêmera;
- publishers, leases cifradas e contador de realm_epoch separados;
- PostgreSQL real sem skip obrigatório em R6/R8;
- migration 020 em produção continua proibida.

**Git/worktrees**
- API/PWA/Cloud continua em `feat/spec027-cloud`, base C1 final `61342b2...`;
- Desktop `feat/spec027-cloud` só deve ser criado após R6, quando C2-B exigir publisher, em worktree separada a partir do `develop` corrente;
- checkout do Shadow nunca deve ser usado para implementação C2.

**Estado para revisão**
- C2-P contém somente documentação;
- C2 funcional permanece **BLOQUEADO até R5**;
- commit do C2-P também fica bloqueado até R5;
- merge/push/deploy/migration produção/WebPilot real/SessionLease operacional/`source=cloud`/failover/failback permanecem proibidos;
- Shadow não foi manipulado.

**PARECER SOLICITADO:** **R5 independente** sobre o C2-P e os checkpoints C2-A/B/C. Não implementar C2 antes do parecer.

### R5 independente — revisão do C2-P (2026-10-08)

**Resultado:** CORREÇÕES DOCUMENTAIS OBRIGATÓRIAS. A arquitetura macro do C2-P está aprovada em direção, incluindo os três checkpoints maiores C2-A/B/C, mas quatro contratos precisam ser fechados no plano antes de liberar implementação.

**Evidência independente**
- Base C1 final confirmada: `61342b2ac47ffa48bfe90787b8aa2afb4bb4cda8`.
- Working tree C2-P contém apenas documentação: handoff central + novo plano C2; nenhum código C2, stage, migration 020 ou alteração Desktop/Cloud foi iniciada.
- Estratégia de 3 checkpoints maiores é aceitável e preserva revisão por risco.
- Cruzamento feito com `specs/027-alertam-cloud-continuity.md` e roadmap Cloud, em especial federação multi-provider, anti-replay, `realm_epoch` e compatibilidade operacional de providers.

**R5-F1 — idempotência de `publisher_id + local_generation` não define mismatch de payload**
O plano diz que retry da mesma generation é idempotente e não incrementa `realm_epoch`, mas não define o que ocorre quando o mesmo `publisher_id + local_generation` chega novamente com cookies/`expires_at` diferentes. Apenas a unique constraint não distingue retry legítimo de reutilização conflitante.

**Critério de aceite R5-F1:** definir no contrato e nos testes de C2-A que:
- mesma publisher/generation + mesmo payload semanticamente normalizado => retorna exatamente a lease/epoch já aceita, sem nova escrita/epoch;
- mesma publisher/generation + payload diferente => conflito tipado/fail-closed, sem overwrite e sem incremento de epoch;
- concorrência de requests iguais e diferentes deve ser exercitada em PostgreSQL real;
- a equivalência deve ser comprovada server-side; se usar fingerprint persistido, não armazenar hash simples reutilizável de material secreto — usar comparação segura/decrypt ou fingerprint keyed/HMAC equivalente.

**R5-F2 — envelope criptográfico não vincula ciphertext à identidade/metadata e rotação de chave está ambígua**
O plano escolhe AEAD 'preferencialmente AES-GCM', mas ainda não fixa algoritmo, AAD nem keyring. Sem AAD, um ciphertext/nonce válido poderia ser associado por erro de persistência a outra linha/realm/publisher e ainda autenticar criptograficamente. Além disso, `key_version` não é suficiente para rotação se o runtime possuir apenas uma chave corrente.

**Critério de aceite R5-F2:** escolher explicitamente um AEAD (ex.: AES-256-GCM) e definir:
- AAD canônica que vincule ao menos versão de schema + `realm_id` + `publisher_id` + `local_generation` + metadata imutável relevante (`expires_at` normalizado e/ou lease id quando aplicável);
- troca/swap de ciphertext entre leases/realms deve falhar decrypt;
- configuração de keyring por `key_version` com uma versão ativa para encrypt e versões anteriores permitidas somente para decrypt durante rotação, ou remover a alegação de rotação compatível e declarar explicitamente a limitação;
- chave/version/AAD inválida => fail-closed; nenhum material criptográfico em log/error.

**R5-F3 — requisito obrigatório de compatibilidade entre contas/providers do mesmo realm está ausente**
A SPEC 027 exige validar ou registrar que o escopo operacional é compatível antes de permitir federação entre contas/providers diferentes. O C2-P já planeja dois publishers no mesmo realm, mas não modela esse gate.

**Critério de aceite R5-F3:** incluir um contrato explícito de compatibilidade de provider/conta antes do multi-provider:
- registrar/validar um `provider_scope`/capability profile ou mecanismo equivalente por publisher/realm, sem armazenar credencial WebPilot;
- publisher incompatível não pode tornar sua lease selecionável para o realm;
- C2-A deve definir persistência/contrato mínimo; C2-C deve testar provider compatível vs incompatível com publishers sintéticos;
- não confiar apenas na premissa verbal de que hoje todas as contas possuem a mesma permissão.

**R5-F4 — estratégia do wheel canônico ainda puxaria dependências Desktop desnecessárias para o Cloud**
O `pyproject.toml` Desktop atual declara no pacote principal `selenium`, `webdriver-manager`, `pillow` e `pyttsx3`. Instalar o wheel normalmente no Cloud traria essas dependências, embora o núcleo headless auditado (`webpilot_auth`, `webpilot_http`, parser e weather WebPilot) tenha closure majoritariamente stdlib.

**Critério de aceite R5-F4:** tornar o plano de empacotamento executável antes do C2-B:
- preferir instalar o wheel canônico **sem dependências transitivas Desktop** (`--no-deps` ou mecanismo equivalente) e declarar somente dependências realmente necessárias ao import closure headless;
- testes devem provar não apenas que Selenium/Tk/browser não inicializam, mas também que dependências operacionais de Selenium/browser não são requisito do runtime Cloud;
- se o closure headless exigir dependência não prevista, parar no checkpoint e pedir decisão; não copiar módulos nem instalar o stack Desktop inteiro silenciosamente.

**Higiene documental obrigatória antes da R5.1**
`git diff --no-index --check` no novo plano encontrou trailing whitespace nas linhas iniciais do cabeçalho Markdown. Remover esses espaços e repetir `git diff --check` cobrindo também o arquivo untracked.

**Demais pontos R5**
- fronteira C2 × C3: **APROVADA**;
- três checkpoints C2-A/R6, C2-B/R7, C2-C/R8: **APROVADOS em estrutura**;
- publisher identity + generation persistente + `realm_epoch` server-side: **APROVADOS em princípio**, condicionado a R5-F1;
- fail-closed, semantic invalidation e no máximo um retry após mudança efetiva de lease: **APROVADOS**;
- C2 sem snapshot/`source=cloud`/failover/failback: **APROVADO**;
- migration 020 somente local/efêmera: **APROVADO**;
- C2 funcional permanece **BLOQUEADO**.

**Próximo passo autorizado:** Executor corrige somente R5-F1..F4 e a higiene `diff --check` no C2-P/handoff, sem implementar C2 e sem commit/stage; atualizar este documento e parar para **R5.1 independente**. Não criar migration 020, não criar branch Desktop, não alterar `cloud/`, não push/deploy/prod-migrate e não tocar no Shadow.

### Correções R5-F1..F4 — Executor (2026-10-08)

**Status:** **PRONTO PARA R5.1 INDEPENDENTE**. Somente documentação C2-P foi alterada; C2 funcional permanece bloqueado.

**R5-F1 — idempotência completa de publisher/generation**
- chave de idempotência fixada em `publisher_id + local_generation`;
- payload é normalizado server-side antes de fingerprint/encrypt;
- cookies duplicados por nome são rejeitados e a representação é canônica;
- broker calcula `payload_fingerprint` com **HMAC-SHA-256 keyed**, usando secret dedicado distinto das chaves AEAD;
- mesmo publisher/generation + mesmo fingerprint retorna exatamente lease/epoch já aceitos, sem overwrite e sem incremento de epoch;
- mesmo publisher/generation + fingerprint diferente produz conflito tipado, sem overwrite e sem incremento de epoch;
- PostgreSQL deve lockar publisher e resolver idempotência/conflito antes de tocar no contador de `realm_epoch`;
- C2-A exige concorrência PostgreSQL real tanto para payloads iguais quanto diferentes.

**R5-F2 — envelope criptográfico fixado**
- AEAD escolhido explicitamente: **AES-256-GCM**;
- nonce aleatório de 96 bits; reuso proibido;
- AAD canônica vincula `schema_version + lease_id + realm_id + publisher_id + local_generation + expires_at_normalized + key_version`;
- ciphertext swap entre leases/realms/publishers/generations deve falhar;
- keyring definido como `key_version -> chave 32 bytes`, com exatamente uma active version para encrypt e versões anteriores decrypt-only;
- versão/chave/AAD/nonce/tag inválidos falham fechado;
- C2-A inclui testes de swap, wrong key/version/AAD e rotação decrypt-only.

**R5-F3 — compatibilidade obrigatória de provider**
- introduzido `ProviderScopeProfile` com `scope_id/schema_version/capabilities`;
- realm possui `required_provider_scope` administrativamente configurado;
- publisher apenas propõe o profile e nasce `scope_unverified`; somente operação backend/admin autenticada pode marcá-lo `verified`, sem armazenar credencial WebPilot;
- profile incompatível ou `scope_unverified` nunca torna lease selecionável/consumível;
- mudança de required scope torna publishers divergentes inelegíveis fail-closed;
- persistência mínima de scope/verification pertence ao C2-A;
- C2-C agora testa compatível×compatível e compatível×incompatível **antes** da matriz multi-provider.

**R5-F4 — wheel canônico headless sem dependências Desktop**
- mantido wheel do SHA Desktop revisado como fonte canônica;
- instalação no Cloud deve usar **`--no-deps` ou equivalente comprovado**;
- `cloud/pyproject.toml` só poderá declarar dependências realmente necessárias ao closure headless;
- ambiente de contract test deve permanecer sem Selenium, webdriver-manager, Pillow e pyttsx3, salvo dependência tecnicamente comprovada;
- testes verificam ausência do stack via inventário/import closure e ausência de inicialização Selenium/Tk/browser/UI;
- se closure headless exigir dependência imprevista, checkpoint para para decisão arquitetural; proibidos fork silencioso e instalação do stack Desktop inteiro como atalho.

**Higiene e fronteiras**
- trailing whitespace do cabeçalho do plano removido;
- nenhum código C2 implementado;
- migration 020 não criada;
- branch Desktop SPEC027 não criada;
- `cloud/` não alterado;
- nenhum commit/stage;
- push/deploy/prod-migrate/WebPilot real/SessionLease operacional/`source=cloud`/failover/failback continuam proibidos;
- Shadow não foi manipulado.

**PARECER SOLICITADO:** **R5.1 independente** sobre R5-F1..F4 e o C2-P corrigido. Não implementar C2 antes do parecer.

### R5.1 independente — encerramento do C2-P (2026-10-08)

**Resultado:** APROVADO. R5-F1..F4 encerrados; o C2-P está apto a virar commit documental e liberar somente o C2-A.

**Evidência independente**
- Base C1 permaneceu `61342b2ac47ffa48bfe90787b8aa2afb4bb4cda8` durante a revisão.
- Working tree permaneceu exclusivamente documental: handoff central + plano C2; nenhum código C2, migration 020, branch Desktop SPEC027, alteração em `cloud/` ou stage.
- `git diff --check` do conteúdo rastreado e `git diff --no-index --check` do plano untracked: PASS.
- migration `020_webpilot_session_broker.sql`: ausente, como exigido antes de R6.
- Shadow permaneceu ativo nos PIDs observados 14865/14873.

**R5-F1 — ENCERRADO**
- idempotência definida por `publisher_id + local_generation` com payload canônico server-side;
- fingerprint HMAC-SHA-256 keyed usa secret próprio, distinto do AEAD;
- mesmo payload retorna a mesma lease/epoch sem overwrite; payload diferente gera conflito tipado sem novo epoch;
- PostgreSQL real deve cobrir concorrência igual × diferente e resolver fingerprint antes de tocar no contador de `realm_epoch`;
- chave HMAC ausente/inválida é fail-closed; rotação não é implícita em C2 e exige planejamento/versionamento próprio para preservar retries históricos.

**R5-F2 — ENCERRADO**
- AEAD fixado em AES-256-GCM com nonce aleatório de 96 bits;
- AAD canônica vincula schema, lease, realm, publisher, generation, expiry normalizado e key version;
- keyring versionado possui uma active key para encrypt e versões antigas decrypt-only;
- swap de ciphertext/AAD/key/version inválida deve falhar fechado; nenhum secret/material crypto pode vazar.

**R5-F3 — ENCERRADO**
- `ProviderScopeProfile` e `required_provider_scope` tornam compatibilidade multi-provider um gate explícito;
- publisher nasce unverified e não pode autoaprovar o próprio scope;
- incompatível/unverified é inelegível para consumo;
- persistência e revalidação sob lock entram no C2-A; matriz compatível/incompatível entra no C2-C.

**Condição explícita de R6:** C2-A deve materializar uma operação backend/admin autenticada para configurar/versionar o `required_provider_scope` do realm e verificar/reclassificar publisher scope. O nome concreto pode ser endpoint, RPC+admin script ou mecanismo equivalente, mas não pode existir apenas como mutação direta de fixture/repository nos testes.

**R5-F4 — ENCERRADO**
- wheel do Desktop permanece fonte canônica, mas instalação Cloud deve usar `--no-deps` ou equivalente comprovado;
- runtime/import closure deve funcionar sem Selenium, webdriver-manager, Pillow e pyttsx3 salvo dependência tecnicamente justificada;
- se o closure headless não for executável sem o stack Desktop, C2-B para para decisão arquitetural; fork/cópia silenciosa continuam proibidos.

**Parecer R5.1**
- C2-P: **APROVADO**.
- R5-F1..F4: **ENCERRADOS**.
- estrutura de três checkpoints C2-A/R6, C2-B/R7 e C2-C/R8: **APROVADA**.
- commit documental do C2-P: **AUTORIZADO agora**, contendo exatamente o plano/handoff revisados.
- após o commit, confirmar working tree limpo e registrar SHA como base de entrada do C2-A.
- C2-A: **LIBERADO somente após** esse commit; executar apenas broker/persistência/crypto/anti-replay/endpoints do checkpoint A e parar para R6 independente, novamente sem commit.
- C2-B/C2-C permanecem bloqueados até seus gates.
- merge/push/deploy, migration 020 em produção, WebPilot real no Cloud, SessionLease operacional real, `source=cloud`, snapshot Cloud, failover/failback e cutover continuam proibidos.

**Próximo passo autorizado:** Executor deve (1) fazer um único commit local documental do C2-P exatamente aprovado; (2) confirmar working tree limpo e registrar SHA; (3) executar somente C2-A/A1→A7 com TDD; (4) criar migration 020 apenas local/efêmera; (5) cumprir PostgreSQL real sem skip, Supabase MockTransport, crypto/idempotência/provider-scope e endpoints; (6) deixar todo o C2-A sem commit/stage e parar para **R6 independente**. Não iniciar C2-B.

### C2-A — Executor; A1→A7 no working tree (2026-10-08)

**Status:** **PRONTO PARA R6 INDEPENDENTE**. C2-A concluído no working tree, sem commit/stage. C2-B não iniciado.

**Base documental de entrada**
- ao iniciar o checkpoint, o working tree já estava limpo em **`7c9f19516673c80860b144b9f421aaea0810e423`** — `docs(cloud): approve c2 auth broker plan`;
- esse commit contém exatamente o C2-P/handoff aprovados em R5.1 e foi criado pela sessão de revisão R5.1;
- por já existir o commit documental exato solicitado, o Executor **não criou commit vazio/duplicado**;
- `7c9f19516673c80860b144b9f421aaea0810e423` é a base aprovada do C2-A e permanece o HEAD atual.

**A1/A2 — domínio, anti-replay e crypto — RED→GREEN**
- RED inicial: collection errors porque `app.models.session_broker` e `app.repositories.session_broker` ainda não existiam.
- criados contratos:
  - `ProviderScopeProfile`;
  - publisher status/scope status;
  - `SessionPublisherRecord`;
  - `EncryptedSessionLeaseRecord`;
  - `SessionLeasePublishRequest` e metadata/consume responses;
  - exceções tipadas de publisher conflict, generation conflict e replay.
- canonicalização server-side:
  - cookies ordenados por nome;
  - nomes duplicados rejeitados antes de crypto;
  - `expires_at` exige timezone e é normalizado para UTC;
  - payload canônico inclui realm/publisher/generation/expiry/cookies.
- fingerprint:
  - HMAC-SHA-256 keyed;
  - key dedicada distinta das chaves AEAD;
  - fingerprint não é hash simples do cookie.
- AES-256-GCM:
  - nonce randômico 96 bits;
  - AAD com schema, lease, realm, publisher, generation, expiry e key version;
  - keyring versionado com uma active key para encrypt e antigas decrypt-only.
- testes cobrem roundtrip, nonce distinto, wrong lease/realm/expiry/key version, nonce/ciphertext swap/tamper, unknown/invalid keyring e redaction.
- Memory broker cobre scope verify/reclassify, generation local, `realm_epoch` por realm, idempotência same payload, conflito different payload, revoke/invalidate/replay.

**A3 — migration 020 + PostgreSQL real — RED→GREEN**
- RED estrutural: `020_webpilot_session_broker.sql` ausente.
- criada somente localmente/efêmera:
  - `webpilot_provider_scope_requirements`;
  - `webpilot_session_publishers`;
  - `webpilot_session_leases`;
  - `webpilot_realm_epoch_counters`.
- invariantes:
  - publisher único ativo por realm/device;
  - unique `publisher_id + local_generation`;
  - unique `realm_id + realm_epoch`;
  - generation/epoch/key/schema positivos;
  - status/temporal checks;
  - provider scope status persistido.
- RLS habilitado nas quatro tabelas; sem policy pública.
- RPCs `SECURITY DEFINER`, search path fixo e EXECUTE backend-only/service_role.
- RED PostgreSQL real inicial: migration aplicou, mas repository ainda não tinha os métodos C2.
- durante GREEN, PostgreSQL real encontrou duas ambiguidades PL/pgSQL em `ON CONFLICT (realm_id)`; corrigidas usando PK constraints explícitas.
- `accept_session_lease`:
  - locka/revalida device, realm, membership, publisher e required scope;
  - procura mesma publisher/generation **antes** do contador;
  - mesmo fingerprint retorna a lease persistida;
  - fingerprint diferente gera `session_lease_generation_conflict`;
  - generation menor/reuso após revoke/invalidate gera `session_lease_replay`;
  - só nova aceitação incrementa `realm_epoch`.
- concorrência PostgreSQL real:
  - mesmo payload/same generation → mesma lease/epoch, uma linha;
  - payload diferente/same generation → um vencedor + conflito, `last_epoch=1`;
  - rotação concorrente de publisher → exatamente um publisher ativo.
- PostgreSQL final: **5 passed / 0 skipped / 0 failed**.

**A4 — envelope crypto**
- `cryptography>=50,<51` passou a ser dependência direta da API; lock atualizado offline.
- Settings novos, todos secrets com `repr=False`:
  - `SESSION_BROKER_FINGERPRINT_KEY`;
  - `SESSION_BROKER_KEYRING`;
  - `SESSION_BROKER_ACTIVE_KEY_VERSION`.
- ausência total de configuração mantém app inicializável, mas publish/consume de lease falha fechado;
- configuração parcial/inválida falha fechado;
- keyring JSON versionado e fingerprint key base64url exigem 32 bytes.

**A5 — repositories + Supabase MockTransport**
- Postgres, Supabase e Memory implementam o mesmo `SessionBrokerRepository`.
- Supabase RED: **7 falhas** por métodos ausentes.
- GREEN MockTransport: **7 passed / 0 skipped / 0 failed**.
- cobre payloads RPC, mapping, malformed HTTP 200 sanitizado, backend failure sanitizada e erros tipados de replay/generation conflict.
- server key/backend payload não aparece em exceptions.

**A6 — endpoints e autoridade administrativa**
- endpoints Desktop-only:
  - `PUT/DELETE /api/v1/devices/{device_id}/webpilot-session-publisher`;
  - `POST /api/v1/devices/{device_id}/webpilot-session-leases`;
  - `POST /api/v1/devices/{device_id}/webpilot-session-leases/revoke`.
- endpoints Cloud backend:
  - `GET /api/v1/cloud-bindings/{cloud_binding_id}/webpilot-session-lease`;
  - `POST .../invalidate`.
- Desktop usa Device auth; Cloud usa CloudBinding credential + verificador C1.
- responses de consume/invalidate usam `Cache-Control: no-store`.
- OpenAPI documenta códigos 401/403/404/409/422/503 conforme operação.
- cookie input é `writeOnly`; nenhuma rota Mobile/PWA de SessionLease foi criada.
- operação backend/admin materializada em `scripts/admin_session_broker.py`:
  - `set-required-scope`;
  - `verify-publisher`;
  - usa o mesmo carregamento autenticado de Supabase admin/server credentials do C1;
  - imprime apenas IDs/status, sem credenciais/cookies.
- `admin_device.py` passou a tratar `webpilot_session_publishers.device_id` como dependência para compensação segura.
- publisher nasce `unverified`; only admin/backend verify/reclassify; incompatible/unverified é inelegível.
- mudança de required scope invalida elegibilidade fail-closed.
- duplicidade de cookie retorna 422 sem eco do secret; keyring ausente retorna 503 sem eco do cookie.
- um contract test legado do C1 inicialmente falhou porque tratava qualquer path contendo “cloud-binding” como Desktop; o teste foi refinado para preservar exatamente as rotas Desktop C1 e permitir os novos endpoints internos C2, sem alterar runtime.

**A7 — gates finais**
- C2-A direcionados locais: **38 passed / 0 skipped / 0 failed**.
- Supabase MockTransport: **7 passed / 0 skipped / 0 failed**.
- PostgreSQL 16 real: **5 passed / 0 skipped / 0 failed**.
- primeira execução de `make test-all`: **617 passed / 1 failed**; única falha era o contract test legado C1 descrito acima.
- `make test-all` final: **618 passed / 0 skipped / 0 failed**.
- `make migrate-list`: migrations **001→020**, incluindo `020_webpilot_session_broker.sql`.
- `git diff --check`: PASS.
- staged files: **0**.
- HEAD: **`7c9f19516673c80860b144b9f421aaea0810e423`**.

**Security audit**
- nenhum secret/cookie/key real encontrado em produção; valores sensíveis literais existem apenas nas fixtures sintéticas;
- cookie/ciphertext/nonce/fingerprint/key version usam `repr=False` onde aplicável;
- quick check confirmou plaintext de cookie ausente do `repr` do response model;
- malformed Supabase payloads e crypto failures saem sanitizados;
- migration 020 mantém RLS e nenhuma `CREATE POLICY` pública;
- RPC EXECUTE revogado de PUBLIC/anon/authenticated e concedido apenas a service_role;
- nenhuma rota Mobile/PWA de broker;
- nenhuma implementação de snapshot, `source=cloud`, failover/failback, collector ou WebPilot Cloud real.

**Fronteiras preservadas**
- migration 020 foi aplicada **somente** em PostgreSQL Docker efêmero para testes; **não foi aplicada em produção**;
- C2-B não iniciado;
- branch Desktop `feat/spec027-cloud`: não criada;
- diretório `cloud/`: sem alterações;
- nenhum push/deploy/prod-migrate;
- nenhum SessionLease operacional real;
- nenhum WebPilot real no Cloud;
- nenhum snapshot/`source=cloud`;
- nenhum failover/failback;
- Shadow não foi manipulado; permaneceu ativo nos PIDs observados 14865/14873.

**Estado para revisão**
- todo o C2-A está no working tree da API/PWA, baseado em `7c9f195...`;
- nenhum arquivo staged;
- nenhum commit C2-A;
- se R6 encontrar achados, corrigir o mesmo working tree e retornar para re-revisão;
- C2-B permanece bloqueado até R6 aprovado + commit exato do diff revisado.

**PARECER SOLICITADO:** **R6 independente** sobre o working tree C2-A completo. Não iniciar C2-B.

### R6 independente — revisão do C2-A (2026-10-08)

**Resultado:** CORREÇÕES OBRIGATÓRIAS. O C2-A está amplamente aderente ao plano e todos os gates normais passam, mas quatro contratos aprovados no C2-P falham sob probes adversariais. C2-B permanece bloqueado e nenhum commit C2-A é autorizado ainda.

**Evidência independente**
- HEAD/base permaneceu `7c9f19516673c80860b144b9f421aaea0810e423`; working tree C2-A sem commit/stage.
- testes C2-A direcionados: **38/38 passed**.
- PostgreSQL 16 real `test_session_broker_postgres.py`: **5/5 passed**, sem skip.
- `make test-all` independente: **618 passed / 0 skipped / 0 failed**.
- `git diff --check`: PASS.
- migration 020 foi exercitada apenas em PostgreSQL Docker efêmero; não foi aplicada em produção.
- operação backend/admin exigida em R5.1 foi materializada em `scripts/admin_session_broker.py` com `set-required-scope` e `verify-publisher`; essa condição está satisfeita.

**R6-F1 — `payload_schema_version` persistido não está autenticado pelo AEAD**
O plano aprovado exige AAD vinculando a versão de schema. A implementação de `_aad()` hardcodeia `schema_version=1`, enquanto `EncryptedSessionLeaseRecord.payload_schema_version` é uma coluna persistida separada e nunca é fornecida a `encrypt()`/`decrypt()`. Assim, alterar somente a coluna `payload_schema_version` não invalida o ciphertext.

**Reprodução independente:** uma lease foi publicada normalmente; o registro em MemoryRepository foi alterado somente de `payload_schema_version=1` para `99`, mantendo ciphertext/nonce/metadata restantes intactos. `SessionBrokerService.consume()` ainda decriptou e devolveu o cookie com sucesso: `TAMPERED_SCHEMA_STILL_CONSUMED 1 secret`.

**Critério de aceite R6-F1:**
- `payload_schema_version` deve participar explicitamente da AAD usada em encrypt e decrypt, sem hardcode desconectado da metadata persistida;
- `encrypt()`/`decrypt()` e o service devem usar a versão persistida/canônica correta;
- alterar somente `payload_schema_version` deve causar `SessionCryptoError`/503 fail-closed;
- adicionar RED específico para schema-version tamper e regressão de roundtrip/key rotation.

**R6-F2 — wire contract aceita entradas inválidas e não possui limite de payload total**
O C2-P exige nomes não vazios e limite de payload total. Hoje `scope_id=' '` passa pelo Pydantic e falha depois em `ProviderScopeProfile`, produzindo **500**; cookie com `name='   '` é aceito e a lease retorna **200**; e 64 cookies de 4096 caracteres cada produzem payload canônico de **264838 bytes** sem qualquer limite total.

**Reprodução independente:**
- `WHITESPACE_SCOPE_STATUS 500 Internal Server Error`;
- `WHITESPACE_COOKIE_STATUS 200`;
- `LARGE_PAYLOAD_ACCEPTED_BYTES 264838`.

**Critério de aceite R6-F2:**
- validar/normalizar `scope_id` na camada de request para que whitespace-only seja 422, nunca 500;
- rejeitar cookie name vazio/whitespace-only antes de crypto; preservar secret redaction;
- definir um limite total explícito e testável para o payload SessionLease, além dos limites por campo/quantidade;
- excesso de payload deve falhar como 422 (ou erro de contrato equivalente documentado), sem fingerprint/encrypt/persistência e sem eco de cookie;
- incluir testes de fronteira imediatamente abaixo/no/acima do limite.

**R6-F3 — Base64URL malformado pode ser aceito pelo decoder criptográfico**
`_b64decode()` usa `urlsafe_b64decode()` sem validação estrita. Caracteres fora do alfabeto podem ser ignorados. Em probe independente, um nonce válido prefixado/sufixado por `!` ou newline continuou decriptando o payload com sucesso, contrariando o contrato aprovado de `malformed nonce/ciphertext/tag => fail-closed`.

**Reprodução independente:** nonce com `!`/newline extra resultou em `ACCEPTED` e devolveu o plaintext; o conteúdo binário subjacente foi silenciosamente aceito pelo decoder permissivo.

**Critério de aceite R6-F3:**
- usar decodificação Base64URL estrita/canônica, rejeitando caracteres fora do alfabeto, whitespace e encoding não-canônico;
- continuar aceitando o formato URL-safe sem padding escolhido pelo encoder;
- malformed nonce/ciphertext e também keys/config Base64URL inválidos devem falhar fechado;
- adicionar RED específico para `!`, newline e outras formas não-canônicas, sem vazar material criptográfico.

**R6-F4 — semântica de conflito de publisher diverge entre Memory e PostgreSQL/Supabase**
`MemoryDeviceRepository.ensure_session_publisher()` retorna `None` quando o mesmo `publisher_id` já está revogado (e também em colisões de owner/realm), enquanto a migration PostgreSQL levanta `session_publisher_conflict`, mapeado para `SessionPublisherConflictError`/HTTP 409. Portanto, o backend de teste e o backend persistente não implementam o mesmo contrato.

**Reprodução independente:** create publisher → revoke → ensure do mesmo `publisher_id` em Memory retornou `None`; a função SQL `ensure_session_publisher()` explicitamente levanta `session_publisher_conflict` para esse estado.

**Critério de aceite R6-F4:**
- definir uma única semântica para colisão/reuso de `publisher_id` e torná-la idêntica em Memory/Postgres/Supabase;
- para o contrato atual já documentado como 409 e implementado no SQL, alinhar Memory com `SessionPublisherConflictError` nos mesmos casos, salvo se todos os backends/API forem conscientemente alterados para outra política;
- adicionar testes de paridade para publisher revogado e colisão de owner/realm.

**Pontos aceitos em R6**
- migration 020: tabelas, RLS, backend-only RPCs, epoch e concorrência principal estão coerentes com o C2-P, condicionados às correções acima;
- idempotência same-generation/same-HMAC e conflito different-HMAC: aceita nos gates atuais;
- AES-256-GCM/keyring/nonce aleatório e swap de lease/realm/expiry/key version: aceitos, exceto R6-F1/F3;
- provider-scope + operação administrativa backend: aceitos;
- endpoints Desktop/Cloud, CloudBinding auth, `Cache-Control: no-store`, ausência de rota Mobile/PWA e redaction principal: aceitos;
- nenhuma implementação C2-B, Desktop publisher runtime, collector Cloud, snapshot, `source=cloud`, failover/failback ou WebPilot real foi antecipada.

**Próximo passo autorizado:** Executor corrige somente R6-F1..F4 com TDD no mesmo working tree, sem commit/stage. Repetir testes direcionados, crypto/config/API, Supabase MockTransport, PostgreSQL real sem skip, `make test-all`, `make migrate-list`, security/redaction e `git diff --check`; atualizar este handoff e parar para **R6.1 independente**. Não iniciar C2-B, não criar branch Desktop, não push/deploy/prod-migrate e não tocar no Shadow.


### Correções R6-F1..F4 — Executor (2026-10-08)

**Status:** **PRONTO PARA R6.1 INDEPENDENTE**. Somente R6-F1..F4 foram corrigidos no mesmo working tree C2-A; nenhum commit/stage foi criado e C2-B permanece bloqueado.

**Base/estado**
- HEAD/base permanece `7c9f19516673c80860b144b9f421aaea0810e423`;
- branch `feat/spec027-cloud`;
- nenhum commit C2-A;
- staged files: **0**.

**R6-F1 — `payload_schema_version` autenticado pela AAD — RED→GREEN**
- RED: o teste adulterou somente `EncryptedSessionLeaseRecord.payload_schema_version` de 1 para 99 e `SessionBrokerService.consume()` continuou decriptando; `PersistenceUnavailableApiError` esperado não ocorreu.
- GREEN:
  - `SessionCryptoKeyring.encrypt()` e `decrypt()` recebem `payload_schema_version` explicitamente;
  - `_aad()` deixou de hardcodear schema 1 e usa a versão fornecida;
  - publish usa uma única `SESSION_PAYLOAD_SCHEMA_VERSION=1` tanto para encrypt quanto para persistência;
  - consume usa **`record.payload_schema_version` persistido** no decrypt.
- alterar somente a coluna/record de schema agora invalida a tag GCM e falha fechado como 503 sanitizado.
- regressões de roundtrip, swap/tamper e key rotation permanecem verdes.

**R6-F2 — wire contract e limite total — RED→GREEN**
- RED 1: `scope_id="   "` retornou **500**.
- RED 2: cookie `name="   "` era aceito.
- RED 3: payload com 64 cookies × 4096 chars retornou **200** e persistiu.
- RED 4: `limit+1` no payload canônico não gerava erro.
- RED 5: probe do service mostrou `session_payload_fingerprint()` sendo chamado antes de qualquer limite.
- GREEN:
  - `ProviderScopeRequest.scope_id` é strip/validado no request model; whitespace-only → 422;
  - `SessionCookieIn.name` é strip/validado no request model; vazio/whitespace-only → 422;
  - limite total explícito: **262.144 bytes (256 KiB)** sobre a representação canônica UTF-8 exata;
  - `limit-1` e `limit` são aceitos; `limit+1` é rejeitado;
  - `canonical_session_payload()` rejeita excesso antes de retornar bytes ao fingerprint;
  - service converte excesso em `422 session_lease_payload_too_large`;
  - probe confirma **zero chamada ao fingerprint** e nenhuma persistência quando excede o limite; encrypt fica inalcançável pela mesma ordem;
  - responses 422 não ecoam cookie secret.

**R6-F3 — Base64URL estrito/canônico — RED→GREEN**
- RED adversarial reproduziu aceitações de `!`, newline, padding `=` e pad bits não-canônicos em nonce/ciphertext e material de configuração.
- GREEN:
  - somente alfabeto `A-Z a-z 0-9 _ -`;
  - input vazio, whitespace/newline, caracteres externos e `=` são rejeitados;
  - comprimento impossível (`len % 4 == 1`) é rejeitado;
  - decode usa `base64.b64decode(..., altchars=b"-_", validate=True)`;
  - após decode, re-encode sem padding precisa ser **idêntico** ao input, rejeitando encoding não-canônico/pad bits;
  - formato produzido pelo encoder continua URL-safe **sem padding**;
  - fingerprint key não é mais sanitizada com `.strip()`, portanto newline/whitespace não é silenciosamente removido.
- testes strict Base64URL: **14/14 passed** para nonce/ciphertext + fingerprint/keyring config.

**R6-F4 — paridade de `publisher_id` — RED→GREEN**
- RED Memory:
  - create → revoke → ensure do mesmo `publisher_id` não levantava conflito;
  - owner/realm collision retornava `None`.
- GREEN:
  - `MemoryDeviceRepository.ensure_session_publisher()` agora levanta `SessionPublisherConflictError` para publisher revogado e para colisão de device/realm, igual ao SQL/Supabase;
  - publisher ativo do mesmo owner/realm continua idempotente/atualizável conforme contrato existente.
- cobertura de paridade adicionada:
  - Memory: revoked + owner/realm collision;
  - PostgreSQL real: revoked + owner/realm collision;
  - Supabase MockTransport: `session_publisher_conflict` → `SessionPublisherConflictError`;
  - API/Memory: reuso após revoke → **409 `session_publisher_conflict`**.

**Gates finais repetidos**
- C2-A direcionados locais: **61/61 passed**.
- crypto/config/API: **40/40 passed**.
- Supabase MockTransport: **8/8 passed**.
- PostgreSQL 16 real: **7/7 passed, 0 skipped, 0 failed**.
- `make test-all`: **643 passed / 0 skipped / 0 failed**.
- `make migrate-list`: migrations **001→020**, incluindo `020_webpilot_session_broker.sql`.
- `git diff --check`: PASS.
- arquivos novos/untracked também validados com `git diff --no-index --check`: zero diagnósticos.

**Security/redaction**
- scan de produção não encontrou os secrets sintéticos usados pelos testes;
- scan de escopo não encontrou `source=cloud`, failover/failback, Selenium/WebDriver ou publicação de snapshot nos arquivos C2-A;
- `Settings.__repr__` não expõe fingerprint key nem keyring;
- `SessionLeaseConsumeResponse.__repr__` não expõe plaintext do cookie;
- probes de payload oversized/422 não ecoam secrets;
- malformed crypto/config continua fail-closed e sanitizado.

**Fronteiras preservadas**
- migration 020 continua apenas local/efêmera; nenhuma aplicação em produção;
- C2-B não iniciado;
- branch Desktop `feat/spec027-cloud`: não criada;
- `cloud/`: sem alterações;
- nenhum push/deploy/prod-migrate;
- nenhum WebPilot real no Cloud;
- nenhum snapshot/`source=cloud`;
- nenhum failover/failback;
- Shadow não foi manipulado; permaneceu ativo nos PIDs observados **14865/14873**.

**PARECER SOLICITADO:** **R6.1 independente** sobre R6-F1..F4 e o working tree C2-A corrigido. Não iniciar C2-B.

### R6.1 independente — encerramento do C2-A (2026-10-08)

**Resultado:** APROVADO. R6-F1..F4 encerrados; C2-A aprovado para commit consolidado único nesta revisão.

**Evidência independente**
- HEAD/base de revisão permaneceu `7c9f19516673c80860b144b9f421aaea0810e423`; nenhum commit/stage C2-A existia antes da aprovação.
- probes independentes reproduzindo exatamente R6-F1..F4 agora falham/retornam conforme contrato esperado.
- C2-A direcionados completos: **61/61 passed**.
- conjunto focal crypto/config/memory/service/API/Supabase: **58/58 passed**.
- PostgreSQL 16 real `test_session_broker_postgres.py`: **7/7 passed / 0 skipped**.
- `make test-all` independente: **643 passed / 0 skipped / 0 failed**.
- `make migrate-list`: migrations **001→020**.
- `git diff --check` e checks dos arquivos untracked: PASS.
- auditoria de escopo: nenhuma alteração em `cloud/` ou frontend, nenhuma branch Desktop SPEC027, nenhum `source=cloud`, failover/failback, Selenium/WebDriver ou snapshot Cloud antecipado.
- Shadow permaneceu ativo nos PIDs observados 14865/14873.

**R6-F1 — ENCERRADO**
- `payload_schema_version` agora é argumento explícito de encrypt/decrypt e participa da AAD;
- publish usa `SESSION_PAYLOAD_SCHEMA_VERSION=1` para AAD e persistência;
- consume usa `record.payload_schema_version` persistido;
- adulterar somente a versão persistida agora produz falha GCM e `PersistenceUnavailableApiError` fail-closed.

**R6-F2 — ENCERRADO**
- `scope_id` e cookie name whitespace-only são rejeitados como 422 na camada de request;
- payload canônico possui limite total explícito de **262144 bytes (256 KiB)**;
- payload acima do limite é rejeitado antes de fingerprint/encrypt/persistência com `session_lease_payload_too_large`, sem eco de secret;
- testes de fronteira abaixo/no/acima do limite estão presentes.

**R6-F3 — ENCERRADO**
- Base64URL agora exige alfabeto URL-safe sem padding, tamanho possível e roundtrip canônico;
- `!`, newline, whitespace, `=` e pad bits/representações não-canônicas são rejeitados;
- nonce/ciphertext e material de configuração usam o mesmo decoder estrito; malformed input falha fechado.

**R6-F4 — ENCERRADO**
- Memory agora levanta `SessionPublisherConflictError` para publisher revogado e colisão de owner/realm, alinhado a PostgreSQL/Supabase e HTTP 409;
- paridade foi coberta em Memory, PostgreSQL real, Supabase MockTransport e API.

**Parecer R6.1**
- C2-A: **APROVADO**.
- R6-F1..F4: **ENCERRADOS**.
- conforme autorização do usuário para reduzir commits, todo o ciclo C2-A (implementação + correções R6 + testes + documentação) deve entrar em **um único commit consolidado** feito após esta aprovação.
- C2-B: **LIBERADO somente após** confirmação desse commit e working tree limpo.
- C2-B deve permanecer o checkpoint seguinte já aprovado pelo plano C2-P; C2-C continua bloqueado até R7.
- push/deploy/prod-migrate, migration 020 em produção, WebPilot real no Cloud, snapshot/`source=cloud`, failover/failback e cutover continuam proibidos.

**Próximo passo após o commit consolidado:** executar somente C2-B conforme plano, incluindo integração publisher Desktop + wheel headless canônico/`--no-deps` e standby Cloud sem source efetivo; ao concluir, deixar o próximo ciclo sem commit/stage e parar para **R7 independente**.


### C2-B — Executor; B1→B4 parcial; **STOP ARQUITETURA** (2026-10-08)

**Status:** **BLOQUEADO EM B4**. B1, B2 e B3 estão GREEN; B4 provou que o wheel Desktop canônico instalado com `--no-deps` não possui import closure headless executável sem Selenium por causa de imports eager dos packages. Conforme o plano C2-P, o Executor parou **antes de B5/B6** e não solicitou R7.

**Bases reais de entrada**
- API/PWA/Cloud: `/home/ciro/dev/prog/alertamaritimoAPI/.worktrees/spec027-cloud`, branch `feat/spec027-cloud`, base limpa **`1e0e4f84366eec2c816a5a271c70d83e89d86eb5`** — `feat(cloud): implement c2 session broker core`.
- Desktop `develop` corrente no início de B1: **`9e5b5e1a33cb7d61db200866aea683a6334de922`**.
- criada worktree Desktop isolada `/home/ciro/dev/prog/alertamaritimo/.worktrees/spec027-cloud`, branch `feat/spec027-cloud`, baseada exatamente em `9e5b5e1...`.
- o checkout original `/home/ciro/dev/prog/alertamaritimo` permaneceu na branch `feat/spec025-plan5-shadow-evidence-gate@9e5b5e1...`; nenhum checkout/reset/stash ocorreu nele.
- Shadow original observado durante B1/B2/B3/B4 nos PIDs **14865/14873**, sem interrupção/manipulação.

**Baseline antes das mudanças**
- Desktop auth/http/grid/session-bootstrap/Shadow direcionados: GREEN.
- `make cloud-test`: **9/9 passed**.

#### B1 — worktree Desktop isolada — GREEN
- `.worktrees/` confirmado ignorado.
- branch Desktop `feat/spec027-cloud` não existia e foi criada apenas na nova worktree.
- SHA real de entrada registrado: `9e5b5e1a33cb7d61db200866aea683a6334de922`.
- worktrees preexistentes não relacionadas permaneceram intactas.

#### B2 — publisher state Desktop — RED→GREEN
**RED**
- `tests/unit/test_session_publisher_state.py` falhou na coleta com `ModuleNotFoundError: alertam.infrastructure.session_publisher_state`.

**GREEN**
- criado `SessionPublisherStateStore` dedicado com JSON persistente contendo exclusivamente:
  - version;
  - publisher_id;
  - last_assigned_generation;
  - realm_id;
  - device_id.
- criação inicial e restart preservam o mesmo `publisher_id`;
- incremento é serializado e persistido atomicamente via tempfile + fsync + `os.replace`;
- generations 1..32 concorrentes foram atribuídas sem duplicação no teste;
- corrupção/schema/scope divergente resulta em `SessionPublisherStateError`, sem reset/overwrite silencioso;
- rotação é operação explícita e cria novo UUID com generation 0;
- arquivo não contém cookie/secret;
- `AppPaths.session_publisher_state_path` dedicado = `webpilot_session_publisher.json`.
- B2 inicial: **6/6 passed**; cobertura final do arquivo inclui também o AppPaths contract.

#### B3 — publisher HTTP + integração Desktop — RED→GREEN
**RED HTTP/background**
- testes falharam na coleta por ausência de `session_publisher_http` e `session_lease_publisher`.

**GREEN HTTP/background**
- `SessionBrokerHttpClient`:
  - usa apenas `Device <secret>`;
  - HTTPS obrigatório fora de localhost/loopback;
  - PUT publisher com realm/profile C2;
  - POST lease com somente whitelist `name/value/expiry`;
  - ignora domain/path/secure/httpOnly/sameSite;
  - nenhum username/password WebPilot;
  - erros HTTP/rede sanitizados, sem response body/secret.
- `SessionLeasePublisher`:
  - daemon thread própria `session-lease-publisher`;
  - `submit()` não faz rede;
  - generation é reservada no worker;
  - retry máximo = **1** (duas tentativas totais);
  - retry reutiliza exatamente o mesmo `publisher_id + local_generation + cookies`;
  - corrupção do state desabilita somente publisher remoto e não chama transport;
  - logs registram apenas tipo da exceção.
- HTTP/background: **11/11 passed**.

**RED integração bootstrap**
- faltavam AppPaths/settings/factories e `_on_webpilot_session` só publicava localmente.

**GREEN integração bootstrap**
- publisher federado é **opt-in** por `ALERTAM_SESSION_BROKER_PUBLISH_ENABLED`, default **false**;
- requer identidade Device completa;
- timeout/retry próprios configuráveis;
- setup/start/stop integrados ao lifecycle sem alterar a autoridade Selenium;
- `_on_webpilot_session()` primeiro executa `webpilot_auth.publish(cookies)` local; somente após sucesso agenda publisher remoto;
- falha/exception do publisher remoto é absorvida com log sanitizado; local lease continua válida;
- nenhuma chamada broker acontece no thread chamador/Tk.
- integração bootstrap/path: **6/6 passed**.

**Verificação parcial consolidada antes do STOP**
- C2-B Desktop B2/B3: **23/23 passed**.
- regressões Desktop auth/HTTP/grid/session-bootstrap/Shadow: **83/83 passed**.
- `make cloud-test` após contratos B4 de source: **13/13 passed**.

#### B4 — wheel canônico / import closure — RED→GREEN estrutural, depois **STOP ARQUITETURA**
**RED estrutural**
- `make cloud-test` passou de 9 para 13 testes e inicialmente teve quatro falhas esperadas:
  - target Docker headless ausente;
  - install `--no-deps` ausente;
  - script de import closure ausente;
  - Make targets wheel contract/build/smoke ausentes.

**GREEN estrutural**
- Cloud mantém target `infra` isolado e ganhou target Docker `headless` separado;
- wheel é fornecido por BuildKit named context externo `alertam_wheel`; nenhum wheel é versionado;
- Docker headless instala explicitamente com `python -m pip install ... --no-deps`;
- criados targets locais:
  - `cloud-wheel-contract`;
  - `cloud-build-wheel`;
  - `cloud-smoke-wheel`.
- `cloud/scripts/headless_contract.py` exige:
  - stack Selenium/webdriver/Pillow/pyttsx3 ausente;
  - imports canônicos do wheel;
  - `sys.modules` sem Selenium/Tk/UI/browser/driver;
  - fixture histórica `grid_real_2026-09-21.html` mantendo 22 navios e resumo 4/2/16;
  - `WebPilotHttpClient` same-origin;
  - login detection + exatamente um retry;
  - segundo login não cria loop.
- contract source confirma que `webpilot_auth.py`, `webpilot_http.py`, grid/parser/weather parser **não foram copiados para `cloud/`**.
- `make cloud-test`: **13/13 passed** após esse GREEN estrutural.

**Wheel canônico material**
- construído de um `git archive` do Desktop SHA revisado **`9e5b5e1a33cb7d61db200866aea683a6334de922`**, e não do working tree C2-B;
- artefato temporário: `/tmp/alertam-c2b-wheel/alertam-4.3.3-py3-none-any.whl`;
- SHA-256: **`2154f1b1c573985c03bef5a98e68c1c7505cc2d4962c5db9d87476892c591d06`**;
- instalado em venv limpo com `pip --no-deps`: instalação do wheel em si concluiu sem instalar dependências.

**RED material que bloqueou B4**
`make cloud-wheel-contract DESKTOP_WHEEL=<wheel> DESKTOP_FIXTURE=<fixture>` falhou no primeiro import canônico:

```text
alertam.application.webpilot_auth
  -> importa package alertam.application
  -> alertam/application/__init__.py importa Controller
  -> controller/.../weather_coordinator
  -> alertam.infrastructure.webpilot_weather
  -> importa package alertam.infrastructure
  -> alertam/infrastructure/__init__.py importa BrowserSession
  -> alertam.infrastructure.browser
  -> from selenium import webdriver
  -> ModuleNotFoundError: No module named 'selenium'
```

A inspeção confirmou:
- `alertam/application/__init__.py` exporta eager `Controller` e demais símbolos;
- `alertam/infrastructure/__init__.py` exporta eager `BrowserSession`, `DriverManager`, voz/weather etc.;
- os módulos headless individuais não demonstraram necessidade semântica de Selenium; o bloqueio nasce do **side effect do import de package**;
- porém o contrato aprovado proíbe contornar isso instalando o stack Desktop e o plano determina STOP antes de alterar packaging/extrair subpacote.

**Decisão arquitetural necessária**
Nenhuma das alternativas abaixo foi executada:
1. **refatorar os `__init__.py` Desktop para exports lazy/sem eager UI/Selenium**, preservando API pública quando os símbolos forem realmente acessados — opção mínima provável;
2. criar packaging/subpacote headless/optional-dependencies próprio — mudança arquitetural maior;
3. instalar Selenium/webdriver/Pillow/pyttsx3 no Cloud — **não aceitável pelo contrato atual**.

Conforme B4/§3.10, o Executor **não escolheu silenciosamente** entre 1 e 2 e não executou 3.

**Estado no STOP**
- Desktop working tree contém apenas B2/B3 e seus testes; **sem commit/stage**.
- API/Cloud working tree contém somente contratos/build local B4; **sem commit/stage**.
- `git diff --check`: PASS nos dois repos no momento do STOP.
- B5 `BrokerSessionProvider`: **não iniciado**.
- B6 standby collector: **não iniciado**.
- B7/R7: **não executado/solicitado**, pois o gate de import closure obrigatório está bloqueado.
- nenhuma migration 020 produção, push/merge/deploy/Northflank operacional;
- nenhum WebPilot real;
- nenhuma SessionLease real operacional;
- nenhum snapshot/`source=cloud`, evento/push, failover/failback/fencing/hysteresis/cutover.

**AÇÃO NECESSÁRIA PARA RETOMAR C2-B:** decisão explícita sobre a estratégia de packaging/import closure. Após a decisão, continuar no mesmo working tree a partir de B4; não reiniciar B2/B3 e não iniciar B5 antes de B4 ficar GREEN materialmente.


### C2-B — retomada após decisão arquitetural B4; **PRONTO PARA R7 INDEPENDENTE** (2026-10-08)

**Decisão arquitetural aplicada**
- autorizado corrigir **exclusivamente** os imports eager dos packages Desktop necessários ao closure headless;
- escolhida a opção mínima: exports lazy via `__getattr__` + `TYPE_CHECKING`, sem novo subpackage, sem reorganização ampla e sem alterar responsabilidades;
- API pública preservada: `from alertam.application import Controller` e `from alertam.infrastructure import BrowserSession, DriverManager` continuam resolvendo os mesmos objetos no ambiente Desktop normal;
- nenhum Selenium/webdriver-manager/Pillow/pyttsx3 foi instalado no Cloud como workaround;
- nenhum módulo `webpilot_auth`, `webpilot_http`, parser/grid/weather foi copiado para `cloud/`.

**Bases mantidas**
- Desktop worktree: `/home/ciro/dev/prog/alertamaritimo/.worktrees/spec027-cloud`;
- Desktop branch: `feat/spec027-cloud`;
- Desktop HEAD/base durante todo o checkpoint: **`9e5b5e1a33cb7d61db200866aea683a6334de922`**;
- API/PWA/Cloud worktree: `/home/ciro/dev/prog/alertamaritimoAPI/.worktrees/spec027-cloud`;
- API/PWA/Cloud branch: `feat/spec027-cloud`;
- API/PWA/Cloud HEAD/base durante todo o checkpoint: **`1e0e4f84366eec2c816a5a271c70d83e89d86eb5`**;
- nenhum commit/stage foi criado após a base aprovada;
- checkout original do Shadow permaneceu intocado; PIDs observados ao final: **14865/14873**.

#### B4 — correção estreita do import closure — RED→GREEN

**RED Desktop**
Novo `tests/unit/test_headless_package_imports.py` reproduziu o problema em subprocesso limpo:
- `alertam.application.webpilot_auth`;
- `alertam.infrastructure.webpilot_http`;
- `alertam.infrastructure.webpilot_grid_html`;
- `alertam.domain`;
- `alertam.domain.webpilot_weather_parser`;
- `alertam.infrastructure.webpilot_weather`.

Resultado RED:
- 2 falhas / 1 pass;
- apenas importar packages/headless carregava `alertam.infrastructure.browser`, `driver_manager` e múltiplos módulos `selenium.*`;
- o teste de compatibilidade dos exports públicos pesados já passava no Desktop normal.

**GREEN Desktop**
Somente:
- `src/alertam/application/__init__.py`;
- `src/alertam/infrastructure/__init__.py`.

foram alterados para:
- tabela explícita de exports públicos;
- `__getattr__` lazy;
- cache do símbolo resolvido em `globals()`;
- `TYPE_CHECKING` para type checkers;
- `__all__` preservado;
- `__dir__` preservando descoberta dos nomes públicos.

Resultado:
- lazy/import closure tests: **3/3 passed**;
- acesso explícito a `Controller`, `BrowserSession` e `DriverManager` continua retornando exatamente os objetos dos módulos originais;
- simples import de `alertam.application` / `alertam.infrastructure` não carrega browser/UI/Tk/Selenium.

**Regressões após lazy imports**
- B2/B3 Desktop: **23/23 passed**;
- auth/HTTP/grid/session-bootstrap/Shadow: **83/83 passed**.

#### B4 — wheel pré-R7 construído do working tree revisável

Conforme decisão do usuário, antes da R7 o wheel **não** foi gerado de commit novo. Foi construído diretamente do working tree Desktop baseado em `9e5b5e1...`.

**Diff exato de source usado no wheel**
Patch reconstruível relativo ao HEAD/base somente para `src/alertam`:
- arquivo temporário: `/tmp/alertam-c2b-desktop-source-final.patch`;
- SHA-256 do patch: **`6cc21a4832bd1304cf23b6de1dce16e14a784434491e990df0aae182a943e2be`**;
- hash foi regenerado no gate final e permaneceu idêntico ao hash usado no build inicial.

Arquivos de source do patch:
- `src/alertam/application/__init__.py`;
- `src/alertam/bootstrap.py`;
- `src/alertam/infrastructure/__init__.py`;
- `src/alertam/infrastructure/session_lease_publisher.py`;
- `src/alertam/infrastructure/session_publisher_http.py`;
- `src/alertam/infrastructure/session_publisher_state.py`;
- `src/alertam/paths.py`;
- `src/alertam/settings.py`.

**Wheel pré-R7**
- nome: **`alertam-4.3.3-py3-none-any.whl`**;
- caminho temporário: `/tmp/alertam-c2b-working-wheel/alertam-4.3.3-py3-none-any.whl`;
- SHA-256: **`c2009dee82de7353dc2b0eb4004bc7cb4c268200b178bdc6c58fd92d7027629e`**;
- instalado em venv limpo com `pip --no-deps`.

**Contract headless material — GREEN**
`make cloud-wheel-contract` prova:
- `selenium`, `webdriver_manager`, `PIL`, `pyttsx3` ausentes;
- imports headless canônicos funcionam;
- `sys.modules` não carrega Selenium/Tk/UI/browser/driver;
- fixture histórica `grid_real_2026-09-21.html` mantém **22 navios** e resumo **ATRACADO 4 / FUNDEADO 2 / PREVISTO 16**;
- `WebPilotHttpClient` mantém same-origin;
- login detection;
- exatamente um retry;
- segundo login não cria loop;
- weather parser/service headless também importáveis sem stack Desktop.

**Obrigação pós-R7 preservada**
Se R7 aprovar e o diff exato for commitado, reconstruir o wheel a partir do **SHA Desktop commitado** e repetir import-closure antes de qualquer avanço posterior.

#### B5 — BrokerSessionProvider / CloudBinding consumer — RED→GREEN

**RED**
- `cloud/tests/test_broker_session.py` inicialmente falhou por ausência de `alertam_cloud.broker_session`;
- borda adicional RED reproduzida depois: se o broker devolvesse a mesma lease após invalidação, o provider mantinha indevidamente a identidade local corrente.

**GREEN**
Criado `cloud/alertam_cloud/broker_session.py`:
- `SessionBrokerClient` stdlib HTTP;
- CloudBinding credential somente em header `Authorization: CloudBinding ...`;
- nenhuma credencial em query string;
- HTTPS obrigatório fora de localhost/loopback;
- GET consume e POST invalidate do contrato C2-A;
- `SessionCookie.value` e `BrokerLease.cookies` com repr redigido;
- errors HTTP/rede/payload sanitizados, sem body secreto;
- 404 → lease indisponível; 403 → não autorizado.

`BrokerSessionProvider`:
- anexa-se ao `WebPilotAuthCoordinator` canônico;
- `prime()` publica uma lease válida localmente apenas uma vez;
- associa a sessão corrente exatamente a `lease_id + realm_epoch`;
- semantic recovery invalida **exatamente** a identidade corrente;
- consome uma nova lease;
- só publica localmente/retorna sucesso quando há mudança efetiva de identidade;
- mesma lease devolvida após invalidação é descartada e vira `AUTH_UNAVAILABLE`;
- ausência/falha de broker permanece `AUTH_UNAVAILABLE`;
- sem current lease, `request_recovery()` não busca repetidamente e não cria loop;
- `invalidate_current()` permite invalidar a lease do último retry sem buscar terceira lease.

B5 final direcionado: **10/10 passed**.

#### B6 — collector Cloud headless standby — RED→GREEN

**RED**
- `cloud/tests/test_standby.py` falhou por ausência de `alertam_cloud.standby`;
- contrato material `standby_contract.py` inicialmente ausente e o source contract falhou como esperado;
- o teste legado do spike que proibia qualquer WebPilot/SessionLease em todo o package passou a falhar após B5/B6, expondo contrato obsoleto.

**GREEN**
Criado `cloud/alertam_cloud/standby.py`:
- `StandbyCollector` somente in-memory/status;
- `build_canonical_standby()` importa lazy diretamente do wheel Desktop:
  - `WebPilotAuthCoordinator`;
  - `WebPilotHttpClient`;
  - `extract_grid_rows`;
  - `parse_grid_rows`;
  - `parse_webpilot_weather`;
  - URLs WebPilot canônicas;
- nenhum código parser/auth/http foi duplicado no Cloud;
- nenhuma ligação automática ao server default.

Sem lease:
- ciclo retorna **`AUTH_UNAVAILABLE`**;
- zero chamada ao fake WebPilot;
- zero loop de login.

Com lease válida:
- maneuvers + weather via transport sintético;
- resultado mantém somente metadata sanitizada:
  - realm_id;
  - realm_epoch;
  - auth_state;
  - last_collection_at/result;
  - maneuver_count;
  - weather_ok;
- nenhum raw HTML/cookie no status.

Login semântico:
- primeira lease é invalidada pelo par exato lease/epoch;
- nova lease efetiva é publicada localmente;
- o `WebPilotHttpClient` realiza no máximo um retry;
- se o retry também retornar login, a segunda lease é invalidada sem terceira aquisição/retry e o ciclo termina `AUTH_UNAVAILABLE`.

B6 unitário: **4/4 passed**.

**Contrato sintético material**
Criado `cloud/scripts/standby_contract.py`, executado no venv com o wheel `--no-deps`:
1. lease válida → fixture real de maneuvers + fixture weather → `OK`, 22 navios, weather OK;
2. primeiro GET login → A invalidada → B consumida → único retry → coleta OK com novo epoch;
3. retry também login → A e B invalidadas nos respectivos pares → sem terceiro retry → `AUTH_UNAVAILABLE`;
4. sem lease → `AUTH_UNAVAILABLE`, zero WebPilot call.

Resultado: **`standby synthetic contract: PASS`**.

**Servidor default preservado**
O contrato legado foi estreitado para o requisito C2-B correto:
- `alertam_cloud.server` continua apenas health/readiness;
- importar/iniciar o servidor default não importa `broker_session` nem `standby`;
- o standby não inicia por default;
- não existe ativação operacional automática.

#### B7 — gate R7 concluído

**API / broker**
- broker direcionado:
  - `test_session_broker_service.py`;
  - `test_supabase_session_broker_repository.py`;
  - `test_session_broker_api.py`;
  - **21/21 passed**.
- API full local com JUnit temporário:
  - **643 tests**;
  - **595 passed**;
  - **48 skipped**;
  - **0 failures**;
  - **0 errors**.
- skips são integrações/backends não disponíveis no gate local; C2-B não alterou persistence/migration.

**Desktop**
- C2-B focado final, incluindo lazy imports + publisher/state + auth/http/grid/Shadow: **109/109 passed**.
- `make check`:
  - **1099 passed**;
  - **84 skipped**;
  - import sweep: **imports OK**.

**Cloud**
- `make cloud-test`: **28/28 passed**.
- `make cloud-wheel-contract`: PASS:
  - headless wheel contract PASS;
  - standby synthetic contract PASS.
- `make cloud-smoke-wheel DESKTOP_WHEEL=<wheel>`:
  - image headless buildada com `pip --no-deps`;
  - `/healthz=200`;
  - `/readyz=200`;
  - UID **10001**;
  - mounts = `[]`;
  - restart saudável;
  - filesystem diff vazio;
  - logs sanitizados.
- inspeção correta dentro da imagem com `docker run -i --entrypoint python ... -`:
  - `selenium`, `webdriver_manager`, `PIL`, `pyttsx3` **não instalados**;
  - imports headless canônicos passam;
  - nenhum Selenium/Tk/UI/browser/driver em `sys.modules`;
  - resultado: **`container headless dependency/import closure: PASS`**.
- `pip list --format=freeze` dentro da imagem headless:
  - `alertam==4.3.3`;
  - `pip==25.0.1`;
  - nenhum stack Desktop adicional.

**git / higiene**
- Desktop `git diff --check`: PASS;
- Desktop untracked `diff --no-index --check`: zero diagnósticos;
- API/Cloud `git diff --check`: PASS;
- API/Cloud untracked `diff --no-index --check`: zero diagnósticos;
- staged Desktop: **0**;
- staged API/Cloud: **0**;
- HEAD Desktop permanece `9e5b5e1...`;
- HEAD API/Cloud permanece `1e0e4f8...`.

**Security/redaction audit**
- nenhum literal sintético `COOKIE-SECRET`, `DEVICE-SECRET`, `CLOUD-CREDENTIAL`, `TOP-SECRET` ou equivalente encontrado em production source Desktop/Cloud;
- `SessionBrokerClient.__repr__` não inclui credential;
- cookie value e coleção de cookies têm repr redigido;
- logs do provider registram somente tipo da exceção;
- nenhum raw response/body secreto é usado na mensagem de erro;
- nenhuma URL contém credential;
- nenhum módulo canônico foi copiado para `cloud/alertam_cloud`;
- produção Cloud contém apenas `broker_session.py` e `standby.py` novos, além do shell já existente;
- nenhuma migration nem frontend foi tocado no C2-B.

**Fronteiras preservadas**
- C2-C: **não iniciado**;
- WebPilot real no Cloud: **não usado**;
- SessionLease real operacional: **não habilitada**;
- publisher Desktop: **opt-in e default false**;
- standby Cloud: **não ligado ao server default**;
- snapshot Cloud: **não implementado/não chamado**;
- `source=cloud`: **não existe**;
- eventos/push Cloud: **não implementados**;
- failover/failback/fencing/hysteresis/source arbitration: **não implementados**;
- migration 020 produção: **não aplicada**;
- Northflank operacional: **não alterado**;
- push/merge/deploy: **não executados**;
- checkout/Shadow original: **intocado**, PIDs finais **14865/14873**.

**Estado entregue ao Revisor**
- Desktop e API/Cloud permanecem com o diff C2-B completo **sem commit e sem stage**, conforme política vigente;
- wheel pré-R7 é somente artefato temporário do working tree e não substitui a reconstrução obrigatória pós-commit;
- nenhuma etapa C2-C foi iniciada.

**PARECER SOLICITADO:** **R7 independente** sobre o C2-B completo nos dois working trees. Se aprovado, autorizar os commits exatos do diff revisado e então reconstruir o wheel Desktop a partir do SHA commitado para repetir o import-closure. Não iniciar C2-C automaticamente.


### R7 independente — revisão do C2-B (2026-10-08)

**Resultado:** CORREÇÕES OBRIGATÓRIAS. B1→B7 estão majoritariamente aderentes ao plano e os gates normais passam, mas dois defeitos de segurança/fail-closed precisam ser corrigidos antes de autorizar commits ou avançar ao C2-C.

**Evidência independente**
- API/Cloud HEAD/base: `1e0e4f84366eec2c816a5a271c70d83e89d86eb5`; Desktop HEAD/base: `9e5b5e1a33cb7d61db200866aea683a6334de922`.
- Ambos os working trees permaneceram sem commit/stage durante a revisão.
- Desktop direcionado headless/publisher/auth/http/grid: **69/69 passed**.
- API broker direcionado: **21/21 passed**.
- `make cloud-test`: **28/28 passed**.
- `make cloud-wheel-contract` com o wheel pré-R7: PASS; headless import closure e standby synthetic contract PASS.
- wheel pré-R7 SHA-256 confirmado: `c2009dee82de7353dc2b0eb4004bc7cb4c268200b178bdc6c58fd92d7027629e`.
- patch source Desktop usado no wheel SHA-256 confirmado: `6cc21a4832bd1304cf23b6de1dce16e14a784434491e990df0aae182a943e2be`.
- `git diff --check` + checks dos arquivos untracked: PASS nos dois repos; staged files: 0.
- Shadow permaneceu ativo nos PIDs observados 14865/14873.

**R7-F1 — redirects HTTP podem vazar Device secret e CloudBinding credential**
Os dois clientes novos usam `urllib.request.urlopen` padrão com header `Authorization`. O handler padrão de redirect do urllib copia headers para o request redirecionado. Assim, uma resposta 30x do broker pode encaminhar a credencial para outro origin.

Reprodução independente com dois servidores loopback sintéticos:
- Desktop publish POST → 302 para segundo servidor: o destino recebeu `Authorization: Device SYNTH-DEVICE-SECRET`;
- Cloud consume GET → 302 para segundo servidor: o destino recebeu `Authorization: CloudBinding SYNTH-CLOUD-CREDENTIAL`.

Isso viola a fronteira de transporte autenticado/seguro e a regra de não vazar credentials.

**Critério de aceite R7-F1:**
- Desktop `SessionBrokerHttpClient` e Cloud `SessionBrokerClient` devem tratar redirect de forma fail-closed;
- preferir rejeitar redirects para esses endpoints, ou no mínimo nunca seguir cross-origin e nunca reenviar `Authorization` fora do origin original;
- cobrir GET/POST relevantes e 301/302/303/307/308 proporcionalmente;
- adicionar RED que prove que nenhum destino redirecionado recebe Device secret, CloudBinding credential ou cookie payload;
- manter HTTPS obrigatório fora de loopback e erros sanitizados.

**R7-F2 — falha ao invalidar lease semanticamente expirada deixa provider local como AUTH_READY**
Quando o WebPilot retorna login e `BrokerSessionProvider.invalidate_current()` falha ao chamar o broker, o método mantém `self._current`. O standby então retorna `last_collection_result=AUTH_UNAVAILABLE`, mas `auth_state=AUTH_READY`, e o próximo ciclo pode reutilizar a mesma sessão já comprovadamente inválida.

Reprodução independente:
- lease A foi primed;
- broker.invalidate levantou `OSError`;
- após resposta `SESSION_EXPIRED`, o provider continuou com identidade A;
- status observado: `AUTH_READY / AUTH_UNAVAILABLE`.

**Critério de aceite R7-F2:**
- login semântico deve invalidar localmente a lease corrente **mesmo se a chamada remota de invalidation falhar**;
- após detectar sessão expirada, o provider deve ficar `AUTH_UNAVAILABLE` e nunca reutilizar a mesma lease local no ciclo seguinte;
- a falha de invalidation remota pode ser registrada de forma sanitizada/retentável, mas não pode manter a lease local como válida;
- não buscar terceira lease/não criar loop; preservar o limite de um retry por operação;
- adicionar RED para outage do broker durante invalidation e provar estado local fail-closed.

**Pontos aceitos em R7**
- STOP arquitetura B4 foi resolvido pela mudança estreita de lazy imports; wheel `--no-deps` funciona sem Selenium/webdriver-manager/Pillow/pyttsx3;
- exports públicos pesados continuam disponíveis no Desktop quando acessados explicitamente;
- publisher Desktop é opt-in, assíncrono e não interfere no `webpilot_auth.publish()` local;
- estado persistente/generation e retry idempotente estão coerentes no escopo atual;
- collector Cloud reutiliza wheel canônico, sem cópia de parser/auth/http;
- standby permanece desligado do server default e usa somente fake transport/fixtures;
- nenhuma publicação snapshot, `source=cloud`, eventos/push, failover/failback/fencing/hysteresis foi antecipada;
- nenhuma migration produção, push/deploy ou WebPilot real no Cloud foi executado.

**Próximo passo autorizado:** Executor corrige somente R7-F1 e R7-F2 com TDD nos mesmos dois working trees, ainda sem commit/stage. Repetir testes Desktop publisher/http/headless, API broker relevante, `make cloud-test`, `make cloud-wheel-contract`, smoke-wheel se aplicável, `git diff --check` nos dois repos, atualizar este handoff e parar para **R7.1 independente**. Não iniciar C2-C e não reconstruir wheel de SHA commitado antes da aprovação.


### Correções R7-F1/R7-F2 — Executor (2026-10-08)

**Status:** **PRONTO PARA R7.1 INDEPENDENTE**. Somente R7-F1 e R7-F2 foram corrigidos nos mesmos working trees; nenhum commit/stage foi criado e C2-C permanece bloqueado.

**Bases preservadas**
- Desktop: `feat/spec027-cloud@9e5b5e1a33cb7d61db200866aea683a6334de922`;
- API/PWA/Cloud: `feat/spec027-cloud@1e0e4f84366eec2c816a5a271c70d83e89d86eb5`;
- staged files: **0** em ambos;
- Shadow original não foi manipulado.

#### R7-F1 — redirects autenticados fail-closed — RED→GREEN

**RED**
- testes com dois servidores loopback reais reproduziram o vazamento do urllib default;
- Desktop POST `webpilot-session-leases`: 301/302/303 seguiram redirect e não levantaram erro;
- revisão independente já havia reproduzido o header `Authorization: Device ...` no segundo origin;
- Cloud GET/POST também usavam o redirect handler default.

**GREEN**
Desktop `SessionBrokerHttpClient` e Cloud `SessionBrokerClient` agora usam por default:
- `HTTPRedirectHandler` dedicado cuja `redirect_request()` retorna `None`;
- `build_opener(...).open`;
- qualquer 301/302/303/307/308 é tratado como `HTTPError` e falha fechado;
- o objeto `HTTPError` é fechado explicitamente antes de propagar erro sanitizado, evitando ResourceWarning/socket leak.

Cobertura real de transporte:
- Desktop publish **POST**: 301/302/303/307/308;
- Desktop publisher registration **PUT**: 301/302/303/307/308;
- Cloud consume **GET**: 301/302/303/307/308;
- Cloud invalidate **POST**: 301/302/303/307/308.

Para todos os casos:
- servidor de origem recebe a request autenticada;
- servidor de destino do `Location` recebe **zero requests**;
- portanto nenhum Device secret, CloudBinding credential ou cookie body é encaminhado;
- mensagens de erro não ecoam secrets;
- HTTPS obrigatório fora de loopback continua inalterado;
- openers injetados por teste continuam suportados.

Desktop `test_session_publisher_http.py`: **17/17 passed** com `-W error`.

#### R7-F2 — invalidation outage fail-closed — RED→GREEN

**RED**
- reproduzido: `BrokerSessionProvider.invalidate_current()` com `broker.invalidate()` levantando `OSError` mantinha `current_identity` e `AUTH_READY`.

**GREEN**
- ao detectar invalidação semântica, a identidade corrente `(lease_id, realm_epoch)` é adicionada a `_rejected_identities`;
- `_current` é limpo **antes** da tentativa remota;
- isso vale para `invalidate_current()` e `request_recovery()`;
- falha remota é registrada somente pelo tipo da exceção e retorna false, mas o estado local permanece `AUTH_UNAVAILABLE`;
- `prime()` rejeita qualquer lease cuja identidade esteja tombstonada localmente;
- se o broker, por ter falhado a invalidação, servir novamente a mesma lease no ciclo seguinte, ela não é republicada no coordinator e não volta a `AUTH_READY`;
- nenhum terceiro fetch/retry foi introduzido;
- quando a invalidação remota funciona, o fluxo normal de uma única lease substituta continua preservado.

Cobertura:
- provider direto com outage em `invalidate_current()`;
- provider direto com outage em `request_recovery()`;
- ambos provam que um `prime()` subsequente consumindo a mesma lease permanece fail-closed e não republica cookies;
- standby integrado prova `AUTH_UNAVAILABLE / AUTH_UNAVAILABLE` no ciclo do login e no ciclo seguinte, com apenas a primeira chamada WebPilot e sem loop.

Cloud:
- `test_broker_session.py`: **14/14 passed**;
- `test_standby.py`: **5/5 passed**.

#### Gates repetidos para R7.1

- Desktop publisher/http/headless/auth/grid direcionados: **79/79 passed**.
- API broker relevante: **21/21 passed**.
- `make cloud-test`: **33/33 passed**.
- `make cloud-wheel-contract`: PASS:
  - headless wheel contract PASS;
  - standby synthetic contract PASS.
- `make cloud-smoke-wheel`: PASS:
  - health/readiness 200;
  - UID 10001;
  - mounts vazios;
  - restart saudável;
  - filesystem diff vazio;
  - logs sanitizados.
- inspeção dentro da imagem: `container headless dependency/import closure: PASS`.

**Wheel pré-R7.1 do working tree revisável**
- base Desktop permanece `9e5b5e1a33cb7d61db200866aea683a6334de922`;
- patch de source `src/alertam` relativo à base:
  - `/tmp/alertam-c2b-r71-source.patch`;
  - SHA-256 **`229a344f3766060458ea1001e2b36da1b11974f363c253b4b5cdf314dcce5c29`**;
- wheel:
  - `/tmp/alertam-c2b-r71-wheel/alertam-4.3.3-py3-none-any.whl`;
  - SHA-256 **`76f2b566874798b2b471d9f4ba74903a3992d23b1695df41d072f6ee54f30056`**;
- continua sendo artefato temporário do working tree, não wheel de SHA commitado.

**Fronteiras preservadas**
- nenhum commit/stage;
- C2-C não iniciado;
- nenhum WebPilot real no Cloud;
- nenhuma SessionLease operacional habilitada;
- nenhum snapshot/`source=cloud`;
- nenhum evento/push;
- nenhum failover/failback/fencing/hysteresis;
- nenhuma migration produção;
- nenhum push/merge/deploy;
- checkout/Shadow original intocado.

**PARECER SOLICITADO:** **R7.1 independente** sobre somente R7-F1/R7-F2 e o C2-B corrigido. Não iniciar C2-C nem reconstruir wheel de SHA commitado antes da aprovação.


### R7.1 independente — revisão das correções R7-F1/R7-F2 (2026-10-08)

**Resultado:** CORREÇÃO OBRIGATÓRIA. R7-F1 está encerrado. R7-F2 melhorou corretamente o fail-closed imediato, mas ainda permite ressuscitar uma lease previamente rejeitada em uma recuperação posterior.

**Evidência independente**
- Bases preservadas: Desktop `9e5b5e1a33cb7d61db200866aea683a6334de922`; API/Cloud `1e0e4f84366eec2c816a5a271c70d83e89d86eb5`.
- Ambos os working trees seguem sem commit/stage.
- Desktop redirect tests: **17/17 passed**.
- Cloud broker/standby correções: **14/14 + 5/5 passed**.
- `git diff --check`: PASS nos dois repos; staged files: 0.
- Shadow permaneceu ativo nos PIDs observados 14865/14873.

**R7-F1 — ENCERRADO**
Reprodução independente com dois servidores loopback confirmou que redirects agora são bloqueados:
- Desktop POST → 302: `Session broker HTTP 302`; destino recebeu zero requests;
- Cloud GET → 302: `Session broker HTTP 302`; destino recebeu zero requests.
Device secret, CloudBinding credential e payload não foram reenviados ao destino. O tratamento fail-closed por `HTTPRedirectHandler` dedicado está adequado.

**R7.1-F1 — lease tombstonada pode ser ressuscitada por `request_recovery()`**
O novo `_rejected_identities` é consultado por `prime()`, mas não pelo caminho de replacement dentro de `request_recovery()`.

Cenário reproduzido independentemente:
1. lease B/epoch 7 é publicada localmente;
2. login semântico ocorre e a invalidação remota de B falha; B é corretamente tombstonada e `_current` vira `None`;
3. depois o broker oferece lease A/epoch 8; `prime()` aceita A;
4. A expira; sua invalidação remota funciona;
5. o broker volta a oferecer B/epoch 7, que permaneceu aceita remotamente porque a primeira invalidation falhou;
6. `request_recovery()` aceita B novamente, apesar de B constar em `_rejected_identities`.

Saída observada:
- após outage de B: `current_identity=None`;
- A é aceita como current;
- recovery de A publica novamente B;
- `current_identity` volta para B/7.

Isso viola a regra do C2-P de que uma lease semanticamente invalidada não pode ser ressuscitada e reabre a sessão que o Cloud já comprovou inválida.

**Critério de aceite R7.1-F1**
- qualquer lease retornada pelo broker deve ser rejeitada se `(lease_id, realm_epoch)` estiver em `_rejected_identities`, independentemente de entrar por `prime()` ou `request_recovery()`;
- centralizar a decisão de elegibilidade do candidate para evitar divergência entre os dois caminhos;
- ao receber uma identidade tombstonada durante recovery, permanecer `AUTH_UNAVAILABLE`, sem republicar cookies;
- não buscar terceira lease e não criar loop;
- adicionar RED reproduzindo a sequência B invalidation outage → A válida → recovery de A → broker devolve B tombstonada;
- preservar o fluxo normal de uma única substituição quando a identidade realmente é nova.

**Próximo passo autorizado:** corrigir somente R7.1-F1 no Cloud, com TDD, no mesmo working tree e sem commit/stage. Repetir `test_broker_session.py`, `test_standby.py`, `make cloud-test`, `make cloud-wheel-contract`, `git diff --check`; atualizar este handoff e parar para **R7.2 independente**. Desktop não precisa de nova alteração para este achado. C2-C continua bloqueado.


### Correção R7.1-F1 — Executor (2026-10-08)

**Status:** **PRONTO PARA R7.2 INDEPENDENTE**. Somente o achado R7.1-F1 foi corrigido no Cloud; Desktop não recebeu alteração adicional. Ambos os working trees permanecem sem commit/stage e C2-C segue bloqueado.

**RED válido**
- novo cenário em `cloud/tests/test_broker_session.py` reproduziu integralmente a sequência revisada:
  1. lease **B/epoch 7** é aceita;
  2. login semântico ocorre e a invalidation remota de B falha;
  3. B fica tombstonada localmente e `current_identity=None`;
  4. o broker fornece lease **A/epoch 8**, aceita por `prime()`;
  5. A expira e sua invalidation remota funciona;
  6. o broker volta a fornecer **B/epoch 7**;
  7. implementação anterior aceitava B novamente via `request_recovery()`.
- RED observado: `provider.request_recovery()` retornou **True** quando deveria retornar false.

**GREEN**
- a decisão de elegibilidade de toda lease candidata foi centralizada em `BrokerSessionProvider._accept_candidate()`;
- `prime()` e `request_recovery()` usam exatamente o mesmo caminho de aceitação;
- qualquer `(lease_id, realm_epoch)` presente em `_rejected_identities`:
  - é recusado independentemente da origem do candidate;
  - não é republicado no `WebPilotAuthCoordinator`;
  - deixa `_current=None`;
  - mantém `AUTH_UNAVAILABLE`;
- não há terceira aquisição/retry;
- uma identidade realmente nova continua sendo aceita normalmente;
- o fluxo anterior B outage → A válida permanece permitido, mas B tombstonada nunca pode ressuscitar depois.

**Testes direcionados**
- `test_broker_session.py`: **15/15 passed**;
- `test_standby.py`: **5/5 passed**;
- o novo teste prova:
  - invalidations tentadas exatamente em B/7 e A/8;
  - `consume_calls == 3`;
  - cookies publicados somente para B inicial e A;
  - B retornada no recovery final não é republicada;
  - estado final `AUTH_UNAVAILABLE`.

**Gates R7.2**
- `make cloud-test`: **34/34 passed**;
- `make cloud-wheel-contract`: PASS:
  - headless wheel contract PASS;
  - standby synthetic contract PASS;
- wheel Desktop reutilizado sem rebuild, porque não houve alteração Desktop nesta correção:
  - `/tmp/alertam-c2b-r71-wheel/alertam-4.3.3-py3-none-any.whl`;
  - SHA-256 **`76f2b566874798b2b471d9f4ba74903a3992d23b1695df41d072f6ee54f30056`**;
- Desktop HEAD/base permanece **`9e5b5e1a33cb7d61db200866aea683a6334de922`**;
- API/Cloud HEAD/base permanece **`1e0e4f84366eec2c816a5a271c70d83e89d86eb5`**.

**Escopo preservado**
- Desktop não modificado nesta correção;
- nenhum commit/stage;
- C2-C não iniciado;
- nenhum WebPilot real;
- nenhuma SessionLease operacional ativada;
- nenhum snapshot/`source=cloud`;
- nenhum failover/failback/fencing/hysteresis;
- nenhum push/merge/deploy/prod-migrate;
- Shadow original não manipulado.

**PARECER SOLICITADO:** **R7.2 independente** sobre exclusivamente R7.1-F1 e o C2-B corrigido. Não iniciar C2-C.


### R7.2 independente — encerramento do C2-B (2026-10-08)

**Resultado:** APROVADO. R7-F1, R7-F2 e R7.1-F1 estão encerrados. O C2-B está aprovado para commits exatos nos dois repositórios e verificação material pós-commit do wheel Desktop.

**Evidência independente**
- Bases de revisão preservadas: Desktop `9e5b5e1a33cb7d61db200866aea683a6334de922`; API/Cloud `1e0e4f84366eec2c816a5a271c70d83e89d86eb5`.
- Ambos os working trees permaneceram sem commit/stage durante a revisão.
- Probe independente do cenário R7.1-F1 resultou em:
  - recovery da lease tombstonada: **False**;
  - `current_identity=None`;
  - `AUTH_UNAVAILABLE`;
  - exatamente duas invalidações tentadas (B/7 e A/8);
  - três consumes no cenário inteiro;
  - somente duas publicações locais (B inicial e A), sem ressurreição de B.
- `make cloud-test`: **34/34 passed**.
- `make cloud-wheel-contract` com o wheel pré-R7.1: PASS para import-closure headless e standby synthetic contract.
- `git diff --check`: PASS nos dois repos; staged files: 0.
- nenhum `source=cloud`, snapshot POST, failover/failback funcional ou alteração de source foi encontrado no diff funcional.
- Shadow original permaneceu ativo nos PIDs observados 14865/14873.

**R7-F1 — ENCERRADO**
Os clientes Desktop e Cloud rejeitam redirects autenticados. Os REDs/reprodução real provaram que o destino de redirect não recebe Device secret, CloudBinding credential nem payload secreto.

**R7-F2 / R7.1-F1 — ENCERRADOS**
A identidade semanticamente rejeitada é tombstonada antes da invalidation remota, a lease local é removida imediatamente e toda lease candidata passa por um único caminho de elegibilidade. Isso vale tanto para `prime()` quanto para `request_recovery()`. Uma identidade tombstonada não pode ser republicada mesmo que o broker a sirva novamente após uma falha anterior de invalidation.

**Parecer R7.2**
- C2-B: **APROVADO**.
- Commits do checkpoint: **AUTORIZADOS agora**, contendo exatamente os diffs revisados em cada repositório.
- Desktop e API/Cloud devem receber commits locais separados, sem alteração adicional entre esta aprovação e os commits.
- Após ambos os commits, confirmar working trees limpos.
- Em seguida, **reconstruir o wheel a partir do SHA Desktop commitado**, não do working tree, e repetir `cloud-wheel-contract`/import-closure headless.
- O SHA Desktop final, SHA API/Cloud final e SHA-256 do wheel pós-commit devem ser registrados no handoff como base de entrada do C2-C.
- C2-C: **LIBERADO somente se** o rebuild pós-commit e o import-closure passarem. Até essa verificação, continua bloqueado.
- push/merge/deploy, WebPilot real no Cloud, SessionLease operacional real, migration produção, snapshot/`source=cloud`, failover/failback e cutover continuam proibidos.

**Sequência autorizada agora:** (1) commit exato Desktop; (2) commit exato API/Cloud; (3) confirmar ambos limpos; (4) rebuild wheel do SHA Desktop commitado; (5) repetir import-closure/`cloud-wheel-contract`; (6) registrar SHAs/hashes; somente então iniciar C2-C, novamente sem commit/stage até R8.
