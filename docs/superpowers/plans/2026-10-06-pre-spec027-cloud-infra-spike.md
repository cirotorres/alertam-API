# Pré-SPEC 027 — Cloud Infrastructure Spike

**Status:** pronto para execução em branch isolada; não libera SPEC 027 operacional.
**Objetivo:** provar rapidamente o substrato de execução do futuro AlertaM Cloud enquanto o Plan 5 acumula evidência real, sem consumir WebPilot, SessionLease, device_id operacional ou publicar `source=cloud`.

## Guardrails obrigatórios

- Não executar collector WebPilot real.
- Não receber/armazenar cookies, SessionLease ou credenciais WebPilot reais.
- Não criar CloudBinding operacional nem migrations Supabase.
- Não publicar snapshot Cloud na API.
- Não implementar failover/failback, lease/fencing ou arbitragem de source.
- Não alterar Desktop, PWA ou autoridade mobile.
- Não copiar/reimplementar collector do Desktop.
- Não criar terceiro repositório nesta fase.
- O spike vive em `alertamaritimoAPI/cloud/`.
- Northflank é alvo inicial de sandbox, não decisão irrevogável de produção.

## Arquitetura do spike

    GitHub / alertamaritimoAPI
              │
              └── cloud/
                    ├── app headless mínimo
                    ├── /healthz
                    ├── /readyz
                    └── Dockerfile
                          │
                          ↓
                     Northflank

O serviço deve apenas provar build, start, health, readiness, logs, restart e permanência always-on.

## Task 1 — Shell headless mínimo

Criar em `cloud/` um subprojeto Python 3.12 isolado, com testes antes da implementação.

Contrato mínimo:

- processo HTTP headless;
- bind `0.0.0.0`;
- porta por `PORT`, default 8080;
- `GET /healthz` retorna 200 com payload sanitizado identificando `alertam-cloud-infra-spike`;
- `GET /readyz` retorna 200 quando o processo terminou bootstrap local;
- nenhum endpoint operacional adicional;
- nenhuma dependência de Supabase/WebPilot/Desktop;
- logs sem dump de env/secrets.

Testes devem confirmar ausência de imports/uso de WebPilot, SessionLease, CloudBinding e publicação de snapshot.

## Task 2 — Container de produção do spike

Criar `cloud/Dockerfile` e `.dockerignore` adequados.

Requisitos:

- imagem Python 3.12 slim;
- dependências locked/reprodutíveis;
- usuário não-root;
- `PYTHONUNBUFFERED=1`;
- healthcheck local em `/healthz`;
- respeitar `PORT`;
- sem volumes obrigatórios;
- sem secrets baked na imagem.

Validar localmente:

1. build da imagem;
2. container inicia;
3. `/healthz` e `/readyz` respondem;
4. SIGTERM/restart não deixam artefatos obrigatórios;
5. logs não expõem ambiente completo.

## Task 3 — Atalhos de desenvolvimento e CI local

Adicionar ao Makefile apenas alvos de suporte do spike, por exemplo:

- `make cloud-test`;
- `make cloud-build`;
- `make cloud-smoke`.

Os novos alvos não podem tocar banco, migrations, Vercel, Supabase ou Desktop.

Rodar também a suíte existente do API/PWA relevante para provar ausência de regressão.

## Task 4 — Deploy sandbox Northflank

Configurar um **Service** no projeto já criado `AlertaM Cloud`, apontando para este repositório/branch e para `cloud/Dockerfile`.

Configuração mínima esperada:

- serviço always-on;
- porta do container conforme `PORT`;
- health check em `/healthz`;
- restart automático da plataforma;
- somente variáveis não sensíveis de spike, se necessárias;
- nenhum secret WebPilot/Supabase de produção;
- nenhum volume/database nesta etapa.

Registrar evidência:

- build/deploy bem-sucedido;
- URL/health disponível;
- logs de startup;
- restart controlado;
- serviço continua saudável após restart.

## Task 5 — Observação de infraestrutura

Deixar o serviço sandbox ativo em paralelo ao Shadow local para provar permanência.

Meta recomendada: 24h de disponibilidade contínua do shell, sem confundir isso com o gate do collector.

A evidência deve registrar apenas uptime/restarts/health do container.

## Task 6 — Handoff e STOP

Atualizar handoff com commits, testes, Docker smoke e status Northflank.

**STOP obrigatório antes de:**

- adicionar WebPilot ao container;
- transportar SessionLease;
- criar binding real;
- escrever `source=cloud`;
- iniciar C1/C2/C3 da SPEC 027.

Esses itens só podem começar após o gate humano da SPEC 025.

## Critério de sucesso do spike

O spike está aprovado quando:

- `cloud/` é isolado e não operacional;
- testes estão verdes;
- imagem builda e roda localmente;
- Northflank mantém o shell saudável/restartável;
- nenhum segredo real foi necessário;
- nenhuma semântica Cloud operacional foi antecipada.
