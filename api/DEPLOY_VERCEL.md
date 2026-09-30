# Deploy do AlertaM — Vercel + Supabase

Atualizado em 2026-09-27.

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

Antes de alterar o banco de produção, conferir o estado real:

```bash
make prod-migrate-status
```

O comando compara, sem modificar o banco, os arquivos locais com `public.schema_migrations`. Se houver migrations pendentes, aplicar com `make prod-migrate` e repetir o status ao final. Migrations registradas no banco mas ausentes do checkout aparecem como **desconhecidas** e devem ser investigadas antes de qualquer alteração.

Executar na ordem:

1. `supabase/migrations/001_devices.sql`
2. `supabase/migrations/002_accept_snapshot_rpc.sql`
3. `supabase/migrations/003_rotate_view_secret_rpc.sql`
4. `supabase/migrations/004_maneuver_events.sql`
5. `supabase/migrations/005_push_installations_deliveries.sql`
6. `supabase/migrations/006_event_retention.sql`
7. `supabase/migrations/007_maneuver_event_detail_index.sql`
8. `supabase/migrations/008_vessel_tracking_events.sql`
9. `supabase/migrations/009_vessel_tracking_retention.sql`
10. `supabase/migrations/010_mobile_installations.sql`
11. `supabase/migrations/011_tracked_vessels.sql`
12. `supabase/migrations/012_vessel_tracking_deliveries.sql`
13. `supabase/migrations/013_mobile_installation_management.sql`
14. `supabase/migrations/014_mobile_session_switch.sql`

As migrations:

- criam uma linha por dispositivo e aceitação atômica do snapshot;
- persistem `ManeuverEvent` com `ingestion_id` estável/idempotente;
- persistem instalações push e bookkeeping de deliveries;
- fazem a rotação de `VIEW_SECRET` desativar todas as instalações do device;
- criam cleanup explícito de eventos/deliveries com retenção de 30 dias;
- habilitam RLS e não criam policy pública para essas tabelas;
- adicionam `platform` + `display_code` às instalações mobile, revogação individual completa e listagem administrativa;
- persistem o switch A→B por `switch_id` e executam a troca de instalação em uma única RPC transacional.

As migrations 004–006 e 013–014 devem ser validadas em Postgres/Supabase real antes do deploy final. Testes locais com repository em memória/MockTransport não substituem esse gate. A API da SPEC 026 deve ser publicada antes da PWA e do Desktop que consumirem os novos contratos.

### Agendar a retenção de eventos

Depois de validar a migration 006 no projeto real, agendar no Supabase Cron uma
execução periódica de:

```sql
select public.cleanup_event_retention();
```

A função remove primeiro `push_deliveries` vinculados a eventos com mais de 30
dias e depois os próprios `maneuver_events`. Ela não remove
`push_installations`. Não habilitar o cron antes de validar migrations 004–006
no banco alvo.

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

Para habilitar Web Push em produção:

```env
WEB_PUSH_ENABLED=true
VAPID_PUBLIC_KEY=<public-key>
VAPID_PRIVATE_KEY=<private-key>
VAPID_SUBJECT=mailto:<contato-do-projeto>
PUSH_FOREGROUND_FRESH_SECONDS=75
```

`VAPID_PRIVATE_KEY` é segredo exclusivo do backend. O frontend recebe somente
`VAPID_PUBLIC_KEY` pelo endpoint autenticado e nenhuma das duas chaves deve ser
registrada em logs.

Enquanto frontend e API estiverem sob a mesma origem, `ALLOWED_ORIGINS` pode
ficar vazio. Se houver frontend em outra origem, listar explicitamente as
origens separadas por vírgula.

Marcar `SUPABASE_SECRET_KEY` e `VAPID_PRIVATE_KEY` como variáveis sensíveis na Vercel.

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

A implementação local da SPEC 021 inclui ManeuverEvent, feed mobile, instalações
push, VAPID/dispatcher, `injectManifest`, heartbeat foreground e retenção de 30
dias. O roteamento same-origin continua mantendo `/api/v1/*` prioritário.

Antes de produção ainda são obrigatórios:
- aplicar e validar migrations 004–006 e 013–014 em Postgres/Supabase real;
- habilitar o Cron de retenção somente após essa validação;
- configurar VAPID real no backend;
- executar smoke Desktop → API → PWA e Web Push real em aparelho/browser;
- confirmar que nenhum segredo foi configurado no service frontend.

Os testes locais não substituem esses gates externos.
