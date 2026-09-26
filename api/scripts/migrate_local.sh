#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL é obrigatório}"

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
do $$
begin
    create role anon noinherit;
exception when duplicate_object then null;
end $$;

do $$
begin
    create role authenticated noinherit;
exception when duplicate_object then null;
end $$;

do $$
begin
    create role service_role noinherit bypassrls;
exception when duplicate_object then null;
end $$;
SQL

exec /bin/sh /scripts/migrate.sh
