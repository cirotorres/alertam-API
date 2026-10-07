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


---

## Execução — 2026-10-07 — Tasks 1–4 (Task 4 parada no gate manual Northflank)

### Base e branch

- Base executada por instrução explícita do operador: `af5e81f4bb7c10ac7f0c07712f84f107c4a41aa4`.
- O SHA acima é descendente do Planning SHA originalmente registrado neste handoff (`40842796ef6d63ff38e0df6b5524f2b8bd82d62d`) e acrescenta apenas documentação do próprio spike.
- Branch de implementação: `feat/pre-spec027-cloud-infra-spike`.
- Worktree: `/home/ciro/dev/prog/alertamaritimoAPI/.worktrees/pre-spec027-cloud-infra-spike`.
- Branch publicada em `origin/feat/pre-spec027-cloud-infra-spike` para ficar disponível ao Northflank.

### Commits de implementação

1. `146f09bdf01d544056af3ca8055c40163720d138` — `feat(cloud): add infrastructure-only headless shell`
2. `0eccfa1de1b79a22fa87b7e780880bab76cfeb9d` — `build(cloud): add non-root production container`
3. `9558f298c41dd382b8ce6f0a6a6689feedc7842c` — `test(cloud): add local build and smoke workflow`

### Task 1 — shell headless mínimo — CONCLUÍDA

Implementado somente o shell de infraestrutura em `cloud/`:

- Python 3.12;
- bind `0.0.0.0`;
- `PORT`, default `8080`;
- `GET /healthz` → 200;
- `GET /readyz` → 200;
- demais rotas → 404;
- sem dependência de API, Supabase, Desktop ou WebPilot;
- logs sanitizados, sem dump de ambiente;
- teste negativo explícito contra WebPilot, SessionLease, CloudBinding, Supabase, `source=cloud` e `DEVICE_SECRET`.

TDD:

- RED inicial: 4 falhas, pois o pacote/runtime ainda não existia;
- GREEN: contrato HTTP, bind/porta, logging e ausência de dependências operacionais verdes.

### Task 2 — Docker/container — CONCLUÍDA

Arquivos principais:

- `cloud/Dockerfile`;
- `cloud/.dockerignore`;
- testes de contrato do container.

Contrato comprovado:

- base `python:3.12-slim`;
- `PYTHONUNBUFFERED=1`;
- usuário não-root `10001:10001`;
- `EXPOSE 8080`;
- `HEALTHCHECK` em `/healthz`;
- sem volume obrigatório;
- sem secret baked;
- sem escrita obrigatória no filesystem.

TDD:

- RED: 2 falhas pela ausência de `Dockerfile` e `.dockerignore`;
- GREEN: testes de contrato verdes.

Smoke Docker real:

- build: verde;
- `/healthz`: 200;
- `/readyz`: 200;
- UID runtime: `10001`;
- mounts: `[]`;
- segredo sentinela: ausente dos logs;
- restart após stop/start: saudável;
- `docker diff`: vazio.

### Task 3 — Make/testes locais — CONCLUÍDA

Adicionados:

- `make cloud-test`;
- `make cloud-build`;
- `make cloud-smoke`;
- `cloud/scripts/smoke.sh`.

Os alvos foram testados para não tocar em banco, migrations, Vercel, Supabase ou Desktop.

TDD:

- RED: ausência dos alvos Make e do script de smoke;
- GREEN inicial: 8 testes Cloud;
- o smoke repetível revelou duas condições reais:
  1. a porta dinâmica publicada pelo Docker muda após `docker start`;
  2. o serviço precisava tratar SIGTERM explicitamente para saída limpa como PID 1 do container.
- RED adicional:
  - `test_sigterm_exits_cleanly`: retorno `-15`, esperado `0`;
  - smoke continha apenas uma resolução de host port antes do restart.
- GREEN:
  - SIGTERM tratado explicitamente;
  - host port reconsultada após restart;
  - suíte Cloud final: **9/9 verde**;
  - smoke final: verde.

### Regressões

Verificação final executada em sequência:

```bash
make cloud-test
make cloud-smoke
make test
cd frontend && npm test -- --run
git diff --check af5e81f4bb7c10ac7f0c07712f84f107c4a41aa4..HEAD
```

Resultado:

- Cloud: **9/9 passed**;
- API: suíte concluída em 100% com os skips já esperados localmente;
- PWA: **50 test files / 290 tests passed**;
- `git diff --check`: limpo;
- smoke Docker: verde.

Observações fora do escopo, não alteradas neste spike:

- Vitest mantém warning existente de atualização React fora de `act(...)` em `AppShell.test.tsx`;
- `npm ci` reportou vulnerabilidades em dependências existentes; nenhuma atualização foi feita por estar fora do escopo.

### Task 4 — Northflank sandbox — STOP MANUAL PREVISTO

A branch necessária já está publicada no GitHub.

No computador de execução:

- CLI Northflank não está instalada/configurada como contexto autenticado;
- não existe token Northflank disponível no ambiente;
- a documentação atual do Northflank exige autenticação/vínculo de conta para criar o Combined Service.

Portanto não foram improvisadas credenciais nem solicitados secrets operacionais.

Estado: **Task 4 parada somente no ponto de interação manual da UI do Northflank**, conforme autorizado pelo plano.

Configuração a aplicar manualmente no projeto já criado **AlertaM Cloud**:

1. criar um **Combined Service**;
2. repositório: `cirotorres/alertam-API`;
3. branch: `feat/pre-spec027-cloud-infra-spike`;
4. build type: **Dockerfile**;
5. Dockerfile: `/cloud/Dockerfile`;
6. build context: `/cloud`;
7. uma instância ativa, sem scale-to-zero/pausa;
8. porta: `8080`, protocolo HTTP, acesso público;
9. variável não sensível opcional/explicita: `PORT=8080`;
10. nenhum volume/database;
11. nenhum secret WebPilot, Supabase, Desktop, SessionLease ou CloudBinding;
12. adicionar **liveness probe HTTP** na porta 8080, path `/healthz`;
13. adicionar **readiness probe HTTP** na porta 8080, path `/readyz`;
14. criar o serviço e aguardar build/deploy saudável;
15. validar a URL pública em `/healthz` e `/readyz`;
16. executar um restart controlado pela UI e validar novamente os dois endpoints.

### Guardrails preservados

Nenhum destes itens foi implementado:

- WebPilot real no Cloud;
- SessionLease/cookies;
- CloudBinding operacional;
- migrations Supabase;
- publicação `source=cloud`;
- arbitragem/failover/failback;
- eventos/push Cloud;
- cutover;
- qualquer alteração do Desktop ou Mobile.

### Pendência / próximo gate

Após a criação manual do serviço Northflank, registrar:

- URL pública;
- build/deploy saudável;
- logs de startup;
- liveness/readiness verdes;
- restart controlado verde.

Depois disso, **STOP para revisão independente**. Não iniciar C1/C2/C3 da SPEC 027.

---

## R1 independente — 2026-10-07

### Parecer

**Tasks 1–3 aprovadas tecnicamente. Task 4 permanece corretamente parada no gate manual do Northflank.**

A revisão independente não encontrou antecipação de comportamento operacional da SPEC 027.

### Evidências reproduzidas independentemente

- branch: `feat/pre-spec027-cloud-infra-spike`;
- base exata: `af5e81f4bb7c10ac7f0c07712f84f107c4a41aa4`;
- HEAD revisado: `9508af3cd10710260b9c2685a882c71805315b5e`;
- working tree limpa e sincronizada com `origin/feat/pre-spec027-cloud-infra-spike`;
- `git diff --check af5e81f..HEAD`: PASS;
- `make cloud-test`: **9/9 passed**;
- `make cloud-smoke`: PASS;
- API: suíte completa local PASS com skips esperados;
- PWA: **50 files / 290 tests passed**;
- Docker runtime user: `10001:10001`;
- mounts obrigatórios: nenhum;
- `/healthz`: 200;
- `/readyz`: 200;
- restart local: saudável;
- filesystem diff no smoke: vazio;
- sentinela de ambiente: não apareceu nos logs.

### Isolamento do spike — APROVADO

A busca independente nos artefatos de runtime/container não encontrou referências a WebPilot, SessionLease, CloudBinding, Supabase, `source=cloud`, `DEVICE_SECRET`, service-role ou cookies.

O serviço expõe somente health/readiness e 404 para rotas não reconhecidas. Não publica snapshots, não consulta banco, não possui vínculo de device_id e não implementa arbitragem/failover.

### Northflank

As instruções do Executor foram conferidas contra a documentação atual do Northflank. Para um monorepo, o serviço pode usar:

- Combined Service;
- repository `cirotorres/alertam-API`;
- branch `feat/pre-spec027-cloud-infra-spike`;
- Dockerfile `/cloud/Dockerfile`;
- build context `/cloud`;
- porta HTTP pública 8080;
- liveness `/healthz`;
- readiness `/readyz`.

Esses paths com `/` inicial são aceitos pelo Northflank como caminhos relativos à raiz do repositório no formulário/API.

### Gate manual restante

O único passo pendente do spike é criar/deployar manualmente o Combined Service no projeto Northflank `AlertaM Cloud`, validar build, health/readiness e um restart controlado.

Não inserir secrets operacionais. `PORT=8080` é suficiente se a plataforma não inferir a porta automaticamente.

### Status R1

- Task 1: **APROVADA**;
- Task 2: **APROVADA**;
- Task 3: **APROVADA**;
- Task 4: **PENDENTE SOMENTE INTERAÇÃO MANUAL NORTHFLANK**;
- C1/C2/C3 SPEC 027: **CONTINUAM BLOQUEADOS**;
- WebPilot/SessionLease/CloudBinding/source=cloud/failover: **NÃO AUTORIZADOS**.

Após o deploy manual saudável, registrar URL pública, estado do build/deploy, probes e restart e retornar para fechamento independente do spike.

---

## Fechamento do spike — 2026-10-07

### Northflank sandbox — VALIDADO

O operador concluiu manualmente a Task 4 no projeto Northflank `AlertaM Cloud`.

Serviço:

    alertam-cloud

Branch implantada:

    feat/pre-spec027-cloud-infra-spike

Commit implantado:

    9508af3cd10710260b9c2685a882c71805315b5e

URL pública:

    https://p01--alertam-cloud--x8mfxqmhb4gj.code.run

Validações confirmadas após deploy:

    GET /healthz
    {"service":"alertam-cloud-infra-spike","status":"ok"}

    GET /readyz
    {"service":"alertam-cloud-infra-spike","ready":true}

O operador executou restart controlado pela UI do Northflank e confirmou retorno saudável.

A revisão independente repetiu os dois requests públicos após o restart e recebeu novamente HTTP 200 com os payloads esperados.

### Resultado final

- build/deploy Northflank: **PASS**;
- serviço público: **PASS**;
- health: **PASS**;
- readiness: **PASS**;
- restart controlado: **PASS**;
- container non-root: **PASS**;
- smoke local: **PASS**;
- isolamento operacional: **PASS**;
- secrets operacionais usados: **nenhum**.

### Parecer final

**Pré-SPEC 027 Cloud Infrastructure Spike APROVADO e ENCERRADO TECNICAMENTE.**

O shell Cloud pode permanecer ativo no Northflank apenas como observação de infraestrutura/uptime.

Este fechamento NÃO autoriza:

- WebPilot real no Cloud;
- SessionLease/cookies;
- CloudBinding operacional;
- migrations Supabase;
- publicação source=cloud;
- arbitragem/failover/failback;
- eventos/push Cloud;
- cutover;
- início de C1/C2/C3 antes do gate humano da SPEC 025.

A próxima liberação funcional da SPEC 027 continua dependente da conclusão da janela real do Plan 5 e da aprovação humana explícita do collector HTTP.
