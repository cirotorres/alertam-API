# Handoff — Pré-SPEC 027 Cloud Infrastructure Spike

**Data:** 2026-10-06
**Papel:** entrada para Executor; revisão independente após o primeiro deploy sandbox.
**Repositório:** `/home/ciro/dev/prog/alertamaritimoAPI`
**Branch de planejamento:** `prep/spec027-cloud-infra-spike`
**Planning SHA:** `40842796ef6d63ff38e0df6b5524f2b8bd82d62d`

## Contexto

A SPEC 025 Plan 5 está com Shadow real coletando evidência em paralelo no repositório Desktop. Essa janela não deve ser interrompida nem alterada por este trabalho.

A SPEC 027 operacional continua bloqueada até o gate humano da SPEC 025. Foi liberado apenas um spike de infraestrutura não operacional para reduzir tempo de preparação.

## Fonte autoritativa

Leia integralmente antes de editar:

1. `docs/superpowers/plans/2026-10-06-pre-spec027-cloud-infra-spike.md`;
2. `specs/027-alertam-cloud-continuity.md`;
3. `docs/superpowers/strategy/2026-10-02-alertam-cloud-evolution-roadmap.md`.

## Decisões já tomadas

- Não criar terceiro repositório agora.
- Criar shell isolado em `alertamaritimoAPI/cloud/`.
- Northflank é o sandbox inicial.
- O serviço é apenas infraestrutura: health/readiness/logs/restart/always-on.
- Nenhum código WebPilot/SessionLease/CloudBinding operacional entra neste spike.
- Nenhuma migration Supabase é permitida.
- Nenhuma publicação `source=cloud` é permitida.
- Nenhum failover/failback é permitido.
- Não copiar collector do Desktop.

## Execução autorizada

Crie uma branch de implementação a partir do Planning SHA exato, sugestão:

    feat/pre-spec027-cloud-infra-spike

Execute com TDD:

- Task 1 — shell headless mínimo;
- Task 2 — Docker/container;
- Task 3 — atalhos Make/testes locais;
- Task 4 — deploy sandbox Northflank, se a conexão ao repositório estiver disponível.

Se o deploy exigir interação manual do usuário na UI do Northflank, pare apenas nesse ponto e entregue os passos exatos; não improvise credenciais nem peça secrets de produção.

## Evidência mínima esperada

- testes do subprojeto Cloud verdes;
- suíte existente relevante sem regressão;
- `docker build` verde;
- smoke local de `/healthz` e `/readyz`;
- container roda como usuário não-root;
- logs sem dump de env;
- deploy Northflank saudável ou instruções exatas para completar o vínculo;
- `git diff --check` limpo.

## Guardrails de segurança

Não adicionar ao Northflank nesta fase:

- credenciais WebPilot;
- cookies/session material;
- SUPABASE_SECRET_KEY/service-role;
- DEVICE_SECRET real;
- credencial CloudBinding;
- qualquer secret operacional do Desktop.

Valores de teste não sensíveis são suficientes para o spike.

## STOP

Após Task 4, atualize este handoff ou crie handoff de execução com:

- branch/SHAs;
- RED/GREEN;
- arquivos alterados;
- comandos Docker;
- resultado dos testes;
- resultado do deploy Northflank;
- pendências.

Pare para revisão independente antes de qualquer trabalho C1/C2/C3 da SPEC 027.

**Não tocar:** WebPilot real no Cloud, SessionLease real, CloudBinding operacional, Supabase migrations, publicação Cloud, failover/failback, Mobile ou cutover.
