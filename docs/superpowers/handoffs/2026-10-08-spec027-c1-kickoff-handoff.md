# SPEC 027 — Handoff de entrada C1 após gate Shadow (2026-10-08)

**Objetivo imediato:** avançar o desenvolvimento Cloud sem ativar Cloud operacional prematuramente.
**Protocolo único de troca de checkpoints Executor ↔ Revisor:** docs/superpowers/handoffs/2026-10-08-spec027-controle-checkpoints-executor-revisor.md. Começar pelo P0, aguardar R0 independente; depois executar C1-A → R1 → C1-B → R2 → C1-C → R3 → C1-D → R4. Não passar de um checkpoint sem aprovação registrada.
**Repositório:** /home/ciro/dev/prog/alertamaritimoAPI.
**Autoridade:** specs/027-alertam-cloud-continuity.md, specs/025-webpilot-http-observed-weather-shadow-migration.md e docs/superpowers/handoffs/2026-10-08-spec025-final-handoff.md.

## Contexto e autorização

- Gate técnico SPEC 025 MET, 25h53m/1501 comparáveis/1499 equivalentes/109 limpos, 0 falhas/0 críticas abertas.
- Os dois episódios divergentes foram explicados como **hipótese temporal forte e não comprovada**; usuário autorizou dar sequência à feature Cloud, mantendo Selenium oficial e o Shadow em paralelo.
- SPEC 027 está liberada para começar **planejamento/implementação incremental sujeita a TDD e revisão independente**, não para ativação em produção ou cutover.
- Achado Plan 5: mesmo id de divergência explained não é reaberto automaticamente se reaparecer; priorizar correção TDD independente no Desktop e observação manual de last_seen/occurrences até o runtime atualizar.

## Infraestrutura preexistente

- Planejamento spike: branch prep/spec027-cloud-infra-spike, SHA af5e81f; plano docs/superpowers/plans/2026-10-06-pre-spec027-cloud-infra-spike.md.
- Implementação spike: worktree /home/ciro/dev/prog/alertamaritimoAPI/.worktrees/pre-spec027-cloud-infra-spike, branch feat/pre-spec027-cloud-infra-spike.
- Commit funcional de infraestrutura no remote: 9508af3; commit documental local não publicado: dc23003.
- Shell cloud/ com healthz/readyz, Docker não-root, smoke/restart Northflank homologados em sandbox: https://p01--alertam-cloud--x8mfxqmhb4gj.code.run .
- O spike está aprovado **somente como infraestrutura**: não contém WebPilot real, SessionLease real, CloudBinding operacional, Supabase migration, publicação ou failover.
- Branch de integração API/PWA: feat/api-bootstrap; HEAD local após organização 3253e44, origin/feat/api-bootstrap observado 3d85578 (4 commits locais à frente; sem push). Documentação SPEC025/027/checkpoints já commitada em 3253e44; o shell cloud/ **ainda não está integrado** à base canônica (checar antes de planejar).

## Próxima etapa — C1: plano e executor separados

1. Preparar plano de implementação C1 (Binding, WebPilotAuthRealm e autoridade administrativa), com tarefas pequenas, interfaces, migrações versionadas e TDD RED/GREEN.
2. Reconciliar bases antes de programar: integrar o spike somente após aprovação do merge e review; depois usar **uma única branch `feat/spec027-cloud` para C1→C4**. Não criar branch por checkpoint; os checkpoints/revisões fazem o isolamento.
3. Definir modelo CloudBinding separado da credencial WebPilot; identidade device_id existente; vínculo autorizável/revogável; realm explícito; isolamento cross-device e cross-realm.
4. Definir endpoints Desktop-only com autorização, rotação/revogação, idempotência e auditoria sanitizada; nunca expor secrets no PWA.
5. Planejar DeviceOperationalGate fail-closed, incluindo enabled=false, autorização indisponível, revogação e bloqueio da coleta.
6. Revisar arquitetura/segurança e testes antes de implementar; tarefas C2 Auth Broker/SessionLease reais, C3 failover/failback e publicação source=cloud são etapas posteriores, não partes implícitas de C1.
7. Garantir que nenhum deploy operacional, WebPilot real no Northflank, segredo real, migration em Supabase produção, source=cloud ou failover seja feito sem solicitação explícita e gate de deploy.

## Critérios mínimos da primeira revisão C1

- Modelo e contrato de binding isolados do PWA/credencial WebPilot.
- DeviceOperationalGate fail-closed em todas as entradas previstas.
- Identidades, revogação e isolamento cobertos por testes de unidade/integração.
- Nenhum efeito em Selenium oficial, PWA existente, push/histórico, ou Cloud shell sandbox até aprovação de deployment.
- Handoff de checkpoint com commits, testes RED/GREEN, diff/security review e STOP para revisão independente.
- Não executar merge/push/deploy automático ao terminar C1.

## Prompt sugerido ao próximo planejador/executor

Leia integralmente specs/027-alertam-cloud-continuity.md, docs/superpowers/handoffs/2026-10-08-spec025-final-handoff.md e este handoff. Revalide as branches do spike Cloud e a base feat/api-bootstrap. Prepare o Plano C1 Binding/realm/autoridade com TDD, isolamento por device_id, credencial revogável, DeviceOperationalGate fail-closed e checkpoints de revisão. A estratégia de Git é **uma única branch `feat/spec027-cloud` para C1→C4**, criada somente após P0/R0 e reconciliação da base; não criar branches C1/C2/C3/C4 separadas. Não implemente C2/C3 durante o P0, não ative Cloud operacional e não faça migrations em produção/deploy/merge/push sem autorização. Pare para revisão do plano antes de executar.
