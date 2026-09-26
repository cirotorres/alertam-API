# Deploy da API — Vercel + Supabase

Atualizado em 2026-09-25.

Este runbook prepara apenas a API. O frontend Vite será adicionado depois como
um segundo Vercel Service no mesmo monorepo/projeto.

## Arquitetura de deploy

A raiz do monorepo contém `vercel.json`.

O serviço atual é:

- service: `api`
- root: `api/`
- entrypoint: `main:app`
- rota pública: `/api/v1/:path*`

`api/main.py` não cria outra aplicação. Ele reexporta exatamente a instância
`app` de `app.main`.

Quando o frontend existir, ele será adicionado ao mesmo `vercel.json`; a regra
de `/api/v1/:path*` deve continuar antes do catch-all do frontend.

## 1. Criar o Supabase

Quando estiver pronto:

1. criar o projeto Supabase;
2. copiar o Project URL;
3. criar/copiar uma Secret Key atual no formato `sb_secret_...`;
4. não usar Publishable Key no backend;
5. não expor a Secret Key ao Desktop ou frontend.

Para projetos novos, preferir `SUPABASE_SECRET_KEY`.
`SUPABASE_SERVICE_ROLE_KEY` existe apenas como fallback legado temporário.

## 2. Aplicar as migrations

Executar na ordem:

1. `supabase/migrations/001_devices.sql`
2. `supabase/migrations/002_accept_snapshot_rpc.sql`
3. `supabase/migrations/003_rotate_view_secret_rpc.sql`

As migrations:

- criam uma linha por dispositivo;
- habilitam RLS;
- não criam policy pública;
- implementam aceitação atômica do snapshot;
- implementam rotação do hash de VIEW_SECRET.

## 3. Provisionar o primeiro dispositivo

Na pasta `api/`:

```bash
uv run python -m scripts.provision_device pecem-01
```

O comando mostra o `DEVICE_SECRET` em plaintext uma única vez e gera um
`INSERT` que contém somente o SHA-256.

Guardar o `DEVICE_SECRET` de forma segura e executar o `INSERT` no SQL Editor
do Supabase.

## 4. Variáveis obrigatórias na Vercel

Configurar no Project Settings → Environment Variables:

```env
ENVIRONMENT=production
PERSISTENCE_BACKEND=supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
```

Recomendadas:

```env
STALE_AFTER_SECONDS=120
LOG_LEVEL=INFO
ALLOWED_ORIGINS=
```

Enquanto frontend e API estiverem sob a mesma origem, `ALLOWED_ORIGINS` pode
ficar vazio. Se houver frontend em outra origem, listar explicitamente as
origens separadas por vírgula.

Marcar `SUPABASE_SECRET_KEY` como variável sensível na Vercel.

A aplicação recusa `ENVIRONMENT=production` com
`PERSISTENCE_BACKEND=memory`.

## 5. Criar/importar o projeto Vercel

Importar o repositório GitHub do monorepo:

`cirotorres/alertam-API`

O `vercel.json` da raiz define o Vercel Service da API. O serviço usa o
`pyproject.toml` e o Python fixado em `api/.python-version`.

Nenhum `vercel.json` legado com builders ou redirects é necessário.

## 6. Smoke check depois do deploy

```http
GET https://<dominio>/api/v1/health
```

Esperado:

```json
{"ok": true}
```

Depois do provisionamento do dispositivo, validar também o POST real do Desktop.

## 7. Variáveis do Desktop

Quando a URL pública estiver definida, configurar no AlertaM Desktop:

```env
ALERTAM_API_BASE_URL=https://<dominio>
ALERTAM_DEVICE_ID=pecem-01
ALERTAM_DEVICE_SECRET=<segredo gerado no provisionamento>
```

A API recebe a Secret Key do Supabase; o Desktop nunca recebe credenciais
Supabase.

## Estado atual

A preparação de deploy pode ser testada localmente sem Supabase real.
O deploy de produção propriamente dito depende da criação do projeto Supabase e
do preenchimento das variáveis acima.
