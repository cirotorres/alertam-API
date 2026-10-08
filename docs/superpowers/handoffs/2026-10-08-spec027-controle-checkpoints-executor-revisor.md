# SPEC 027 — Controle de checkpoints Executor ↔ Revisor

**Data de abertura:** 2026-10-08
**Status:** R0.1-FIX — R0-F2..F5 encerrados; dois ajustes documentais finais pendentes antes de liberar reconciliação/C1-A
**Repositório coordenador:** /home/ciro/dev/prog/alertamaritimoAPI
**Base API/PWA para R0.1:** `feat/api-bootstrap@20c8576` antes deste commit de correção (sucessora documental de `3b7c932`); o HEAD após a correção será apenas seu sucessor documental. **Base Desktop auditada:** `develop@abe386f`, com Plan 5 pendente em `9e5b5e1`. A futura implementação da SPEC 027 usará uma única `feat/spec027-cloud`, criada somente após R0.1 e reconciliação aprovada.
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
8. `docs/superpowers/plans/2026-10-08-spec027-c1-binding-realm-authority.md` — criado no P0, corrigido por R0-F1..F5; execução depende de aprovação R0.1.

## 2. Estado de entrada verificado (2026-10-08)

- SPEC 025 Plan 5: gate técnico MET; 25h53m, 1501 comparáveis, 1499 equivalentes, 109 limpos, nenhuma falha; 4 registros explicados de 2 episódios, hipótese forte de diferença temporal Selenium/HTTP, **não comprovada como causa-raiz**.
- Usuário aceitou a hipótese documentada e autorizou avançar o **desenvolvimento** da SPEC 027; **não** autorizou migrações de produção, WebPilot real no Cloud, publicação source=cloud, cutover ou failover real.
- Desktop: feat/spec025-plan5-shadow-evidence-gate, HEAD após organização 9e5b5e1 (documentação R2/Task 5 commitada); develop abe386f; checkout limpo, branch Plan 5 não integrada, Shadow real não deve ser interrompido.
- API/PWA: correção R0.1 iniciada em `feat/api-bootstrap@20c8576`, `origin/feat/api-bootstrap@3d85578`; checkout limpo, sem push. `20c8576` contém apenas a revisão R0 sobre o P0 documental `3b7c932`.
- API/PWA checkout principal auditado novamente em `20c8576`; merge-base com o spike = `af5e81f4bb7c10ac7f0c07712f84f107c4a41aa4`; `git merge-tree --write-tree 20c8576 dc23003` = `f6d55bd52048d183895f72be70fcb32ce8819617`, PASS sem conflito.
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
| 0 | P0 — Reconciliação e plano | Verificar estado cross-repo; preparar proposta de integração sem alterar produção; planejar C1 com tasks TDD e contratos | R0/R0.1 aprovam base e plano antes de programar | **R0.1-FIX — 2 ajustes documentais finais** |
| 1 | C1-A — Domínio/contrato | Modelo CloudBinding, associação realm/device_id, invariantes, interfaces, testes unitários; migração **somente proposta** | R1 revisa identidade, constraints, isolamento e contrato | BLOQUEADO por R0.2 |
| 2 | C1-B — Persistência/credenciais | Credencial própria, hash/rotação/revogação, repos/endpoints Desktop-only e testes; migração versionada **não aplicada** | R2 revisa autorização, secrets e idempotência | BLOQUEADO |
| 3 | C1-C — Gate e isolamento | Fail-closed (enabled=false, indisponível), cross-device/cross-realm, tentativas indevidas, testes adversariais | R3 revisa proibições de bypass | BLOQUEADO |
| 4 | C1-D — Integração/encerramento | Testes completos, documentação, mocks API e contratos Desktop, smoke local sem WebPilot real | R4 revisa regressão e segurança; gate humano para merge/deploy separado | BLOQUEADO |
| 5 | C2-P — Plano Auth Broker | Desenhar reuso do coletor validado, contrato SessionLease, epoch, segurança, standby | R5 (plano); **não** copiar parser/coletor | BLOQUEADO |
| 6 | C2 — Execução em checkpoints próprios | Broker federado, anti-replay e core HTTP em standby headless sem source efetivo | Revisões por subtask e gate sandbox | BLOQUEADO |
| 7 | C3-P / C3 — Autoridade e snapshots | Plano aprovado; lease/fencing, hysteresis, failover/failback, anti-split-brain; primeira versão só snapshots | Revisões por subtask, gate operacional explícito | BLOQUEADO |
| 8 | C4 — Observabilidade | Status, logs sanitizados, smoke prolongado, degradação e reconciliação | Revisão operacional humana | BLOQUEADO |
| 9 | C5 — Eventos/Push | Plano próprio de idempotência cross-source, sem duplicação | **Somente se autorizado separadamente** | FORA DA LIBERAÇÃO ATUAL |

O detalhamento e subdivisão de C1-A a C1-D podem ser aperfeiçoados pelo plano P0, **mas agora exigem aprovação de R0.1 antes da execução**. Para C2/C3, criar planos e checkpoints detalhados antes de iniciar; a aprovação de C1 não é aprovação operacional dessas fases.

### Estratégia simplificada de branch/worktree

A SPEC 027 usa **uma branch longa de feature por repositório**, e não uma branch por fase/checkpoint:

- API/PWA/Cloud: `feat/spec027-cloud`, criada somente após aprovação R0.1 e reconciliação efetiva de `feat/api-bootstrap` com o spike Northflank.
- Desktop: usar também `feat/spec027-cloud` **somente quando surgir a primeira alteração Desktop da SPEC 027**, criada a partir de `develop` já contendo o fechamento da SPEC 025.
- C1, C2, C3 e C4 avançam na mesma branch, separados por commits e checkpoints independentes R1...Rn.
- Preferir uma única worktree `.worktrees/spec027-cloud` por repo quando necessário; não criar worktree por subetapa.
- Ao final de cada checkpoint: commit local + testes + handoff + STOP para revisor. **A revisão é o isolamento; a branch não precisa mudar.**
- Sincronizações com a branch-base acontecem apenas em pontos planejados, com working tree limpa e revisão de conflito; não fazer rebase/merge oportunista no meio de um checkpoint.
- A branch antiga `feat/pre-spec027-cloud-infra-spike` só pode ser integrada/removida após aprovação R0.1 e execução explícita da reconciliação.
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

**Status:** R0.1-FIX — R0-F2..F5 encerrados; dois ajustes documentais finais pendentes.
**Executor:** P0 e correções R0-F1..F5 concluídos em 2026-10-08. **Revisor R0.1:** revisão independente concluída abaixo.
**Próximo ato permitido:** corrigir somente R0.1-F1 e R0.1-F2 e retornar para R0.2. Nenhuma integração, criação de `feat/spec027-cloud` ou implementação C1-A antes da aprovação.

**Estado Git auditado**
- API/PWA base executável para a correção: `feat/api-bootstrap@20c8576`, limpa antes dos edits; `origin/feat/api-bootstrap@3d85578`; sem push. O commit desta correção será somente documental e sucessor de `20c8576`.
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

**Pendências para depois de R0.1**
- executar as integrações aprovadas e registrar os novos SHAs reconciliados;
- rodar regressões da base reconciliada;
- criar `feat/spec027-cloud` somente então;
- iniciar apenas C1-A.

**Confirmação de escopo P0:** nenhum merge, push, deploy, migration, branch de implementação, WebPilot Cloud, cookie/SessionLease, `source=cloud`, failover/failback ou cutover foi executado.

### C1-A / C1-B / C1-C / C1-D

**Status:** BLOQUEADO até aprovação de R0.1; abrir seção específica em cada entrega.

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
