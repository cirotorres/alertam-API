# Deploy do AlertaM — Vercel + Supabase

Atualizado em 2026-09-26.

Este runbook cobre a FastAPI e o frontend Vite/PWA como Services do mesmo
monorepo/projeto Vercel. O frontend nunca recebe credenciais administrativas do
Supabase.

## Arquitetura de deploy

A raiz do monorepo contém `vercel.json`.

Os Services definidos são:

- `api`: root `api/`, entrypoint `main:app`;
- `frontend`: root `frontend/`, autodetectado como Vite.

A ordem de roteamento é obrigatória:

1. `/api/v1/:path*` → service `api`;
2. `/:path*` → service `frontend`.

`api/main.py` não cria outra aplicação. Ele reexporta exatamente a instância
`app` de `app.main`.

Essa ordem preserva a origem única: o PWA chama paths relativos `/api/v1/*` e
não precisa conhecer uma URL separada da API.

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

O `vercel.json` da raiz define os Services `api` e `frontend`. A API usa
o `pyproject.toml` e o Python fixado em `api/.python-version`; o frontend usa
`frontend/package.json` e o build Vite.

Nenhuma variável `SUPABASE_SECRET_KEY`, `SUPABASE_DB_URL` ou
`ALERTAM_DEVICE_SECRET` deve ser configurada/exposta ao service frontend.

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

A API já possui infraestrutura de produção com Supabase. A configuração local da
SPEC 020 adiciona o service `frontend` e mantém `/api/v1/*` prioritário.

O deploy público do novo frontend e o smoke real Desktop → QR → PWA → API ainda
devem ser executados no gate final da SPEC 020 antes de marcar a feature como
concluída.
