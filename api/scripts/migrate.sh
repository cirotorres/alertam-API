#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL é obrigatório}"

MIGRATIONS_PATH="${MIGRATIONS_PATH:-/migrations}"

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
create table if not exists public.schema_migrations (
    version text primary key,
    applied_at timestamptz not null default now()
);

alter table public.schema_migrations enable row level security;
revoke all on table public.schema_migrations from anon, authenticated;
SQL

for migration in "$MIGRATIONS_PATH"/*.sql; do
    [ -f "$migration" ] || continue

    version="$(basename "$migration")"
    applied="$(
        psql "$DATABASE_URL" -Atq \
            -v ON_ERROR_STOP=1 \
            -v version="$version" <<'SQL'
select exists (
    select 1
    from public.schema_migrations
    where version = :'version'
);
SQL
    )"

    if [ "$applied" = "t" ]; then
        echo "Já aplicada: $version"
        continue
    fi

    echo "Aplicando: $version"
    psql "$DATABASE_URL" \
        -v ON_ERROR_STOP=1 \
        -v version="$version" <<SQL
begin;
\i '$migration'
insert into public.schema_migrations (version)
values (:'version');
commit;
SQL
done
