# Infraestrutura local e Docker

## Desenvolvimento

O stack de desenvolvimento usa PostgreSQL local de verdade:

```text
frontend/Vite :5173
      │
      ├── /api/* ──► api:8000
      │                 │
      │                 ▼
      │             postgres:16
      │                 │
      │       migrations 001 → 003
      │                 │
      │              seed DEV
      └── React + TypeScript + PWA (HMR)
```

Subir em foreground:

```bash
make run
```

Ou em background:

```bash
make dev-up
```

URLs padrão:

- frontend/proxy: http://localhost:5173
- API direta: http://localhost:8000
- health via frontend: http://localhost:5173/api/v1/health
- PostgreSQL host: localhost:55431

Credenciais locais fixas, somente para desenvolvimento:

```env
DEVICE_ID=pecem-01
DEVICE_SECRET=dev-device-secret-change-me
VIEW_SECRET=VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV
```

O banco dev usa volume persistente. `make dev-down` preserva os dados.
`make dev-reset` apaga explicitamente o volume.

## Testes

Rápido, usando o ambiente Python local:

```bash
make test
```

Completo e reproduzível, com PostgreSQL efêmero em Docker:

```bash
make test-all
```

O banco de teste é separado do banco dev e não reutiliza seu volume.

## Produção / Supabase

Criar o arquivo local de produção:

```bash
make prod-env
```

Depois preencher `api/.env.prod` com pelo menos:

```env
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
```

Validar:

```bash
make prod-config
```

Subir:

```bash
make prod
```

O compose de produção não possui serviço PostgreSQL. A API força
`ENVIRONMENT=production` + `PERSISTENCE_BACKEND=supabase`; se o Supabase
não estiver configurado, a aplicação falha cedo.

## Frontend

O diretório `frontend/` contém o PWA React + TypeScript + Vite da SPEC 020.

No ambiente DEV, o Compose usa o target `dev` do Dockerfile, monta o código-fonte
e um volume separado para `node_modules`, publica o Vite em `:5173` e define
`VITE_DEV_API_TARGET=http://api:8000`. Assim, requests para `/api/*` permanecem
same-origin no navegador e são encaminhados pelo proxy do Vite para a FastAPI.

No ambiente PROD-like, o target `prod` gera o bundle estático e o Nginx serve a
SPA em `:8080`, com fallback para `index.html` e proxy de `/api/*` para a API.
`sw.js` e `manifest.webmanifest` recebem `Cache-Control: no-cache`; assets
versionados continuam sendo cacheados normalmente pelo navegador/service worker.

O `frontend/.dockerignore` exclui `node_modules`, `dist`, relatórios e arquivos
locais de ambiente do contexto Docker.

## Verificação da etapa — 2026-09-25

Foram executados e validados:

- `make help`;
- `make dev-config`;
- `make prod-config` com ambiente temporário;
- build da imagem production da API;
- `make test-all` em Docker com PostgreSQL efêmero: **147 testes verdes**;
- `make dev-up` com Postgres local, migrations, seed, API e frontend;
- health direto da API em `:8000`;
- health via proxy do frontend em `:5173/api/v1/health`;
- POST real do fixture MobileSnapshot usando o DEVICE_SECRET local;
- GET real do mesmo snapshot via Nginx usando o VIEW_SECRET local;
- stack production com Supabase fictício apenas para startup: API healthy e proxy em `:8080/api/v1/health`.

Nenhuma chamada ao Supabase real foi feita e nenhum segredo de produção foi criado.

## Verificação do frontend — 2026-09-26

Durante a implementação da SPEC 020 foram validados:

- `make dev-config` e `make prod-config` em modo silencioso (`config --quiet`);
- build do frontend Vite/PWA;
- stack DEV real com target Vite + HMR;
- `GET http://localhost:5173/` servindo o frontend;
- `GET http://localhost:5173/api/v1/health` retornando `{"ok":true}` via proxy same-origin;
- teardown completo do stack após o smoke.

O deploy público do frontend na Vercel ainda pertence ao gate final da SPEC 020.

## Migrations

As migrations ficam em `api/supabase/migrations/` e são numeradas em ordem:

```text
001_devices.sql
002_accept_snapshot_rpc.sql
003_rotate_view_secret_rpc.sql
...
```

O runner mantém `public.schema_migrations` e aplica cada arquivo somente uma vez.

### Desenvolvimento

Aplicar somente migrations pendentes:

```bash
make migrate
```

Aplicar pendentes e reaplicar o seed local:

```bash
make migrate-seed
```

Listar migrations:

```bash
make migrate-list
```

Criar a próxima migration numerada:

```bash
make migration-new NAME=add_alerts
```

Exemplo resultante:

```text
api/supabase/migrations/004_add_alerts.sql
```

### Produção / Supabase

Além das credenciais HTTP da API, `api/.env.prod` precisa da conexão PostgreSQL:

```env
SUPABASE_DB_URL=postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
```

Antes de aplicar qualquer alteração, conferir se o checkout e o banco estão sincronizados:

```bash
make prod-migrate-status
```

Esse comando é somente leitura: compara os arquivos `.sql` locais com `public.schema_migrations`. Quando há pendências, lista cada migration local ainda não aplicada. Quando o banco contém uma migration que não existe no checkout atual, lista-a como **desconhecida** para investigação. O comando retorna sucesso somente quando os dois lados estão sincronizados.

Para aplicar somente as migrations pendentes:

```bash
make prod-migrate
```

Depois, repetir `make prod-migrate-status` para confirmar o estado final. O runner usa a mesma tabela `schema_migrations` e portanto aplica somente arquivos ainda não registrados. A URL PostgreSQL é usada apenas pelos comandos de migration e não pela API em runtime.

O status compara nomes registrados, não checksum do conteúdo. Uma migration já aplicada deve ser tratada como imutável; correções posteriores devem entrar em um novo arquivo de migration.
