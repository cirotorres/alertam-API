# Handoff — alinhamento pré-Plan 4 após SPEC 030

**Data:** 2026-10-06
**Papel:** Revisor independente
**Preparação original:** `docs/pre-plan4-gate-alignment`
**Base revisada:** `origin/feat/api-bootstrap` em `3d8557856858fbbecbae2326a1f620f197d53a64`
**Reconciliação canônica:** conteúdo incorporado localmente à `feat/api-bootstrap` em 2026-10-06, sem push.

## Diagnóstico

A SPEC 030 está presente na base remota e introduziu `DeviceOperationalGate` fail-closed.

No Desktop atual, o gate protege o `COLLECT` oficial Selenium. Porém `WebPilotWeatherService` ainda pode fazer GET WebPilot HTTP sem consultar o gate. Isso precisa ser corrigido antes de adicionar o Shadow.

O Plan 4 remoto já possuía uma obrigação resumida de respeitar o gate, mas não definia:
- compartilhamento da mesma instância;
- check no worker imediatamente antes do GET;
- comportamento de item já enfileirado;
- semântica das métricas quando o request é bloqueado;
- impacto no Plan 5.

## Decisão pré-Plan 4

Criar primeiro a hotfix Desktop H1:
`hotfix/pre-plan4-device-operational-gate`

Ela deve:
- tornar o gate uma referência compartilhada do runtime;
- manter Selenium usando essa instância;
- fazer `WebPilotWeatherService` usar a mesma instância;
- impedir GET/recovery HTTP quando o gate negar;
- preservar active/grace/disabled/authorization_unavailable;
- reativar sem restart;
- não implementar Shadow.

Plano detalhado no Desktop:
`docs/superpowers/plans/2026-10-06-pre-plan4-hotfixes-and-branching.md`

Prompt:
`docs/superpowers/prompts/2026-10-06-pre-plan4-device-gate-hotfix-start-prompt.md`

## Hotfix separado de fotos

A divergência de prioridade de foto continua como hotfix pequeno independente:
- IMO exato via Wikidata `P458`;
- `P18` primeiro;
- Commons textual como fallback;
- preservar crédito/licença/cache/timeout.

Não incluir essa divergência como comportamento permanente no FAQ.

## Janela de UI

Depois de H1/H2 e antes do Plan 4, o usuário pode concluir ajustes de UI em branches pequenas.

O Plan 4 só deve ser cortado depois dessa janela para evitar branch Shadow antiga acumulando rebase de UI/hotfix.

## Branch correta do Plan 4

Recomendação:
`feat/spec025-plan4-maneuver-shadow`

Base:
SHA corrente de `develop` depois de:
1. H1 integrado;
2. H2 concluído ou explicitamente adiado;
3. UI pré-Plan 4 concluída;
4. suíte verde;
5. revisão independente de abertura.

Não reutilizar branch antiga da SPEC 025.

## Ajustes autoritativos feitos nesta revisão

Atualizados:
- SPEC 025 overview;
- SPEC 025 principal;
- Plan 4;
- Plan 5;
- roadmap Cloud;
- SPEC 027.

Contrato novo do Plan 4:
- mesma instância de `DeviceOperationalGate`;
- zero segundo status client/gate;
- check imediatamente antes do GET no worker;
- `disabled` e `authorization_unavailable` fora do grace => zero GET;
- operational skip separado de falha técnica;
- skip não conta como comparable/equivalent;
- re-enable sem restart;
- nenhum efeito em tracker/eventos/push/voz/histórico/MobileSnapshot/PWA.

Plan 5:
- operational skips aparecem no relatório;
- não contam como falha do collector nem ciclo comparável;
- skips antes do primeiro request real não iniciam a janela;
- skips durante a janela permanecem visíveis para o gate humano;
- `GateStatus=MET` continua sem cutover/Cloud automático.

Cloud:
- `enabled=false` tem precedência sobre failover;
- Cloud não pode assumir como forma de contornar desativação administrativa.

## Sequência de continuidade

1. Executar H1.
2. Revisão independente H1.
3. Merge H1 em `develop`.
4. Executar H2 se ainda desejado.
5. Ajustes UI.
6. Revisão pré-Plan 4 e registro do SHA.
7. Criar branch Plan 4.
8. Executar Plan 4.
9. Revisão independente Plan 4.
10. Somente então Plan 5.

## Reconciliação da árvore canônica — 2026-10-06

A `feat/api-bootstrap` canônica estava 2 commits atrás do remoto e possuía somente dirt documental pré-existente.

Procedimento seguro executado:
- dirt integral preservado em `stash@{0}` com nome `safety/pre-align-feat-api-bootstrap-2026-10-06`;
- fast-forward de `c3de5c1` para `3d85578`, incorporando SPEC 029 e SPEC 030 já presentes no remoto;
- alinhamento pós-SPEC 030 deste handoff/Plans aplicado sobre a base nova;
- evidência humana útil do A3 preservada em forma consolidada;
- seção lateral da SPEC 029 preservada no roadmap;
- `specs/README.md` atualizado para refletir Plans 1–3 concluídos, Plan 4 em HOLD e SPEC 029 integrada;
- documentos locais antigos da SPEC 029 não foram reaplicados porque o remoto contém versões posteriores de implementação.

O stash de segurança permanece disponível e não deve ser aplicado integralmente sobre a base nova, pois contém versões documentais superadas. Ele pode ser removido futuramente após confirmação humana de que não há mais informação a recuperar.

## STOP

Este handoff não autoriza:
- implementação de H1/H2;
- início do Plan 4;
- Plan 5;
- Cloud;
- cutover;
- push/deploy/migration/release.
